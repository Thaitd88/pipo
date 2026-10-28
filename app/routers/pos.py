# POS Cashier management router for PiPo Garden
import os
import re
import io
import json
import base64
import logging
import urllib.parse
import urllib.request
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from ..database import get_db, deduct_inventory_for_order_item, restore_inventory_for_order_item, get_dynamic_bom_for_item
from ..timezone_utils import now_vn_str
from .auth import require_api_auth, get_current_user_from_request

logger = logging.getLogger("pos")

router = APIRouter(prefix="/api/pos", tags=["POS Cashier"])

ws_broadcaster = None

def set_broadcaster(broadcaster):
    global ws_broadcaster
    ws_broadcaster = broadcaster

@router.get("/overview")
def get_pos_overview():
    conn = get_db()
    try:
        cursor = conn.cursor()

        # Thống kê bàn
        cursor.execute("SELECT COUNT(*) as total FROM tables")
        total_tables = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as occupied FROM tables WHERE status IN ('OCCUPIED', 'BILLING')")
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

        return {
            "total_tables": total_tables,
            "occupied_tables": occupied_tables,
            "available_tables": total_tables - occupied_tables,
            "current_unpaid_revenue": current_unpaid,
            "pending_calls": pending_calls
        }
    finally:
        conn.close()

@router.get("/admins")
def get_admins_list():
    """Lấy danh sách các tài khoản Quản trị viên (ADMIN) để chọn khi tính bill với Admin."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, full_name, role 
        FROM users 
        WHERE (role = 'ADMIN' OR role = 'SUPER_ADMIN') AND is_active = 1 
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
    session_id = table["current_session_id"]

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

    # Bàn đang có khách: Lấy các đơn hàng của phiên hiện tại nếu có session_id, hoặc UNPAID nếu không có session_id
    if session_id:
        cursor.execute("""
            SELECT * FROM orders 
            WHERE table_id = ? AND (session_id = ? OR (session_id IS NULL AND payment_status = 'UNPAID'))
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
    paid_total = 0
    unpaid_total = 0
    first_order_time = None

    for order in orders:
        if not first_order_time and order.get("created_at"):
            first_order_time = order["created_at"]
        cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC", (order["id"],))
        items = [dict(it) for it in cursor.fetchall()]
        for it in items:
            it["name"] = it["item_name"]
            it["price"] = it["unit_price"]
            it["total"] = it["total_price"]
            it["order_created_at"] = order.get("created_at")
            it["round_number"] = order.get("round_number", 1)

            # Phân giải danh sách tùy chọn / vị (modifiers)
            mods = []
            raw_mods = it.get("modifiers_json")
            if raw_mods:
                try:
                    mods = json.loads(raw_mods) if isinstance(raw_mods, str) else raw_mods
                    if not isinstance(mods, list):
                        mods = []
                except Exception:
                    mods = []
            it["modifiers"] = mods

            # Trích xuất chuỗi tên vị trực quan (VD: "Úp trứng", "Muối ớt")
            flav = ""
            for m in mods:
                if isinstance(m, dict):
                    v = str(m.get("value") or "").strip()
                    if not v:
                        raw_n = str(m.get("name") or "").strip()
                        if raw_n.lower() not in ("chọn vị chế biến", "chon vi che bien", "vị", "vi"):
                            v = raw_n
                    if v and v.lower() not in ("chọn vị chế biến", "chon vi che bien"):
                        flav = v
                        break
                elif isinstance(m, str) and m.strip():
                    flav = m.strip()
                    break
            it["flavor"] = flav
        all_items.extend(items)
        # Chỉ cộng các món chưa bị hủy (status != 'CANCELLED')
        order_active_sum = sum(it["total_price"] for it in items if it["status"] != "CANCELLED")
        order_net = max(0, order_active_sum - (order.get("discount") or 0))
        grand_total += order_net
        if order.get("payment_status") == "PAID":
            paid_total += order_net
        else:
            unpaid_total += order_net

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
    vietqr_url = f"/api/pos/vietqr-image?amount={grand_total}&add_info={encoded_note}&table_code={clean_table_code}"
    vietqr_direct_url = f"https://img.vietqr.io/image/970422-075624456-compact2.png?amount={grand_total}&addInfo={encoded_note}&accountName=PIPO%20GARDEN"

    return {
        "table": dict(table),
        "table_id": table_id,
        "table_name": table["name"],
        "table_code": table["table_code"],
        "area": table["area"],
        "status": table["status"],
        "orders_count": len(orders),
        "grand_total": grand_total,
        "total": grand_total,
        "paid_total": paid_total,
        "unpaid_total": unpaid_total,
        "items": all_items,
        "transfer_note": transfer_note,
        "in_time": in_time_str,
        "out_time": out_time_str,
        "vietqr_url": vietqr_url,
        "vietqr_direct_url": vietqr_direct_url
    }

@router.get("/vietqr-image")
def get_vietqr_image(amount: int = 0, add_info: str = "TT PiPo", table_code: str = ""):
    """
    Tạo ảnh VietQR chuẩn PNG bitmap (MB Bank 970422 - STK 075624456 - PIPO GARDEN):
    1. Gọi VietQR API v2 (api.vietqr.io/v2/generate) lấy mẫu ảnh PNG compact2 đẹp mắt, có logo MB Bank.
    2. Nếu mạng chậm (>2.5s) hoặc VietQR server lỗi:
       Tự động sinh mã QR chuẩn Napas247 VietQR EMVCo trực tiếp bằng thư viện qrcode và app.escpos.generate_vietqr_emvco.
    3. Luôn trả về hình ảnh PNG chuẩn (b'\x89PNG...') cùng header CORS.
    """
    from ..escpos import generate_vietqr_emvco

    note = add_info
    if table_code and not add_info:
        clean_code = re.sub(r'[^a-zA-Z0-9]', '', table_code.replace("BAN ", "").replace("BÀN ", "")) or "01"
        note = f"TT PiPo Ban {clean_code}"
    
    # 1. Thử lấy ảnh VietQR template compact2 dạng PNG chuẩn từ VietQR API v2
    try:
        url = "https://api.vietqr.io/v2/generate"
        payload = json.dumps({
            "accountNo": "075624456",
            "accountName": "PIPO GARDEN",
            "acqId": "970422",
            "amount": int(amount or 0),
            "addInfo": note,
            "format": "text",
            "template": "compact2"
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (PiPo POS)"
            }
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            if resp.status == 200:
                res_data = json.loads(resp.read().decode("utf-8"))
                if res_data.get("code") == "00" and "data" in res_data:
                    qr_data_url = res_data["data"].get("qrDataURL", "")
                    if "," in qr_data_url:
                        b64_str = qr_data_url.split(",", 1)[1]
                    else:
                        b64_str = qr_data_url
                    raw_png = base64.b64decode(b64_str)
                    if raw_png.startswith(b"\x89PNG\r\n\x1a\n"):
                        return Response(
                            content=raw_png,
                            media_type="image/png",
                            headers={
                                "Access-Control-Allow-Origin": "*",
                                "Cache-Control": "public, max-age=3600"
                            }
                        )
    except Exception as e:
        logger.warning(f"VietQR API v2 warning: {e}")

    # 2. Fallback offline: Tự sinh mã QR chuẩn Napas247 VietQR EMVCo bằng qrcode
    try:
        import qrcode
        emvco_payload = generate_vietqr_emvco(
            bank_bin="970422",
            account_no="075624456",
            amount=int(amount or 0),
            message=note
        )
        qr = qrcode.QRCode(
            box_size=8,
            border=2,
            error_correction=qrcode.constants.ERROR_CORRECT_M
        )
        qr.add_data(emvco_payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=3600"
            }
        )
    except Exception as e:
        logger.error(f"Fallback VietQR error: {e}")
        raise HTTPException(status_code=500, detail=f"Không thể sinh mã VietQR: {e}")

@router.post("/table/{table_id}/checkout")
async def checkout_table(table_id: int, request: Request):
    user = require_api_auth(request, allowed_roles=["ADMIN", "CASHIER", "WAITER", "PICKLEBALL"])
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    try:
        discount_percent = float(payload.get("discount_percent") or 0)
    except (ValueError, TypeError):
        discount_percent = 0.0
    discount_amount = max(0, int(payload.get("discount_amount") or 0))
    discount_reason = (payload.get("discount_reason") or "").strip()
    service_fee = max(0, int(payload.get("service_fee") or 0))
    payment_method = (payload.get("payment_method") or "CASH").strip().upper()
    bill_target = (payload.get("bill_target") or "CUSTOMER").strip().upper()
    billed_admin_id = payload.get("billed_admin_id")
    billed_admin_name = (payload.get("billed_admin_name") or "").strip()

    if payment_method == "INTERNAL":
        bill_target = "ADMIN"
    elif payment_method in ("CASH", "TRANSFER", "VIETQR"):
        bill_target = "CUSTOMER"
        if payment_method == "VIETQR":
            payment_method = "TRANSFER"

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

    now_ts = now_vn_str("%Y-%m-%d %H:%M:%S")

    # 1. Đánh dấu đơn là PAID hoặc TẠO MỚI nếu bàn chỉ kê phí phục vụ / tiền sân không gọi món
    import uuid
    if not checkout_orders:
        # Nếu không có đơn hàng và không có phụ thu -> Giải phóng bàn, tuyệt đối không tạo đơn 0đ rác
        if service_fee <= 0 and discount_amount <= 0:
            cursor.execute("UPDATE tables SET status = 'AVAILABLE', current_session_id = NULL WHERE id = ?", (table_id,))
            cursor.execute("UPDATE table_sessions SET status = 'CLOSED', closed_at = ? WHERE table_id = ?", (now_ts, table_id))
            conn.commit()
            conn.close()

            if ws_broadcaster:
                try:
                    event_data = {
                        "event": "TABLE_CHECKED_OUT",
                        "table_id": table_id,
                        "table_code": table["table_code"],
                        "table_name": table["name"]
                    }
                    await ws_broadcaster.send_to_pos(event_data)
                    await ws_broadcaster.send_to_kds(event_data)
                except Exception as _ws_err:
                    logger.warning(f"[POS Checkout WS error]: {_ws_err}")

            return {
                "status": "SUCCESS",
                "message": f"Bàn {table['name']} đã được trả về trạng thái trống (không phát sinh hóa đơn).",
                "final_total": 0,
                "table_id": table_id,
                "receipt_text": None
            }

        session_id = table["current_session_id"]
        if not session_id:
            sess_token = f"sess_{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO table_sessions (table_id, session_token, guest_count, status, opened_at, closed_at)
                VALUES (?, ?, 1, 'CLOSED', ?, ?)
            """, (table_id, sess_token, now_ts, now_ts))
            session_id = cursor.lastrowid

        subtotal = 0
        total = max(0, subtotal - discount_amount + service_fee)
        new_uuid = f"ord_{uuid.uuid4().hex}"
        cursor.execute("""
            INSERT INTO orders (
                order_uuid, session_id, table_id, round_number, subtotal, discount, discount_reason,
                service_fee, total, status, payment_status, payment_method,
                bill_target, billed_admin_id, billed_admin_name, customer_note,
                created_at, completed_at
            ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, 'COMPLETED', 'PAID', ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_uuid, session_id, table_id, subtotal, discount_amount, discount_reason,
            service_fee, total, payment_method, bill_target, billed_admin_id, billed_admin_name,
            "Phiếu thu phí dịch vụ / phụ thu", now_ts, now_ts
        ))
        new_order_id = cursor.lastrowid
        checkout_orders = [{"id": new_order_id, "subtotal": subtotal, "total": total}]
    else:
        # Nếu có đơn hàng unpaid: Đơn đầu tiên nhận toàn bộ discount & service_fee của hóa đơn
        first_order = checkout_orders[0]
        first_total = max(0, first_order["subtotal"] - discount_amount + service_fee)
        first_uuid = first_order.get("order_uuid") or f"ord_{uuid.uuid4().hex}"
        cursor.execute("""
            UPDATE orders 
            SET payment_status = 'PAID', 
                status = 'COMPLETED',
                completed_at = ?,
                discount = ?,
                discount_reason = ?,
                service_fee = ?,
                payment_method = ?,
                bill_target = ?,
                billed_admin_id = ?,
                billed_admin_name = ?,
                total = ?,
                order_uuid = COALESCE(order_uuid, ?)
            WHERE id = ?
        """, (now_ts, discount_amount, discount_reason, service_fee, payment_method, bill_target, billed_admin_id, billed_admin_name, first_total, first_uuid, first_order["id"]))

        # Các đơn tiếp theo nếu có (round 2, 3...)
        for other_order in checkout_orders[1:]:
            cursor.execute("SELECT COALESCE(SUM(total_price), 0) as s FROM order_items WHERE order_id = ? AND status != 'CANCELLED'", (other_order["id"],))
            actual_sub = cursor.fetchone()["s"] or other_order.get("subtotal", 0)
            other_uuid = other_order.get("order_uuid") or f"ord_{uuid.uuid4().hex}"
            cursor.execute("""
                UPDATE orders 
                SET payment_status = 'PAID', 
                    status = 'COMPLETED',
                    completed_at = ?,
                    discount = 0,
                    discount_reason = '',
                    service_fee = 0,
                    payment_method = ?,
                    bill_target = ?,
                    billed_admin_id = ?,
                    billed_admin_name = ?,
                    subtotal = ?,
                    total = ?,
                    order_uuid = COALESCE(order_uuid, ?)
                WHERE id = ?
            """, (now_ts, payment_method, bill_target, billed_admin_id, billed_admin_name, actual_sub, actual_sub, other_uuid, other_order["id"]))

    # 2. Đánh dấu tất cả món của các đơn checkout là SERVED và tự động trừ kho NVL
    order_ids = [co["id"] for co in checkout_orders if co.get("id")]
    if order_ids:
        placeholders = ",".join("?" for _ in order_ids)
        cursor.execute(f"""
            UPDATE order_items 
            SET status = 'SERVED'
            WHERE order_id IN ({placeholders}) AND status NOT IN ('CANCELLED', 'SERVED')
        """, order_ids)

    try:
        from ..database import deduct_inventory_for_order_item
        for it in checkout_items:
            deduct_inventory_for_order_item(conn, it["id"])
    except Exception as _deduct_err:
        print("[POS Checkout] Loi tu dong tru kho:", _deduct_err)

    # 3. Đóng toàn bộ session của bàn
    cursor.execute("""
        UPDATE orders 
        SET payment_status = 'PAID', status = 'COMPLETED', completed_at = COALESCE(completed_at, ?)
        WHERE table_id = ? AND payment_status = 'UNPAID'
    """, (now_ts, table_id))
    cursor.execute("UPDATE table_sessions SET status = 'CLOSED', closed_at = ? WHERE table_id = ?", (now_ts, table_id))

    # 4. Đưa bàn về trạng thái AVAILABLE sẵn sàng cho khách mới
    cursor.execute("UPDATE tables SET status = 'AVAILABLE', current_session_id = NULL WHERE id = ?", (table_id,))

    conn.commit()
    conn.close()

    # Tự động in hóa đơn thanh toán xuống Máy in Thu ngân (80mm)
    print_success = False
    receipt_text = None
    receipt_b64 = None
    try:
        from ..escpos import format_receipt_ticket_text, build_escpos_receipt_bytes
        cashier_display = user.get("full_name") or "Thu Ngan PiPo"
        totals_info = {
            "title": "HOA DON THANH TOAN",
            "cashier_name": cashier_display,
            "discount": discount_amount,
            "discount_percent": int(discount_percent) if isinstance(discount_percent, float) and discount_percent.is_integer() else (discount_percent if discount_percent > 0 else None),
            "discount_reason": discount_reason,
            "service_fee": service_fee,
            "payment_method": payment_method,
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
        logger.error(f"[POS Checkout Receipt Print Error]: {ex}")

    if ws_broadcaster:
        try:
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
        except Exception as ws_err:
            logger.warning(f"[POS Checkout WS error]: {ws_err}")

    total_bill_amount = sum(it["total_price"] for it in checkout_items if it.get("status") != "CANCELLED")
    final_checkout_total = max(0, total_bill_amount - discount_amount + service_fee)

    target_msg = f" (Tính bill với Admin: {billed_admin_name})" if bill_target == "ADMIN" else ""
    return {
        "status": "SUCCESS",
        "message": f"Đã thanh toán và mở lại bàn {table['name']}{target_msg}",
        "receipt_text": receipt_text if 'receipt_text' in locals() else None,
        "receipt_b64": receipt_b64 if 'receipt_b64' in locals() else None,
        "final_total": final_checkout_total,
        "table_id": table_id
    }

@router.post("/table/{table_id}/release-court")
async def release_court(table_id: int, request: Request):
    """
    Dành riêng cho POS Sân Pickleball:
    Khi khách chơi xong và về hết, nhân viên bấm 'Báo Sân Trống'.
    Endpoint này đóng phiên, đưa sân về trạng thái AVAILABLE mà TUYỆT ĐỐI KHÔNG IN LẠI BILL.
    """
    user = require_api_auth(request, allowed_roles=["ADMIN", "CASHIER", "WAITER", "PICKLEBALL"])
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    table = cursor.fetchone()
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Sân không tồn tại")

    now_ts = now_vn_str("%Y-%m-%d %H:%M:%S")

    # 1. Chốt tất cả đơn còn lại nếu có sang PAID (CASH)
    cursor.execute("""
        UPDATE orders 
        SET payment_status = 'PAID', status = 'COMPLETED', completed_at = COALESCE(completed_at, ?)
        WHERE table_id = ? AND payment_status = 'UNPAID'
    """, (now_ts, table_id))

    cursor.execute("""
        UPDATE order_items 
        SET status = 'SERVED'
        WHERE order_id IN (SELECT id FROM orders WHERE table_id = ?) AND status != 'CANCELLED'
    """, (table_id,))

    # 2. Đóng toàn bộ session của sân
    if table["current_session_id"]:
        cursor.execute("UPDATE table_sessions SET status = 'CLOSED', closed_at = ? WHERE id = ?", (now_ts, table["current_session_id"]))
    cursor.execute("UPDATE table_sessions SET status = 'CLOSED', closed_at = ? WHERE table_id = ? AND (status = 'ACTIVE' OR status = 'OPEN')", (now_ts, table_id))

    # 3. Đưa sân về trạng thái AVAILABLE
    cursor.execute("UPDATE tables SET status = 'AVAILABLE', current_session_id = NULL WHERE id = ?", (table_id,))

    conn.commit()
    conn.close()

    # 4. Phát sự kiện WebSocket
    if ws_broadcaster:
        await ws_broadcaster.send_to_pos({
            "event": "TABLE_STATUS_CHANGED",
            "table_id": table_id,
            "status": "AVAILABLE"
        })

    return {
        "status": "SUCCESS",
        "message": f"Sân {table['name']} đã được giải phóng thành sân trống thành công.",
        "table_id": table_id
    }

@router.get("/bills/history")
async def get_bills_history(limit: int = 60, search: str = ""):
    """Lấy danh sách các hóa đơn đã thanh toán để thu ngân xem lại và in lại bill (gom toàn bộ món theo phiên bàn)."""
    conn = get_db()
    cursor = conn.cursor()

    # Lấy tất cả orders PAID cùng items của chúng bằng 1 JOIN query duy nhất (tránh N+1 queries)
    query = """
        SELECT o.id, o.session_id, o.table_id, o.round_number, o.subtotal, o.total,
               o.payment_status, o.payment_method, o.discount, o.discount_reason,
               o.service_fee, o.bill_target, o.billed_admin_name, o.created_at, o.completed_at,
               t.name as table_name, t.table_code, t.area,
               oi.item_name, oi.quantity, oi.unit_price, oi.total_price,
               oi.station, oi.note, oi.status as item_status
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        LEFT JOIN order_items oi ON oi.order_id = o.id
        WHERE o.payment_status = 'PAID'
    """
    params = []
    if search:
        clean_s = search.strip()
        query += """ AND (
            t.name LIKE ? OR t.table_code LIKE ? OR o.id LIKE ? OR o.billed_admin_name LIKE ?
            OR o.session_id IN (SELECT session_id FROM orders WHERE id = ? AND session_id IS NOT NULL)
        )"""
        s = f"%{clean_s}%"
        params.extend([s, s, s, s, clean_s])

    query += " ORDER BY COALESCE(o.completed_at, o.created_at) DESC, o.id DESC, oi.id ASC LIMIT ?"
    params.append(limit * 4 * 20)  # Giới hạn đủ rộng để cover items

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    from collections import OrderedDict
    grouped = OrderedDict()

    for r in rows:
        sess_id = r["session_id"]
        key = f"sess_{sess_id}" if sess_id else f"ord_{r['id']}"

        if key not in grouped:
            grouped[key] = {
                "id": r["id"],
                "session_id": sess_id,
                "table_id": r["table_id"],
                "table_name": r["table_name"],
                "table_code": r["table_code"],
                "area": r["area"],
                "subtotal": 0,
                "discount": 0,
                "discount_reason": r["discount_reason"] or "",
                "service_fee": 0,
                "total": 0,
                "payment_method": r["payment_method"] or "CASH",
                "bill_target": r["bill_target"],
                "billed_admin_name": r["billed_admin_name"],
                "paid_at": r["completed_at"] or r["created_at"],
                "raw_items": [],
                "order_ids": []
            }

        g = grouped[key]
        if r["id"] not in g["order_ids"]:
            g["order_ids"].append(r["id"])
            g["subtotal"] += (r["subtotal"] or 0)
            g["discount"] += (r["discount"] or 0)
            if r["discount_reason"] and not g["discount_reason"]:
                g["discount_reason"] = r["discount_reason"]
            g["service_fee"] += (r["service_fee"] or 0)
            g["total"] += (r["total"] or 0)

            cur_paid_at = r["completed_at"] or r["created_at"]
            if cur_paid_at and (not g["paid_at"] or cur_paid_at > g["paid_at"]):
                g["paid_at"] = cur_paid_at

        # Thêm item nếu có (LEFT JOIN trả None nếu order không có items)
        if r["item_name"] is not None:
            g["raw_items"].append({
                "item_name": r["item_name"],
                "quantity": r["quantity"],
                "unit_price": r["unit_price"],
                "total_price": r["total_price"],
                "station": r["station"],
                "note": r["note"],
                "status": r["item_status"]
            })

    bills = []
    for g in list(grouped.values())[:limit]:
        merged_items = OrderedDict()
        for it in g["raw_items"]:
            if it.get("status") == "CANCELLED":
                continue
            name = it.get("item_name", "Món")
            price = it.get("unit_price", 0)
            note = (it.get("note") or "").strip()
            item_k = (name, price, note)
            if item_k not in merged_items:
                merged_items[item_k] = {
                    "item_name": name,
                    "quantity": 0,
                    "unit_price": price,
                    "total_price": 0,
                    "station": it.get("station", ""),
                    "note": note,
                    "status": it.get("status", "SERVED")
                }
            merged_items[item_k]["quantity"] += (it.get("quantity") or 1)
            merged_items[item_k]["total_price"] += (it.get("total_price") or (price * (it.get("quantity") or 1)))

        g["items"] = list(merged_items.values())
        del g["raw_items"]
        bills.append(g)

    return {"status": "SUCCESS", "bills": bills, "count": len(bills)}

@router.post("/bills/{order_id}/reprint")
async def reprint_bill(order_id: int, request: Request):
    """In lại hóa đơn đã thanh toán xuống máy in thu ngân (in đầy đủ toàn bộ món trong phiên)."""
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

    session_id = order_row["session_id"]
    if session_id:
        cursor.execute("""
            SELECT o.id, o.subtotal, o.discount, o.discount_reason, o.service_fee, o.total,
                   o.payment_method, o.bill_target, o.billed_admin_name
            FROM orders o
            WHERE o.session_id = ? AND o.payment_status = 'PAID'
            ORDER BY o.round_number ASC
        """, (session_id,))
        sess_orders = cursor.fetchall()

        tot_discount = sum(so["discount"] or 0 for so in sess_orders)
        tot_fee = sum(so["service_fee"] or 0 for so in sess_orders)
        disc_reason = next((so["discount_reason"] for so in sess_orders if so["discount_reason"]), "")

        cursor.execute("""
            SELECT item_name, quantity, unit_price, total_price, station, note, status
            FROM order_items
            WHERE order_id IN (
                SELECT id FROM orders WHERE session_id = ? AND payment_status = 'PAID'
            ) AND status != 'CANCELLED'
            ORDER BY id ASC
        """, (session_id,))
        raw_items = [dict(it) for it in cursor.fetchall()]
    else:
        tot_discount = order_row["discount"] or 0
        tot_fee = order_row["service_fee"] or 0
        disc_reason = order_row["discount_reason"] or ""
        cursor.execute("""
            SELECT item_name, quantity, unit_price, total_price, station, note, status
            FROM order_items
            WHERE order_id = ? AND status != 'CANCELLED'
        """, (order_id,))
        raw_items = [dict(it) for it in cursor.fetchall()]
    conn.close()

    from collections import OrderedDict
    merged_items = OrderedDict()
    for it in raw_items:
        name = it.get("item_name", "Món")
        price = it.get("unit_price", 0)
        note = (it.get("note") or "").strip()
        item_k = (name, price, note)
        if item_k not in merged_items:
            merged_items[item_k] = {
                "item_name": name,
                "quantity": 0,
                "unit_price": price,
                "total_price": 0,
                "note": note
            }
        merged_items[item_k]["quantity"] += (it.get("quantity") or 1)
        merged_items[item_k]["total_price"] += (it.get("total_price") or (price * (it.get("quantity") or 1)))

    items = list(merged_items.values())

    table_dict = {
        "name": order_row["table_name"],
        "table_code": order_row["table_code"],
        "area": order_row["area"]
    }
    cashier_display = (user.get("full_name") if user else None) or "Thu Ngan PiPo"
    totals_info = {
        "title": "HOA DON BAN HANG (IN LAI)",
        "cashier_name": cashier_display,
        "discount": tot_discount,
        "discount_reason": disc_reason,
        "service_fee": tot_fee,
        "payment_method": order_row["payment_method"] or "CASH",
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

class BillEditItem(BaseModel):
    id: Optional[int] = None
    item_id: Optional[int] = None
    item_name: str
    quantity: int
    unit_price: int
    total_price: Optional[int] = None
    station: Optional[str] = "HOT_KITCHEN"
    note: Optional[str] = ""

class EditBillRequest(BaseModel):
    items: List[BillEditItem]
    discount: int = 0
    discount_reason: Optional[str] = ""
    service_fee: int = 0
    payment_method: str = "CASH"
    bill_target: Optional[str] = "CUSTOMER"
    billed_admin_id: Optional[int] = None
    billed_admin_name: Optional[str] = ""
    edit_reason: Optional[str] = "Khách báo nhầm"

@router.get("/bills/{order_id}")
def get_bill_detail(order_id: int):
    """Lấy chi tiết đầy đủ của 1 hóa đơn bao gồm toàn bộ các món trong phiên để sửa hoặc xem."""
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
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn.")
    
    order_dict = dict(order_row)
    session_id = order_dict.get("session_id")
    if session_id:
        cursor.execute("""
            SELECT id, subtotal, discount, discount_reason, service_fee, total
            FROM orders 
            WHERE session_id = ? AND payment_status = 'PAID'
            ORDER BY id ASC
        """, (session_id,))
        sess_rows = [dict(r) for r in cursor.fetchall()]
        order_ids = [r["id"] for r in sess_rows]
        if order_id not in order_ids:
            order_ids.append(order_id)
            
        tot_discount = sum(r.get("discount") or 0 for r in sess_rows)
        tot_service_fee = sum(r.get("service_fee") or 0 for r in sess_rows)
        disc_reason = next((r.get("discount_reason") for r in sess_rows if r.get("discount_reason")), order_dict.get("discount_reason") or "")
    else:
        order_ids = [order_id]
        tot_discount = order_dict.get("discount") or 0
        tot_service_fee = order_dict.get("service_fee") or 0
        disc_reason = order_dict.get("discount_reason") or ""
        
    placeholders = ",".join("?" for _ in order_ids)
    cursor.execute(f"""
        SELECT oi.*, m.category_id
        FROM order_items oi
        LEFT JOIN menu_items m ON oi.item_id = m.id
        WHERE oi.order_id IN ({placeholders}) AND oi.status != 'CANCELLED'
        ORDER BY oi.id ASC
    """, order_ids)
    raw_items = [dict(it) for it in cursor.fetchall()]
    conn.close()
    
    # Nhóm các món cùng tên, cùng đơn giá, cùng ghi chú
    from collections import OrderedDict
    merged_items = OrderedDict()
    for it in raw_items:
        name = it.get("item_name") or "Món"
        price = it.get("unit_price") or 0
        note = (it.get("note") or "").strip()
        k = (name, price, note)
        if k not in merged_items:
            merged_items[k] = {
                "id": it.get("id"),
                "order_id": it.get("order_id"),
                "item_id": it.get("item_id"),
                "item_name": name,
                "quantity": 0,
                "unit_price": price,
                "total_price": 0,
                "station": it.get("station") or "HOT_KITCHEN",
                "note": note,
                "category_id": it.get("category_id")
            }
        merged_items[k]["quantity"] += (it.get("quantity") or 1)
        merged_items[k]["total_price"] += ((it.get("quantity") or 1) * price)

    final_items = list(merged_items.values())
    calc_subtotal = sum(it["total_price"] for it in final_items)
    calc_total = max(0, calc_subtotal - tot_discount + tot_service_fee)
    
    return {
        "status": "SUCCESS",
        "bill": {
            **order_dict,
            "subtotal": calc_subtotal,
            "discount": tot_discount,
            "discount_reason": disc_reason,
            "service_fee": tot_service_fee,
            "total": calc_total,
            "order_ids": order_ids,
            "items": final_items
        }
    }

@router.put("/bills/{order_id}")
async def edit_paid_bill(order_id: int, req: EditBillRequest, request: Request):
    """
    Cho phép Admin chỉnh sửa hóa đơn đã thanh toán:
    - Sửa số lượng món, xóa món tính nhầm, thêm món mới
    - Sửa giảm giá, phí dịch vụ, hình thức thanh toán
    - Tự động hoàn/trừ kho nguyên vật liệu tương ứng
    - Cập nhật lại tổng tiền đơn hàng và doanh thu / báo cáo tức thì
    """
    user = get_current_user_from_request(request)
    admin_name = (user.get("full_name") if user else None) or "Quản trị viên"
    
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
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn cần sửa.")
        
    order = dict(order_row)
    session_id = order.get("session_id")
    if session_id:
        cursor.execute("SELECT id FROM orders WHERE session_id = ? AND payment_status = 'PAID'", (session_id,))
        order_ids = [r[0] for r in cursor.fetchall()]
        if order_id not in order_ids:
            order_ids.append(order_id)
    else:
        order_ids = [order_id]
        
    main_order_id = order_id
    
    placeholders = ",".join("?" for _ in order_ids)
    cursor.execute(f"""
        SELECT * FROM order_items
        WHERE order_id IN ({placeholders}) AND status != 'CANCELLED'
    """, order_ids)
    existing_items = {r["id"]: dict(r) for r in cursor.fetchall()}
    
    payload_item_ids = set()
    new_subtotal = 0
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for it in req.items:
        qty = max(0, int(it.quantity))
        u_price = max(0, int(it.unit_price))
        tot_price = qty * u_price
        
        if it.id and it.id in existing_items:
            payload_item_ids.add(it.id)
            old_item = existing_items[it.id]
            old_qty = old_item["quantity"]
            
            if qty == 0:
                cursor.execute("""
                    UPDATE order_items
                    SET status = 'CANCELLED',
                        cancelled_by = ?,
                        cancel_reason = ?,
                        cancelled_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (f"{admin_name} (Sửa bill)", req.edit_reason or "Admin xóa khỏi bill", now_ts, now_ts, it.id))
                
                if old_item.get("inventory_deducted") == 1:
                    try:
                        restore_inventory_for_order_item(conn, it.id, reason=f"Sửa bill #{main_order_id}: hủy {old_item['item_name']}")
                    except Exception as _e:
                        logger.warning(f"[Inventory Restore Error]: {_e}")
            else:
                cursor.execute("""
                    UPDATE order_items
                    SET quantity = ?, unit_price = ?, total_price = ?, note = ?, updated_at = ?
                    WHERE id = ?
                """, (qty, u_price, tot_price, it.note or "", now_ts, it.id))
                new_subtotal += tot_price
                
                if old_item.get("inventory_deducted") == 1 and old_item.get("item_id"):
                    delta = qty - old_qty
                    if delta != 0:
                        try:
                            recipes = get_dynamic_bom_for_item(cursor, old_item["item_id"], old_item["modifiers_json"], old_item["item_name"])
                            for r in recipes:
                                ing_delta = r["bom_qty"] * delta
                                cursor.execute("UPDATE inventory_items SET stock_quantity = stock_quantity - ? WHERE id = ?", (ing_delta, r["ingredient_id"]))
                                cursor.execute("""
                                    INSERT INTO inventory_transactions 
                                    (ingredient_id, transaction_type, quantity, unit_price, reference_id, note, created_by)
                                    VALUES (?, 'ORDER_DEDUCT', ?, ?, ?, ?, ?)
                                """, (
                                    r["ingredient_id"],
                                    -ing_delta,
                                    r["cost_price"],
                                    main_order_id,
                                    f"Sửa bill #{main_order_id}: {old_item['item_name']} (SL {old_qty} -> {qty})",
                                    admin_name
                                ))
                        except Exception as _ie:
                            logger.warning(f"[Inventory Delta Error]: {_ie}")
        elif qty > 0:
            station = it.station or "HOT_KITCHEN"
            item_name = it.item_name.strip()
            item_id_val = it.item_id
            cursor.execute("""
                INSERT INTO order_items 
                (order_id, item_id, item_name, quantity, unit_price, total_price, station, note, status, created_at, updated_at, inventory_deducted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'SERVED', ?, ?, 0)
            """, (main_order_id, item_id_val, item_name, qty, u_price, tot_price, station, it.note or "", now_ts, now_ts))
            new_item_id = cursor.lastrowid
            new_subtotal += tot_price
            
            try:
                deduct_inventory_for_order_item(conn, new_item_id)
            except Exception as _de:
                logger.warning(f"[Inventory Deduct Error]: {_de}")
                
    for old_id, old_it in existing_items.items():
        if old_id not in payload_item_ids:
            cursor.execute("""
                UPDATE order_items
                SET status = 'CANCELLED',
                    cancelled_by = ?,
                    cancel_reason = ?,
                    cancelled_at = ?,
                    updated_at = ?
                WHERE id = ?
            """, (f"{admin_name} (Sửa bill)", req.edit_reason or "Admin xóa khỏi bill", now_ts, now_ts, old_id))
            if old_it.get("inventory_deducted") == 1:
                try:
                    restore_inventory_for_order_item(conn, old_id, reason=f"Sửa bill #{main_order_id}: hủy {old_it['item_name']}")
                except Exception as _re:
                    logger.warning(f"[Inventory Restore Error]: {_re}")
                    
    discount_amt = max(0, int(req.discount))
    service_fee_amt = max(0, int(req.service_fee))
    new_grand_total = max(0, new_subtotal - discount_amt + service_fee_amt)
    
    p_method = (req.payment_method or "CASH").strip().upper()
    if p_method == "VIETQR":
        p_method = "TRANSFER"
    b_target = (req.bill_target or "CUSTOMER").strip().upper()
    b_admin_id = req.billed_admin_id
    b_admin_name = (req.billed_admin_name or "").strip()
    if p_method == "INTERNAL":
        b_target = "ADMIN"
    else:
        b_target = "CUSTOMER"
        b_admin_id = None
        b_admin_name = ""
        
    edit_note_entry = f" [Sửa bill: {req.edit_reason or 'Khách báo nhầm'} - {admin_name} lúc {now_ts}]"
    existing_note = order.get("customer_note") or ""
    new_note = existing_note + edit_note_entry
    
    cursor.execute("""
        UPDATE orders
        SET subtotal = ?,
            discount = ?,
            discount_reason = ?,
            service_fee = ?,
            total = ?,
            payment_method = ?,
            bill_target = ?,
            billed_admin_id = ?,
            billed_admin_name = ?,
            customer_note = ?
        WHERE id = ?
    """, (new_subtotal, discount_amt, req.discount_reason or "", service_fee_amt, new_grand_total,
          p_method, b_target, b_admin_id, b_admin_name, new_note, main_order_id))
          
    for other_oid in order_ids:
        if other_oid != main_order_id:
            cursor.execute("""
                UPDATE orders
                SET subtotal = 0,
                    discount = 0,
                    service_fee = 0,
                    total = 0,
                    payment_method = ?,
                    bill_target = ?,
                    billed_admin_id = ?,
                    billed_admin_name = ?
                WHERE id = ?
            """, (p_method, b_target, b_admin_id, b_admin_name, other_oid))
            
    conn.commit()
    conn.close()
    
    if ws_broadcaster:
        try:
            await ws_broadcaster.send_to_pos({"event": "BILL_UPDATED", "bill_id": main_order_id, "total": new_grand_total})
            await ws_broadcaster.send_to_pos({"event": "ORDERS_REFRESH"})
        except Exception as _wse:
            logger.warning(f"[WS Error]: {_wse}")
            
    return {
        "status": "SUCCESS",
        "message": f"Đã cập nhật hóa đơn #HD-{main_order_id} thành công! Doanh thu mới: {new_grand_total:,} đ",
        "bill_id": main_order_id,
        "subtotal": new_subtotal,
        "discount": discount_amt,
        "service_fee": service_fee_amt,
        "total": new_grand_total,
        "payment_method": p_method
    }


class UpdateBillPaymentMethodRequest(BaseModel):
    payment_method: str  # "CASH", "TRANSFER", "INTERNAL"
    bill_target: Optional[str] = "CUSTOMER"  # "CUSTOMER" or "ADMIN"
    billed_admin_id: Optional[int] = None
    billed_admin_name: Optional[str] = None
    order_ids: Optional[List[int]] = None
    session_id: Optional[int] = None

@router.post("/bills/{order_id}/update-payment-method")
async def update_bill_payment_method(order_id: int, req: UpdateBillPaymentMethodRequest, request: Request):
    """Cập nhật lại hình thức thanh toán (Tiền mặt, Chuyển khoản, Tính Admin) cho hóa đơn đã thanh toán."""
    user = get_current_user_from_request(request)
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, session_id, table_id, payment_status, total FROM orders WHERE id = ?", (order_id,))
    order_row = cursor.fetchone()
    if not order_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn cần cập nhật.")

    raw_method = (req.payment_method or "CASH").upper().strip()
    target = (req.bill_target or "CUSTOMER").upper().strip()
    admin_id = req.billed_admin_id
    admin_name = (req.billed_admin_name or "").strip()

    if raw_method in ("INTERNAL", "ADMIN") or target == "ADMIN":
        method = "INTERNAL"
        target = "ADMIN"
        if not admin_name and admin_id:
            cursor.execute("SELECT full_name FROM users WHERE id = ?", (admin_id,))
            u = cursor.fetchone()
            if u:
                admin_name = u["full_name"]
    elif raw_method in ("TRANSFER", "VIETQR"):
        method = "TRANSFER"
        target = "CUSTOMER"
        admin_id = None
        admin_name = ""
    else:
        method = "CASH"
        target = "CUSTOMER"
        admin_id = None
        admin_name = ""

    # Xác định danh sách order ids cần cập nhật (phiên bàn hoặc danh sách gửi lên)
    session_id = req.session_id or order_row["session_id"]
    if req.order_ids and len(req.order_ids) > 0:
        placeholders = ",".join("?" for _ in req.order_ids)
        cursor.execute(f"""
            UPDATE orders
            SET payment_method = ?, bill_target = ?, billed_admin_id = ?, billed_admin_name = ?
            WHERE id IN ({placeholders})
        """, (method, target, admin_id, admin_name, *req.order_ids))
    elif session_id:
        cursor.execute("""
            UPDATE orders
            SET payment_method = ?, bill_target = ?, billed_admin_id = ?, billed_admin_name = ?
            WHERE session_id = ?
        """, (method, target, admin_id, admin_name, session_id))
    else:
        cursor.execute("""
            UPDATE orders
            SET payment_method = ?, bill_target = ?, billed_admin_id = ?, billed_admin_name = ?
            WHERE id = ?
        """, (method, target, admin_id, admin_name, order_id))

    conn.commit()
    conn.close()

    # Phát sự kiện WebSocket thông báo đồng bộ realtime đến toàn bộ máy thu ngân & admin
    if ws_broadcaster:
        try:
            event_data = {
                "event": "BILL_PAYMENT_METHOD_UPDATED",
                "order_id": order_id,
                "session_id": session_id,
                "payment_method": method,
                "bill_target": target,
                "billed_admin_name": admin_name
            }
            await ws_broadcaster.send_to_pos(event_data)
        except Exception as _ws_e:
            logger.warning(f"[WS error BILL_PAYMENT_METHOD_UPDATED]: {_ws_e}")

    return {
        "status": "SUCCESS",
        "message": f"Đã cập nhật hình thức thanh toán hóa đơn #{order_id} thành công!",
        "order_id": order_id,
        "payment_method": method,
        "bill_target": target,
        "billed_admin_name": admin_name
    }
