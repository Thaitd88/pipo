# POS Cashier management router for PiPo Garden
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

    for order in orders:
        cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC", (order["id"],))
        items = [dict(it) for it in cursor.fetchall()]
        all_items.extend(items)
        # Chỉ cộng các món chưa bị hủy (status != 'CANCELLED')
        order_active_sum = sum(it["total_price"] for it in items if it["status"] != "CANCELLED")
        grand_total += max(0, order_active_sum - order["discount"])

    conn.close()

    # Link VietQR động cho nhà hàng PiPo Garden (chuẩn VietQR Napas247)
    # Cú pháp: https://img.vietqr.io/image/<BANK_ID>-<ACCOUNT_NO>-compact.png?amount=<AMOUNT>&addInfo=<CONTENT>
    vietqr_url = f"https://img.vietqr.io/image/MB-0988889999-compact.png?amount={grand_total}&addInfo=PiPo Garden {table['table_code']}"

    return {
        "table": dict(table),
        "orders_count": len(orders),
        "grand_total": grand_total,
        "items": all_items,
        "vietqr_url": vietqr_url
    }

@router.post("/table/{table_id}/checkout")
async def checkout_table(table_id: int, request: Request, payload: dict = None):
    require_api_auth(request, allowed_roles=["ADMIN", "CASHIER"])
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    table = cursor.fetchone()
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")

    # 1. Đánh dấu tất cả đơn của bàn là PAID
    cursor.execute("UPDATE orders SET payment_status = 'PAID', status = 'COMPLETED' WHERE table_id = ? AND payment_status = 'UNPAID'", (table_id,))

    # 2. Đóng session hiện tại
    cursor.execute("UPDATE table_sessions SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP WHERE table_id = ? AND status = 'ACTIVE'", (table_id,))

    # 3. Đưa bàn về AVAILABLE
    cursor.execute("UPDATE tables SET status = 'AVAILABLE', current_session_id = NULL WHERE id = ?", (table_id,))

    conn.commit()
    conn.close()

    if ws_broadcaster:
        # Thông báo tới toàn hệ thống
        event_data = {
            "event": "TABLE_CHECKED_OUT",
            "table_id": table_id,
            "table_code": table["table_code"],
            "table_name": table["name"]
        }
        await ws_broadcaster.send_to_pos(event_data)
        await ws_broadcaster.send_to_customer(table_id, {
            "event": "SESSION_CLOSED",
            "message": "Cảm ơn quý khách đã dùng bữa tại PiPo Garden! Hẹn gặp lại quý khách."
        })

    return {"status": "SUCCESS", "message": f"Đã thanh toán và mở lại bàn {table['name']}"}

@router.post("/service-call/{call_id}/dismiss")
async def dismiss_service_call(call_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE service_calls SET status = 'HANDLED' WHERE id = ?", (call_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "call_id": call_id}
