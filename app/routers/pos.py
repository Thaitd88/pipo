# POS Cashier management router for PiPo Garden
import os
import re
import base64
import urllib.parse
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
from ..database import get_db
from .auth import require_api_auth, get_current_user_from_request

router = APIRouter(prefix="/api/pos", tags=["POS Cashier"])

ws_broadcaster = None

def set_broadcaster(broadcaster):
    global ws_broadcaster
    ws_broadcaster = broadcaster

@router.get("/overview")
def get_pos_overview():
    conn = get_db()
    cursor = conn.cursor()

    # Thống kê bàn
    cursor.execute("SELECT COUNT(*) as total FROM tables")
    total_tables = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as occupied FROM tables WHERE status = 'OCCUPIED'")
    occupied_tables = cursor.fetchone()["occupied"]

    # Doanh thu tạm tính của các bàn đang ngồi
    cursor.execute("SELECT COALESCE(SUM(total), 0) as current_unpaid FROM orders WHERE payment_status = 'UNPAID'")
    current_unpaid = cursor.fetchone()["current_unpaid"]

    # Yêu cầu phục vụ đang chờ xử lý (Kèm khu vực bàn và giới hạn 30 đơn mới nhất)
    cursor.execute("""
        SELECT sc.*, t.area 
        FROM service_calls sc 
        LEFT JOIN tables t ON sc.table_id = t.id 
        WHERE sc.status = 'PENDING' 
        ORDER BY sc.created_at DESC LIMIT 30
    """)
    pending_calls = [dict(c) for c in cursor.fetchall()]

    conn.close()
    return {
        "total_tables": total_tables,
        "occupied_tables": occupied_tables,
        "available_tables": total_tables - occupied_tables,
        "current_unpaid_revenue": current_unpaid,
        "pending_calls": pending_calls
    }

@router.get("/admins")
def get_admins_list():
    """Lấy danh sách các tài khoản Quản trị viên (ADMIN) để chọn khi tính bill với Admin."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, full_name, role 
        FROM users 
        WHERE role = 'ADMIN' AND is_active = 1 
        ORDER BY full_name ASC
    """)
    admins = [dict(a) for a in cursor.fetchall()]
    conn.close()
    return admins

@router.get("/admin-bills")
def get_admin_bills(admin_id: int = None):
    """Tổng hợp danh sách các hóa đơn tính cho Quản trị viên (Admin)."""
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT o.id as order_id, o.session_id, o.table_id, t.name as table_name, t.table_code, t.area,
               o.subtotal, o.discount, o.discount_reason, o.total, o.bill_target, 
               o.billed_admin_id, o.billed_admin_name, o.created_at, o.payment_status
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        WHERE o.bill_target = 'ADMIN'
    """
    params = []
    if admin_id:
        query += " AND o.billed_admin_id = ?"
        params.append(admin_id)
    query += " ORDER BY o.created_at DESC"

    cursor.execute(query, params)
    bills = [dict(b) for b in cursor.fetchall()]

    for b in bills:
        cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC", (b["order_id"],))
        b["items"] = [dict(it) for it in cursor.fetchall()]

    total_amount = sum(b["total"] for b in bills)
    total_count = len(bills)

    by_admin = {}
    for b in bills:
        adm_name = b.get("billed_admin_name") or f"Admin #{b.get('billed_admin_id', 0)}"
        if adm_name not in by_admin:
            by_admin[adm_name] = {"count": 0, "total": 0}
        by_admin[adm_name]["count"] += 1
        by_admin[adm_name]["total"] += b["total"]

    conn.close()
    return {
        "total_count": total_count,
        "total_amount": total_amount,
        "by_admin": by_admin,
        "bills": bills
    }

@router.get("/table/{table_id}/bill")
def get_table_bill(table_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")

    table = dict(row)
    session_id = table.get("current_session_id")

    # Nếu bàn đang trống VÀ không có phiên hoạt động -> Trả về hóa đơn rỗng
    if table["status"] == "AVAILABLE" and not session_id:
        conn.close()
        return {
            "table": table,
            "table_id": table_id,
            "table_name": table["name"],
            "table_code": table["table_code"],
            "area": table["area"],
            "status": "AVAILABLE",
            "orders": [],
            "items": [],
            "grand_total": 0,
            "subtotal": 0,
            "discount": 0,
            "qr_code_url": ""
        }

    # Bàn đang có khách: Chỉ lấy các đơn hàng của đúng phiên hiện tại nếu có session_id
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
    grand_total = 0
    first_order_time = None

    for order in orders:
        if not first_order_time and order.get("created_at"):
            first_order_time = order["created_at"]
        cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC", (order["id"],))
        items = [dict(it) for it in cursor.fetchall()]
        all_items.extend(items)
        # Chỉ cộng các món chưa bị hủy (status != 'CANCELLED')
        order_active_sum = sum(it["total_price"] for it in items if it["status"] != "CANCELLED")
        grand_total += max(0, order_active_sum - order["discount"])

    conn.close()

    # Xác định khung giờ thanh toán (in_time - out_time)
    now = datetime.now()
    out_time_str = now.strftime("%Hh%M")
    if first_order_time:
        try:
            in_dt = datetime.fromisoformat(str(first_order_time))
            in_time_str = in_dt.strftime("%Hh%M")
        except Exception:
            in_time_str = out_time_str
    else:
        in_time_str = out_time_str

    raw_table_code = str(table["table_code"] or table["name"] or "01").upper()
    if raw_table_code.startswith("BAN "):
        raw_table_code = raw_table_code.replace("BAN ", "")
    clean_table_code = re.sub(r'[^a-zA-Z0-9]', '', raw_table_code) or "01"

    transfer_note = f"TT PiPo Ban {clean_table_code}"
    encoded_note = urllib.parse.quote(transfer_note)

    # Link VietQR động cho nhà hàng PiPo Garden (MB Bank 970422 - STK 075624456)
    vietqr_url = f"https://img.vietqr.io/image/970422-075624456-compact2.png?amount={grand_total}&addInfo={encoded_note}&accountName=PIPO%20GARDEN"

    return {
        "table": dict(table),
        "table_id": table_id,
        "table_name": table["name"],
        "table_code": table["table_code"],
        "area": table["area"],
        "status": table["status"],
        "orders_count": len(orders),
        "grand_total": grand_total,
        "items": all_items,
        "transfer_note": transfer_note,
        "in_time": in_time_str,
        "out_time": out_time_str,
        "vietqr_url": vietqr_url
    }

@router.post("/table/{table_id}/checkout")
async def checkout_table(table_id: int, request: Request, payload: dict = None):
    user = require_api_auth(request, allowed_roles=["ADMIN", "CASHIER", "WAITER"])
    if payload is None:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    discount_percent = float(payload.get("discount_percent") or 0)
    discount_amount = max(0, int(payload.get("discount_amount") or 0))
    discount_reason = (payload.get("discount_reason") or "").strip()
    bill_target = (payload.get("bill_target") or "CUSTOMER").strip().upper()
    billed_admin_id = payload.get("billed_admin_id")
    billed_admin_name = (payload.get("billed_admin_name") or "").strip()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    table = cursor.fetchone()
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")

    # Lấy thông tin các món để tự động in hóa đơn thanh toán
    cursor.execute("""
        SELECT * FROM orders 
        WHERE table_id = ? AND payment_status = 'UNPAID'
        ORDER BY round_number ASC
    """, (table_id,))
    checkout_orders = [dict(o) for o in cursor.fetchall()]
    checkout_items = []
    for co in checkout_orders:
        cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC", (co["id"],))
        checkout_items.extend([dict(it) for it in cursor.fetchall()])

    # 1. Đánh dấu tất cả đơn của bàn là PAID, cập nhật giảm giá & đối tượng thanh toán
    cursor.execute("""
        UPDATE orders 
        SET payment_status = 'PAID', 
            status = 'COMPLETED',
            completed_at = CURRENT_TIMESTAMP,
            discount = ?,
            discount_reason = ?,
            bill_target = ?,
            billed_admin_id = ?,
            billed_admin_name = ?,
            total = MAX(0, subtotal - ?)
        WHERE table_id = ? AND payment_status = 'UNPAID'
    """, (discount_amount, discount_reason, bill_target, billed_admin_id, billed_admin_name, discount_amount, table_id))

    # 2. Đánh dấu tất cả món của các đơn bàn này là SERVED (đã phục vụ xong)
    cursor.execute("""
        UPDATE order_items 
        SET status = 'SERVED'
        WHERE order_id IN (SELECT id FROM orders WHERE table_id = ?)
    """, (table_id,))

    # 3. Đóng toàn bộ session của bàn
    cursor.execute("UPDATE table_sessions SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP WHERE table_id = ?", (table_id,))

    # 4. Đưa bàn về trạng thái AVAILABLE sẵn sàng cho khách mới
    cursor.execute("UPDATE tables SET status = 'AVAILABLE', current_session_id = NULL WHERE id = ?", (table_id,))

    conn.commit()
    conn.close()

    # Tự động in hóa đơn thanh toán xuống Máy in Thu ngân (80mm)
    try:
        from ..escpos import format_receipt_ticket_text, build_escpos_receipt_bytes
        cashier_display = user.get("full_name") or "Thu Ngan PiPo"
        totals_info = {
            "title": "HOA DON THANH TOAN",
            "cashier_name": cashier_display,
            "discount": discount_amount,
            "discount_percent": int(discount_percent) if discount_percent.is_integer() else discount_percent if discount_percent > 0 else None,
            "discount_reason": discount_reason,
            "bill_target": bill_target,
            "billed_admin_name": billed_admin_name
        }
        receipt_text = format_receipt_ticket_text(dict(table), checkout_items, totals_info=totals_info)
        receipt_bytes = build_escpos_receipt_bytes(dict(table), checkout_items, totals_info=totals_info)
        receipt_b64 = base64.b64encode(receipt_bytes).decode("ascii")

        first_order_id = checkout_orders[0]["id"] if checkout_orders else 0
        conn_p = get_db()
        cur_p = conn_p.cursor()
        cur_p.execute("""
            INSERT INTO print_jobs (order_id, station, job_type, status, ticket_text)
            VALUES (?, 'CASHIER', 'RECEIPT', 'PENDING', ?)
        """, (first_order_id, receipt_text))
        job_id = cur_p.lastrowid
        conn_p.commit()
        conn_p.close()

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

        # Nếu đang chạy local (mạng LAN), gửi socket trực tiếp (có tự động fallback máy in nếu cần)
        is_cloud = os.environ.get("VIBE_PROJECT_ID") or os.environ.get("KUBERNETES_SERVICE_HOST") or (os.name != "nt")
        if not is_cloud:
            from ..printer_service import async_dispatch_cashier_print
            await async_dispatch_cashier_print(receipt_bytes)
    except Exception as ex:
        print("[POS Checkout Receipt Print Error]:", ex)

    if ws_broadcaster:
        # Thông báo tới toàn hệ thống
        event_data = {
            "event": "TABLE_CHECKED_OUT",
            "table_id": table_id,
            "table_code": table["table_code"],
            "table_name": table["name"]
        }
        await ws_broadcaster.send_to_pos(event_data)
        await ws_broadcaster.send_to_kds(event_data)
        await ws_broadcaster.send_to_customer(table_id, {
            "event": "TABLE_CHECKED_OUT",
            "message": "Cảm ơn quý khách đã dùng bữa tại PiPo Garden! Hẹn gặp lại quý khách."
        })

    target_msg = f" (Tính bill với Admin: {billed_admin_name})" if bill_target == "ADMIN" else ""
    return {"status": "SUCCESS", "message": f"Đã thanh toán và mở lại bàn {table['name']}{target_msg}"}

@router.get("/bills/history")
async def get_bills_history(limit: int = 60, search: str = ""):
    """Lấy danh sách các hóa đơn đã thanh toán để thu ngân xem lại và in lại bill."""
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT o.id, o.session_id, o.table_id, o.round_number, o.subtotal, o.total,
               o.payment_status, o.payment_method, o.discount, o.discount_reason,
               o.bill_target, o.billed_admin_name, o.created_at, o.completed_at,
               t.name as table_name, t.table_code, t.area
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        WHERE o.payment_status = 'PAID'
    """
    params = []
    if search:
        query += " AND (t.name LIKE ? OR t.table_code LIKE ? OR o.id LIKE ? OR o.billed_admin_name LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s])

    query += " ORDER BY COALESCE(o.completed_at, o.created_at) DESC, o.id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    bills = []
    for r in rows:
        order_id = r["id"]
        cursor.execute("""
            SELECT item_name, quantity, unit_price, total_price, station, note, status
            FROM order_items
            WHERE order_id = ?
        """, (order_id,))
        items = [dict(it) for it in cursor.fetchall()]

        bills.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "table_id": r["table_id"],
            "table_name": r["table_name"],
            "table_code": r["table_code"],
            "area": r["area"],
            "subtotal": r["subtotal"],
            "discount": r["discount"] or 0,
            "discount_reason": r["discount_reason"] or "",
            "total": r["total"],
            "payment_method": r["payment_method"] or "TIỀN MẶT",
            "bill_target": r["bill_target"],
            "billed_admin_name": r["billed_admin_name"],
            "paid_at": r["completed_at"] or r["created_at"],
            "items": items
        })

    conn.close()
    return {"status": "SUCCESS", "bills": bills, "count": len(bills)}

@router.post("/bills/{order_id}/reprint")
async def reprint_bill(order_id: int, request: Request):
    """In lại hóa đơn đã thanh toán xuống máy in thu ngân."""
    user = get_current_user_from_request(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.*, t.name as table_name, t.table_code, t.area
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        WHERE o.id = ?
    """, (order_id,))
    order_row = cursor.fetchone()
    if not order_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn cần in lại.")

    cursor.execute("""
        SELECT item_name, quantity, unit_price, total_price, station, note, status
        FROM order_items
        WHERE order_id = ?
    """, (order_id,))
    items = [dict(it) for it in cursor.fetchall()]
    conn.close()

    table_dict = {
        "name": order_row["table_name"],
        "table_code": order_row["table_code"],
        "area": order_row["area"]
    }
    cashier_display = (user.get("full_name") if user else None) or "Thu Ngan PiPo"
    totals_info = {
        "title": "HOA DON BAN HANG (IN LAI)",
        "cashier_name": cashier_display,
        "discount": order_row["discount"] or 0,
        "discount_reason": order_row["discount_reason"] or "",
        "bill_target": order_row["bill_target"],
        "billed_admin_name": order_row["billed_admin_name"]
    }

    from ..escpos import format_receipt_ticket_text, build_escpos_receipt_bytes
    receipt_text = format_receipt_ticket_text(table_dict, items, totals_info=totals_info)
    receipt_bytes = build_escpos_receipt_bytes(table_dict, items, totals_info=totals_info)
    receipt_b64 = base64.b64encode(receipt_bytes).decode("ascii")

    conn_p = get_db()
    cur_p = conn_p.cursor()
    cur_p.execute("""
        INSERT INTO print_jobs (order_id, station, job_type, status, ticket_text)
        VALUES (?, 'CASHIER', 'RECEIPT', 'PENDING', ?)
    """, (order_id, receipt_text))
    job_id = cur_p.lastrowid
    conn_p.commit()
    conn_p.close()

    if ws_broadcaster:
        await ws_broadcaster.send_to_printers({
            "event": "PRINT_JOB",
            "job_id": job_id,
            "station": "CASHIER",
            "job_type": "RECEIPT",
            "ticket_text": receipt_text,
            "escpos_b64": receipt_b64,
            "table_name": order_row["table_name"]
        })

    is_cloud = os.environ.get("VIBE_PROJECT_ID") or os.environ.get("KUBERNETES_SERVICE_HOST") or (os.name != "nt")
    if not is_cloud:
        try:
            from ..printer_service import get_printer_config, send_escpos_to_printer
            p_cfg = get_printer_config()
            import asyncio
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, send_escpos_to_printer, p_cfg["cashier_ip"], p_cfg["cashier_port"], receipt_bytes)
        except Exception:
            pass

    return {
        "status": "SUCCESS",
        "message": f"Đã gửi lệnh in lại hóa đơn #{order_id} ({order_row['table_name']}) xuống máy in thành công!"
    }

@router.post("/service-call/{call_id}/dismiss")
async def dismiss_service_call(call_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE service_calls SET status = 'HANDLED' WHERE id = ?", (call_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "call_id": call_id}

@router.post("/service-call/dismiss-all")
async def dismiss_all_service_calls():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE service_calls SET status = 'HANDLED' WHERE status = 'PENDING'")
    conn.commit()
    conn.close()
    return {"status": "SUCCESS"}
