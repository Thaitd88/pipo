# Router for Accounting, Cash Transactions (Capex & Opex) and Profit & Loss (P&L) Report
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..database import get_db
from .auth import require_api_auth, get_current_user_from_request

router = APIRouter(prefix="/api/accounting", tags=["Accounting & PnL"])

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

@router.get("/transactions")
def list_transactions(
    request: Request,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    department: Optional[str] = None,
    cost_category: Optional[str] = None,
    transaction_type: Optional[str] = None,
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

    return {
        "status": "SUCCESS",
        "count": len(rows),
        "total_expense": total_expense,
        "total_income": total_income,
        "balance": total_income - total_expense,
        "transactions": rows
    }

@router.post("/transactions")
def create_transaction(payload: TransactionCreate, request: Request):
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
    c_cat = payload.cost_category.upper().strip()
    dept = payload.department.upper().strip()

    if t_type not in ["EXPENSE", "INCOME"]:
        raise HTTPException(status_code=400, detail="Loại giao dịch không hợp lệ (chỉ chấp nhận EXPENSE hoặc INCOME).")
    if c_cat not in ["OPEX", "CAPEX", "GENERAL"]:
        c_cat = "OPEX" if t_type == "EXPENSE" else "GENERAL"
    if dept not in ["RESTAURANT", "PICKLEBALL", "GENERAL"]:
        dept = "GENERAL"

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
        payload.payment_method or "CASH",
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

    return {
        "status": "SUCCESS",
        "message": f"Đã lập {('Phiếu Chi' if t_type == 'EXPENSE' else 'Phiếu Thu')} [{trans_code}] thành công!",
        "transaction": created
    }

@router.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, request: Request):
    """Xóa phiếu Thu/Chi (chỉ ADMIN và SUPER_ADMIN mới có quyền xóa)."""
    user = require_api_auth(request, allowed_roles=["ADMIN", "SUPER_ADMIN"])

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT transaction_code FROM accounting_transactions WHERE id = ?", (transaction_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu cần xóa.")

    code = row["transaction_code"]
    cursor.execute("DELETE FROM accounting_transactions WHERE id = ?", (transaction_id,))
    conn.commit()
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
    """Tổng hợp nhanh dòng tiền hôm nay cho Thu ngân và Sân Pick."""
    user = require_api_auth(request, allowed_roles=["ADMIN", "SUPER_ADMIN", "CASHIER", "PICKLEBALL"])
    
    today = datetime.now().strftime("%Y-%m-%d")
    today_start = f"{today} 00:00:00"
    today_end = f"{today} 23:59:59"

    conn = get_db()
    cursor = conn.cursor()

    # Doanh thu bán hàng POS hôm nay
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN payment_method = 'CASH' THEN total ELSE 0 END), 0) as pos_cash,
            COALESCE(SUM(CASE WHEN payment_method != 'CASH' THEN total ELSE 0 END), 0) as pos_transfer,
            COALESCE(SUM(total), 0) as pos_total
        FROM orders
        WHERE payment_status = 'PAID' AND completed_at BETWEEN ? AND ?
    """, (today_start, today_end))
    pos_row = cursor.fetchone()

    # Chi OPEX & CAPEX hôm nay từ sổ quỹ
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN cost_category = 'OPEX' THEN amount ELSE 0 END), 0) as opex_today,
            COALESCE(SUM(CASE WHEN cost_category = 'CAPEX' THEN amount ELSE 0 END), 0) as capex_today,
            COALESCE(SUM(CASE WHEN payment_method = 'CASH' THEN amount ELSE 0 END), 0) as cash_expense_today
        FROM accounting_transactions
        WHERE transaction_type = 'EXPENSE' AND DATE(created_at) = ?
    """, (today,))
    exp_row = cursor.fetchone()

    # Thu ngoài hôm nay
    cursor.execute("""
        SELECT 
            COALESCE(SUM(amount), 0) as inc_today,
            COALESCE(SUM(CASE WHEN payment_method = 'CASH' THEN amount ELSE 0 END), 0) as cash_inc_today
        FROM accounting_transactions
        WHERE transaction_type = 'INCOME' AND DATE(created_at) = ?
    """, (today,))
    inc_row = cursor.fetchone()

    conn.close()

    pos_cash = pos_row["pos_cash"] or 0
    cash_expense = exp_row["cash_expense_today"] or 0
    cash_inc = inc_row["cash_inc_today"] or 0
    estimated_cash_drawer = pos_cash + cash_inc - cash_expense

    return {
        "status": "SUCCESS",
        "date": today,
        "revenue_today": pos_row["pos_total"] or 0,
        "pos_cash": pos_cash,
        "pos_transfer": pos_row["pos_transfer"] or 0,
        "opex_today": exp_row["opex_today"] or 0,
        "capex_today": exp_row["capex_today"] or 0,
        "other_income_today": inc_row["inc_today"] or 0,
        "estimated_cash_drawer": estimated_cash_drawer
    }
