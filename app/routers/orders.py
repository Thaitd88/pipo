# Orders and Kitchen Dispatch router for PiPo Garden
import os
from fastapi import APIRouter, HTTPException, Request
import json
import base64
from datetime import datetime
from ..database import get_db, deduct_inventory_for_order_item, restore_inventory_for_order_item
from ..escpos import format_kitchen_ticket_text, build_escpos_kitchen_bytes, build_escpos_bytes
from ..printer_service import get_printer_config, send_escpos_to_printer
from .auth import get_current_user_from_request, require_api_auth

router = APIRouter(prefix="/api/orders", tags=["Orders"])

# Khai báo các connection manager sẽ được inject từ main.py
ws_broadcaster = None

def set_broadcaster(broadcaster):
    global ws_broadcaster
    ws_broadcaster = broadcaster

@router.post("")
async def create_order(payload: dict):
    """
    Khách bấm GỬI ĐƠN HÀNG từ điện thoại di động:
    1. Lưu thông tin đơn vào cơ sở dữ liệu.
    2. Tự động bóc tách trạm (Bếp Nóng, Bếp Lạnh, Quầy Bar).
    3. Tự động biên dịch mã in nhiệt ESC/POS chuẩn 80mm có còi hú.
    4. Bắn sự kiện tức thì qua WebSocket tới Máy in Bếp, Màn hình KDS và Thu ngân POS!
    """
    table_id = payload.get("table_id")
    session_token = payload.get("session_token")
    items = payload.get("items", [])
    customer_note = payload.get("customer_note", "")

    if not table_id or not items:
        raise HTTPException(status_code=400, detail="Thiếu thông tin bàn hoặc danh sách món ăn")

    conn = get_db()
    cursor = conn.cursor()

    # 1. Lấy thông tin bàn
    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    table = cursor.fetchone()
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")

    # 2. Kiểm tra hoặc tạo mới Session bàn
    cursor.execute("SELECT * FROM table_sessions WHERE table_id = ? AND status = 'ACTIVE'", (table_id,))
    session = cursor.fetchone()
    if not session:
        import uuid
        session_token = f"sess_{uuid.uuid4().hex[:12]}"
        cursor.execute(
            "INSERT INTO table_sessions (table_id, session_token, guest_count, status) VALUES (?, ?, 2, 'ACTIVE')",
            (table_id, session_token)
        )
        session_id = cursor.lastrowid
        cursor.execute("UPDATE tables SET status = 'OCCUPIED', current_session_id = ? WHERE id = ?", (session_id, table_id))
    else:
        session_id = session["id"]

    # 3. Tính số đợt gọi món (Round Number) của bàn
    cursor.execute("SELECT COUNT(*) as round_cnt FROM orders WHERE session_id = ?", (session_id,))
    round_number = (cursor.fetchone()["round_cnt"] or 0) + 1

    # 4. Tính toán tổng tiền đơn
    subtotal = 0
    detailed_items = []
    
    for it in items:
        item_id = it.get("item_id")
        qty = int(it.get("quantity", 1))
        note = it.get("note", "")
        mods = it.get("modifiers", [])

        cursor.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,))
        menu_row = cursor.fetchone()
        if not menu_row:
            continue

        orig_price = menu_row["price"]
        disc_pct = menu_row["discount_percent"] if "discount_percent" in menu_row.keys() and menu_row["discount_percent"] else 0
        if 0 < disc_pct <= 100:
            effective_price = int(round(orig_price * (100 - disc_pct) / 100))
        else:
            disc_pct = 0
            effective_price = orig_price

        line_total = effective_price * qty
        subtotal += line_total

        detailed_items.append({
            "item_id": item_id,
            "item_name": menu_row["name"],
            "quantity": qty,
            "unit_price": effective_price,
            "original_price": orig_price,
            "discount_percent": disc_pct,
            "total_price": line_total,
            "station": menu_row["station"],
            "note": note,
            "modifiers": mods,
            "portion": menu_row["portion"] if "portion" in menu_row.keys() and menu_row["portion"] else "",
        })

    if not detailed_items:
        conn.close()
        raise HTTPException(status_code=400, detail="Các món được chọn không hợp lệ")

    total = subtotal

    # 5. Lưu vào bảng Orders
    import uuid
    new_order_uuid = f"ord_{uuid.uuid4().hex}"
    cursor.execute("""
        INSERT INTO orders (order_uuid, session_id, table_id, round_number, subtotal, total, status, payment_status, customer_note)
        VALUES (?, ?, ?, ?, ?, ?, 'CONFIRMED', 'UNPAID', ?)
    """, (new_order_uuid, session_id, table_id, round_number, subtotal, total, customer_note))
    order_id = cursor.lastrowid

    # 6. Lưu vào bảng Order Items
    order_items_to_broadcast = []
    for dit in detailed_items:
        cursor.execute("""
            INSERT INTO order_items (order_id, item_id, item_name, quantity, unit_price, total_price, station, note, modifiers_json, status, discount_percent, original_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'QUEUED', ?, ?)
        """, (order_id, dit["item_id"], dit["item_name"], dit["quantity"], dit["unit_price"], dit["total_price"], 
              dit["station"], dit["note"], json.dumps(dit["modifiers"]), dit["discount_percent"], dit["original_price"]))
        order_item_id = cursor.lastrowid
        order_items_to_broadcast.append({**dit, "id": order_item_id, "status": "QUEUED"})

    # 7. TỰ ĐỘNG TẠO PHIẾU IN BẾP THEO TỪNG TRẠM (HOT_KITCHEN, COLD_KITCHEN, BAR)
    station_groups = {}
    for dit in detailed_items:
        st = dit["station"]
        if st not in station_groups:
            station_groups[st] = []
        station_groups[st].append(dit)

    order_info = {
        "id": order_id,
        "table_name": table["name"],
        "area": table["area"],
        "round_number": round_number,
        "customer_note": customer_note
    }

    print_jobs_created = []

    for station, st_items in station_groups.items():
        # Định dạng text phiếu in
        ticket_text = format_kitchen_ticket_text(order_info, st_items, station)
        
        # Biên dịch mã byte ESC/POS nhị phân chuẩn 80mm T80W
        escpos_bytes = build_escpos_kitchen_bytes(order_info, st_items, station=station, beep=True)
        escpos_b64 = base64.b64encode(escpos_bytes).decode("ascii")

        cursor.execute("""
            INSERT INTO print_jobs (order_id, station, job_type, status, ticket_text)
            VALUES (?, ?, 'KOT', 'PENDING', ?)
        """, (order_id, station, ticket_text))
        job_id = cursor.lastrowid

        print_jobs_created.append({
            "job_id": job_id,
            "station": station,
            "ticket_text": ticket_text,
            "escpos_b64": escpos_b64,
            "table_name": table["name"]
        })

    conn.commit()
    conn.close()

    # Bắn lệnh in trực tiếp qua mạng LAN nếu server chạy nội bộ (không chạy trên Cloud)
    is_cloud = os.environ.get("VIBE_PROJECT_ID") or os.environ.get("KUBERNETES_SERVICE_HOST") or (os.name != "nt")
    if not is_cloud:
        try:
            p_cfg = get_printer_config()
            if p_cfg.get("auto_kitchen"):
                for pjob in print_jobs_created:
                    dest_ip = p_cfg["cashier_ip"] if pjob["station"] == "BAR" else p_cfg["kitchen_ip"]
                    dest_port = p_cfg["cashier_port"] if pjob["station"] == "BAR" else p_cfg["kitchen_port"]
                    raw_b = base64.b64decode(pjob["escpos_b64"]) if pjob.get("escpos_b64") else b""
                    if raw_b:
                        import asyncio
                        loop = asyncio.get_event_loop()
                        loop.run_in_executor(None, send_escpos_to_printer, dest_ip, dest_port, raw_b)
        except Exception:
            pass

    # 8. PHÁT SỰ KIỆN REAL-TIME
    full_order_payload = {
        "order_id": order_id,
        "table_id": table_id,
        "table_code": table["table_code"],
        "table_name": table["name"],
        "area": table["area"],
        "round_number": round_number,
        "total": total,
        "customer_note": customer_note,
        "created_at": datetime.now().strftime("%H:%M:%S"),
        "items": order_items_to_broadcast,
    }

    if ws_broadcaster:
        # A. Đẩy lệnh in tức thì xuống Print Agent máy thu ngân
        for pjob in print_jobs_created:
            await ws_broadcaster.send_to_printers({
                "event": "PRINT_JOB",
                **pjob
            })

        # B. Đẩy vé món lên Màn hình Bếp KDS (kèm hiệu ứng chuông báo)
        await ws_broadcaster.send_to_kds({
            "event": "NEW_ORDER",
            "order": full_order_payload
        })

        # C. Đẩy thông báo lên Màn hình Thu ngân POS
        await ws_broadcaster.send_to_pos({
            "event": "NEW_ORDER",
            "order": full_order_payload
        })

        # D. Cập nhật trạng thái đơn cho điện thoại khách
        await ws_broadcaster.send_to_customer(table_id, {
            "event": "ORDER_SUBMITTED",
            "order_id": order_id,
            "status": "CONFIRMED",
            "message": "Đơn hàng đã được chuyển thẳng tới Bếp để chế biến!"
        })

    return {
        "status": "SUCCESS",
        "order_id": order_id,
        "round_number": round_number,
        "print_jobs_count": len(print_jobs_created),
        "total": total
    }

@router.get("/active")
def get_active_orders():
    """Lấy danh sách các đơn đang hoạt động (dành cho KDS và POS)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.*, t.name as table_name, t.table_code, t.area
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        WHERE o.payment_status = 'UNPAID'
          AND t.status != 'AVAILABLE'
        ORDER BY o.created_at ASC
    """)
    orders = [dict(o) for o in cursor.fetchall()]

    for order in orders:
        cursor.execute("""
            SELECT oi.*, m.image_url
            FROM order_items oi
            JOIN menu_items m ON oi.item_id = m.id
            WHERE oi.order_id = ?
            ORDER BY oi.id ASC
        """, (order["id"],))
        items = [dict(it) for it in cursor.fetchall()]
        for it in items:
            if it.get("modifiers_json"):
                try:
                    it["modifiers"] = json.loads(it["modifiers_json"])
                except Exception:
                    it["modifiers"] = []
            else:
                it["modifiers"] = []
        order["items"] = items

    conn.close()
    return orders

@router.patch("/table/{table_id}/serve-all")
async def serve_all_table_items(table_id: int):
    """Xác nhận đã ra tất cả món cho bàn từ POS/Thu ngân."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM order_items 
        WHERE order_id IN (SELECT id FROM orders WHERE table_id = ? AND payment_status = 'UNPAID')
          AND status != 'SERVED'
    """, (table_id,))
    item_rows = cursor.fetchall()
    for ir in item_rows:
        try:
            deduct_inventory_for_order_item(conn, ir["id"])
        except Exception:
            pass

    cursor.execute("""
        UPDATE order_items 
        SET status = 'SERVED', updated_at = CURRENT_TIMESTAMP
        WHERE order_id IN (SELECT id FROM orders WHERE table_id = ? AND payment_status = 'UNPAID')
          AND status != 'SERVED'
    """, (table_id,))
    conn.commit()
    conn.close()

    if ws_broadcaster:
        await ws_broadcaster.send_to_pos({
            "event": "TABLE_ITEMS_SERVED",
            "table_id": table_id
        })
        await ws_broadcaster.send_to_kds({
            "event": "TABLE_ITEMS_SERVED",
            "table_id": table_id
        })
        await ws_broadcaster.send_to_customer(table_id, {
            "event": "ITEM_STATUS_CHANGED",
            "item_name": "Tất cả món",
            "new_status": "SERVED"
        })

    return {"status": "SUCCESS", "table_id": table_id}

@router.patch("/item/{order_item_id}/status")
async def update_item_status(order_item_id: int, payload: dict):
    """Bếp hoặc Thu ngân bấm chuyển trạng thái món: QUEUED -> COOKING -> READY -> SERVED."""
    new_status = payload.get("status")
    if new_status not in ["QUEUED", "COOKING", "READY", "SERVED", "CANCELLED"]:
        raise HTTPException(status_code=400, detail="Trạng thái không hợp lệ")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT oi.*, o.table_id, t.name as table_name 
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN tables t ON o.table_id = t.id
        WHERE oi.id = ?
    """, (order_item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy món")

    cursor.execute("UPDATE order_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, order_item_id))
    conn.commit()

    # TỰ ĐỘNG TRỪ TỒN KHO NẾU BẮT ĐẦU NẤU HOẶC HOÀN TẤT / RA MÓN
    if new_status in ["COOKING", "READY", "SERVED"]:
        try:
            deduct_inventory_for_order_item(conn, order_item_id)
        except Exception as e:
            print(f"[Inventory Error]: {e}")

    conn.close()

    # Bắn sự kiện cập nhật
    if ws_broadcaster:
        update_data = {
            "event": "ITEM_STATUS_CHANGED",
            "order_item_id": order_item_id,
            "new_status": new_status,
            "item_name": item["item_name"],
            "table_id": item["table_id"],
            "table_name": item["table_name"]
        }
        await ws_broadcaster.send_to_kds(update_data)
        await ws_broadcaster.send_to_customer(item["table_id"], update_data)
        await ws_broadcaster.send_to_pos(update_data)

    return {"status": "SUCCESS", "order_item_id": order_item_id, "new_status": new_status}

@router.patch("/{order_id}/complete-all")
async def complete_all_order_items(order_id: int):
    """Bếp bấm hoàn tất toàn bộ các món trong 1 vé."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.table_id, t.name as table_name
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        WHERE o.id = ?
    """, (order_id,))
    order_row = cursor.fetchone()
    if not order_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    cursor.execute("""
        SELECT id FROM order_items 
        WHERE order_id = ? AND status IN ('QUEUED', 'COOKING')
    """, (order_id,))
    items_to_complete = [r["id"] for r in cursor.fetchall()]

    cursor.execute("""
        UPDATE order_items 
        SET status = 'READY', updated_at = CURRENT_TIMESTAMP 
        WHERE order_id = ? AND status IN ('QUEUED', 'COOKING')
    """, (order_id,))
    conn.commit()

    # TỰ ĐỘNG TRỪ TỒN KHO CHO TOÀN BỘ MÓN TRONG VÉ
    for o_item_id in items_to_complete:
        try:
            deduct_inventory_for_order_item(conn, o_item_id)
        except Exception as e:
            print(f"[Inventory Error on complete-all]: {e}")

    conn.close()

    if ws_broadcaster:
        update_data = {
            "event": "ORDER_ITEMS_COMPLETED",
            "order_id": order_id,
            "table_id": order_row["table_id"],
            "table_name": order_row["table_name"]
        }
        await ws_broadcaster.send_to_kds(update_data)
        await ws_broadcaster.send_to_customer(order_row["table_id"], update_data)
        await ws_broadcaster.send_to_pos(update_data)

    return {"status": "SUCCESS", "order_id": order_id, "message": "Đã hoàn tất tất cả món trong vé"}

# ==========================================
# CÁC ENDPOINT TRẢ MÓN & HỦY MÓN
# ==========================================

@router.get("/cancel-requests")
def get_pending_cancel_requests(request: Request):
    """Lấy danh sách các món đang chờ Bếp xác nhận thu hồi (CANCEL_PENDING)."""
    require_api_auth(request, allowed_roles=["ADMIN", "CHEF", "CASHIER", "WAITER", "PICKLEBALL"])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT oi.*, o.table_id, t.name as table_name, t.table_code, o.round_number
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN tables t ON o.table_id = t.id
        WHERE oi.status = 'CANCEL_PENDING'
        ORDER BY oi.cancel_requested_at DESC
    """)
    rows = cursor.fetchall()
    requests = [dict(r) for r in rows]
    conn.close()
    return requests

@router.post("/item/{order_item_id}/cancel-request")
async def request_cancel_item(order_item_id: int, payload: dict, request: Request):
    """
    Thu ngân hoặc Phục vụ bấm Hủy/Trả món:
    - Lý do: Khách hủy món, Không phục vụ được, Hết NVL, Khác...
    - Nếu Bếp chưa ra món (QUEUED, COOKING): HỦY NGAY LẬP TỨC, hoàn kho (nếu đã trừ) và cập nhật hóa đơn.
    - Nếu Bếp đã ra món (READY) hoặc đã bưng ra bàn (SERVED): Chuyển thành CANCEL_PENDING, gửi yêu cầu tới Bếp xác nhận thu hồi.
    """
    user = require_api_auth(request, allowed_roles=["ADMIN", "CASHIER", "WAITER", "PICKLEBALL"])
    reason = payload.get("reason", "Khách hủy món").strip()
    cancel_qty = payload.get("cancel_quantity")
    note = payload.get("note", "").strip()
    if note:
        reason = f"{reason} ({note})"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT oi.*, o.table_id, o.id as order_id, o.subtotal, o.discount, o.total, t.name as table_name, t.table_code
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN tables t ON o.table_id = t.id
        WHERE oi.id = ?
    """, (order_item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy món ăn trong đơn")

    if item["status"] == "CANCELLED":
        conn.close()
        raise HTTPException(status_code=400, detail="Món ăn này đã bị hủy trước đó")

    if item["status"] == "CANCEL_PENDING":
        conn.close()
        raise HTTPException(status_code=400, detail="Món ăn này đang chờ Bếp xác nhận thu hồi")

    current_qty = item["quantity"]
    target_item_id = order_item_id
    cancelled_quantity = current_qty

    # Xử lý trường hợp hủy một phần số lượng (ví dụ gọi 3 dĩa, chỉ hủy 1 dĩa)
    if cancel_qty and 0 < int(cancel_qty) < current_qty:
        cancelled_quantity = int(cancel_qty)
        remain_qty = current_qty - cancelled_quantity
        remain_total = remain_qty * item["unit_price"]

        cursor.execute("""
            UPDATE order_items 
            SET quantity = ?, total_price = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (remain_qty, remain_total, order_item_id))

        cursor.execute("""
            INSERT INTO order_items 
            (order_id, item_id, item_name, quantity, unit_price, total_price, station, note, modifiers_json, status, inventory_deducted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["order_id"], item["item_id"], item["item_name"],
            cancelled_quantity, item["unit_price"], cancelled_quantity * item["unit_price"],
            item["station"], item["note"], item["modifiers_json"],
            item["status"], item["inventory_deducted"]
        ))
        target_item_id = cursor.lastrowid
        conn.commit()

    current_status = item["status"]

    # Kiểm tra quyền Admin (qua session đăng nhập hoặc mật khẩu Admin truyền kèm)
    is_admin = (user.get("role") == "ADMIN")
    admin_name = user.get("full_name", "Admin") if is_admin else None

    if not is_admin and payload.get("admin_password"):
        from .auth import verify_password
        cursor.execute("SELECT id, full_name, password_hash FROM users WHERE role = 'ADMIN'")
        admins = cursor.fetchall()
        for adm in admins:
            if verify_password(payload["admin_password"], adm["password_hash"]):
                is_admin = True
                admin_name = adm["full_name"]
                break
        if not is_admin:
            conn.close()
            raise HTTPException(status_code=403, detail="Mật khẩu Quản lý (Admin) không chính xác!")

    # TRƯỜNG HỢP 1: Món chưa ra bàn (QUEUED, COOKING, READY) HOẶC đã có Admin xác nhận duyệt trả
    if current_status in ["QUEUED", "COOKING", "READY"] or is_admin:
        canceller_display = f"{admin_name} (Admin duyệt trả)" if is_admin else f"{user['full_name']} ({user['role']})"
        cursor.execute("""
            UPDATE order_items
            SET status = 'CANCELLED',
                cancel_reason = ?,
                cancelled_by = ?,
                cancelled_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (reason, canceller_display, target_item_id))

        # Nếu đã trừ kho (đang COOKING hoặc SERVED), tự động hoàn lại NVL vào kho
        if item["inventory_deducted"] == 1:
            try:
                restore_inventory_for_order_item(conn, target_item_id, reason=reason)
            except Exception as e:
                print(f"[Inventory Restore Error]: {e}")

        # Tính toán lại tổng tiền của đơn hàng
        cursor.execute("""
            UPDATE orders 
            SET subtotal = (SELECT COALESCE(SUM(total_price), 0) FROM order_items WHERE order_id = ? AND status != 'CANCELLED'),
                total = MAX(0, (SELECT COALESCE(SUM(total_price), 0) FROM order_items WHERE order_id = ? AND status != 'CANCELLED') - discount)
            WHERE id = ?
        """, (item["order_id"], item["order_id"], item["order_id"]))
        conn.commit()
        conn.close()

        # Bắn WebSocket thông báo hủy món
        if ws_broadcaster:
            event_data = {
                "event": "ITEM_CANCELLED",
                "order_item_id": target_item_id,
                "item_name": item["item_name"],
                "quantity": cancelled_quantity,
                "table_id": item["table_id"],
                "table_name": item["table_name"],
                "cancel_reason": reason,
                "cancelled_by": canceller_display,
                "order_id": item["order_id"]
            }
            await ws_broadcaster.send_to_kds(event_data)
            await ws_broadcaster.send_to_pos(event_data)
            await ws_broadcaster.send_to_customer(item["table_id"], event_data)

        succ_msg = f"Đã duyệt trả món '{item['item_name']} x{cancelled_quantity}' thành công và giảm tiền trên hóa đơn bàn!" if is_admin and current_status == "SERVED" else f"Đã hủy món '{item['item_name']} x{cancelled_quantity}' thành công và cập nhật lại hóa đơn!"
        return {
            "status": "CANCELLED_IMMEDIATELY",
            "message": succ_msg,
            "order_item_id": target_item_id
        }

    # TRƯỜNG HỢP 2: Món đã ra bàn (SERVED) nhưng chưa có Admin duyệt -> Chuyển CANCEL_PENDING để Admin xác nhận
    cursor.execute("""
        UPDATE order_items
        SET status = 'CANCEL_PENDING',
            cancel_reason = ?,
            cancel_requested_by = ?,
            cancel_requested_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (reason, f"{user['full_name']} ({user['role']})", target_item_id))
    conn.commit()
    conn.close()

    if ws_broadcaster:
        event_data = {
            "event": "CANCEL_REQUESTED",
            "order_item_id": target_item_id,
            "item_name": item["item_name"],
            "quantity": cancelled_quantity,
            "table_id": item["table_id"],
            "table_name": item["table_name"],
            "cancel_reason": reason,
            "cancel_requested_by": f"{user['full_name']} ({user['role']})",
            "current_status": current_status,
            "order_id": item["order_id"]
        }
        await ws_broadcaster.send_to_kds(event_data)
        await ws_broadcaster.send_to_pos(event_data)
        await ws_broadcaster.send_to_customer(item["table_id"], event_data)

    return {
        "status": "CANCEL_PENDING",
        "message": f"Món '{item['item_name']} x{cancelled_quantity}' đã ra bàn. Đã gửi yêu cầu tới Quản trị viên (Admin) để xác nhận duyệt trả món!",
        "order_item_id": target_item_id
    }

@router.post("/item/{order_item_id}/kitchen-confirm-cancel")
async def kitchen_confirm_cancel(order_item_id: int, payload: dict, request: Request):
    """
    Admin hoặc Bếp duyệt yêu cầu thu hồi / trả món:
    - action: 'APPROVE' (Duyệt trả món) -> Chuyển CANCELLED, trừ tiền bill, hoàn kho nếu chọn.
    - action: 'REJECT' (Từ chối trả món) -> Khôi phục trạng thái SERVED/READY.
    """
    user = require_api_auth(request, allowed_roles=["ADMIN", "CHEF", "CASHIER", "WAITER", "PICKLEBALL"])
    action = payload.get("action", "APPROVE").upper() # APPROVE or REJECT
    rejection_note = (payload.get("rejection_reason") or payload.get("note") or "").strip()
    restore_stock = payload.get("restore_inventory", True)

    conn = get_db()
    cursor = conn.cursor()

    is_admin = (user.get("role") == "ADMIN")
    admin_name = user.get("full_name") if is_admin else None

    if action == "APPROVE" and not is_admin and payload.get("admin_password"):
        from .auth import verify_password
        cursor.execute("SELECT id, full_name, password_hash FROM users WHERE role = 'ADMIN'")
        admins = cursor.fetchall()
        for adm in admins:
            if verify_password(payload["admin_password"], adm["password_hash"]):
                is_admin = True
                admin_name = adm["full_name"]
                break
        if not is_admin:
            conn.close()
            raise HTTPException(status_code=403, detail="Mật khẩu Quản lý (Admin) không chính xác!")

    if action == "APPROVE" and not is_admin:
        conn.close()
        raise HTTPException(status_code=403, detail="Chỉ Quản lý (Admin) mới có quyền duyệt trả lại món đã ra bàn!")

    cursor.execute("""
        SELECT oi.*, o.table_id, o.id as order_id, o.subtotal, o.discount, o.total, t.name as table_name
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN tables t ON o.table_id = t.id
        WHERE oi.id = ?
    """, (order_item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy món ăn")

    if item["status"] != "CANCEL_PENDING":
        conn.close()
        raise HTTPException(status_code=400, detail="Món ăn này không trong trạng thái chờ thu hồi")

    if action == "APPROVE":
        cursor.execute("""
            UPDATE order_items
            SET status = 'CANCELLED',
                cancelled_by = ?,
                cancelled_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (f"{admin_name or user['full_name']} (Admin duyệt trả món)", order_item_id))

        # Hoàn lại nguyên vật liệu vào kho nếu được chọn
        if restore_stock and item["inventory_deducted"] == 1:
            try:
                restore_inventory_for_order_item(conn, order_item_id, reason=f"Admin duyệt trả món: {item['cancel_reason']}")
            except Exception as e:
                print(f"[Inventory Restore Error]: {e}")

        # Tính toán lại tổng tiền của đơn hàng
        cursor.execute("""
            UPDATE orders 
            SET subtotal = (SELECT COALESCE(SUM(total_price), 0) FROM order_items WHERE order_id = ? AND status != 'CANCELLED'),
                total = MAX(0, (SELECT COALESCE(SUM(total_price), 0) FROM order_items WHERE order_id = ? AND status != 'CANCELLED') - discount)
            WHERE id = ?
        """, (item["order_id"], item["order_id"], item["order_id"]))
        conn.commit()
        conn.close()

        if ws_broadcaster:
            event_data = {
                "event": "CANCEL_APPROVED",
                "order_item_id": order_item_id,
                "item_name": item["item_name"],
                "quantity": item["quantity"],
                "table_id": item["table_id"],
                "table_name": item["table_name"],
                "order_id": item["order_id"],
                "confirmed_by": f"{user['full_name']} (Bếp)"
            }
            await ws_broadcaster.send_to_kds(event_data)
            await ws_broadcaster.send_to_pos(event_data)
            await ws_broadcaster.send_to_customer(item["table_id"], event_data)

        return {
            "status": "SUCCESS",
            "message": f"Bếp đã xác nhận thu hồi món '{item['item_name']}'. Đã trừ tiền trên hóa đơn thành công!"
        }

    else: # REJECT
        prev_status = "SERVED"
        cursor.execute("""
            UPDATE order_items
            SET status = ?,
                cancel_rejection_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (prev_status, rejection_note or "Bếp từ chối thu hồi", order_item_id))
        conn.commit()
        conn.close()

        if ws_broadcaster:
            event_data = {
                "event": "CANCEL_REJECTED",
                "order_item_id": order_item_id,
                "item_name": item["item_name"],
                "table_id": item["table_id"],
                "table_name": item["table_name"],
                "rejection_note": rejection_note,
                "rejected_by": f"{user['full_name']} (Bếp)"
            }
            await ws_broadcaster.send_to_kds(event_data)
            await ws_broadcaster.send_to_pos(event_data)
            await ws_broadcaster.send_to_customer(item["table_id"], event_data)

        return {
            "status": "SUCCESS",
            "message": f"Đã từ chối thu hồi món '{item['item_name']}'."
        }

@router.post("/service-call")
async def create_service_call(payload: dict):
    """Khách bấm nút gọi phục vụ, xin đá, khăn lạnh hoặc xin thanh toán."""
    table_id = payload.get("table_id")
    call_type = payload.get("call_type", "WAITER") # ICE, TISSUE, WAITER, BILL

    call_labels = {
        "ICE": "🍺🧊 Lên bia + đá",
        "TISSUE": "🥢🥂 Chén + ly",
        "WAITER": "🔔 Cần gặp nhân viên hỗ trợ",
        "BILL": "💳 Khách yêu cầu thanh toán hóa đơn"
    }
    label = call_labels.get(call_type, "Yêu cầu hỗ trợ")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    table = cursor.fetchone()
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")

    cursor.execute("""
        INSERT INTO service_calls (table_id, table_name, call_type, status)
        VALUES (?, ?, ?, 'PENDING')
    """, (table_id, table["name"], call_type))
    call_id = cursor.lastrowid
    conn.commit()
    conn.close()

    call_data = {
        "event": "SERVICE_CALL",
        "call_id": call_id,
        "table_id": table_id,
        "table_name": table["name"],
        "call_type": call_type,
        "label": label,
        "time": datetime.now().strftime("%H:%M:%S")
    }

    if ws_broadcaster:
        await ws_broadcaster.send_to_pos(call_data)

    return {"status": "SUCCESS", "message": f"Đã gửi yêu cầu: {label}"}
