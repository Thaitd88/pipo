# Reservations & Pre-order router for PiPo Garden website
import json
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from ..database import get_db

router = APIRouter(prefix="/api/reservations", tags=["Reservations"])

ws_broadcaster = None

def set_broadcaster(broadcaster):
    global ws_broadcaster
    ws_broadcaster = broadcaster

class ReservationCreate(BaseModel):
    guest_name: str
    phone: str
    booking_date: str
    booking_time: str
    guest_count: Optional[int] = 2
    service_type: Optional[str] = "DINING"
    table_code: Optional[str] = ""
    area: Optional[str] = ""
    preorder_items_json: Optional[str] = "[]"
    total_estimated: Optional[int] = 0
    note: Optional[str] = ""

class ReservationUpdateStatus(BaseModel):
    status: str # PENDING, CONFIRMED, CANCELLED, SEATED

class AssignTableRequest(BaseModel):
    table_code: Optional[str] = None
    table_id: Optional[int] = None
    activate_order: Optional[bool] = True
    assigned_by: Optional[str] = "Quản lý / Thu ngân"

@router.post("")
async def create_reservation(data: ReservationCreate):
    """Đặt bàn / Đặt sân trực tuyến & Đơn gọi món trước từ website."""
    name = data.guest_name.strip()
    phone = data.phone.strip()
    date_val = data.booking_date.strip()
    time_val = data.booking_time.strip()

    if not name or not phone:
        raise HTTPException(status_code=400, detail="Vui lòng nhập họ tên và số điện thoại liên hệ.")
    if not date_val or not time_val:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ngày và giờ dự kiến đến.")

    conn = get_db()
    cursor = conn.cursor()

    # Tìm table_id nếu có table_code
    table_id = None
    area_val = (data.area or "").strip()
    table_code_val = (data.table_code or "").strip().upper()
    if table_code_val:
        cursor.execute("SELECT id, area FROM tables WHERE UPPER(table_code) = ?", (table_code_val,))
        t_row = cursor.fetchone()
        if t_row:
            table_id = t_row["id"]
            if not area_val:
                area_val = t_row["area"]

    # Phân tích & làm giàu dữ liệu món gọi trước (đảm bảo luôn có tên món, id, giá, trạm bếp)
    enriched_items = []
    try:
        raw_items = json.loads(data.preorder_items_json or "[]")
        if isinstance(raw_items, list):
            for it in raw_items:
                raw_obj = it.get("raw_item") if isinstance(it.get("raw_item"), dict) else {}
                iid = it.get("item_id") or it.get("id") or raw_obj.get("id") or 0
                iname = it.get("name") or it.get("item_name") or raw_obj.get("name")
                iprice = it.get("price") if it.get("price") is not None else raw_obj.get("price", 0)
                iqty = it.get("quantity") or 1
                istation = it.get("station") or raw_obj.get("station") or "HOT_KITCHEN"
                inote = it.get("note") or ""

                if (not iname or not iprice) and iid:
                    cursor.execute("SELECT name, price, station FROM menu_items WHERE id = ?", (iid,))
                    d_row = cursor.fetchone()
                    if d_row:
                        if not iname:
                            iname = d_row["name"]
                        if not iprice:
                            iprice = d_row["price"]
                        if not istation or istation == "HOT_KITCHEN":
                            istation = d_row["station"]

                enriched_items.append({
                    "id": iid,
                    "item_id": iid,
                    "name": iname or f"Món #{iid or '?'}",
                    "price": int(iprice or 0),
                    "quantity": int(iqty or 1),
                    "station": istation or "HOT_KITCHEN",
                    "note": inote
                })
    except Exception as e:
        print(f"[Reservations] Error parsing preorder_items_json: {e}")
        enriched_items = []

    final_preorder_json = json.dumps(enriched_items, ensure_ascii=False)
    calculated_total = sum(it["price"] * it["quantity"] for it in enriched_items)
    final_total = max(data.total_estimated or 0, calculated_total)

    cursor.execute("""
        INSERT INTO reservations (
            guest_name, phone, booking_date, booking_time, guest_count, 
            service_type, table_id, table_code, area, preorder_items_json, 
            total_estimated, note, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
    """, (
        name, 
        phone, 
        date_val, 
        time_val, 
        max(1, data.guest_count or 1), 
        data.service_type or "DINING",
        table_id,
        table_code_val or None,
        area_val or None,
        final_preorder_json,
        final_total,
        (data.note or "").strip()
    ))
    res_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM reservations WHERE id = ?", (res_id,))
    created = dict(cursor.fetchone())
    conn.close()

    # Bắn WebSocket cập nhật tức thời tới POS & Admin
    if ws_broadcaster:
        try:
            await ws_broadcaster.send_to_pos({
                "event": "NEW_RESERVATION",
                "reservation": created
            })
        except Exception as e:
            print(f"[WebSocket] Error broadcasting NEW_RESERVATION: {e}")

    has_preorder = len(enriched_items) > 0
    msg = f"Đặt bàn thành công! PiPo Garden sẽ liên hệ xác nhận qua số {phone}."
    if has_preorder:
        msg = f"Đơn gọi món trước & đặt bàn thành công! Thu ngân/Quản lý PiPo Garden sẽ liên hệ xác nhận và phân bàn chu đáo cho quý khách."

    return {
        "status": "SUCCESS",
        "message": msg,
        "reservation": created
    }

@router.get("")
def list_reservations(limit: int = 100, status: Optional[str] = None):
    """Danh sách yêu cầu đặt bàn và đơn gọi món trước (dành cho quản lý và thu ngân)."""
    conn = get_db()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM reservations WHERE status = ? ORDER BY id DESC LIMIT ?", (status.upper(), limit))
    else:
        cursor.execute("SELECT * FROM reservations ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@router.get("/{res_id}")
def get_reservation(res_id: int):
    """Chi tiết một yêu cầu đặt bàn."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reservations WHERE id = ?", (res_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu đặt bàn.")
    return dict(row)

@router.post("/{res_id}/assign-table")
@router.put("/{res_id}/assign-table")
async def assign_table_to_reservation(res_id: int, req: AssignTableRequest):
    """Thu ngân hoặc Quản trị phân bàn chính thức cho khách đã đặt bàn/gọi món trước."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM reservations WHERE id = ?", (res_id,))
    res = cursor.fetchone()
    if not res:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin đặt bàn.")

    res_dict = dict(res)

    # Tìm bàn chỉ định
    target_table = None
    if req.table_id:
        cursor.execute("SELECT * FROM tables WHERE id = ?", (req.table_id,))
        target_table = cursor.fetchone()
    elif req.table_code:
        cursor.execute("SELECT * FROM tables WHERE UPPER(table_code) = UPPER(?)", (req.table_code.strip(),))
        target_table = cursor.fetchone()
    elif res_dict.get("table_code"):
        cursor.execute("SELECT * FROM tables WHERE UPPER(table_code) = UPPER(?)", (res_dict["table_code"].strip(),))
        target_table = cursor.fetchone()

    if not target_table:
        # Nếu chưa có bàn nào khớp, lấy bàn nhà hàng khả dụng đầu tiên
        cursor.execute("SELECT * FROM tables WHERE status = 'AVAILABLE' ORDER BY id ASC LIMIT 1")
        target_table = cursor.fetchone()

    if not target_table:
        conn.close()
        raise HTTPException(status_code=400, detail="Không tìm thấy bàn phù hợp để phân bàn. Vui lòng kiểm tra lại sơ đồ bàn.")

    table_dict = dict(target_table)
    table_id = table_dict["id"]
    table_code = table_dict["table_code"]
    area_name = table_dict["area"]

    # Cập nhật thông tin đặt bàn
    cursor.execute("""
        UPDATE reservations 
        SET table_id = ?, table_code = ?, area = ?, status = 'CONFIRMED', 
            assigned_at = CURRENT_TIMESTAMP, assigned_by = ?
        WHERE id = ?
    """, (table_id, table_code, area_name, req.assigned_by or "Thu ngân", res_id))

    # Nếu có danh sách món gọi trước và có yêu cầu kích hoạt đơn:
    # Mở phiên bàn active và tạo đơn hàng sẵn sàng cho bếp
    created_order_id = None
    if req.activate_order:
        preorder_items = []
        try:
            preorder_items = json.loads(res_dict.get("preorder_items_json") or "[]")
        except Exception:
            preorder_items = []

        if preorder_items:
            # 1. Tìm hoặc tạo phiên bàn (table_session)
            cursor.execute("SELECT * FROM table_sessions WHERE table_id = ? AND status = 'ACTIVE'", (table_id,))
            session = cursor.fetchone()
            if not session:
                sess_token = f"sess_{uuid.uuid4().hex[:12]}"
                guest_count = res_dict.get("guest_count") or 2
                cursor.execute("""
                    INSERT INTO table_sessions (table_id, session_token, guest_count, status)
                    VALUES (?, ?, ?, 'ACTIVE')
                """, (table_id, sess_token, guest_count))
                session_id = cursor.lastrowid
                cursor.execute("UPDATE tables SET status = 'OCCUPIED', current_session_id = ? WHERE id = ?", (session_id, table_id))
            else:
                session_id = session["id"]

            # 2. Tạo đơn hàng từ các món đã gọi trước
            subtotal = 0
            for item in preorder_items:
                qty = item.get("quantity", 1)
                price = item.get("price", 0)
                subtotal += qty * price

            cursor.execute("""
                INSERT INTO orders (session_id, table_id, round_number, subtotal, discount, total, status, payment_status, customer_note)
                VALUES (?, ?, 1, ?, 0, ?, 'CONFIRMED', 'UNPAID', ?)
            """, (session_id, table_id, subtotal, subtotal, f"Đơn đặt bàn trước của khách {res_dict['guest_name']} ({res_dict['phone']}) - Giờ đến: {res_dict['booking_time']}"))
            created_order_id = cursor.lastrowid

            # 3. Thêm các món vào order_items (đảm bảo tên món chính xác)
            for item in preorder_items:
                qty = item.get("quantity", 1)
                price = item.get("price", 0)
                raw_obj = item.get("raw_item") if isinstance(item.get("raw_item"), dict) else {}
                item_id = item.get("item_id") or item.get("id") or raw_obj.get("id") or 0
                item_name = item.get("name") or item.get("item_name") or raw_obj.get("name")
                station = item.get("station") or raw_obj.get("station") or "HOT_KITCHEN"

                if (not item_name or not station) and item_id:
                    cursor.execute("SELECT name, station FROM menu_items WHERE id = ?", (item_id,))
                    d_row = cursor.fetchone()
                    if d_row:
                        if not item_name:
                            item_name = d_row["name"]
                        if not station:
                            station = d_row["station"]

                item_name = item_name or "Món đặt trước"
                station = station or "HOT_KITCHEN"
                cursor.execute("""
                    INSERT INTO order_items (order_id, item_id, item_name, quantity, unit_price, total_price, station, note, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'QUEUED')
                """, (created_order_id, item_id, item_name, qty, price, qty * price, station, item.get("note", "")))

    conn.commit()

    cursor.execute("SELECT * FROM reservations WHERE id = ?", (res_id,))
    updated_res = dict(cursor.fetchone())
    conn.close()

    # Bắn WebSocket cập nhật thời gian thực
    if ws_broadcaster:
        try:
            await ws_broadcaster.send_to_pos({
                "event": "RESERVATION_UPDATED",
                "reservation": updated_res
            })
            if created_order_id:
                await ws_broadcaster.send_to_kds({
                    "event": "NEW_ORDER",
                    "order_id": created_order_id,
                    "table_code": table_code,
                    "table_name": f"Bàn {table_code}"
                })
                await ws_broadcaster.send_to_pos({
                    "event": "NEW_ORDER",
                    "order_id": created_order_id,
                    "table_code": table_code
                })
        except Exception as e:
            print(f"[WebSocket] Error broadcasting assignment: {e}")

    return {
        "status": "SUCCESS",
        "message": f"Đã phân thành công Bàn {table_code} cho khách {res_dict['guest_name']}!",
        "reservation": updated_res,
        "table": table_dict,
        "order_id": created_order_id
    }

@router.put("/{res_id}/status")
async def update_reservation_status(res_id: int, req: ReservationUpdateStatus):
    """Cập nhật trạng thái duyệt đặt bàn (PENDING, CONFIRMED, CANCELLED, SEATED)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE reservations SET status = ? WHERE id = ?", (req.status.upper(), res_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu đặt bàn.")
    conn.commit()
    cursor.execute("SELECT * FROM reservations WHERE id = ?", (res_id,))
    row = cursor.fetchone()
    updated_res = dict(row) if row else None
    conn.close()

    if ws_broadcaster:
        try:
            await ws_broadcaster.send_to_pos({
                "event": "RESERVATION_UPDATED",
                "res_id": res_id,
                "status": req.status.upper(),
                "reservation": updated_res
            })
        except Exception:
            pass

    return {"status": "SUCCESS", "message": f"Đã cập nhật trạng thái sang {req.status.upper()}."}

@router.delete("/{res_id}")
async def delete_reservation(res_id: int):
    """Xóa yêu cầu đặt bàn khỏi hệ thống."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reservations WHERE id = ?", (res_id,))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu đặt bàn.")
    conn.commit()
    conn.close()

    if ws_broadcaster:
        try:
            await ws_broadcaster.send_to_pos({
                "event": "RESERVATION_DELETED",
                "res_id": res_id
            })
        except Exception:
            pass

    return {"status": "SUCCESS", "message": "Đã xóa yêu cầu đặt bàn."}
