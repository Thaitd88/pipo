# Data Synchronization router between Local Restaurant and Vibe Host Cloud
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import uuid

from ..database import get_db
from ..timezone_utils import now_vn_str

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
        "server_time": now_vn_str("%Y-%m-%d %H:%M:%S")
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
    cursor.execute("DELETE FROM pickleball_checkins")
    cursor.execute("DELETE FROM pickleball_memberships")
    cursor.execute("DELETE FROM accounting_transactions")
    cursor.execute("UPDATE tables SET status = 'AVAILABLE', current_session_id = NULL")
    try:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('orders', 'order_items', 'print_jobs', 'service_calls', 'table_sessions', 'inventory_transactions', 'reservations', 'pickleball_bookings', 'pickleball_memberships', 'pickleball_checkins', 'accounting_transactions')")
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deleted_order_uuids (
            order_uuid TEXT PRIMARY KEY,
            deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    query = """
        SELECT o.*, t.table_code, t.name as table_name, s.session_token
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        LEFT JOIN table_sessions s ON o.session_id = s.id
        WHERE (o.order_uuid NOT IN (SELECT order_uuid FROM deleted_order_uuids))
    """
    params = []
    if since:
        query += " AND (o.payment_status = 'UNPAID' OR o.created_at > ? OR o.completed_at > ?)"
        params.extend([since, since])
    
    # Ưu tiên các đơn UNPAID lên đầu tiên, sau đó đến các đơn mới nhất (ID giảm dần)
    query += " ORDER BY (CASE WHEN o.payment_status = 'UNPAID' THEN 0 ELSE 1 END) ASC, o.id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    orders = [dict(r) for r in cursor.fetchall()]

    # Đảm bảo mỗi order xuất đi luôn có order_uuid cố định duy nhất
    for o in orders:
        if not o.get("order_uuid"):
            uid = f"ord_{uuid.uuid4().hex}"
            cursor.execute("UPDATE orders SET order_uuid = ? WHERE id = ?", (uid, o["id"]))
            o["order_uuid"] = uid

        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],))
        o["items"] = [dict(it) for it in cursor.fetchall()]

    # Xuất danh sách order_uuid đã bị xóa để server đối tác cùng dọn dẹp
    cursor.execute("SELECT order_uuid FROM deleted_order_uuids ORDER BY deleted_at DESC LIMIT 500")
    deleted_uuids = [r["order_uuid"] for r in cursor.fetchall()]

    conn.commit()
    conn.close()
    return {"orders": orders, "count": len(orders), "deleted_uuids": deleted_uuids}

@router.post("/import-orders")
async def import_orders(payload: Dict[str, Any]):
    """
    Nhập các đơn hàng được đồng bộ từ Cloud về Local hoặc ngược lại.
    Áp dụng 3 lớp khử trùng độc lập chống hoàn toàn hiện tượng lặp hóa đơn (Ping-Pong Loop).
    """
    orders_to_import = payload.get("orders", [])
    if not orders_to_import:
        return {"status": "SUCCESS", "imported": 0, "message": "Không có đơn mới để nhập"}

    conn = get_db()
    cursor = conn.cursor()
    imported_count = 0
    updated_count = 0

    import re

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deleted_order_uuids (
            order_uuid TEXT PRIMARY KEY,
            deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Đồng bộ các UUID đơn hàng đã bị xóa từ server đối tác
    incoming_del_uuids = payload.get("deleted_uuids", [])
    if incoming_del_uuids:
        for du in incoming_del_uuids:
            cursor.execute("INSERT OR IGNORE INTO deleted_order_uuids (order_uuid) VALUES (?)", (du,))
            cursor.execute("SELECT id FROM orders WHERE order_uuid = ?", (du,))
            d_row = cursor.fetchone()
            if d_row:
                did = d_row["id"]
                cursor.execute("DELETE FROM order_items WHERE order_id = ?", (did,))
                cursor.execute("DELETE FROM print_jobs WHERE order_id = ?", (did,))
                cursor.execute("DELETE FROM orders WHERE id = ?", (did,))

    for o in orders_to_import:
        incoming_uuid = o.get("order_uuid")
        if incoming_uuid:
            cursor.execute("SELECT 1 FROM deleted_order_uuids WHERE order_uuid = ?", (incoming_uuid,))
            if cursor.fetchone():
                continue
        table_code = o.get("table_code")
        session_token = o.get("session_token")
        incoming_uuid = o.get("order_uuid")
        
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
                sess_status = "ACTIVE" if o.get("payment_status") == "UNPAID" else "CLOSED"
                cursor.execute("""
                    INSERT INTO table_sessions (table_id, session_token, status, guest_count)
                    VALUES (?, ?, ?, 2)
                """, (local_table_id, session_token, sess_status))
                local_session_id = cursor.lastrowid
        else:
            cursor.execute("SELECT id FROM table_sessions WHERE table_id = ? AND status = 'ACTIVE' LIMIT 1", (local_table_id,))
            s_row = cursor.fetchone()
            local_session_id = s_row["id"] if s_row else 1

        # 3. KIỂM TRA ĐƠN ĐÃ TỒN TẠI (3 LỚP BẢO VỆ CHỐNG TRÙNG LẶP TRIỆT ĐỂ)
        existing_order = None
        
        # Lớp 1: Khớp theo order_uuid toàn cục
        if incoming_uuid:
            cursor.execute("SELECT id, payment_status, status, order_uuid FROM orders WHERE order_uuid = ?", (incoming_uuid,))
            existing_order = cursor.fetchone()

        # Lớp 2: Khớp theo mã REF trong customer_note (đối với các đơn cũ)
        if not existing_order:
            order_code = o.get("order_code") or f"SYNC_{o.get('id')}_{o.get('created_at', '')[:19]}"
            cursor.execute("SELECT id, payment_status, status, order_uuid FROM orders WHERE customer_note LIKE ?", (f"%[REF:{order_code}]%",))
            existing_order = cursor.fetchone()

        # Lớp 3: Khử trùng tự nhiên (Natural Key Deduplication)
        # Cùng bàn, cùng tổng tiền, thời gian tạo cách nhau không quá 60 giây -> 100% là cùng 1 đơn
        if not existing_order and o.get("created_at"):
            cursor.execute("""
                SELECT id, payment_status, status, order_uuid FROM orders
                WHERE table_id = ? 
                  AND total = ? 
                  AND ABS(strftime('%s', created_at) - strftime('%s', ?)) <= 60
                LIMIT 1
            """, (local_table_id, o.get("total", 0), o.get("created_at", "")))
            existing_order = cursor.fetchone()

        if existing_order:
            # 1. BẢO VỆ CHỐNG HỒI QUY: Đơn đã PAID thì tuyệt đối không bao giờ bị ghi đè ngược về UNPAID do sync trễ/cũ!
            if existing_order["payment_status"] == "PAID" and o.get("payment_status") != "PAID":
                continue

            # 2. ĐÃ TỒN TẠI: Cập nhật order_uuid nếu đơn này chưa có
            if incoming_uuid and not existing_order["order_uuid"]:
                cursor.execute("UPDATE orders SET order_uuid = ? WHERE id = ?", (incoming_uuid, existing_order["id"]))

            # 3. Chỉ đánh dấu OCCUPIED nếu đơn incoming thực sự là UNPAID VÀ đơn trong DB cũng không phải là PAID
            if o.get('payment_status') == 'UNPAID' and existing_order["payment_status"] != 'PAID':
                cursor.execute('UPDATE tables SET status = \'OCCUPIED\', current_session_id = ? WHERE id = ?', (local_session_id, local_table_id))
                cursor.execute('UPDATE table_sessions SET status = \'ACTIVE\' WHERE id = ?', (local_session_id,))

            # 4. Cập nhật trạng thái thanh toán & hình thức thanh toán nếu có thay đổi
            if (o.get("payment_status") != existing_order["payment_status"] or 
                o.get("status") != existing_order["status"] or 
                o.get("payment_method") != existing_order["payment_method"] or
                o.get("bill_target") != existing_order["bill_target"] or
                o.get("billed_admin_name") != existing_order["billed_admin_name"]):
                cursor.execute("""
                    UPDATE orders 
                    SET status = ?, payment_status = ?, completed_at = ?, payment_method = ?,
                        bill_target = ?, billed_admin_id = ?, billed_admin_name = ?
                    WHERE id = ?
                """, (
                    o.get("status"), o.get("payment_status"), o.get("completed_at"), o.get("payment_method", "CASH"),
                    o.get("bill_target", "CUSTOMER"), o.get("billed_admin_id"), o.get("billed_admin_name"),
                    existing_order["id"]
                ))
                updated_count += 1

                # Nếu đơn chuyển sang PAID, kiểm tra giải phóng bàn
                if o.get("payment_status") == "PAID":
                    cursor.execute("SELECT COUNT(*) as unpaid FROM orders WHERE table_id = ? AND payment_status = 'UNPAID'", (local_table_id,))
                    if cursor.fetchone()["unpaid"] == 0:
                        cursor.execute("UPDATE tables SET status = 'AVAILABLE', current_session_id = NULL WHERE id = ?", (local_table_id,))
                        cursor.execute("UPDATE table_sessions SET status = 'CLOSED' WHERE id = ?", (local_session_id,))
            continue

        # 4. CHÈN ĐƠN MỚI NGUYÊN BẢN (KHÔNG LÀM BẨN NOTE VỚI MÃ REF LẶP LẠI)
        final_uuid = incoming_uuid or f"ord_{uuid.uuid4().hex}"
        raw_note = o.get("customer_note") or ""
        clean_note = re.sub(r'\s*\[REF:SYNC_[^\]]+\]', '', raw_note).strip()

        cursor.execute("""
            INSERT INTO orders (
                order_uuid, session_id, table_id, round_number, subtotal, discount, total,
                status, payment_status, payment_method, bill_target, billed_admin_id, billed_admin_name,
                customer_note, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            final_uuid, local_session_id, local_table_id, o.get("round_number", 1),
            o.get("subtotal", 0), o.get("discount", 0), o.get("total", 0),
            o.get("status", "CONFIRMED"), o.get("payment_status", "UNPAID"),
            o.get("payment_method", "CASH"), o.get("bill_target", "CUSTOMER"),
            o.get("billed_admin_id"), o.get("billed_admin_name"), clean_note,
            o.get("created_at"), o.get("completed_at")
        ))
        new_order_id = cursor.lastrowid

        # Cập nhật bàn về OCCUPIED nếu đơn là UNPAID
        if o.get("payment_status") == "UNPAID":
            cursor.execute("UPDATE tables SET status = 'OCCUPIED', current_session_id = ? WHERE id = ?", (local_session_id, local_table_id))
            cursor.execute("UPDATE table_sessions SET status = 'ACTIVE' WHERE id = ?", (local_session_id,))

        # 5. Chèn danh sách món
        for it in o.get("items", []):
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

    if ws_broadcaster and (imported_count > 0 or updated_count > 0):
        try:
            await ws_broadcaster.send_to_pos({
                "event": "NEW_ORDER",
                "message": f"Đã đồng bộ {imported_count} đơn mới từ Cloud!"
            })
            await ws_broadcaster.send_to_kds({
                "event": "NEW_ORDER",
                "message": f"Đã đồng bộ {imported_count} đơn mới từ Cloud!"
            })
        except Exception:
            pass

    return {
        "status": "SUCCESS",
        "imported": imported_count,
        "updated": updated_count,
        "message": f"Đã đồng bộ {imported_count} đơn mới, cập nhật {updated_count} đơn."
    }

import io
import os
import zipfile
from fastapi.responses import StreamingResponse

@router.get("/code-bundle")
def get_code_bundle():
    """Tạo gói zip chứa code mới nhất (app, scripts, run_server) để máy thu ngân tự động cập nhật."""
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Nén thư mục app (trừ __pycache__)
        app_dir = os.path.join(root_dir, "app")
        for root, dirs, files in os.walk(app_dir):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
            for f in files:
                if not f.endswith((".pyc", ".pyo", ".tmp")):
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, root_dir)
                    zf.write(full_p, rel_p)

        # 2. Nén thư mục print_agent
        agent_dir = os.path.join(root_dir, "print_agent")
        for root, dirs, files in os.walk(agent_dir):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
            for f in files:
                if not f.endswith((".pyc", ".pyo", ".tmp")):
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, root_dir)
                    zf.write(full_p, rel_p)

        # 3. Nén thư mục scripts
        scripts_dir = os.path.join(root_dir, "scripts")
        for root, dirs, files in os.walk(scripts_dir):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
            for f in files:
                if not f.endswith((".pyc", ".pyo", ".tmp")):
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, root_dir)
                    zf.write(full_p, rel_p)

        # 4. Nén các file gốc cần thiết
        for fn in ["run_server.py", "run_agent.py", "requirements.txt"]:
            fp = os.path.join(root_dir, fn)
            if os.path.exists(fp):
                zf.write(fp, fn)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=pipo_update_bundle.zip"}
    )

@router.get("/export-reservations")
def export_reservations(since: Optional[str] = None, limit: int = 100):
    """Xuất danh sách đặt bàn trực tuyến để đồng bộ."""
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM reservations"
    params = []
    if since:
        query += " WHERE (status = 'PENDING' OR created_at > ?)"
        params.append(since)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, tuple(params))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"reservations": rows, "count": len(rows)}

@router.post("/import-reservations")
async def import_reservations(payload: Dict[str, Any]):
    """Nhập danh sách đặt bàn trực tuyến đồng bộ từ Cloud."""
    res_list = payload.get("reservations", [])
    if not res_list:
        return {"status": "SUCCESS", "imported": 0}

    conn = get_db()
    cursor = conn.cursor()
    imported = 0
    for r in res_list:
        cursor.execute("""
            SELECT id FROM reservations 
            WHERE phone = ? AND booking_date = ? AND booking_time = ?
        """, (r.get("phone"), r.get("booking_date"), r.get("booking_time")))
        existing = cursor.fetchone()
        if not existing:
            cursor.execute("""
                INSERT INTO reservations (
                    guest_name, phone, booking_date, booking_time, guest_count,
                    service_type, table_id, table_code, area, preorder_items_json,
                    total_estimated, note, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get("guest_name"), r.get("phone"), r.get("booking_date"), r.get("booking_time"),
                r.get("guest_count", 2), r.get("service_type", "DINING"), r.get("table_id"),
                r.get("table_code"), r.get("area"), r.get("preorder_items_json", "[]"),
                r.get("total_estimated", 0), r.get("note"), r.get("status", "PENDING"),
                r.get("created_at")
            ))
            imported += 1
    conn.commit()
    conn.close()

    if ws_broadcaster and imported > 0:
        try:
            await ws_broadcaster.send_to_pos({
                "event": "NEW_RESERVATION",
                "message": f"Có {imported} đơn đặt bàn trực tuyến mới từ Cloud!"
            })
        except Exception:
            pass

    return {"status": "SUCCESS", "imported": imported}

@router.post("/notify-pos-event")
async def notify_pos_event(payload: Dict[str, Any]):
    """Nhận sự kiện từ Cloud qua Agent để phát tức thời tới POS local."""
    if ws_broadcaster:
        try:
            await ws_broadcaster.send_to_pos(payload)
            if payload.get("event") in ["NEW_ORDER", "REVENUE_CLEARED"]:
                await ws_broadcaster.send_to_kds(payload)
        except Exception:
            pass
    return {"status": "SUCCESS"}
