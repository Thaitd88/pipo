# Router for Accounting, Cash Transactions (Capex & Opex) and Profit & Loss (P&L) Report
import os
import io
import re
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File
from pydantic import BaseModel, Field
from PIL import Image, ImageOps

from ..database import get_db, DATA_DIR
from .auth import require_api_auth, get_current_user_from_request

router = APIRouter(prefix="/api/accounting", tags=["Accounting & PnL"])

broadcaster = None

def set_broadcaster(b):
    global broadcaster
    broadcaster = b

# Thu muc luu anh chung tu phieu thu chi
STATIC_RECEIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads", "receipts")
os.makedirs(STATIC_RECEIPTS_DIR, exist_ok=True)

PERSISTENT_RECEIPTS_DIR = os.path.join(DATA_DIR, "uploads", "receipts")
os.makedirs(PERSISTENT_RECEIPTS_DIR, exist_ok=True)

EXPENSE_CATEGORIES = {
    "OPEX": [
        {"code": "NGUYEN_LIEU", "name": "Nguyên liệu / Thực phẩm chợ", "icon": "🥩", "desc": "Mua bổ sung thịt, cá, rau củ quả, gia vị phát sinh"},
        {"code": "DIEN_NUOC_NET", "name": "Tiền Điện, Nước, Internet", "icon": "⚡", "desc": "Chi phí điện cao áp sân pickle, điều hòa, nước sạch, wifi"},
        {"code": "LUONG_CONG_NHAT", "name": "Lương công nhật / Thưởng ca", "icon": "💵", "desc": "Chi trả nhân sự thời vụ, công nhật, phụ bếp, nhặt bóng"},
        {"code": "VESINH_DUNG_CU", "name": "Vật tư tiêu hao / Vệ sinh", "icon": "🧹", "desc": "Đá lạnh, giấy vệ sinh, túi rác, than hoa, cồn sát khuẩn"},
        {"code": "BAO_TRI_SUACHUA", "name": "Bảo trì / Sửa chữa thường xuyên", "icon": "🔧", "desc": "Sửa điện nước vặt, thay lưới bóng, bóng pickleball, sơn dặm"},
        {"code": "BONG_PHU_KIEN", "name": "Mua bóng & Phụ kiện Pickleball", "icon": "🎾", "desc": "Bóng 40 lỗ thi đấu, quấn cán vợt, dụng cụ sân"},
        {"code": "MARKETING_QUANGCAO", "name": "Marketing & Tiếp thị", "icon": "📢", "desc": "Chi phí tờ rơi, quảng cáo mạng xã hội, giải đấu"},
        {"code": "CHI_OPEX_KHAC", "name": "Chi phí vận hành khác", "icon": "📝", "desc": "Các khoản chi vận hành thường xuyên khác"}
    ],
    "CAPEX": [
        {"code": "THIET_BI_MAY_MOC", "name": "Máy móc & Thiết bị", "icon": "🖨️", "desc": "Máy in bill, tủ đông, tủ mát, điều hòa, máy bắn bóng pickleball"},
        {"code": "XAY_DUNG_CO_SO", "name": "Cải tạo & Xây dựng cơ sở", "icon": "🏗️", "desc": "Thi công mái che sân pickle, sơn mặt sân, giàn đèn LED, hồ bơi"},
        {"code": "BAN_GHE_NOI_THAT", "name": "Bàn ghế & Nội thất", "icon": "🪑", "desc": "Bàn ghế sân vườn, ô dù ngoài trời, ghế nghỉ khán đài sân pick"},
        {"code": "CHI_CAPEX_KHAC", "name": "Đầu tư tài sản khác", "icon": "💎", "desc": "Các khoản đầu tư tài sản cố định giá trị lớn khác"}
    ],
    "INCOME": [
        {"code": "THU_TIEN_SAN_NGOAI", "name": "Thu tiền sân / Thẻ trực tiếp", "icon": "🎾", "desc": "Khách thanh toán trực tiếp tại sân, tiền cọc sân"},
        {"code": "THU_DICH_VU_SU_KIEN", "name": "Thu tổ chức sự kiện / Giải đấu", "icon": "🏆", "desc": "Tài trợ, đăng ký giải đấu Pickleball, đặt tiệc trọn gói"},
        {"code": "THANH_LY_TAI_SAN", "name": "Thanh lý đồ cũ / Phế liệu", "icon": "♻️", "desc": "Thanh lý vợt cũ, bóng cũ, vỏ lon bia, thùng giấy"},
        {"code": "THU_KHAC", "name": "Khoản thu ngoài khác", "icon": "💰", "desc": "Các khoản thu ngoài hoạt động thông thường"}
    ]
}

class TransactionCreate(BaseModel):
    transaction_type: str # EXPENSE, INCOME
    cost_category: str    # OPEX, CAPEX (nếu là INCOME thì có thể để REVENUE/GENERAL)
    department: str       # RESTAURANT, PICKLEBALL, GENERAL
    expense_type: str
    amount: int
    payment_method: Optional[str] = "CASH" # CASH, TRANSFER
    recipient_payer: Optional[str] = ""
    description: str
    receipt_url: Optional[str] = ""

@router.get("/categories")
def get_accounting_categories():
    """Lấy danh mục định nghĩa phân loại chi phí OPEX và CAPEX."""
    return {
        "status": "SUCCESS",
        "categories": EXPENSE_CATEGORIES
    }

@router.post("/upload-receipt")
async def upload_receipt_image(file: UploadFile = File(...)):
    """
    Tải ảnh chụp phiếu thu/chi, hóa đơn, chứng từ:
    - Hỗ trợ JPG, PNG, WEBP, GIF, JFIF, BMP, AVIF.
    - Xoay chiều chuẩn theo EXIF.
    - Nén WebP tối ưu.
    - Lưu vào static/uploads/receipts và persistent uploads.
    """
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".jfif", ".bmp", ".gif", ".avif"}
    original_name = file.filename or "receipt.jpg"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Định dạng tệp '{ext}' không được hỗ trợ. Vui lòng chọn ảnh JPG, PNG hoặc WebP.")

    contents = await file.read()
    if len(contents) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Dung lượng ảnh vượt quá giới hạn 15MB.")

    try:
        img = Image.open(io.BytesIO(contents))
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể xử lý tệp ảnh: {str(e)}")

    # Auto-Resize ảnh: cạnh dài nhất tối đa 1200px
    max_dim = 1200
    w, h = img.size
    if w > max_dim or h > max_dim:
        if w > h:
            new_w = max_dim
            new_h = int(h * (max_dim / w))
        else:
            new_h = max_dim
            new_w = int(w * (max_dim / h))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    unique_name = f"receipt_{datetime.now().strftime('%y%m%d')}_{uuid.uuid4().hex[:8]}.webp"
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=85, method=6)
    webp_bytes = buf.getvalue()

    # Lưu vào static/uploads/receipts
    target_path = os.path.join(STATIC_RECEIPTS_DIR, unique_name)
    with open(target_path, "wb") as f:
        f.write(webp_bytes)

    # Lưu vào persistent storage
    try:
        with open(os.path.join(PERSISTENT_RECEIPTS_DIR, unique_name), "wb") as f:
            f.write(webp_bytes)
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "receipt_url": f"/static/uploads/receipts/{unique_name}",
        "file_name": unique_name
    }

@router.get("/transactions")
def list_transactions(
    request: Request,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    department: Optional[str] = None,
    cost_category: Optional[str] = None,
    transaction_type: Optional[str] = None,
    payment_method: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
):
    """
    Danh sách các phiếu Thu / Chi (Sổ Quỹ Tiền Mặt & Chuyển Khoản).
    Cả Thu Ngân, Nhân Viên Sân Pick và Admin đều có quyền xem.
    """
    user = require_api_auth(request, allowed_roles=["ADMIN", "SUPER_ADMIN", "CASHIER", "PICKLEBALL"])
    
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM accounting_transactions WHERE 1=1"
    params = []

    if from_date:
        query += " AND DATE(created_at) >= ?"
        params.append(from_date)

    if to_date:
        query += " AND DATE(created_at) <= ?"
        params.append(to_date)

    if department and department != "ALL":
        query += " AND department = ?"
        params.append(department)

    if cost_category and cost_category != "ALL":
        query += " AND cost_category = ?"
        params.append(cost_category)

    if transaction_type and transaction_type != "ALL":
        query += " AND transaction_type = ?"
        params.append(transaction_type)

    if payment_method and payment_method != "ALL":
        if payment_method.upper() == "CASH":
            query += " AND (payment_method IS NULL OR UPPER(payment_method) = 'CASH')"
        else:
            query += " AND UPPER(payment_method) IN ('TRANSFER', 'BANK_TRANSFER', 'VIETQR', 'CK')"

    if search:
        s = f"%{search.strip()}%"
        query += " AND (description LIKE ? OR recipient_payer LIKE ? OR transaction_code LIKE ?)"
        params.extend([s, s, s])

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_expense = sum(r["amount"] for r in rows if r["transaction_type"] == "EXPENSE")
    total_income = sum(r["amount"] for r in rows if r["transaction_type"] == "INCOME")
    
    cash_expense = sum(r["amount"] for r in rows if r["transaction_type"] == "EXPENSE" and (r.get("payment_method") or "CASH").upper() == "CASH")
    cash_income = sum(r["amount"] for r in rows if r["transaction_type"] == "INCOME" and (r.get("payment_method") or "CASH").upper() == "CASH")
    
    transfer_expense = sum(r["amount"] for r in rows if r["transaction_type"] == "EXPENSE" and (r.get("payment_method") or "").upper() in ["TRANSFER", "BANK_TRANSFER", "VIETQR", "CK"])
    transfer_income = sum(r["amount"] for r in rows if r["transaction_type"] == "INCOME" and (r.get("payment_method") or "").upper() in ["TRANSFER", "BANK_TRANSFER", "VIETQR", "CK"])

    return {
        "status": "SUCCESS",
        "count": len(rows),
        "total_expense": total_expense,
        "total_income": total_income,
        "balance": total_income - total_expense,
        "cash_income": cash_income,
        "cash_expense": cash_expense,
        "cash_balance": cash_income - cash_expense,
        "transfer_income": transfer_income,
        "transfer_expense": transfer_expense,
        "transfer_balance": transfer_income - transfer_expense,
        "transactions": rows
    }

@router.post("/transactions")
async def create_transaction(payload: TransactionCreate, request: Request):
    """
    Tạo phiếu Thu hoặc Phiếu Chi mới.
    Cho phép nhân viên Thu Ngân (CASHIER), Sân Pick (PICKLEBALL) và Admin lập phiếu hàng ngày.
    """
    user = require_api_auth(request, allowed_roles=["ADMIN", "SUPER_ADMIN", "CASHIER", "PICKLEBALL"])

    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Số tiền giao dịch phải lớn hơn 0 VNĐ.")
    if not payload.description.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập lý do / diễn giải chi tiết.")

    t_type = payload.transaction_type.upper().strip()
    c_cat = payload.cost_category.upper().strip() if payload.cost_category else "OPEX"
    dept = payload.department.upper().strip() if payload.department else "GENERAL"

    if t_type not in ["EXPENSE", "INCOME"]:
        raise HTTPException(status_code=400, detail="Loại giao dịch không hợp lệ (chỉ chấp nhận EXPENSE hoặc INCOME).")
    if c_cat not in ["OPEX", "CAPEX", "GENERAL"]:
        c_cat = "OPEX" if t_type == "EXPENSE" else "GENERAL"
    if dept not in ["RESTAURANT", "PICKLEBALL", "GENERAL"]:
        dept = "GENERAL"

    # Chuẩn hóa phương thức thanh toán: CASH hoặc TRANSFER
    raw_p_method = (payload.payment_method or "CASH").upper().strip()
    if raw_p_method in ["TRANSFER", "BANK_TRANSFER", "VIETQR", "CK"]:
        p_method = "TRANSFER"
    else:
        p_method = "CASH"

    now = datetime.now()
    prefix = "PC" if t_type == "EXPENSE" else "PT"
    date_code = now.strftime("%y%m%d")

    conn = get_db()
    cursor = conn.cursor()

    # Sinh mã phiếu tự tăng trong ngày (VD: PC-261021-001)
    cursor.execute("""
        SELECT COUNT(*) as count FROM accounting_transactions 
        WHERE transaction_code LIKE ?
    """, (f"{prefix}-{date_code}-%",))
    seq = cursor.fetchone()["count"] + 1
    trans_code = f"{prefix}-{date_code}-{seq:03d}"

    creator_name = user.get("username") or user.get("full_name") or "staff"

    cursor.execute("""
        INSERT INTO accounting_transactions (
            transaction_code, transaction_type, cost_category, department,
            expense_type, amount, payment_method, recipient_payer,
            description, receipt_url, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trans_code,
        t_type,
        c_cat,
        dept,
        payload.expense_type,
        payload.amount,
        p_method,
        payload.recipient_payer.strip() if payload.recipient_payer else "",
        payload.description.strip(),
        payload.receipt_url.strip() if payload.receipt_url else "",
        creator_name,
        now.strftime("%Y-%m-%d %H:%M:%S")
    ))
    new_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM accounting_transactions WHERE id = ?", (new_id,))
    created = dict(cursor.fetchone())
    conn.close()

    # Bắn thông báo realtime tới toàn bộ hệ thống
    if broadcaster:
        try:
            await broadcaster.send_to_pos({
                "event": "ACCOUNTING_TRANSACTION_UPDATED",
                "transaction_id": new_id,
                "transaction_code": trans_code,
                "transaction_type": t_type,
                "payment_method": p_method,
                "amount": payload.amount
            })
        except Exception:
            pass

    return {
        "status": "SUCCESS",
        "message": f"Đã lập {('Phiếu Chi' if t_type == 'EXPENSE' else 'Phiếu Thu')} [{trans_code}] thành công!",
        "transaction": created
    }

@router.delete("/transactions/{transaction_id}")
async def delete_transaction(transaction_id: int, request: Request):
    """Xóa phiếu Thu/Chi (chỉ ADMIN và SUPER_ADMIN mới có quyền xóa)."""
    user = require_api_auth(request, allowed_roles=["ADMIN", "SUPER_ADMIN"])

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT transaction_code, transaction_type, payment_method, amount FROM accounting_transactions WHERE id = ?", (transaction_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu cần xóa.")

    code = row["transaction_code"]
    t_type = row["transaction_type"]
    p_method = row["payment_method"]
    amount = row["amount"]

    cursor.execute("DELETE FROM accounting_transactions WHERE id = ?", (transaction_id,))
    conn.commit()
    conn.close()

    # Bắn thông báo realtime tới toàn bộ hệ thống
    if broadcaster:
        try:
            await broadcaster.send_to_pos({
                "event": "ACCOUNTING_TRANSACTION_UPDATED",
                "transaction_id": transaction_id,
                "transaction_code": code,
                "action": "DELETED"
            })
        except Exception:
            pass

    return {
        "status": "SUCCESS",
        "message": f"Đã xóa phiếu [{code}] khỏi sổ quỹ."
    }
    conn.close()

    return {
        "status": "SUCCESS",
        "message": f"Đã xóa phiếu [{code}] khỏi sổ quỹ."
    }

@router.get("/pnl")
def get_pnl_report(
    request: Request,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    department: Optional[str] = "ALL"
):
    """
    Báo Cáo Lãi - Lỗ Toàn Diện (Profit & Loss Statement - P&L):
    1. Doanh thu: F&B + Sân Pickleball (Social, Hội viên tháng/năm, Thuê giờ) + Thu ngoài.
    2. Giá vốn NVL (COGS) tính tự động từ BOM đơn hàng.
    3. Chi phí vận hành OPEX (Điện, nước, nhân sự, đá lạnh, bảo trì...)
    4. Chi phí đầu tư tài sản CAPEX (Máy móc, thiết bị, sân bãi...)
    5. Lợi nhuận gộp & Lợi nhuận thuần.
    """
    user = require_api_auth(request, allowed_roles=["ADMIN", "SUPER_ADMIN", "CASHIER", "PICKLEBALL"])

    now = datetime.now()
    if not from_date:
        from_date = now.strftime("%Y-%m-01") # Đầu tháng
    if not to_date:
        to_date = now.strftime("%Y-%m-%d")   # Hôm nay

    from_ts = f"{from_date} 00:00:00"
    to_ts = f"{to_date} 23:59:59"

    conn = get_db()
    cursor = conn.cursor()

    # 1. Doanh Thu F&B Nhà Hàng (Đơn thanh toán thuộc các bàn không phải Sân Pick)
    cursor.execute("""
        SELECT COALESCE(SUM(o.total), 0) as fb_rev
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        WHERE o.payment_status = 'PAID'
          AND o.completed_at BETWEEN ? AND ?
          AND t.area != 'Sân Pickle'
    """, (from_ts, to_ts))
    fb_revenue = cursor.fetchone()["fb_rev"] or 0

    # 2. Doanh Thu Sân Pickleball:
    # 2.1. Doanh thu POS tại các bàn Sân Pick (PK-01 .. PK-04: vé social, thuê giờ, nước tại sân...)
    cursor.execute("""
        SELECT COALESCE(SUM(o.total), 0) as pickle_pos_rev
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        WHERE o.payment_status = 'PAID'
          AND o.completed_at BETWEEN ? AND ?
          AND t.area = 'Sân Pickle'
    """, (from_ts, to_ts))
    pickle_pos_revenue = cursor.fetchone()["pickle_pos_rev"] or 0

    # 2.2. Doanh thu Hội viên đóng gói (Social tháng, Social năm, Đặt sân cố định tháng)
    cursor.execute("""
        SELECT COALESCE(SUM(paid_amount), 0) as mbr_rev
        FROM pickleball_memberships
        WHERE payment_status IN ('PAID', 'PARTIAL')
          AND DATE(created_at) BETWEEN ? AND ?
    """, (from_date, to_date))
    mbr_revenue = cursor.fetchone()["mbr_rev"] or 0

    # 2.3. Doanh thu Đặt sân trực tuyến online
    cursor.execute("""
        SELECT COALESCE(SUM(deposit_amount), 0) as booking_rev
        FROM pickleball_bookings
        WHERE payment_status IN ('PAID', 'DEPOSITED', 'COMPLETED')
          AND booking_date BETWEEN ? AND ?
    """, (from_date, to_date))
    online_booking_revenue = cursor.fetchone()["booking_rev"] or 0

    total_pickleball_revenue = pickle_pos_revenue + mbr_revenue + online_booking_revenue

    # 3. Thu nhập ngoài khác (từ sổ quỹ)
    dept_income_filter = ""
    income_params = [from_date, to_date]
    if department and department != "ALL":
        dept_income_filter = " AND department = ?"
        income_params.append(department)

    cursor.execute(f"""
        SELECT COALESCE(SUM(amount), 0) as other_inc
        FROM accounting_transactions
        WHERE transaction_type = 'INCOME'
          AND DATE(created_at) BETWEEN ? AND ?
          {dept_income_filter}
    """, tuple(income_params))
    other_income = cursor.fetchone()["other_inc"] or 0

    # Tổng Doanh Thu Hợp Nhất
    if department == "RESTAURANT":
        total_revenue = fb_revenue + other_income
    elif department == "PICKLEBALL":
        total_revenue = total_pickleball_revenue + other_income
    else:
        total_revenue = fb_revenue + total_pickleball_revenue + other_income

    # 4. Giá vốn hàng bán (COGS - Cost of Goods Sold tính từ tồn kho xuất)
    # Lấy tổng giá vốn từ các giao dịch trừ kho bán hàng (ORDER_DEDUCT hoặc DEDUCT hoặc EXPORT)
    cursor.execute("""
        SELECT COALESCE(SUM(ABS(it.quantity) * COALESCE(it.unit_price, ii.cost_price, 0)), 0) as cogs
        FROM inventory_transactions it
        JOIN inventory_items ii ON it.ingredient_id = ii.id
        WHERE it.transaction_type IN ('ORDER_DEDUCT', 'DEDUCT', 'EXPORT')
          AND DATE(it.created_at) BETWEEN ? AND ?
    """, (from_date, to_date))
    cogs_total = cursor.fetchone()["cogs"] or 0

    # 5. Chi phí vận hành OPEX (Phân theo loại chi phí)
    dept_opex_filter = ""
    opex_params = [from_date, to_date]
    if department and department != "ALL":
        dept_opex_filter = " AND department = ?"
        opex_params.append(department)

    cursor.execute(f"""
        SELECT expense_type, COALESCE(SUM(amount), 0) as total_amt
        FROM accounting_transactions
        WHERE transaction_type = 'EXPENSE'
          AND cost_category = 'OPEX'
          AND DATE(created_at) BETWEEN ? AND ?
          {dept_opex_filter}
        GROUP BY expense_type
    """, tuple(opex_params))
    opex_rows = cursor.fetchall()
    opex_breakdown = {r["expense_type"]: r["total_amt"] for r in opex_rows}
    total_opex = sum(opex_breakdown.values())

    # 6. Chi phí đầu tư tài sản CAPEX
    dept_capex_filter = ""
    capex_params = [from_date, to_date]
    if department and department != "ALL":
        dept_capex_filter = " AND department = ?"
        capex_params.append(department)

    cursor.execute(f"""
        SELECT expense_type, COALESCE(SUM(amount), 0) as total_amt
        FROM accounting_transactions
        WHERE transaction_type = 'EXPENSE'
          AND cost_category = 'CAPEX'
          AND DATE(created_at) BETWEEN ? AND ?
          {dept_capex_filter}
        GROUP BY expense_type
    """, tuple(capex_params))
    capex_rows = cursor.fetchall()
    capex_breakdown = {r["expense_type"]: r["total_amt"] for r in capex_rows}
    total_capex = sum(capex_breakdown.values())

    conn.close()

    # Tính toán các chỉ số tài chính P&L
    gross_profit = total_revenue - cogs_total
    gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
    operating_profit = gross_profit - total_opex # EBITDA
    operating_margin = (operating_profit / total_revenue * 100) if total_revenue > 0 else 0
    net_cashflow = operating_profit - total_capex

    return {
        "status": "SUCCESS",
        "period": {
            "from_date": from_date,
            "to_date": to_date,
            "department": department
        },
        "revenue": {
            "fb_restaurant": fb_revenue,
            "pickleball_pos": pickle_pos_revenue,
            "pickleball_memberships": mbr_revenue,
            "pickleball_online_booking": online_booking_revenue,
            "pickleball_total": total_pickleball_revenue,
            "other_income": other_income,
            "total_revenue": total_revenue
        },
        "cost_of_goods_sold": {
            "cogs_total": cogs_total,
            "gross_profit": gross_profit,
            "gross_margin_percent": round(gross_margin, 1)
        },
        "operating_expenses_opex": {
            "total_opex": total_opex,
            "breakdown": opex_breakdown
        },
        "operating_profit_ebitda": {
            "amount": operating_profit,
            "margin_percent": round(operating_margin, 1)
        },
        "capital_expenditures_capex": {
            "total_capex": total_capex,
            "breakdown": capex_breakdown
        },
        "net_cashflow": {
            "amount": net_cashflow
        }
    }

@router.get("/summary-today")
def get_accounting_summary_today(request: Request):
    """Tổng hợp nhanh dòng tiền và biến động Quỹ Tiền Mặt / Quỹ Chuyển Khoản hôm nay."""
    user = require_api_auth(request, allowed_roles=["ADMIN", "SUPER_ADMIN", "CASHIER", "PICKLEBALL"])
    
    today = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    cursor = conn.cursor()

    # Doanh thu bán hàng POS hôm nay (chỉ tính đơn PAID, không tính nợ nội bộ Admin)
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN UPPER(COALESCE(payment_method, 'CASH')) = 'CASH' AND COALESCE(bill_target, 'CUSTOMER') != 'ADMIN' THEN total ELSE 0 END), 0) as pos_cash,
            COALESCE(SUM(CASE WHEN UPPER(payment_method) IN ('TRANSFER', 'VIETQR') AND COALESCE(bill_target, 'CUSTOMER') != 'ADMIN' THEN total ELSE 0 END), 0) as pos_transfer,
            COALESCE(SUM(CASE WHEN COALESCE(bill_target, 'CUSTOMER') != 'ADMIN' THEN total ELSE 0 END), 0) as pos_total
        FROM orders
        WHERE payment_status = 'PAID' AND DATE(COALESCE(completed_at, created_at)) = ?
    """, (today,))
    pos_row = cursor.fetchone()

    # Chi hôm nay từ sổ quỹ: tách Tiền Mặt vs Chuyển Khoản
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN cost_category = 'OPEX' THEN amount ELSE 0 END), 0) as opex_today,
            COALESCE(SUM(CASE WHEN cost_category = 'CAPEX' THEN amount ELSE 0 END), 0) as capex_today,
            COALESCE(SUM(CASE WHEN payment_method IS NULL OR UPPER(payment_method) = 'CASH' THEN amount ELSE 0 END), 0) as cash_expense_today,
            COALESCE(SUM(CASE WHEN UPPER(payment_method) IN ('TRANSFER', 'BANK_TRANSFER', 'VIETQR', 'CK') THEN amount ELSE 0 END), 0) as transfer_expense_today,
            COALESCE(SUM(amount), 0) as total_expense_today
        FROM accounting_transactions
        WHERE transaction_type = 'EXPENSE' AND DATE(created_at) = ?
    """, (today,))
    exp_row = cursor.fetchone()

    # Thu ngoài hôm nay: tách Tiền Mặt vs Chuyển Khoản
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN payment_method IS NULL OR UPPER(payment_method) = 'CASH' THEN amount ELSE 0 END), 0) as cash_inc_today,
            COALESCE(SUM(CASE WHEN UPPER(payment_method) IN ('TRANSFER', 'BANK_TRANSFER', 'VIETQR', 'CK') THEN amount ELSE 0 END), 0) as transfer_inc_today,
            COALESCE(SUM(amount), 0) as inc_today
        FROM accounting_transactions
        WHERE transaction_type = 'INCOME' AND DATE(created_at) = ?
    """, (today,))
    inc_row = cursor.fetchone()

    conn.close()

    pos_cash = pos_row["pos_cash"] or 0
    cash_expense = exp_row["cash_expense_today"] or 0
    cash_inc = inc_row["cash_inc_today"] or 0
    estimated_cash_drawer = pos_cash + cash_inc - cash_expense

    pos_transfer = pos_row["pos_transfer"] or 0
    transfer_expense = exp_row["transfer_expense_today"] or 0
    transfer_inc = inc_row["transfer_inc_today"] or 0
    estimated_transfer_balance = pos_transfer + transfer_inc - transfer_expense

    return {
        "status": "SUCCESS",
        "date": today,
        "revenue_today": pos_row["pos_total"] or 0,
        "pos_cash": pos_cash,
        "pos_transfer": pos_transfer,
        "cash_inc_today": cash_inc,
        "cash_expense_today": cash_expense,
        "cash_in_drawer_estimate": estimated_cash_drawer,
        "estimated_cash_drawer": estimated_cash_drawer,
        "transfer_inc_today": transfer_inc,
        "transfer_expense_today": transfer_expense,
        "transfer_balance_today": estimated_transfer_balance,
        "opex_today": exp_row["opex_today"] or 0,
        "capex_today": exp_row["capex_today"] or 0,
        "total_expense_today": exp_row["total_expense_today"] or 0,
        "other_income_today": inc_row["inc_today"] or 0
    }
