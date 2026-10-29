import base64
# Router for Pickleball Court Booking System at PiPo Garden
import json
import random
import re
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Request
from .auth import require_api_auth
from pydantic import BaseModel, Field
from ..database import get_db

router = APIRouter(prefix="/api/pickleball", tags=["Pickleball Booking"])

ws_broadcaster = None

def set_broadcaster(broadcaster):
    global ws_broadcaster
    ws_broadcaster = broadcaster

# Danh sách 4 sân có mái che tiêu chuẩn resort
COURTS_CONFIG = [
    {
        "id": 1,
        "name": "Sân 1 (Center Court)",
        "badge": "Sân Trung Tâm VIP",
        "description": "Sân chính khán đài, đèn LED cao áp chuẩn quốc tế, mái che thoáng mát.",
        "icon": "🏆"
    },
    {
        "id": 2,
        "name": "Sân 2 (Covered Court)",
        "badge": "Mái Che Thoáng Mát",
        "description": "Mặt sân cao su acrylic giảm chấn cao cấp, không gian rộng rãi.",
        "icon": "⚡"
    },
    {
        "id": 3,
        "name": "Sân 3 (Covered Court)",
        "badge": "Mái Che Thoáng Mát",
        "description": "Sát cạnh lối đi sân vườn nhiệt đới, gió tự nhiên đối lưu cực thoáng.",
        "icon": "🎾"
    },
    {
        "id": 4,
        "name": "Sân 4 (Poolside View)",
        "badge": "Gần Hồ Bơi & Pool Bar",
        "description": "Liền kề hồ bơi trung tâm, thuận tiện thư giãn và thưởng thức cocktail sau trận.",
        "icon": "🏊"
    }
]

# 16 khung giờ hoạt động (06:00 đến 22:00)
BASE_TIME_SLOTS = [
    {"slot": "06:00 - 07:00", "start_hour": 6,  "end_hour": 7,  "price": 150000, "is_peak": False, "period": "Sáng"},
    {"slot": "07:00 - 08:00", "start_hour": 7,  "end_hour": 8,  "price": 150000, "is_peak": False, "period": "Sáng"},
    {"slot": "08:00 - 09:00", "start_hour": 8,  "end_hour": 9,  "price": 150000, "is_peak": False, "period": "Sáng"},
    {"slot": "09:00 - 10:00", "start_hour": 9,  "end_hour": 10, "price": 150000, "is_peak": False, "period": "Sáng"},
    {"slot": "10:00 - 11:00", "start_hour": 10, "end_hour": 11, "price": 150000, "is_peak": False, "period": "Trưa"},
    {"slot": "11:00 - 12:00", "start_hour": 11, "end_hour": 12, "price": 150000, "is_peak": False, "period": "Trưa"},
    {"slot": "12:00 - 13:00", "start_hour": 12, "end_hour": 13, "price": 150000, "is_peak": False, "period": "Trưa"},
    {"slot": "13:00 - 14:00", "start_hour": 13, "end_hour": 14, "price": 150000, "is_peak": False, "period": "Chiều"},
    {"slot": "14:00 - 15:00", "start_hour": 14, "end_hour": 15, "price": 150000, "is_peak": False, "period": "Chiều"},
    {"slot": "15:00 - 16:00", "start_hour": 15, "end_hour": 16, "price": 150000, "is_peak": False, "period": "Chiều"},
    {"slot": "16:00 - 17:00", "start_hour": 16, "end_hour": 17, "price": 250000, "is_peak": True,  "period": "Giờ Vàng (Peak)"},
    {"slot": "17:00 - 18:00", "start_hour": 17, "end_hour": 18, "price": 250000, "is_peak": True,  "period": "Giờ Vàng (Peak)"},
    {"slot": "18:00 - 19:00", "start_hour": 18, "end_hour": 19, "price": 250000, "is_peak": True,  "period": "Tối Đèn"},
    {"slot": "19:00 - 20:00", "start_hour": 19, "end_hour": 20, "price": 250000, "is_peak": True,  "period": "Tối Đèn"},
    {"slot": "20:00 - 21:00", "start_hour": 20, "end_hour": 21, "price": 250000, "is_peak": True,  "period": "Tối Đèn"},
    {"slot": "21:00 - 22:00", "start_hour": 21, "end_hour": 22, "price": 250000, "is_peak": True,  "period": "Tối Đèn"}
]

# Dịch vụ bổ sung (Add-ons)
ADDONS_CATALOG = [
    {
        "id": "racket",
        "name": "Thuê vợt Pickleball cao cấp",
        "price": 50000,
        "unit": "cây",
        "icon": "🎾",
        "description": "Vợt carbon siêu nhẹ, mặt nhám chuẩn giải đấu, có sẵn bóng tập."
    },
    {
        "id": "ball",
        "name": "Mua bóng thi đấu Pickleball",
        "price": 30000,
        "unit": "quả",
        "icon": "🥎",
        "description": "Bóng 40 lỗ ngoài trời USAPA tiêu chuẩn nảy chuẩn xác."
    },
    {
        "id": "pool_combo",
        "name": "Combo Nước Dừa Tươi & Vé Tắm Hồ Bơi",
        "price": 60000,
        "unit": "người",
        "icon": "🥥",
        "description": "01 quả dừa xiêm ướp lạnh + khăn tắm & tự do bơi lội sau trận đấu."
    },
    {
        "id": "dining_table",
        "name": "Đặt bàn ăn sau trận tại PiPo Garden",
        "price": 0,
        "unit": "bàn",
        "icon": "🍽️",
        "description": "Miễn phí giữ bàn bờ hồ thoáng mát, bếp chuẩn bị sẵn thực đơn."
    }
]

class AddonItem(BaseModel):
    id: str
    name: str
    price: int = 0
    quantity: int = 1

class PickleballBookingCreate(BaseModel):
    customer_name: str
    phone: str
    email: Optional[str] = ""
    booking_date: str  # YYYY-MM-DD
    court_id: int      # 1..4
    time_slots: List[str] # e.g. ["17:00 - 18:00"]
    addons: Optional[List[AddonItem]] = []
    deposit_percentage: int = 50 # 50 or 100
    dining_reservation: Optional[bool] = False
    notes: Optional[str] = ""

def generate_vietqr_url(bank_id: str, account_no: str, account_name: str, amount: int, memo: str) -> str:
    """
    Tạo URL endpoint nội bộ cho ảnh mã VietQR PNG chuẩn.
    Dùng /api/pos/vietqr-image thay vì img.vietqr.io (ảnh SVG không tương thích).
    """
    import urllib.parse as _uparse
    clean_memo = re.sub(r'[^a-zA-Z0-9 ]', '', memo).strip()[:25]
    return f"/api/pos/vietqr-image?amount={int(amount)}&add_info={_uparse.quote(clean_memo)}"

@router.get("/config")
def get_pickleball_config():
    """Lấy cấu hình các sân, bảng giá khung giờ và danh mục dịch vụ bổ sung."""
    return {
        "status": "SUCCESS",
        "courts": COURTS_CONFIG,
        "time_slots": BASE_TIME_SLOTS,
        "addons": ADDONS_CATALOG,
        "pricing_rules": {
            "off_peak_rate": 150000,
            "off_peak_hours": "06:00 - 16:00",
            "peak_rate": 250000,
            "peak_hours": "16:00 - 22:00",
            "currency": "VND",
            "bank_name": "Ngân Hàng Quân Đội (MB Bank)",
            "bank_account": "0888071139",
            "bank_owner": "PIPO GARDEN RESORT",
            "hotline": "0888 07 1139",
            "address": "Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, Phú Quốc"
        }
    }

@router.get("/slots")
def get_court_slots(date: Optional[str] = None):
    """
    Lấy ma trận trạng thái tất cả các khung giờ của 4 sân trong ngày được chọn.
    Trạng thái: AVAILABLE (Còn trống) hoặc BOOKED (Đã có người đặt).
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT court_id, time_slots_json, customer_name, booking_code, payment_status
        FROM pickleball_bookings
        WHERE booking_date = ? AND payment_status != 'CANCELLED'
    """, (date,))
    rows = cursor.fetchall()
    conn.close()

    # Map các slot đã được đặt theo court_id
    booked_map = {c["id"]: {} for c in COURTS_CONFIG}
    for r in rows:
        c_id = r["court_id"]
        try:
            slots = json.loads(r["time_slots_json"])
            for s in slots:
                # Che bớt tên khách vì quyền riêng tư ở chế độ khách
                raw_name = r["customer_name"] or "Khách Đặt"
                parts = raw_name.split()
                masked_name = parts[-1][0] + "***" if parts else "Đã Đặt"
                booked_map[c_id][s] = {
                    "booking_code": r["booking_code"],
                    "customer_name": f"Khách {masked_name}",
                    "payment_status": r["payment_status"]
                }
        except Exception:
            pass

    # Xây dựng ma trận kết quả
    courts_result = []
    for c in COURTS_CONFIG:
        c_id = c["id"]
        court_slots = []
        for base in BASE_TIME_SLOTS:
            slot_name = base["slot"]
            is_booked = slot_name in booked_map.get(c_id, {})
            booking_info = booked_map[c_id].get(slot_name) if is_booked else None
            court_slots.append({
                "slot": slot_name,
                "start_hour": base["start_hour"],
                "end_hour": base["end_hour"],
                "price": base["price"],
                "is_peak": base["is_peak"],
                "period": base["period"],
                "status": "BOOKED" if is_booked else "AVAILABLE",
                "booking_info": booking_info
            })

        courts_result.append({
            "court_id": c_id,
            "name": c["name"],
            "badge": c["badge"],
            "description": c["description"],
            "icon": c["icon"],
            "slots": court_slots
        })

    return {
        "status": "SUCCESS",
        "date": date,
        "courts": courts_result
    }

@router.post("/bookings")
def create_court_booking(payload: PickleballBookingCreate):
    """
    Tạo đơn đặt sân Pickleball trực tuyến, tính toán chi phí, tiền cọc và xuất vé QR.
    """
    if not payload.customer_name.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập họ và tên của bạn.")
    if not payload.phone.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập số điện thoại hoặc Zalo liên hệ.")
    if not payload.time_slots:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất 01 khung giờ chơi bóng.")
    if payload.court_id not in [1, 2, 3, 4]:
        raise HTTPException(status_code=400, detail="Mã sân không hợp lệ. Vui lòng chọn Sân 1 đến Sân 4.")

    court_conf = next((c for c in COURTS_CONFIG if c["id"] == payload.court_id), None)
    court_name = court_conf["name"] if court_conf else f"Sân {payload.court_id}"

    conn = get_db()
    cursor = conn.cursor()

    # 1. Kiểm tra xung đột lịch đặt sân (Double Booking Prevention)
    cursor.execute("""
        SELECT time_slots_json FROM pickleball_bookings
        WHERE booking_date = ? AND court_id = ? AND payment_status != 'CANCELLED'
    """, (payload.booking_date, payload.court_id))
    existing_rows = cursor.fetchall()

    booked_slots = set()
    for er in existing_rows:
        try:
            for s in json.loads(er["time_slots_json"]):
                booked_slots.add(s)
        except Exception:
            pass

    for requested_slot in payload.time_slots:
        if requested_slot in booked_slots:
            conn.close()
            raise HTTPException(
                status_code=409, 
                detail=f"Rất tiếc! Khung giờ [{requested_slot}] trên {court_name} vào ngày {payload.booking_date} vừa được khách khác đặt trước. Vui lòng chọn khung giờ hoặc sân khác!"
            )

    # 2. Tính toán tiền thuê sân
    slot_map = {s["slot"]: s["price"] for s in BASE_TIME_SLOTS}
    court_fee = 0
    for s in payload.time_slots:
        court_fee += slot_map.get(s, 200000)

    # 3. Tính toán dịch vụ bổ sung
    addons_fee = 0
    addons_list = []
    if payload.addons:
        for it in payload.addons:
            if it.quantity > 0:
                addons_fee += (it.price * it.quantity)
                addons_list.append({
                    "id": it.id,
                    "name": it.name,
                    "price": it.price,
                    "quantity": it.quantity,
                    "subtotal": it.price * it.quantity
                })

    total_amount = court_fee + addons_fee
    deposit_pct = 100 if payload.deposit_percentage >= 100 else 50
    deposit_amount = int(total_amount * (deposit_pct / 100))

    # 4. Sinh mã đặt chỗ duy nhất & Token QR
    date_compact = payload.booking_date.replace("-", "")[2:] # e.g. 261015
    rand_suffix = f"{random.randint(1000, 9999)}"
    booking_code = f"PB-{date_compact}-{rand_suffix}"
    clean_phone = re.sub(r'[^0-9]', '', payload.phone)

    # 5. Lưu đơn đặt sân vào database
    cursor.execute("""
        INSERT INTO pickleball_bookings (
            booking_code, customer_name, phone, email, booking_date, 
            court_id, court_name, time_slots_json, court_fee, 
            addons_json, addons_fee, total_amount, deposit_percentage, 
            deposit_amount, payment_status, notes, qr_token
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
    """, (
        booking_code,
        payload.customer_name.strip(),
        payload.phone.strip(),
        payload.email.strip() if payload.email else "",
        payload.booking_date,
        payload.court_id,
        court_name,
        json.dumps(payload.time_slots, ensure_ascii=False),
        court_fee,
        json.dumps(addons_list, ensure_ascii=False),
        addons_fee,
        total_amount,
        deposit_pct,
        deposit_amount,
        payload.notes.strip() if payload.notes else "",
        f"QR_{booking_code}"
    ))
    new_id = cursor.lastrowid

    # 6. Nếu khách tích chọn đặt bàn ăn sau trận -> tự động liên kết tạo đơn đặt bàn
    if payload.dining_reservation:
        last_slot = payload.time_slots[-1]
        # Thời gian dùng bữa dự kiến là giờ kết thúc trận đấu
        dinner_time = last_slot.split("-")[-1].strip() if "-" in last_slot else "18:00"
        dining_note = f"Khách chơi Pickleball {court_name} ({payload.time_slots[0]} - {last_slot}). Mã đặt sân: {booking_code}."
        cursor.execute("""
            INSERT INTO reservations (
                guest_name, phone, booking_date, booking_time, guest_count,
                service_type, note, status
            ) VALUES (?, ?, ?, ?, 4, 'PICKLEBALL', ?, 'CONFIRMED')
        """, (payload.customer_name.strip(), payload.phone.strip(), payload.booking_date, dinner_time, dining_note))

    conn.commit()

    # 7. Tạo liên kết VietQR và Check-in QR
    bank_memo = f"PIPO {clean_phone[-4:] if len(clean_phone) >= 4 else clean_phone} S{payload.court_id} {date_compact}"
    vietqr_url = generate_vietqr_url(
        bank_id="MB",
        account_no="0888071139",
        account_name="PIPO GARDEN",
        amount=deposit_amount,
        memo=bank_memo
    )
    checkin_qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=PIPO_CHECKIN_{booking_code}"

    cursor.execute("SELECT * FROM pickleball_bookings WHERE id = ?", (new_id,))
    created_booking = dict(cursor.fetchone())
    conn.close()

    created_booking["time_slots"] = payload.time_slots
    created_booking["addons"] = addons_list

    return {
        "status": "SUCCESS",
        "message": f"Đặt sân Pickleball thành công! Mã vé của bạn là {booking_code}.",
        "booking": created_booking,
        "payment": {
            "bank_name": "Ngân hàng Quân Đội (MB Bank)",
            "account_no": "0888071139",
            "account_name": "PIPO GARDEN RESORT",
            "memo_syntax": bank_memo,
            "total_amount": total_amount,
            "deposit_percentage": deposit_pct,
            "deposit_amount": deposit_amount,
            "vietqr_url": vietqr_url
        },
        "ticket": {
            "booking_code": booking_code,
            "court_name": court_name,
            "date": payload.booking_date,
            "time_slots": payload.time_slots,
            "checkin_qr_url": checkin_qr_url,
            "hotline": "0888 07 1139",
            "address": "Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, Phú Quốc"
        }
    }

class BookingStatusUpdate(BaseModel):
    status: Optional[str] = None
    payment_status: Optional[str] = None

@router.get("/bookings")
def list_pickleball_bookings(
    date: Optional[str] = None, 
    court_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    search: Optional[str] = None
):
    """Danh sách các đơn đặt sân Pickleball (cho Admin / Lễ tân / Thu ngân theo dõi)."""
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM pickleball_bookings WHERE 1=1"
    params = []

    if date:
        query += " AND booking_date = ?"
        params.append(date)

    if court_id:
        query += " AND court_id = ?"
        params.append(court_id)

    if status:
        query += " AND UPPER(payment_status) = ?"
        params.append(status.upper().strip())

    if search:
        query += " AND (customer_name LIKE ? OR phone LIKE ? OR booking_code LIKE ?)"
        s_param = f"%{search.strip()}%"
        params.extend([s_param, s_param, s_param])

    query += " ORDER BY booking_date DESC, id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    res = []
    for r in rows:
        d = dict(r)
        try:
            d["time_slots"] = json.loads(d["time_slots_json"])
        except Exception:
            d["time_slots"] = []
        try:
            d["addons"] = json.loads(d["addons_json"])
        except Exception:
            d["addons"] = []
        res.append(d)

    return {
        "status": "SUCCESS",
        "total": len(res),
        "count": len(res),
        "bookings": res
    }

@router.put("/bookings/{booking_id}/status")
@router.patch("/bookings/{booking_id}/status")
def update_booking_payment_status(
    booking_id: int, 
    payload: Optional[BookingStatusUpdate] = None,
    status: Optional[str] = Query(None)
):
    """Cập nhật trạng thái thanh toán hoặc check-in (CONFIRMED, PAID, DEPOSITED, COMPLETED, CANCELLED, PENDING)."""
    valid_statuses = ["PENDING", "CONFIRMED", "DEPOSITED", "PAID", "COMPLETED", "CANCELLED"]
    
    req_status = (payload.status or payload.payment_status) if payload else None
    if not req_status and status:
        req_status = status
    if not req_status:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp trạng thái cần cập nhật (status).")

    status_upper = req_status.upper().strip()
    if status_upper not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Trạng thái không hợp lệ. Chọn một trong: {valid_statuses}")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE pickleball_bookings SET payment_status = ? WHERE id = ?", (status_upper, booking_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt sân.")
    
    conn.commit()
    cursor.execute("SELECT * FROM pickleball_bookings WHERE id = ?", (booking_id,))
    updated = dict(cursor.fetchone())
    conn.close()

    try:
        updated["time_slots"] = json.loads(updated["time_slots_json"])
    except Exception:
        updated["time_slots"] = []
    try:
        updated["addons"] = json.loads(updated["addons_json"])
    except Exception:
        updated["addons"] = []

    return {
        "status": "SUCCESS",
        "message": f"Đã chuyển trạng thái đơn {updated['booking_code']} sang [{status_upper}].",
        "booking": updated
    }

@router.get("/schedule")
def get_pickleball_schedule(date: Optional[str] = None):
    """
    Lịch 4 sân thi đấu trong ngày: {date, schedule: {1:[...], 2:[...], 3:[...], 4:[...]}}
    Mỗi booking chứa: booking_id, booking_code, customer_name, phone, time_slots (list), status
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, booking_code, customer_name, phone, court_id, time_slots_json, payment_status, total_amount, notes, court_name
        FROM pickleball_bookings
        WHERE booking_date = ?
        ORDER BY id ASC
    """, (date,))
    rows = cursor.fetchall()
    conn.close()

    schedule: Dict[int, List[Dict[str, Any]]] = {1: [], 2: [], 3: [], 4: []}
    for r in rows:
        c_id = r["court_id"]
        if c_id not in schedule:
            schedule[c_id] = []
        try:
            slots = json.loads(r["time_slots_json"])
        except Exception:
            slots = []
        schedule[c_id].append({
            "booking_id": r["id"],
            "booking_code": r["booking_code"],
            "customer_name": r["customer_name"],
            "phone": r["phone"],
            "time_slots": slots,
            "status": r["payment_status"],
            "court_id": c_id,
            "court_name": r["court_name"],
            "total_amount": r["total_amount"],
            "notes": r["notes"] or ""
        })

    return {
        "status": "SUCCESS",
        "date": date,
        "schedule": schedule
    }


# =========================================================================
# QUẢN LÝ HỘI VIÊN, GÓI SOCIAL THÁNG/NĂM & ĐẶT SÂN CỐ ĐỊNH (MEMBERSHIPS)
# =========================================================================

class MembershipCreate(BaseModel):
    customer_name: str
    phone: str
    membership_type: str # SOCIAL_MONTH_ALL, SOCIAL_MONTH_MORNING, SOCIAL_YEAR, FIXED_COURT_MONTHLY
    court_id: Optional[Any] = None
    time_slots_desc: Optional[str] = ""
    start_date: Optional[str] = None # YYYY-MM-DD
    end_date: Optional[str] = "" # If empty, auto calculate
    price: Optional[int] = None # Cho phép nhập giá đàm phán
    duration_months: Optional[int] = 1 # Số tháng đăng ký
    paid_amount: Optional[int] = None
    payment_status: Optional[str] = "PAID" # PAID, PARTIAL, UNPAID
    payment_method: Optional[str] = "CASH" # CASH, TRANSFER
    notes: Optional[str] = ""

class MembershipUpdate(BaseModel):
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None # ACTIVE, EXPIRED, SUSPENDED
    end_date: Optional[str] = None
    price: Optional[int] = None
    paid_amount: Optional[int] = None
    payment_status: Optional[str] = None
    time_slots_desc: Optional[str] = None
    notes: Optional[str] = None

class MembershipRenew(BaseModel):
    duration_months: Optional[int] = 1 # 1 or 12
    amount_paid: int
    payment_method: Optional[str] = "CASH"
    notes: Optional[str] = ""

class CheckinCreate(BaseModel):
    membership_id: Optional[int] = None
    phone: Optional[str] = None
    notes: Optional[str] = ""

class SocialDrinkUpdate(BaseModel):
    drink_item_id: int

@router.get("/memberships")
def list_memberships(
    status: Optional[str] = None,
    membership_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
):
    """
    Danh sách các hội viên Social Tháng/Năm và nhóm đặt sân cố định.
    Hỗ trợ tìm kiếm theo Tên, Số điện thoại hoặc Mã thẻ.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Tự động cập nhật trạng thái EXPIRED cho các gói đã quá ngày kết thúc
    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        UPDATE pickleball_memberships 
        SET status = 'EXPIRED' 
        WHERE status = 'ACTIVE' AND end_date < ?
    """, (today_str,))
    conn.commit()

    query = "SELECT * FROM pickleball_memberships WHERE 1=1"
    params = []

    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status.upper().strip())

    if membership_type and membership_type != "ALL":
        query += " AND membership_type = ?"
        params.append(membership_type.strip())

    if search:
        s = f"%{search.strip()}%"
        query += " AND (customer_name LIKE ? OR phone LIKE ? OR member_code LIKE ?)"
        params.extend([s, s, s])

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    # Tính toán số ngày còn lại của gói
    today_dt = datetime.now().date()
    for r in rows:
        try:
            end_dt = datetime.strptime(r["end_date"], "%Y-%m-%d").date()
            diff = (end_dt - today_dt).days
            r["days_remaining"] = diff
            r["is_expiring_soon"] = 0 <= diff <= 5
        except Exception:
            r["days_remaining"] = 0
            r["is_expiring_soon"] = False

    return {
        "status": "SUCCESS",
        "count": len(rows),
        "memberships": rows
    }

def record_membership_order_and_print(cursor, member: dict, amount: int, payment_method: str = "CASH"):
    """
    Tự động ghi nhận đơn thanh toán vào bảng orders và tạo print_job in hóa đơn thu tiền:
    - Đưa trực tiếp vào doanh thu hệ thống (Sân Pickle).
    - Tạo phiếu in hóa đơn cho thu ngân và khách.
    """
    now = datetime.now()
    now_ts = now.strftime("%Y-%m-%d %H:%M:%S")

    court_str = str(member.get("court_id") or "PK-01").upper()
    cursor.execute("SELECT id, name, table_code, area FROM tables WHERE table_code = ? OR name LIKE ? LIMIT 1", (court_str, f"%{court_str}%"))
    table_row = cursor.fetchone()
    if not table_row:
        cursor.execute("SELECT id, name, table_code, area FROM tables WHERE table_code LIKE 'PK-%' ORDER BY id ASC LIMIT 1")
        table_row = cursor.fetchone()

    table_id = table_row["id"] if table_row else 29
    table_dict = dict(table_row) if table_row else {"name": "Sân Pickle", "area": "Sân Pickle", "table_code": "PK-01"}

    sess_token = f"mbr_{uuid.uuid4().hex[:10]}"
    cursor.execute("""
        INSERT INTO table_sessions (table_id, session_token, status, guest_count, opened_at, closed_at)
        VALUES (?, ?, 'CLOSED', 1, ?, ?)
    """, (table_id, sess_token, now_ts, now_ts))
    session_id = cursor.lastrowid

    new_order_uuid = f"ord_{uuid.uuid4().hex}"
    cursor.execute("""
        INSERT INTO orders (
            order_uuid, session_id, table_id, round_number, subtotal, discount, service_fee, total,
            status, payment_status, payment_method, customer_note,
            created_at, completed_at
        ) VALUES (?, ?, ?, 1, ?, 0, 0, ?, 'COMPLETED', 'PAID', ?, ?, ?, ?)
    """, (
        new_order_uuid, session_id, table_id, amount, amount, payment_method or "CASH",
        f"Thu phí hội viên: {member['customer_name']} ({member['member_code']})",
        now_ts, now_ts
    ))
    order_id = cursor.lastrowid

    type_names = {
        "SOCIAL_MONTH_ALL": "Hội Viên Social Tháng (Mọi Giờ)",
        "SOCIAL_MONTH_MORNING": "Hội Viên Social Tháng (Sáng 06h-16h)",
        "SOCIAL_YEAR": "Hội Viên Social Năm (VIP Cá Nhân)",
        "FIXED_COURT_MONTHLY": "Đặt Sân Cố Định Theo Tháng"
    }
    item_title = f"{type_names.get(member.get('membership_type'), 'Hội Viên Sân')}: {member['customer_name']}"

    cursor.execute("""
        INSERT INTO order_items (
            order_id, item_id, item_name, quantity, unit_price, total_price,
            station, status, note, created_at, updated_at, inventory_deducted
        ) VALUES (?, 305, ?, 1, ?, ?, 'BAR', 'COMPLETED', ?, ?, ?, 1)
    """, (
        order_id, item_title, amount, amount,
        f"Mã thẻ: {member['member_code']} | Hạn: {member.get('end_date')}",
        now_ts, now_ts
    ))

    try:
        from ..escpos import format_receipt_ticket_text, build_escpos_receipt_bytes
        receipt_items = [{
            "item_name": item_title,
            "quantity": 1,
            "unit_price": amount,
            "total_price": amount,
            "note": f"Mã: {member['member_code']}"
        }]
        totals_info = {
            "title": "HOA DON THU PHI HOI VIEN",
            "cashier_name": "Thu Ngan San Pickle",
            "discount": 0,
            "service_fee": 0,
            "payment_method": payment_method or "CASH",
            "bill_target": "CUSTOMER"
        }
        ticket_text = format_receipt_ticket_text(table_dict, receipt_items, totals_info=totals_info)
        receipt_bytes = build_escpos_receipt_bytes(table_dict, receipt_items, totals_info=totals_info)
        receipt_b64 = base64.b64encode(receipt_bytes).decode("ascii")

        cursor.execute("""
            INSERT INTO print_jobs (order_id, station, job_type, status, ticket_text)
            VALUES (?, 'CASHIER', 'RECEIPT', 'PENDING', ?)
        """, (order_id, ticket_text))
        job_id = cursor.lastrowid

        if ws_broadcaster:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(ws_broadcaster.send_to_printers({
                        "event": "PRINT_JOB",
                        "job_id": job_id,
                        "station": "CASHIER",
                        "job_type": "RECEIPT",
                        "ticket_text": ticket_text,
                        "escpos_b64": receipt_b64,
                        "table_name": table_dict.get("name", "Sân Pickle")
                    }))
            except Exception:
                pass

        is_cloud = os.environ.get("VIBE_PROJECT_ID") or os.environ.get("KUBERNETES_SERVICE_HOST") or (os.name != "nt")
        if not is_cloud:
            try:
                from ..printer_service import get_printer_config, send_escpos_to_printer
                p_cfg = get_printer_config()
                if p_cfg.get("auto_cashier", True):
                    import asyncio
                    loop = asyncio.get_event_loop()
                    loop.run_in_executor(None, send_escpos_to_printer, p_cfg["cashier_ip"], p_cfg["cashier_port"], receipt_bytes)
            except Exception:
                pass

        return order_id, ticket_text, receipt_b64
    except Exception as ex:
        print("[Pickle Membership Print Error]:", ex)
        return order_id, None, None

@router.post("/memberships")

def create_membership(payload: MembershipCreate):
    """
    Đăng ký mới Hội viên Social Tháng, Năm hoặc Đặt sân cố định theo tháng (cho phép đàm phán giá).
    """
    if not payload.customer_name.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập họ tên hội viên hoặc nhóm trưởng.")
    if not payload.phone.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập số điện thoại liên hệ.")

    # Tự động tính toán ngày kết thúc nếu chưa truyền
    # Tự động tính toán ngày bắt đầu & kết thúc nếu chưa truyền
    start_date_str = payload.start_date or datetime.now().strftime("%Y-%m-%d")
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    duration = payload.duration_months or (12 if "YEAR" in payload.membership_type.upper() else 1)

    if not payload.end_date:
        end_dt = start_dt + timedelta(days=duration * 30 if duration < 12 else 365)
        end_date = end_dt.strftime("%Y-%m-%d")
    else:
        end_date = payload.end_date

    # Xác định giá nếu chưa có
    final_price = payload.price
    if final_price is None:
        if payload.paid_amount is not None:
            final_price = payload.paid_amount
        else:
            defaults = {
                "SOCIAL_MONTH_ALL": 1200000,
                "SOCIAL_MONTH_MORNING": 600000,
                "SOCIAL_YEAR": 5000000,
                "FIXED_COURT_MONTHLY": 0
            }
            final_price = defaults.get(payload.membership_type, 0)

    now = datetime.now()
    date_code = now.strftime("%y%m")

    conn = get_db()
    cursor = conn.cursor()

    # Sinh mã hội viên tự tăng: MBR-2610-001
    cursor.execute("SELECT COUNT(*) as cnt FROM pickleball_memberships WHERE member_code LIKE ?", (f"MBR-{date_code}-%",))
    seq = cursor.fetchone()["cnt"] + 1
    member_code = f"MBR-{date_code}-{seq:03d}"

    paid = payload.paid_amount if payload.paid_amount is not None else final_price
    p_status = payload.payment_status or ("PAID" if paid >= final_price else ("PARTIAL" if paid > 0 else "UNPAID"))

    cursor.execute("""
        INSERT INTO pickleball_memberships (
            member_code, customer_name, phone, membership_type,
            court_id, time_slots_desc, start_date, end_date,
            price, paid_amount, payment_status, payment_method,
            status, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
    """, (
        member_code,
        payload.customer_name.strip(),
        payload.phone.strip(),
        payload.membership_type,
        str(payload.court_id) if payload.court_id is not None else None,
        payload.time_slots_desc or "",
        start_date_str,
        end_date,
        final_price,
        paid,
        p_status,
        payload.payment_method or "CASH",
        payload.notes or "",
        now.strftime("%Y-%m-%d %H:%M:%S"),
        now.strftime("%Y-%m-%d %H:%M:%S")
    ))
    new_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM pickleball_memberships WHERE id = ?", (new_id,))
    created = dict(cursor.fetchone())

    order_id = None
    receipt_text = None
    if paid > 0 and p_status == "PAID":
        try:
            order_id, receipt_text, _ = record_membership_order_and_print(cursor, created, paid, payload.payment_method or "CASH")
            conn.commit()
        except Exception as _e:
            print("[create_membership order error]:", _e)

    conn.close()

    return {
        "status": "SUCCESS",
        "message": f"Đăng ký gói [{member_code}] cho khách {payload.customer_name} thành công! Đã tạo hóa đơn thu tiền #{order_id or ''} và in bill.",
        "membership": created,
        "order_id": order_id,
        "receipt_text": receipt_text
    }

@router.put("/memberships/{membership_id}")
def update_membership(membership_id: int, payload: MembershipUpdate):
    """Cập nhật thông tin hội viên / trạng thái thanh toán / ghi chú."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM pickleball_memberships WHERE id = ?", (membership_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin hội viên.")

    updates = []
    params = []
    for k, v in payload.dict(exclude_unset=True).items():
        if v is not None:
            updates.append(f"{k} = ?")
            params.append(v)

    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        params.append(membership_id)
        cursor.execute(f"UPDATE pickleball_memberships SET {', '.join(updates)} WHERE id = ?", tuple(params))
        conn.commit()

    cursor.execute("SELECT * FROM pickleball_memberships WHERE id = ?", (membership_id,))
    updated = dict(cursor.fetchone())
    conn.close()

    return {
        "status": "SUCCESS",
        "message": "Cập nhật thông tin hội viên thành công!",
        "membership": updated
    }

@router.post("/memberships/{membership_id}/renew")
def renew_membership(membership_id: int, payload: MembershipRenew):
    """
    Gia hạn gói hội viên thêm 1 tháng hoặc 1 năm.
    Tự động cộng nối tiếp từ hạn cũ (hoặc từ hôm nay nếu đã hết hạn lâu).
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pickleball_memberships WHERE id = ?", (membership_id,))
    mbr = cursor.fetchone()
    if not mbr:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy hội viên.")

    mbr_dict = dict(mbr)
    today = datetime.now().date()
    try:
        current_end = datetime.strptime(mbr_dict["end_date"], "%Y-%m-%d").date()
    except Exception:
        current_end = today

    base_date = current_end if current_end >= today else today
    days_to_add = 365 if payload.duration_months == 12 or "YEAR" in mbr_dict["membership_type"] else (payload.duration_months * 30)
    new_end_date = (base_date + timedelta(days=days_to_add)).strftime("%Y-%m-%d")

    new_paid = (mbr_dict["paid_amount"] or 0) + payload.amount_paid
    new_price = (mbr_dict["price"] or 0) + payload.amount_paid
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE pickleball_memberships 
        SET end_date = ?, 
            status = 'ACTIVE',
            price = ?,
            paid_amount = ?,
            payment_status = 'PAID',
            updated_at = ?
        WHERE id = ?
    """, (new_end_date, new_price, new_paid, now_str, membership_id))
    conn.commit()

    cursor.execute("SELECT * FROM pickleball_memberships WHERE id = ?", (membership_id,))
    updated = dict(cursor.fetchone())

    order_id = None
    receipt_text = None
    if payload.amount_paid > 0:
        try:
            order_id, receipt_text, _ = record_membership_order_and_print(cursor, updated, payload.amount_paid, payload.payment_method or "CASH")
            conn.commit()
        except Exception as _e:
            print("[renew_membership order error]:", _e)

    conn.close()

    return {
        "status": "SUCCESS",
        "message": f"Đã gia hạn thành công gói [{updated['member_code']}] đến ngày {new_end_date}! Đã tạo hóa đơn thu tiền #{order_id or ''} và in bill.",
        "membership": updated,
        "order_id": order_id,
        "receipt_text": receipt_text
    }

@router.post("/memberships/{membership_id}/checkin")
@router.post("/checkin")
def checkin_member(payload: CheckinCreate, membership_id: Optional[int] = None):
    """
    Điểm danh / Check-in hội viên vào sân:
    Có thể check-in theo ID hoặc tìm nhanh theo Số điện thoại.
    Tự động kiểm tra hạn sử dụng và ghi nhận lượt chơi.
    """
    conn = get_db()
    cursor = conn.cursor()

    target_id = membership_id or payload.membership_id
    if not target_id and payload.phone:
        clean_phone = payload.phone.strip()
        cursor.execute("SELECT id FROM pickleball_memberships WHERE phone LIKE ? AND status = 'ACTIVE' ORDER BY id DESC LIMIT 1", (f"%{clean_phone}%",))
        row = cursor.fetchone()
        if row:
            target_id = row["id"]

    if not target_id:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy thẻ hội viên phù hợp để check-in.")

    cursor.execute("SELECT * FROM pickleball_memberships WHERE id = ?", (target_id,))
    mbr = cursor.fetchone()
    if not mbr:
        conn.close()
        raise HTTPException(status_code=404, detail="Thẻ hội viên không tồn tại.")

    mbr_dict = dict(mbr)
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Kiểm tra hạn sử dụng
    if mbr_dict["end_date"] < today_str:
        cursor.execute("UPDATE pickleball_memberships SET status = 'EXPIRED' WHERE id = ?", (target_id,))
        conn.commit()
        conn.close()
        raise HTTPException(
            status_code=400, 
            detail=f"Thẻ của khách [{mbr_dict['customer_name']}] đã HẾT HẠN vào ngày {mbr_dict['end_date']}. Vui lòng gia hạn gói!"
        )

    # Ghi nhận lượt check-in
    cursor.execute("""
        INSERT INTO pickleball_checkins (membership_id, member_name, phone, membership_type, checked_in_at, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (target_id, mbr_dict["customer_name"], mbr_dict["phone"], mbr_dict["membership_type"], now_ts, payload.notes or ""))

    # Cập nhật số lượt và thời gian checkin gần nhất
    new_count = (mbr_dict["checkin_count"] or 0) + 1
    cursor.execute("""
        UPDATE pickleball_memberships 
        SET checkin_count = ?, last_checkin_at = ?, updated_at = ?
        WHERE id = ?
    """, (new_count, now_ts, now_ts, target_id))
    conn.commit()
    conn.close()

    return {
        "status": "SUCCESS",
        "message": f"Check-in thành công cho [{mbr_dict['customer_name']}]! Lượt chơi thứ {new_count} (Hạn đến {mbr_dict['end_date']}).",
        "customer_name": mbr_dict["customer_name"],
        "membership_type": mbr_dict["membership_type"],
        "checkin_count": new_count,
        "end_date": mbr_dict["end_date"]
    }

@router.get("/checkins")
def list_today_checkins(date: Optional[str] = None, limit: int = 50):
    """Lấy danh sách các lượt check-in vào sân hôm nay."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, m.member_code 
        FROM pickleball_checkins c
        LEFT JOIN pickleball_memberships m ON c.membership_id = m.id
        WHERE DATE(c.checked_in_at) = ?
        ORDER BY c.id DESC LIMIT ?
    """, (date, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {
        "status": "SUCCESS",
        "date": date,
        "total_checkins": len(rows),
        "checkins": rows
    }

# =========================================================================
# CẤU HÌNH LOẠI ĐỒ UỐNG ĐI KÈM VÉ SOCIAL (60K KÈM NƯỚC)
# =========================================================================

@router.get("/settings/social-drink")
def get_social_drink_setting():
    """Lấy thông tin đồ uống đang được gán kèm vé Social 60k và danh sách các đồ uống để chọn."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM system_settings WHERE key = 'pickle_social_included_drink_id'")
    row = cursor.fetchone()
    current_drink_id = int(row["value"]) if (row and row["value"] and row["value"].isdigit()) else 183

    # Thông tin món nước hiện tại
    cursor.execute("SELECT id, name, price, portion, image_url FROM menu_items WHERE id = ?", (current_drink_id,))
    current_drink = cursor.fetchone()

    # Danh sách tất cả đồ uống khả dụng trong menu để người dùng chọn gán
    cursor.execute("""
        SELECT m.id, m.name, m.price, m.portion, c.name as category_name
        FROM menu_items m
        LEFT JOIN categories c ON m.category_id = c.id
        WHERE m.category_id = 6 OR m.main_menu_type LIKE '%PICKLE%' OR m.name LIKE '%nước%' OR m.name LIKE '%bia%' OR m.name LIKE '%trà%'
        ORDER BY m.id ASC
    """)
    available_drinks = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {
        "status": "SUCCESS",
        "included_drink_id": current_drink_id,
        "current_drink": dict(current_drink) if current_drink else {"id": 183, "name": "Nước suối", "price": 10000},
        "available_drinks": available_drinks
    }

@router.post("/settings/social-drink")
def update_social_drink_setting(payload: SocialDrinkUpdate):
    """Cập nhật loại đồ uống đi kèm vé Social 60k để tự động trừ kho khi bán vé."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM menu_items WHERE id = ?", (payload.drink_item_id,))
    drink = cursor.fetchone()
    if not drink:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy món đồ uống trong thực đơn.")

    cursor.execute("""
        INSERT INTO system_settings (key, value)
        VALUES ('pickle_social_included_drink_id', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (str(payload.drink_item_id),))
    conn.commit()
    conn.close()

    return {
        "status": "SUCCESS",
        "message": f"Đã gán đồ uống kèm vé Social thành công: [{drink['name']}]. Khi khách thanh toán vé Social 60k, hệ thống sẽ tự động trừ kho món này!",
        "included_drink_id": payload.drink_item_id,
        "drink_name": drink["name"]
    }



@router.delete("/memberships/{membership_id}")
def delete_membership(membership_id: int, request: Request):
    """Xóa thẻ hội viên (Dành riêng cho Admin)."""
    user = require_api_auth(request, allowed_roles=["ADMIN", "SUPER_ADMIN"])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT member_code, customer_name FROM pickleball_memberships WHERE id = ?", (membership_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin hội viên.")

    cursor.execute("DELETE FROM pickleball_checkins WHERE membership_id = ?", (membership_id,))
    cursor.execute("DELETE FROM pickleball_memberships WHERE id = ?", (membership_id,))
    conn.commit()
    conn.close()

    return {
        "status": "SUCCESS",
        "message": f"Đã xóa hội viên [{row['customer_name']}] ({row['member_code']}) thành công."
    }


@router.post("/clear-revenue")
async def clear_pickleball_revenue_endpoint(request: Request):
    """Xóa sạch doanh thu Sân Pickleball (Đơn sân PK-01..04, Đặt sân, Hội viên, Thu chi)."""
    from .sync import clear_pickleball_revenue
    return await clear_pickleball_revenue(request)
