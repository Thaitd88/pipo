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
from ..database import get_db

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

    if not all_items:
        conn.close()
        raise HTTPException(status_code=400, detail="Bàn chưa có món nào để in hóa đơn")

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
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "message": f"Đã gửi lệnh in phiếu tạm tính bàn {table['name']} xuống Máy in Thu ngân!",
        "job_id": job_id,
        "discount_amount": discount_amount,
        "discount_percent": discount_percent
    }
