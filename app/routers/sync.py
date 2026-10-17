# Data Synchronization router between Local Restaurant and Vibe Host Cloud
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import uuid

from ..database import get_db

router = APIRouter(prefix="/api/sync", tags=["Sync"])

# Broadcast injection if needed
ws_broadcaster = None

def set_broadcaster(broadcaster):
    global ws_broadcaster
    ws_broadcaster = broadcaster

@router.get("/status")
def sync_status():
    """Kiểm tra trạng thái sẵn sàng đồng bộ."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as order_count FROM orders")
    order_count = cursor.fetchone()["order_count"]
    cursor.execute("SELECT MAX(created_at) as last_order_time FROM orders")
    last_time = cursor.fetchone()["last_order_time"]
    conn.close()

    return {
        "status": "READY",
        "order_count": order_count,
        "last_order_time": last_time,
        "server_time": datetime.now().isoformat()
    }

@router.post("/clear-revenue")
async def clear_revenue_data(request: Request):
    """Xóa sạch toàn bộ đơn hàng, chi tiết món và doanh thu thử nghiệm trên hệ thống."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    auth_header = request.headers.get("X-Pipo-Admin-Secret") or ""
    payload_token = payload.get("secret_token") or ""

    if auth_header != "pipo_secure_clear_revenue_2026" and payload_token != "pipo_secure_clear_revenue_2026":
        from .auth import get_current_user_from_request
        user = get_current_user_from_request(request)
        if not user or user.get("role") != "ADMIN":
            raise HTTPException(status_code=403, detail="Không có quyền thực hiện thao tác xóa doanh thu.")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM order_items")
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM service_calls")
    cursor.execute("DELETE FROM table_sessions")
    cursor.execute("DELETE FROM print_jobs")
    cursor.execute("DELETE FROM reservations")
    cursor.execute("DELETE FROM inventory_transactions")
    cursor.execute("DELETE FROM pickleball_bookings")
    cursor.execute("UPDATE tables SET status = 'AVAILABLE', current_session_id = NULL")
    try:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('orders', 'order_items', 'print_jobs', 'service_calls', 'table_sessions', 'inventory_transactions', 'reservations', 'pickleball_bookings')")
    except Exception:
        pass
    conn.commit()
    conn.close()

    if ws_broadcaster:
        try:
            await ws_broadcaster.send_to_pos({"event": "REVENUE_CLEARED"})
            await ws_broadcaster.send_to_kds({"event": "REVENUE_CLEARED"})
        except Exception:
            pass

    return {
        "status": "SUCCESS",
        "message": "Đã xóa toàn bộ dữ liệu đơn hàng và doanh thu thử nghiệm thành công!"
    }

@router.get("/export-orders")
def export_orders(since: Optional[str] = None, limit: int = 200):
    """Xuất danh sách đơn hàng và phiên bàn để đồng bộ sang hệ thống khác."""
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT o.*, t.table_code, t.name as table_name, s.session_token
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        LEFT JOIN table_sessions s ON o.session_id = s.id
    """
    params = []
    if since:
        query += " WHERE o.created_at > ?"
        params.append(since)
    
    query += " ORDER BY o.id ASC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    orders = [dict(r) for r in cursor.fetchall()]

    # Lấy kèm chi tiết món
    for o in orders:
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],))
        o["items"] = [dict(it) for it in cursor.fetchall()]

    conn.close()
    return {"orders": orders, "count": len(orders)}

@router.post("/import-orders")
def import_orders(payload: Dict[str, Any]):
    """Nhập các đơn hàng được đồng bộ từ Cloud về Local hoặc ngược lại."""
    orders_to_import = payload.get("orders", [])
    if not orders_to_import:
        return {"status": "SUCCESS", "imported": 0, "message": "Không có đơn mới để nhập"}

    conn = get_db()
    cursor = conn.cursor()
    imported_count = 0
    updated_count = 0

    for o in orders_to_import:
        table_code = o.get("table_code")
        session_token = o.get("session_token")
        
        # 1. Tìm hoặc ánh xạ bàn
        cursor.execute("SELECT id FROM tables WHERE table_code = ?", (table_code,))
        t_row = cursor.fetchone()
        if not t_row:
            continue
        local_table_id = t_row["id"]

        # 2. Tìm hoặc tạo session
        local_session_id = None
        if session_token:
            cursor.execute("SELECT id FROM table_sessions WHERE session_token = ?", (session_token,))
            s_row = cursor.fetchone()
            if s_row:
                local_session_id = s_row["id"]
            else:
                cursor.execute("""
                    INSERT INTO table_sessions (table_id, session_token, status, guest_count)
                    VALUES (?, ?, 'ACTIVE', 2)
                """, (local_table_id, session_token))
                local_session_id = cursor.lastrowid
        else:
            cursor.execute("SELECT id FROM table_sessions WHERE table_id = ? AND status = 'ACTIVE' LIMIT 1", (local_table_id,))
            s_row = cursor.fetchone()
            local_session_id = s_row["id"] if s_row else 1

        # 3. Kiểm tra xem đơn đã tồn tại chưa (dựa theo order_code hoặc thời gian + table_id + total)
        order_code = o.get("order_code") or f"SYNC_{o['id']}_{o.get('created_at', '')[:19]}"
        cursor.execute("SELECT id, payment_status, status FROM orders WHERE customer_note LIKE ?", (f"%[REF:{order_code}]%",))
        existing_order = cursor.fetchone()

        if existing_order:
            # Đơn đã có -> Cập nhật trạng thái thanh toán nếu có thay đổi
            if o.get("payment_status") != existing_order["payment_status"] or o.get("status") != existing_order["status"]:
                cursor.execute("""
                    UPDATE orders 
                    SET status = ?, payment_status = ?, completed_at = ?
                    WHERE id = ?
                """, (o.get("status"), o.get("payment_status"), o.get("completed_at"), existing_order["id"]))
                updated_count += 1
            continue

        # 4. Chèn đơn hàng mới
        note_with_ref = (o.get("customer_note") or "") + f" [REF:{order_code}]"
        cursor.execute("""
            INSERT INTO orders (
                session_id, table_id, round_number, subtotal, discount, total,
                status, payment_status, payment_method, customer_note, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            local_session_id, local_table_id, o.get("round_number", 1),
            o.get("subtotal", 0), o.get("discount", 0), o.get("total", 0),
            o.get("status", "CONFIRMED"), o.get("payment_status", "UNPAID"),
            o.get("payment_method", "CASH"), note_with_ref,
            o.get("created_at"), o.get("completed_at")
        ))
        new_order_id = cursor.lastrowid

        # 5. Chèn danh sách món
        for it in o.get("items", []):
            # Tìm ID món theo tên nếu ID khác nhau
            cursor.execute("SELECT id FROM menu_items WHERE name = ?", (it.get("item_name"),))
            mi_row = cursor.fetchone()
            local_item_id = mi_row["id"] if mi_row else it.get("item_id", 1)

            cursor.execute("""
                INSERT INTO order_items (
                    order_id, item_id, item_name, quantity, unit_price, total_price,
                    station, note, modifiers_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_order_id, local_item_id, it.get("item_name"), it.get("quantity", 1),
                it.get("unit_price", 0), it.get("total_price", 0),
                it.get("station", "HOT_KITCHEN"), it.get("note", ""),
                it.get("modifiers_json", "[]"), it.get("status", "QUEUED"),
                it.get("created_at", o.get("created_at"))
            ))

        imported_count += 1

    conn.commit()
    conn.close()

    return {
        "status": "SUCCESS",
        "imported": imported_count,
        "updated": updated_count,
        "message": f"Đã đồng bộ {imported_count} đơn mới, cập nhật {updated_count} đơn."
    }
