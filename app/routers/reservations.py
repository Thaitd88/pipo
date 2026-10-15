# Reservations & Pre-order router for PiPo Garden website
import json
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from ..database import get_db

router = APIRouter(prefix="/api/reservations", tags=["Reservations"])

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
def create_reservation(data: ReservationCreate):
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
        data.preorder_items_json or "[]",
        max(0, data.total_estimated or 0),
        (data.note or "").strip()
    ))
    res_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM reservations WHERE id = ?", (res_id,))
    created = dict(cursor.fetchone())
    conn.close()

    # Kiểm tra xem có món gọi trước không để thông báo
    has_preorder = False
    try:
        items = json.loads(created.get("preorder_items_json") or "[]")
        has_preorder = len(items) > 0
    except Exception:
        pass

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
def assign_table_to_reservation(res_id: int, req: AssignTableRequest):
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

            # 3. Thêm các món vào order_items
            for item in preorder_items:
                qty = item.get("quantity", 1)
                price = item.get("price", 0)
                item_id = item.get("id") or 0
                item_name = item.get("name") or "Món đặt trước"
                station = item.get("station") or "HOT_KITCHEN"
                cursor.execute("""
                    INSERT INTO order_items (order_id, item_id, item_name, quantity, unit_price, total_price, station, note, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'QUEUED')
                """, (created_order_id, item_id, item_name, qty, price, qty * price, station, item.get("note", "")))

    conn.commit()

    cursor.execute("SELECT * FROM reservations WHERE id = ?", (res_id,))
    updated_res = dict(cursor.fetchone())
    conn.close()

    return {
        "status": "SUCCESS",
        "message": f"Đã phân thành công Bàn {table_code} cho khách {res_dict['guest_name']}!",
        "reservation": updated_res,
        "table": table_dict,
        "order_id": created_order_id
    }

@router.put("/{res_id}/status")
def update_reservation_status(res_id: int, req: ReservationUpdateStatus):
    """Cập nhật trạng thái duyệt đặt bàn (PENDING, CONFIRMED, CANCELLED, SEATED)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE reservations SET status = ? WHERE id = ?", (req.status.upper(), res_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu đặt bàn.")
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": f"Đã cập nhật trạng thái sang {req.status.upper()}."}

@router.delete("/{res_id}")
def delete_reservation(res_id: int):
    """Xóa yêu cầu đặt bàn khỏi hệ thống."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reservations WHERE id = ?", (res_id,))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu đặt bàn.")
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "Đã xóa yêu cầu đặt bàn."}
