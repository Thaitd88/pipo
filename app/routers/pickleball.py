# Router for Pickleball Court Booking System at PiPo Garden
import json
import random
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from ..database import get_db

router = APIRouter(prefix="/api/pickleball", tags=["Pickleball Booking"])

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
    """Tạo link mã VietQR động tự điền số tiền và cú pháp."""
    clean_memo = re.sub(r'[^a-zA-Z0-9 ]', '', memo).strip()
    encoded_memo = clean_memo.replace(" ", "%20")
    encoded_name = account_name.replace(" ", "%20")
    return f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact2.png?amount={amount}&addInfo={encoded_memo}&accountName={encoded_name}"

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
            "bank_account": "0838993316",
            "bank_owner": "PIPO GARDEN RESORT",
            "hotline": "0838.993.316",
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
        account_no="0838993316",
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
            "account_no": "0838993316",
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
            "hotline": "0838.993.316",
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

