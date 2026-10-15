# Reservations router for PiPo Garden website
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
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
    note: Optional[str] = ""

class ReservationUpdateStatus(BaseModel):
    status: str # PENDING, CONFIRMED, CANCELLED

@router.post("")
def create_reservation(data: ReservationCreate):
    """Đặt bàn / Đặt sân trực tuyến từ trang chủ."""
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
    cursor.execute("""
        INSERT INTO reservations (guest_name, phone, booking_date, booking_time, guest_count, service_type, note, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')
    """, (name, phone, date_val, time_val, max(1, data.guest_count or 1), data.service_type or "DINING", (data.note or "").strip()))
    res_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM reservations WHERE id = ?", (res_id,))
    created = dict(cursor.fetchone())
    conn.close()

    return {
        "status": "SUCCESS",
        "message": f"Đặt bàn thành công! PiPo Garden sẽ liên hệ xác nhận qua số {phone}.",
        "reservation": created
    }

@router.get("")
def list_reservations(limit: int = 50):
    """Danh sách yêu cầu đặt bàn (dành cho quản lý)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reservations ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@router.put("/{res_id}/status")
def update_reservation_status(res_id: int, req: ReservationUpdateStatus):
    """Cập nhật trạng thái duyệt đặt bàn (CONFIRMED / CANCELLED)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE reservations SET status = ? WHERE id = ?", (req.status.upper(), res_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu đặt bàn.")
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "Đã cập nhật trạng thái đặt bàn."}
