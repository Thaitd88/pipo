# Thermal Printer Management & Control Router for PiPo Garden
import base64
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from ..printer_service import (
    get_printers_status,
    get_printer_config,
    save_printer_config,
    test_kitchen_printer,
    test_cashier_printer,
    print_cashier_receipt,
    async_dispatch_cashier_print
)
import os
from ..database import get_db
from ..timezone_utils import now_vn_str, now_vn_time_str
from ..escpos import format_kitchen_ticket_text, build_escpos_kitchen_bytes
from ..printer_service import send_escpos_to_printer

router = APIRouter(prefix="/api/printer", tags=["Printer Control"])

ws_broadcaster = None

def set_broadcaster(broadcaster):
    global ws_broadcaster
    ws_broadcaster = broadcaster

class PrinterConfigPayload(BaseModel):
    kitchen_ip: Optional[str] = "192.168.31.251"
    kitchen_port: Optional[int] = 9100
    kitchen_enabled: Optional[bool] = True
    cashier_ip: Optional[str] = "192.168.31.252"
    cashier_port: Optional[int] = 9100
    cashier_enabled: Optional[bool] = True
    auto_kitchen: Optional[bool] = True
    auto_cashier: Optional[bool] = True

@router.get("/status")
def api_get_printer_status():
    """Kiểm tra thời gian thực trạng thái kết nối socket port 9100 của cả 2 máy in."""
    return get_printers_status()

@router.get("/config")
def api_get_printer_config():
    """Lấy thông số cấu hình IP, Port của hệ thống máy in."""
    return get_printer_config()

@router.post("/config")
def api_save_printer_config(payload: PrinterConfigPayload):
    """Cập nhật địa chỉ IP và Port cho Máy in Bếp và Máy in Thu ngân."""
    cfg = payload.model_dump(exclude_unset=True)
    save_printer_config(cfg)
    return {"status": "SUCCESS", "message": "Đã lưu cấu hình máy in thành công!", "config": get_printer_config()}

@router.post("/test/kitchen")
def api_test_kitchen():
    """In phiếu kiểm tra Máy in Bếp (192.168.31.251:9100) có còi hú beeper."""
    ok, msg = test_kitchen_printer()
    if not ok:
        raise HTTPException(status_code=500, detail=f"Không thể in tới Máy in Bếp: {msg}")
    return {"status": "SUCCESS", "message": "Đã gửi lệnh in test thành công tới Máy in Bếp (192.168.31.251)!"}

@router.post("/test/cashier")
def api_test_cashier():
    """In phiếu kiểm tra Máy in Thu ngân (192.168.31.252:9100) theo chuẩn 2 dòng."""
    ok, msg = test_cashier_printer()
    if not ok:
        raise HTTPException(status_code=500, detail=f"Không thể in tới Máy in Thu ngân: {msg}")
    return {"status": "SUCCESS", "message": "Đã gửi lệnh in test thành công tới Máy in Thu ngân (192.168.31.252)!"}

@router.post("/table/{table_id}/print-bill")
async def api_print_table_bill(table_id: int, request: Request):
    """
    In Phiếu Tạm Tính (80mm) cho bàn:
    - Bóc tách toàn bộ món của bàn hiện tại (phiên hiện tại).
    - Tính giảm giá theo % hoặc số tiền.
    - Tạo lệnh in print_jobs và bắn WebSocket tới Print Agent (in máy in thu ngân 192.168.31.252).
    - Thử in trực tiếp socket nếu server chạy ở LAN.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    discount_percent = float(payload.get("discount_percent") or 0)
    discount_amount = max(0, int(payload.get("discount_amount") or 0))
    discount_reason = (payload.get("discount_reason") or "").strip()
    service_fee = max(0, int(payload.get("service_fee") or 0))
    payment_method = (payload.get("payment_method") or "CASH").strip().upper()
    billed_admin_name = (payload.get("billed_admin_name") or "").strip()
    cashier_display = (payload.get("cashier_name") or "Thu Ngan PiPo").strip()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")
    table = dict(row)

    session_id = table.get("current_session_id")
    if session_id:
        cursor.execute("""
            SELECT * FROM orders 
            WHERE table_id = ? AND (session_id = ? OR session_id IS NULL) AND payment_status = 'UNPAID'
            ORDER BY round_number ASC
        """, (table_id, session_id))
    else:
        cursor.execute("""
            SELECT * FROM orders 
            WHERE table_id = ? AND payment_status = 'UNPAID'
            ORDER BY round_number ASC
        """, (table_id,))
    orders = [dict(o) for o in cursor.fetchall()]

    all_items = []
    subtotal = 0
    for order in orders:
        cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC", (order["id"],))
        items = [dict(it) for it in cursor.fetchall()]
        all_items.extend(items)
        subtotal += sum(it["total_price"] for it in items if it.get("status") != "CANCELLED")

    if not all_items and service_fee <= 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Bàn chưa có món nào hoặc phí dịch vụ để in hóa đơn")

    if discount_percent > 0:
        discount_amount = int(round(subtotal * discount_percent / 100))
    elif discount_amount > 0 and subtotal > 0:
        discount_percent = round(discount_amount * 100 / subtotal, 1)

    totals_info = {
        "title": "PHIEU TINH TIEN (TAM TINH)",
        "cashier_name": cashier_display,
        "discount": discount_amount,
        "discount_percent": int(discount_percent) if discount_percent.is_integer() else discount_percent if discount_percent > 0 else None,
        "discount_reason": discount_reason,
        "service_fee": service_fee,
        "payment_method": payment_method,
        "billed_admin_name": billed_admin_name,
        "vat": 0
    }

    from ..escpos import format_receipt_ticket_text, build_escpos_receipt_bytes
    receipt_text = format_receipt_ticket_text(table, all_items, totals_info=totals_info)
    receipt_bytes = build_escpos_receipt_bytes(table, all_items, totals_info=totals_info)
    receipt_b64 = base64.b64encode(receipt_bytes).decode("ascii")

    first_order_id = orders[0]["id"] if orders else 0
    cursor.execute("""
        INSERT INTO print_jobs (order_id, station, job_type, status, ticket_text)
        VALUES (?, 'CASHIER', 'RECEIPT', 'PENDING', ?)
    """, (first_order_id, receipt_text))
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Bắn WebSocket cho Print Agent
    if ws_broadcaster:
        await ws_broadcaster.send_to_printers({
            "event": "PRINT_JOB",
            "job_id": job_id,
            "station": "CASHIER",
            "job_type": "RECEIPT",
            "ticket_text": receipt_text,
            "escpos_b64": receipt_b64,
            "table_name": table["name"]
        })

    # Cố gắng gửi socket LAN nếu cùng mạng
    try:
        from ..printer_service import async_dispatch_cashier_print
        await async_dispatch_cashier_print(receipt_bytes)
    except Exception as ex:
        print("[Print Bill Direct LAN Error]:", ex)

    return {
        "status": "SUCCESS",
        "message": f"Đã gửi lệnh in phiếu tạm tính bàn {table['name']} xuống Máy in Thu ngân!",
        "job_id": job_id,
        "discount_amount": discount_amount,
        "discount_percent": discount_percent
    }

class CustomKitchenTicketPayload(BaseModel):
    table_id: Optional[int] = None
    table_name: Optional[str] = "QUẦY THU NGÂN"
    area: Optional[str] = "Nhà Hàng"
    item_name: str
    quantity: Optional[int] = 1
    price: Optional[int] = 0
    note: Optional[str] = ""
    station: Optional[str] = "HOT_KITCHEN"  # HOT_KITCHEN, COLD_KITCHEN, BAR
    add_to_bill: Optional[bool] = False
    beep: Optional[bool] = True

@router.post("/custom-kitchen-ticket")
async def api_custom_kitchen_ticket(payload: CustomKitchenTicketPayload):
    """
    Tự gõ tên món và in phiếu bếp:
    - Bắn lệnh in trực tiếp vào máy in bếp (Bếp Nóng 251, Bếp Lạnh, hoặc Quầy Bar 252).
    - Tạo print_job KOT, phát WebSocket tới Print Agent & Màn hình KDS.
    - Nếu chọn add_to_bill=True và có table_id, tự động ghi món vào order của bàn.
    """
    item_name = (payload.item_name or "").strip()
    if not item_name:
        raise HTTPException(status_code=400, detail="Vui lòng nhập tên món ăn")

    quantity = max(1, payload.quantity or 1)
    price = max(0, payload.price or 0)
    station = (payload.station or "HOT_KITCHEN").strip().upper()
    if station not in ("HOT_KITCHEN", "COLD_KITCHEN", "BAR"):
        station = "HOT_KITCHEN"

    note = (payload.note or "").strip()
    table_id = payload.table_id
    table_name = (payload.table_name or "QUẦY THU NGÂN").strip()
    area = (payload.area or "Nhà Hàng").strip()

    conn = get_db()
    cursor = conn.cursor()

    order_id = 0
    now_ts = now_vn_str("%Y-%m-%d %H:%M:%S")

    if table_id:
        cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
        t_row = cursor.fetchone()
        if t_row:
            table_dict = dict(t_row)
            table_name = table_dict.get("name") or table_name
            area = table_dict.get("area") or area

            if payload.add_to_bill:
                # Tìm active session hoặc tạo mới
                session_id = table_dict.get("current_session_id")
                if not session_id:
                    cursor.execute("SELECT id FROM table_sessions WHERE table_id = ? AND status = 'ACTIVE' ORDER BY id DESC LIMIT 1", (table_id,))
                    s_row = cursor.fetchone()
                    if s_row:
                        session_id = s_row["id"]
                    else:
                        import uuid
                        s_token = f"sess_{uuid.uuid4().hex[:12]}"
                        cursor.execute("INSERT INTO table_sessions (table_id, session_token, guest_count, status, opened_at) VALUES (?, ?, 2, 'ACTIVE', ?)", (table_id, s_token, now_ts))
                        session_id = cursor.lastrowid
                    cursor.execute("UPDATE tables SET status = 'OCCUPIED', current_session_id = ? WHERE id = ?", (session_id, table_id))

                # Tìm đơn UNPAID của session này hoặc tạo mới
                cursor.execute("SELECT id FROM orders WHERE table_id = ? AND (session_id = ? OR session_id IS NULL) AND payment_status = 'UNPAID' ORDER BY id DESC LIMIT 1", (table_id, session_id))
                ord_row = cursor.fetchone()
                line_total = price * quantity
                if ord_row:
                    order_id = ord_row["id"]
                    cursor.execute("UPDATE orders SET subtotal = subtotal + ?, total = total + ? WHERE id = ?", (line_total, line_total, order_id))
                else:
                    import uuid
                    ord_uuid = f"ord_{uuid.uuid4().hex}"
                    cursor.execute("""
                        INSERT INTO orders (order_uuid, session_id, table_id, round_number, subtotal, total, status, payment_status, customer_note, created_at)
                        VALUES (?, ?, ?, 1, ?, ?, 'CONFIRMED', 'UNPAID', 'Món tự gõ từ Thu Ngân', ?)
                    """, (ord_uuid, session_id, table_id, line_total, line_total, now_ts))
                    order_id = cursor.lastrowid

                # Thêm món vào order_items
                cursor.execute("""
                    INSERT INTO order_items (order_id, item_id, item_name, quantity, unit_price, total_price, station, note, modifiers_json, status, created_at, updated_at)
                    VALUES (?, 0, ?, ?, ?, ?, ?, ?, '[]', 'QUEUED', ?, ?)
                """, (order_id, item_name, quantity, price, line_total, station, note, now_ts, now_ts))

    order_info = {
        "id": order_id if order_id else "TU_GO",
        "table_name": table_name,
        "area": area,
        "round_number": "LE",
        "customer_note": f"Món tự gõ: {note}" if note else "Món tự gõ từ Thu Ngân",
        "created_at": now_vn_str("%H:%M:%S - %d/%m/%Y")
    }

    ticket_item = {
        "item_name": item_name,
        "quantity": quantity,
        "note": note,
        "status": "QUEUED"
    }

    ticket_text = format_kitchen_ticket_text(order_info, [ticket_item], station=station)
    escpos_bytes = build_escpos_kitchen_bytes(order_info, [ticket_item], station=station, beep=payload.beep)
    escpos_b64 = base64.b64encode(escpos_bytes).decode("ascii")

    cursor.execute("""
        INSERT INTO print_jobs (order_id, station, job_type, status, ticket_text)
        VALUES (?, ?, 'KOT', 'PENDING', ?)
    """, (order_id or 0, station, ticket_text))
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print_job_payload = {
        "job_id": job_id,
        "station": station,
        "job_type": "KOT",
        "ticket_text": ticket_text,
        "escpos_b64": escpos_b64,
        "table_name": table_name
    }

    # Bắn WebSocket cho Print Agent & KDS
    if ws_broadcaster:
        await ws_broadcaster.send_to_printers({
            "event": "PRINT_JOB",
            **print_job_payload
        })
        await ws_broadcaster.send_to_kds({
            "event": "NEW_ORDER",
            "order": {
                "order_id": order_id or "TU_GO",
                "table_name": table_name,
                "area": area,
                "round_number": "LE",
                "items": [{
                    "id": job_id,
                    "item_name": item_name,
                    "quantity": quantity,
                    "station": station,
                    "note": note,
                    "status": "QUEUED"
                }]
            }
        })

    # Cố gắng gửi socket LAN trực tiếp nếu cùng mạng
    is_cloud = os.environ.get("VIBE_PROJECT_ID") or os.environ.get("KUBERNETES_SERVICE_HOST") or (os.name != "nt")
    if not is_cloud:
        try:
            p_cfg = get_printer_config()
            is_cashier_side = station in ["BAR", "COLD_KITCHEN", "CASHIER"]
            dest_ip = p_cfg["cashier_ip"] if is_cashier_side else p_cfg["kitchen_ip"]
            dest_port = p_cfg["cashier_port"] if is_cashier_side else p_cfg["kitchen_port"]
            import asyncio
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, send_escpos_to_printer, dest_ip, dest_port, escpos_bytes)
        except Exception as _e:
            print("[Custom Kitchen Socket Error]:", _e)

    st_names = {"HOT_KITCHEN": "Bếp Nóng (251)", "COLD_KITCHEN": "Bếp Lạnh", "BAR": "Quầy Bar (252)"}
    st_display = st_names.get(station, "Bếp")
    return {
        "status": "SUCCESS",
        "message": f"Đã in phiếu món '{item_name}' (SL: {quantity}) ra {st_display} thành công!",
        "job_id": job_id,
        "ticket_text": ticket_text,
        "order_id": order_id
    }
