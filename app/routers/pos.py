# POS Cashier management router for PiPo Garden
import urllib.parse
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
from ..database import get_db
from .auth import require_api_auth

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

    # Yêu cầu phục vụ đang chờ xử lý
    cursor.execute("SELECT * FROM service_calls WHERE status = 'PENDING' ORDER BY created_at DESC LIMIT 10")
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
    table = cursor.fetchone()
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")

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

    clean_table_code = str(table["table_code"] or table["name"] or "01").upper()
    if clean_table_code.startswith("BAN "):
        clean_table_code = clean_table_code.replace("BAN ", "")

    transfer_note = f"TT PiPo Garden Ban {clean_table_code} {in_time_str}-{out_time_str}"
    encoded_note = urllib.parse.quote(transfer_note)

    # Link VietQR động cho nhà hàng PiPo Garden (MB Bank 075624456)
    vietqr_url = f"https://img.vietqr.io/image/MB-075624456-compact.png?amount={grand_total}&addInfo={encoded_note}"

    return {
        "table": dict(table),
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

    # Tự động in hóa đơn thanh toán xuống Máy in Thu ngân (192.168.31.252:9100)
    try:
        from ..printer_service import get_printer_config, print_cashier_receipt
        p_cfg = get_printer_config()
        if p_cfg.get("auto_cashier") and checkout_items:
            import asyncio
            cashier_display = user.get("full_name") or "Thu Ngan PiPo"
            totals_info = {
                "title": "HOA DON THANH TOAN",
                "cashier_name": cashier_display,
                "discount": discount_amount,
                "discount_reason": discount_reason,
                "bill_target": bill_target,
                "billed_admin_name": billed_admin_name
            }
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, print_cashier_receipt, dict(table), checkout_items, totals_info)
    except Exception:
        pass

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

@router.post("/service-call/{call_id}/dismiss")
async def dismiss_service_call(call_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE service_calls SET status = 'HANDLED' WHERE id = ?", (call_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "call_id": call_id}
