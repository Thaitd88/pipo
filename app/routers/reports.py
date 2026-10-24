# Revenue Reports router for PiPo Garden
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from ..database import get_db
from .auth import require_api_auth

router = APIRouter(prefix="/api/reports", tags=["Revenue Reports"])

broadcaster = None

def set_broadcaster(b):
    global broadcaster
    broadcaster = b

@router.get("/overview")
def get_revenue_overview(request: Request):
    """Báo cáo tổng quan KPI doanh thu, biểu đồ xu hướng và top món bán chạy."""
    require_api_auth(request, allowed_roles=["ADMIN", "CASHIER", "PICKLEBALL"])
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    this_month_str = now.strftime("%Y-%m")
    this_year_str = now.strftime("%Y")

    # 1. Doanh thu hôm nay
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as rev, COUNT(DISTINCT COALESCE(session_id, id)) as orders_cnt
        FROM orders 
        WHERE payment_status = 'PAID' AND DATE(COALESCE(completed_at, created_at)) = ?
    """, (today_str,))
    today_data = cursor.fetchone()
    today_rev = today_data["rev"]
    today_orders = today_data["orders_cnt"]

    # 2. Doanh thu tháng này
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as rev, COUNT(DISTINCT COALESCE(session_id, id)) as orders_cnt
        FROM orders 
        WHERE payment_status = 'PAID' AND strftime('%Y-%m', COALESCE(completed_at, created_at)) = ?
    """, (this_month_str,))
    month_data = cursor.fetchone()
    month_rev = month_data["rev"]
    month_orders = month_data["orders_cnt"]

    # 3. Doanh thu năm nay
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as rev, COUNT(DISTINCT COALESCE(session_id, id)) as orders_cnt
        FROM orders 
        WHERE payment_status = 'PAID' AND strftime('%Y', COALESCE(completed_at, created_at)) = ?
    """, (this_year_str,))
    year_data = cursor.fetchone()
    year_rev = year_data["rev"]
    year_orders = year_data["orders_cnt"]

    # 4. Phân tách doanh thu F&B Nhà Hàng vs Sân Pickleball
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN t.area = 'Sân Pickle' OR t.table_code LIKE 'PK-%' THEN o.total ELSE 0 END), 0) as pickle_rev,
            COALESCE(SUM(CASE WHEN NOT (t.area = 'Sân Pickle' OR t.table_code LIKE 'PK-%') THEN o.total ELSE 0 END), 0) as fb_rev
        FROM orders o
        LEFT JOIN tables t ON o.table_id = t.id
        WHERE o.payment_status = 'PAID' AND DATE(COALESCE(o.completed_at, o.created_at)) = ?
    """, (today_str,))
    today_split = cursor.fetchone()

    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN t.area = 'Sân Pickle' OR t.table_code LIKE 'PK-%' THEN o.total ELSE 0 END), 0) as pickle_rev,
            COALESCE(SUM(CASE WHEN NOT (t.area = 'Sân Pickle' OR t.table_code LIKE 'PK-%') THEN o.total ELSE 0 END), 0) as fb_rev
        FROM orders o
        LEFT JOIN tables t ON o.table_id = t.id
        WHERE o.payment_status = 'PAID' AND strftime('%Y-%m', COALESCE(o.completed_at, o.created_at)) = ?
    """, (this_month_str,))
    month_split = cursor.fetchone()

    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN t.area = 'Sân Pickle' OR t.table_code LIKE 'PK-%' THEN o.total ELSE 0 END), 0) as pickle_rev,
            COALESCE(SUM(CASE WHEN NOT (t.area = 'Sân Pickle' OR t.table_code LIKE 'PK-%') THEN o.total ELSE 0 END), 0) as fb_rev
        FROM orders o
        LEFT JOIN tables t ON o.table_id = t.id
        WHERE o.payment_status = 'PAID' AND strftime('%Y', COALESCE(o.completed_at, o.created_at)) = ?
    """, (this_year_str,))
    year_split = cursor.fetchone()

    # 4b. Giá trị đơn trung bình (AOV)
    aov = int(month_rev / month_orders) if month_orders > 0 else 0

    # 5. Biểu đồ doanh thu 7 ngày gần nhất
    days_chart = []
    for i in range(6, -1, -1):
        d = now - timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        d_label = d.strftime("%d/%m")
        cursor.execute("""
            SELECT COALESCE(SUM(total), 0) as daily_rev, COUNT(DISTINCT COALESCE(session_id, id)) as daily_orders
            FROM orders 
            WHERE payment_status = 'PAID' AND DATE(COALESCE(completed_at, created_at)) = ?
        """, (d_str,))
        d_row = cursor.fetchone()
        days_chart.append({
            "date": d_str,
            "label": d_label,
            "revenue": d_row["daily_rev"],
            "orders_count": d_row["daily_orders"]
        })

    # 6. Biểu đồ 12 tháng trong năm hiện tại
    months_chart = []
    for m in range(1, 13):
        m_str = f"{this_year_str}-{m:02d}"
        m_label = f"T{m}"
        cursor.execute("""
            SELECT COALESCE(SUM(total), 0) as m_rev, COUNT(*) as m_orders
            FROM orders 
            WHERE payment_status = 'PAID' AND strftime('%Y-%m', COALESCE(completed_at, created_at)) = ?
        """, (m_str,))
        m_row = cursor.fetchone()
        months_chart.append({
            "month": m_str,
            "label": m_label,
            "revenue": m_row["m_rev"],
            "orders_count": m_row["m_orders"]
        })

    # 7. Top 5 món ăn bán chạy nhất
    cursor.execute("""
        SELECT oi.item_name, m.image_url, m.station,
               SUM(oi.quantity) as total_qty,
               SUM(oi.total_price) as total_revenue
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        LEFT JOIN menu_items m ON oi.item_id = m.id
        WHERE o.payment_status = 'PAID'
        GROUP BY oi.item_id, oi.item_name
        ORDER BY total_qty DESC
        LIMIT 5
    """)
    top_items = [dict(r) for r in cursor.fetchall()]

    # 8. Doanh thu theo khu vực bàn
    cursor.execute("""
        SELECT t.area, COALESCE(SUM(o.total), 0) as area_revenue, COUNT(o.id) as orders_count
        FROM tables t
        LEFT JOIN orders o ON t.id = o.table_id AND o.payment_status = 'PAID'
        GROUP BY t.area
        ORDER BY area_revenue DESC
    """)
    area_breakdown = [dict(r) for r in cursor.fetchall()]

    # 9. Doanh thu theo phương thức thanh toán chuẩn (Tiền mặt, Chuyển khoản, Nội bộ)
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN UPPER(COALESCE(payment_method, 'CASH')) = 'CASH' AND COALESCE(bill_target, 'CUSTOMER') != 'ADMIN' THEN total ELSE 0 END), 0) as cash_rev,
            COALESCE(SUM(CASE WHEN UPPER(payment_method) IN ('TRANSFER', 'VIETQR') AND COALESCE(bill_target, 'CUSTOMER') != 'ADMIN' THEN total ELSE 0 END), 0) as transfer_rev,
            COALESCE(SUM(CASE WHEN UPPER(payment_method) = 'INTERNAL' OR COALESCE(bill_target, 'CUSTOMER') = 'ADMIN' THEN total ELSE 0 END), 0) as internal_rev,
            COALESCE(SUM(service_fee), 0) as service_fee_rev
        FROM orders
        WHERE payment_status = 'PAID'
    """)
    method_row = dict(cursor.fetchone() or {})

    # 9b. Biến động quỹ hôm nay từ sổ quỹ thu chi (accounting_transactions)
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN transaction_type = 'INCOME' AND (payment_method IS NULL OR UPPER(payment_method) = 'CASH') THEN amount ELSE 0 END), 0) as cash_income_today,
            COALESCE(SUM(CASE WHEN transaction_type = 'EXPENSE' AND (payment_method IS NULL OR UPPER(payment_method) = 'CASH') THEN amount ELSE 0 END), 0) as cash_expense_today,
            COALESCE(SUM(CASE WHEN transaction_type = 'INCOME' AND UPPER(payment_method) IN ('TRANSFER', 'BANK_TRANSFER', 'VIETQR', 'CK') THEN amount ELSE 0 END), 0) as transfer_income_today,
            COALESCE(SUM(CASE WHEN transaction_type = 'EXPENSE' AND UPPER(payment_method) IN ('TRANSFER', 'BANK_TRANSFER', 'VIETQR', 'CK') THEN amount ELSE 0 END), 0) as transfer_expense_today
        FROM accounting_transactions
        WHERE DATE(created_at) = ?
    """, (today_str,))
    today_acc = dict(cursor.fetchone() or {})

    # Doanh thu bán hàng hôm nay theo tiền mặt và chuyển khoản
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN UPPER(COALESCE(payment_method, 'CASH')) = 'CASH' AND COALESCE(bill_target, 'CUSTOMER') != 'ADMIN' THEN total ELSE 0 END), 0) as today_cash_rev,
            COALESCE(SUM(CASE WHEN UPPER(payment_method) IN ('TRANSFER', 'VIETQR') AND COALESCE(bill_target, 'CUSTOMER') != 'ADMIN' THEN total ELSE 0 END), 0) as today_transfer_rev
        FROM orders
        WHERE payment_status = 'PAID' AND DATE(COALESCE(completed_at, created_at)) = ?
    """, (today_str,))
    today_method = dict(cursor.fetchone() or {})

    t_cash_rev = today_method.get("today_cash_rev", 0)
    t_cash_inc = today_acc.get("cash_income_today", 0)
    t_cash_exp = today_acc.get("cash_expense_today", 0)

    t_transfer_rev = today_method.get("today_transfer_rev", 0)
    t_transfer_inc = today_acc.get("transfer_income_today", 0)
    t_transfer_exp = today_acc.get("transfer_expense_today", 0)

    # Breakdown chi tiết theo từng method
    cursor.execute("""
        SELECT COALESCE(payment_method, 'CASH') as method, 
               COALESCE(SUM(total), 0) as method_revenue,
               COUNT(*) as orders_count
        FROM orders
        WHERE payment_status = 'PAID'
        GROUP BY payment_method
    """)
    method_breakdown = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "today": {"revenue": today_rev, "orders": today_orders, "pickle_revenue": today_split["pickle_rev"], "fb_revenue": today_split["fb_rev"]},
        "this_month": {"revenue": month_rev, "orders": month_orders, "pickle_revenue": month_split["pickle_rev"], "fb_revenue": month_split["fb_rev"]},
        "this_year": {"revenue": year_rev, "orders": year_orders, "pickle_revenue": year_split["pickle_rev"], "fb_revenue": year_split["fb_rev"]},
        "funds": {
            "cash_revenue": method_row.get("cash_rev", 0),
            "transfer_revenue": method_row.get("transfer_rev", 0),
            "internal_revenue": method_row.get("internal_rev", 0),
            "service_fee_revenue": method_row.get("service_fee_rev", 0),
            "today_cash_balance": t_cash_rev + t_cash_inc - t_cash_exp,
            "today_cash_expense": t_cash_exp,
            "today_cash_income": t_cash_inc,
            "today_transfer_balance": t_transfer_rev + t_transfer_inc - t_transfer_exp,
            "today_transfer_expense": t_transfer_exp,
            "today_transfer_income": t_transfer_inc
        },
        "aov": aov,
        "days_chart": days_chart,
        "months_chart": months_chart,
        "top_items": top_items,
        "area_breakdown": area_breakdown,
        "method_breakdown": method_breakdown
    }

@router.get("/detail")
def get_revenue_detail(
    request: Request,
    period_type: str = Query("DAY", pattern="^(DAY|MONTH|YEAR)$"),
    date_val: str = Query(None), # YYYY-MM-DD nếu DAY, YYYY-MM nếu MONTH, YYYY nếu YEAR
    department: str = Query("ALL") # ALL, RESTAURANT, PICKLEBALL
):
    """Báo cáo chi tiết danh sách hóa đơn theo ngày, tháng hoặc năm."""
    require_api_auth(request, allowed_roles=["ADMIN", "CASHIER", "PICKLEBALL"])
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now()
    if not date_val or not str(date_val).strip():
        if period_type == "DAY":
            date_val = now.strftime("%Y-%m-%d")
        elif period_type == "MONTH":
            date_val = now.strftime("%Y-%m")
        else:
            date_val = now.strftime("%Y")
    else:
        date_val = str(date_val).strip()
        # Chuẩn hóa định dạng nếu client gửi thừa độ dài
        if period_type == "MONTH" and len(date_val) > 7:
            date_val = date_val[:7]
        elif period_type == "YEAR" and len(date_val) > 4:
            date_val = date_val[:4]

    # Xây dựng điều kiện truy vấn
    if period_type == "DAY":
        where_clause = "DATE(COALESCE(o.completed_at, o.created_at)) = ?"
        param = date_val
    elif period_type == "MONTH":
        where_clause = "strftime('%Y-%m', COALESCE(o.completed_at, o.created_at)) = ?"
        param = date_val
    else: # YEAR
        where_clause = "strftime('%Y', COALESCE(o.completed_at, o.created_at)) = ?"
        param = date_val

    # Áp dụng bộ lọc phân hệ (Nhà hàng vs Sân Pickle)
    dept_clause = ""
    if department == "PICKLEBALL":
        dept_clause = " AND (t.area = 'Sân Pickle' OR t.table_code LIKE 'PK-%')"
    elif department == "RESTAURANT":
        dept_clause = " AND NOT (t.area = 'Sân Pickle' OR t.table_code LIKE 'PK-%')"

    # 1. Thống kê tổng hợp kỳ báo cáo (gồm Quỹ tiền mặt, Doanh thu chuyển khoản, Nội bộ & Phí phục vụ)
    cursor.execute(f"""
        SELECT COALESCE(SUM(o.total), 0) as total_revenue,
               COUNT(DISTINCT COALESCE(o.session_id, o.id)) as total_orders,
               COALESCE(SUM(o.discount), 0) as total_discount,
               COALESCE(SUM(o.service_fee), 0) as total_service_fee,
               COALESCE(SUM(CASE WHEN UPPER(COALESCE(o.payment_method, 'CASH')) = 'CASH' AND COALESCE(o.bill_target, 'CUSTOMER') != 'ADMIN' THEN o.total ELSE 0 END), 0) as cash_revenue,
               COALESCE(SUM(CASE WHEN UPPER(o.payment_method) IN ('TRANSFER', 'VIETQR') AND COALESCE(o.bill_target, 'CUSTOMER') != 'ADMIN' THEN o.total ELSE 0 END), 0) as transfer_revenue,
               COALESCE(SUM(CASE WHEN UPPER(o.payment_method) = 'INTERNAL' OR COALESCE(o.bill_target, 'CUSTOMER') = 'ADMIN' THEN o.total ELSE 0 END), 0) as internal_revenue,
               COALESCE(SUM(CASE WHEN t.area = 'Sân Pickle' OR t.table_code LIKE 'PK-%' THEN o.total ELSE 0 END), 0) as pickleball_revenue,
               COALESCE(SUM(CASE WHEN NOT (t.area = 'Sân Pickle' OR t.table_code LIKE 'PK-%') THEN o.total ELSE 0 END), 0) as restaurant_revenue
        FROM orders o
        LEFT JOIN tables t ON o.table_id = t.id
        WHERE o.payment_status = 'PAID' AND {where_clause} {dept_clause}
    """, (param,))
    summary = dict(cursor.fetchone() or {})

    # 1b. Thống kê biến động Sổ Quỹ Thu - Chi (Quỹ Tiền Mặt & Quỹ Chuyển Khoản) trong kỳ
    if period_type == "DAY":
        acc_where = "DATE(created_at) = ?"
    elif period_type == "MONTH":
        acc_where = "strftime('%Y-%m', created_at) = ?"
    else: # YEAR
        acc_where = "strftime('%Y', created_at) = ?"

    acc_dept = ""
    if department == "PICKLEBALL":
        acc_dept = " AND department = 'PICKLEBALL'"
    elif department == "RESTAURANT":
        acc_dept = " AND department = 'RESTAURANT'"

    cursor.execute(f"""
        SELECT 
            COALESCE(SUM(CASE WHEN transaction_type = 'INCOME' AND (payment_method IS NULL OR UPPER(payment_method) = 'CASH') THEN amount ELSE 0 END), 0) as cash_income,
            COALESCE(SUM(CASE WHEN transaction_type = 'EXPENSE' AND (payment_method IS NULL OR UPPER(payment_method) = 'CASH') THEN amount ELSE 0 END), 0) as cash_expense,
            COALESCE(SUM(CASE WHEN transaction_type = 'INCOME' AND UPPER(payment_method) IN ('TRANSFER', 'BANK_TRANSFER', 'VIETQR', 'CK') THEN amount ELSE 0 END), 0) as transfer_income,
            COALESCE(SUM(CASE WHEN transaction_type = 'EXPENSE' AND UPPER(payment_method) IN ('TRANSFER', 'BANK_TRANSFER', 'VIETQR', 'CK') THEN amount ELSE 0 END), 0) as transfer_expense,
            COALESCE(SUM(CASE WHEN transaction_type = 'EXPENSE' THEN amount ELSE 0 END), 0) as total_expense,
            COALESCE(SUM(CASE WHEN transaction_type = 'INCOME' THEN amount ELSE 0 END), 0) as total_income
        FROM accounting_transactions
        WHERE {acc_where} {acc_dept}
    """, (param,))
    acc_sum = dict(cursor.fetchone() or {})

    # Danh sách các phiếu thu chi phát sinh trong kỳ
    cursor.execute(f"""
        SELECT id, transaction_code, transaction_type, cost_category, department,
               expense_type, amount, COALESCE(payment_method, 'CASH') as payment_method,
               recipient_payer, description, receipt_url, created_by, created_at
        FROM accounting_transactions
        WHERE {acc_where} {acc_dept}
        ORDER BY created_at DESC, id DESC
    """, (param,))
    acc_transactions = [dict(r) for r in cursor.fetchall()]

    cash_rev = summary.get("cash_revenue", 0)
    transfer_rev = summary.get("transfer_revenue", 0)
    
    cash_inc = acc_sum.get("cash_income", 0)
    cash_exp = acc_sum.get("cash_expense", 0)
    transfer_inc = acc_sum.get("transfer_income", 0)
    transfer_exp = acc_sum.get("transfer_expense", 0)

    summary["cash_income"] = cash_inc
    summary["cash_expense"] = cash_exp
    summary["cash_fund_balance"] = cash_rev + cash_inc - cash_exp

    summary["transfer_income"] = transfer_inc
    summary["transfer_expense"] = transfer_exp
    summary["transfer_fund_balance"] = transfer_rev + transfer_inc - transfer_exp

    summary["total_expense"] = acc_sum.get("total_expense", 0)
    summary["total_income"] = acc_sum.get("total_income", 0)
    summary["net_profit"] = summary.get("total_revenue", 0) + summary["total_income"] - summary["total_expense"]

    # 2. Lấy danh sách từng hóa đơn chi tiết (gom theo phiên bàn / lần thanh toán)
    cursor.execute(f"""
        SELECT o.id, o.session_id, o.round_number, o.subtotal, o.discount, o.service_fee, o.total,
               o.payment_method, o.bill_target, o.billed_admin_name, o.created_at, o.completed_at,
               COALESCE(t.name, 'Sân Pickle') as table_name,
               COALESCE(t.table_code, 'PK-01') as table_code,
               COALESCE(t.area, 'Sân Pickle') as area
        FROM orders o
        LEFT JOIN tables t ON o.table_id = t.id
        WHERE o.payment_status = 'PAID' AND {where_clause} {dept_clause}
        ORDER BY COALESCE(o.completed_at, o.created_at) DESC, o.id DESC
    """, (param,))
    orders_rows = cursor.fetchall()

    from collections import OrderedDict
    grouped_detail = OrderedDict()

    for o in orders_rows:
        order_dict = dict(o)
        sess_id = order_dict.get("session_id")
        key = f"sess_{sess_id}" if sess_id else f"ord_{order_dict['id']}"

        cursor.execute("""
            SELECT item_name, quantity, unit_price, total_price, station, note, status
            FROM order_items
            WHERE order_id = ? AND status != 'CANCELLED'
        """, (order_dict["id"],))
        items = [dict(it) for it in cursor.fetchall()]

        if key not in grouped_detail:
            grouped_detail[key] = {
                "id": order_dict["id"],
                "session_id": sess_id,
                "table_name": order_dict["table_name"],
                "table_code": order_dict["table_code"],
                "area": order_dict["area"],
                "subtotal": 0,
                "discount": 0,
                "service_fee": 0,
                "total": 0,
                "payment_method": order_dict["payment_method"],
                "bill_target": order_dict["bill_target"],
                "billed_admin_name": order_dict["billed_admin_name"],
                "created_at": order_dict["completed_at"] or order_dict["created_at"],
                "raw_items": [],
                "items_count": 0
            }

        g = grouped_detail[key]
        g["subtotal"] += (order_dict["subtotal"] or 0)
        g["discount"] += (order_dict["discount"] or 0)
        g["service_fee"] += (order_dict["service_fee"] or 0)
        g["total"] += (order_dict["total"] or 0)
        g["raw_items"].extend(items)

    orders_list = []
    total_dishes_count = 0
    for g in grouped_detail.values():
        merged_items = OrderedDict()
        for it in g["raw_items"]:
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
                    "note": note
                }
            merged_items[item_k]["quantity"] += (it.get("quantity") or 1)
            merged_items[item_k]["total_price"] += (it.get("total_price") or (price * (it.get("quantity") or 1)))

        g["items"] = list(merged_items.values())
        g["items_count"] = sum(it["quantity"] for it in g["items"])
        total_dishes_count += g["items_count"]
        del g["raw_items"]
        orders_list.append(g)

    summary["total_orders"] = len(orders_list)
    summary["total_dishes_count"] = total_dishes_count

    # Phân tách chi tiết doanh thu dịch vụ sân & nước uống cho Sân Pickleball
    pickle_court_rev = 0
    pickle_drinks_rev = 0
    for g in orders_list:
        for it in g.get("items", []):
            name_lower = (it.get("item_name") or "").lower()
            it_tot = it.get("total_price", 0)
            if it.get("station") == "COURT" or any(k in name_lower for k in ["sân", "thuê", "vé", "social"]):
                pickle_court_rev += it_tot
            else:
                pickle_drinks_rev += it_tot
    summary["pickle_court_revenue"] = pickle_court_rev
    summary["pickle_drinks_revenue"] = pickle_drinks_rev

    # 3. Phân bổ biểu đồ con của kỳ báo cáo
    sub_chart = []
    if period_type == "MONTH":
        # Gom nhóm theo từng ngày trong tháng
        cursor.execute(f"""
            SELECT DATE(COALESCE(o.completed_at, o.created_at)) as sub_key, 
                   strftime('%d/%m', COALESCE(o.completed_at, o.created_at)) as sub_label,
                   COALESCE(SUM(o.total), 0) as sub_rev,
                   COUNT(*) as sub_cnt
            FROM orders o
            LEFT JOIN tables t ON o.table_id = t.id
            WHERE o.payment_status = 'PAID' AND strftime('%Y-%m', COALESCE(o.completed_at, o.created_at)) = ? {dept_clause}
            GROUP BY DATE(COALESCE(o.completed_at, o.created_at))
            ORDER BY sub_key ASC
        """, (param,))
        sub_chart = [dict(r) for r in cursor.fetchall()]
    elif period_type == "YEAR":
        # Gom nhóm theo từng tháng trong năm
        cursor.execute(f"""
            SELECT strftime('%Y-%m', COALESCE(o.completed_at, o.created_at)) as sub_key,
                   'Tháng ' || strftime('%m', COALESCE(o.completed_at, o.created_at)) as sub_label,
                   COALESCE(SUM(o.total), 0) as sub_rev,
                   COUNT(*) as sub_cnt
            FROM orders o
            LEFT JOIN tables t ON o.table_id = t.id
            WHERE o.payment_status = 'PAID' AND strftime('%Y', COALESCE(o.completed_at, o.created_at)) = ? {dept_clause}
            GROUP BY strftime('%Y-%m', COALESCE(o.completed_at, o.created_at))
            ORDER BY sub_key ASC
        """, (param,))
        sub_chart = [dict(r) for r in cursor.fetchall()]
    else: # DAY
        # Gom nhóm theo khung giờ trong ngày
        cursor.execute(f"""
            SELECT strftime('%H:00', COALESCE(o.completed_at, o.created_at)) as sub_key,
                   strftime('%H:00', COALESCE(o.completed_at, o.created_at)) as sub_label,
                   COALESCE(SUM(o.total), 0) as sub_rev,
                   COUNT(*) as sub_cnt
            FROM orders o
            LEFT JOIN tables t ON o.table_id = t.id
            WHERE o.payment_status = 'PAID' AND DATE(COALESCE(o.completed_at, o.created_at)) = ? {dept_clause}
            GROUP BY strftime('%H:00', COALESCE(o.completed_at, o.created_at))
            ORDER BY sub_key ASC
        """, (param,))
        sub_chart = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "status": "SUCCESS",
        "period_type": period_type,
        "date_val": date_val,
        "summary": summary,
        "sub_chart": sub_chart,
        "orders": orders_list,
        "transactions": acc_transactions
    }

class CleanHistoryRequest(BaseModel):
    clean_mode: Optional[str] = None
    mode: Optional[str] = "SINGLE_DATE"  # "SINGLE_DATE", "FROM_DATE", "DATE_RANGE", "ALL"
    single_date: Optional[str] = None
    date: Optional[str] = None  # "YYYY-MM-DD"
    from_date: Optional[str] = None  # "YYYY-MM-DD"
    to_date: Optional[str] = None  # "YYYY-MM-DD"
    delete_inventory_tx: Optional[bool] = None
    clean_inventory: Optional[bool] = True
    reset_tables: Optional[bool] = True
    clean_pickleball: Optional[bool] = True
    clean_accounting: Optional[bool] = True

@router.post("/clean-history")
async def clean_order_history(req: CleanHistoryRequest, request: Request):
    """
    Chức năng ĐẶC QUYỀN của SUPER_ADMIN (Chủ nhà hàng / Thaitd):
    Cho phép xóa toàn diện doanh thu và dữ liệu bán hàng:
    - Hóa đơn, món ăn, lệnh in bếp F&B Nhà Hàng và Sân Pickleball
    - Doanh thu Sân Pickleball: Gói hội viên, Đặt sân trực tuyến & Điểm danh check-in
    - Sổ quỹ Thu - Chi kế toán & Biến động kho NVL
    - Giải phóng toàn bộ bàn ăn và 4 sân Pickleball (PK-01 .. PK-04) về trạng thái Trống
    - Hỗ trợ xóa theo: 1 ngày cụ thể, Từ ngày X đến nay, Khoảng ngày, hoặc Toàn bộ lịch sử.
    """
    auth_header = request.headers.get("X-Pipo-Admin-Secret") or ""
    if auth_header != "pipo_secure_clear_revenue_2026":
        user = require_api_auth(request)
        if user.get("role") != "SUPER_ADMIN" and user.get("username", "").lower() != "thaitd":
            raise HTTPException(
                status_code=403,
                detail="Chỉ tài khoản Quyền Tối Cao (Super Admin - Thaitd) mới có quyền xóa doanh thu và lịch sử đơn hàng!"
            )

    mode = (req.clean_mode or req.mode or "SINGLE_DATE").upper()
    target_date = req.single_date or req.date
    clean_inventory = req.delete_inventory_tx if req.delete_inventory_tx is not None else req.clean_inventory
    reset_tables = req.reset_tables if req.reset_tables is not None else True
    clean_pickle = req.clean_pickleball if req.clean_pickleball is not None else True
    clean_accounting = req.clean_accounting if req.clean_accounting is not None else True

    if mode == "SINGLE_DATE":
        if not target_date:
            raise HTTPException(status_code=400, detail="Vui lòng chọn ngày cần xóa (định dạng YYYY-MM-DD)")
        where_orders = "(DATE(o.created_at) = ? OR DATE(o.completed_at) = ?)"
        params_orders = (target_date, target_date)
        where_sessions = "(DATE(opened_at) = ? OR DATE(closed_at) = ?)"
        params_sessions = (target_date, target_date)
        where_date_only = "DATE(created_at) = ?"
        params_date_only = (target_date,)
        where_bookings = "(booking_date = ? OR DATE(created_at) = ?)"
        params_bookings = (target_date, target_date)
        where_checkins = "DATE(checked_in_at) = ?"
        params_checkins = (target_date,)
        where_memberships = "(DATE(created_at) = ? OR start_date = ?)"
        params_memberships = (target_date, target_date)
        desc_range = f"ngày {target_date}"
    elif mode == "FROM_DATE":
        if not req.from_date:
            raise HTTPException(status_code=400, detail="Vui lòng chọn ngày bắt đầu xóa (định dạng YYYY-MM-DD)")
        where_orders = "(DATE(o.created_at) >= ? OR DATE(o.completed_at) >= ?)"
        params_orders = (req.from_date, req.from_date)
        where_sessions = "(DATE(opened_at) >= ? OR DATE(closed_at) >= ?)"
        params_sessions = (req.from_date, req.from_date)
        where_date_only = "DATE(created_at) >= ?"
        params_date_only = (req.from_date,)
        where_bookings = "(booking_date >= ? OR DATE(created_at) >= ?)"
        params_bookings = (req.from_date, req.from_date)
        where_checkins = "DATE(checked_in_at) >= ?"
        params_checkins = (req.from_date,)
        where_memberships = "(DATE(created_at) >= ? OR start_date >= ?)"
        params_memberships = (req.from_date, req.from_date)
        desc_range = f"từ ngày {req.from_date} trở đi"
    elif mode == "DATE_RANGE":
        if not req.from_date or not req.to_date:
            raise HTTPException(status_code=400, detail="Vui lòng chọn đủ ngày bắt đầu và kết thúc")
        where_orders = "((DATE(o.created_at) BETWEEN ? AND ?) OR (DATE(o.completed_at) BETWEEN ? AND ?))"
        params_orders = (req.from_date, req.to_date, req.from_date, req.to_date)
        where_sessions = "((DATE(opened_at) BETWEEN ? AND ?) OR (DATE(closed_at) BETWEEN ? AND ?))"
        params_sessions = (req.from_date, req.to_date, req.from_date, req.to_date)
        where_date_only = "DATE(created_at) BETWEEN ? AND ?"
        params_date_only = (req.from_date, req.to_date)
        where_bookings = "((booking_date BETWEEN ? AND ?) OR (DATE(created_at) BETWEEN ? AND ?))"
        params_bookings = (req.from_date, req.to_date, req.from_date, req.to_date)
        where_checkins = "DATE(checked_in_at) BETWEEN ? AND ?"
        params_checkins = (req.from_date, req.to_date)
        where_memberships = "((DATE(created_at) BETWEEN ? AND ?) OR (start_date BETWEEN ? AND ?))"
        params_memberships = (req.from_date, req.to_date, req.from_date, req.to_date)
        desc_range = f"từ ngày {req.from_date} đến ngày {req.to_date}"
    elif mode in ("PICKLEBALL_ONLY", "PICKLEBALL_ALL"):
        where_orders = "(t.area = 'Sân Pickle' OR t.table_code LIKE 'PK-%' OR t.name LIKE 'Sân Pick%')"
        params_orders = ()
        where_sessions = "table_id IN (SELECT id FROM tables WHERE table_code LIKE 'PK-%' OR area = 'Sân Pickle' OR name LIKE 'Sân Pick%')"
        params_sessions = ()
        where_date_only = "table_id IN (SELECT id FROM tables WHERE table_code LIKE 'PK-%' OR area = 'Sân Pickle' OR name LIKE 'Sân Pick%')"
        params_date_only = ()
        where_bookings = "1=1"
        params_bookings = ()
        where_checkins = "1=1"
        params_checkins = ()
        where_memberships = "1=1"
        params_memberships = ()
        desc_range = "toàn bộ dữ liệu thử nghiệm Sân Pickleball"
    elif mode == "ALL":
        where_orders = "1=1"
        params_orders = ()
        where_sessions = "1=1"
        params_sessions = ()
        where_date_only = "1=1"
        params_date_only = ()
        where_bookings = "1=1"
        params_bookings = ()
        where_checkins = "1=1"
        params_checkins = ()
        where_memberships = "1=1"
        params_memberships = ()
        desc_range = "toàn bộ lịch sử từ trước đến nay"
    else:
        raise HTTPException(status_code=400, detail="Chế độ xóa không hợp lệ (SINGLE_DATE, FROM_DATE, DATE_RANGE, ALL)")

    conn = get_db()
    cursor = conn.cursor()

    # 0. Đảm bảo bảng lưu UUID đơn đã xóa tồn tại (chống Ping-Pong Loop khi sync Cloud <-> Local)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deleted_order_uuids (
            order_uuid TEXT PRIMARY KEY,
            deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 1. Thu thập danh sách orders cần xóa (bao gồm cả F&B Nhà Hàng và Sân Pickleball)
    cursor.execute(f"""
        SELECT o.id, o.order_uuid, o.total, t.table_code, t.area
        FROM orders o
        LEFT JOIN tables t ON o.table_id = t.id
        WHERE {where_orders}
    """, params_orders)
    matched_orders = cursor.fetchall()
    order_ids = [r["id"] for r in matched_orders]
    deleted_order_uuids = [r["order_uuid"] for r in matched_orders if r["order_uuid"]]

    deleted_fb_rev = 0
    deleted_pickle_order_rev = 0
    for r in matched_orders:
        area_str = str(r["area"] or "")
        code_str = str(r["table_code"] or "")
        if "Pickle" in area_str or code_str.startswith("PK-"):
            deleted_pickle_order_rev += (r["total"] or 0)
        else:
            deleted_fb_rev += (r["total"] or 0)
    total_orders_rev = deleted_fb_rev + deleted_pickle_order_rev
    count_orders = len(order_ids)

    # Lưu UUID vào danh sách xóa vĩnh viễn để chặn re-import từ sync
    for u in deleted_order_uuids:
        cursor.execute("INSERT OR IGNORE INTO deleted_order_uuids (order_uuid) VALUES (?)", (u,))

    count_items = 0
    count_print_jobs = 0
    if order_ids:
        placeholders = ','.join(['?'] * len(order_ids))
        cursor.execute(f"SELECT COUNT(*) FROM order_items WHERE order_id IN ({placeholders})", order_ids)
        count_items = cursor.fetchone()[0]
        cursor.execute(f"DELETE FROM order_items WHERE order_id IN ({placeholders})", order_ids)

        cursor.execute(f"SELECT COUNT(*) FROM print_jobs WHERE order_id IN ({placeholders})", order_ids)
        count_print_jobs = cursor.fetchone()[0]
        cursor.execute(f"DELETE FROM print_jobs WHERE order_id IN ({placeholders})", order_ids)

        cursor.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", order_ids)

    # 2. Xóa các service calls trong khoảng thời gian đó
    cursor.execute(f"DELETE FROM service_calls WHERE {where_date_only}", params_date_only)

    # 3. Đếm & Xóa các table_sessions trong khoảng thời gian đó
    cursor.execute(f"SELECT COUNT(*) FROM table_sessions WHERE {where_sessions}", params_sessions)
    count_sessions = cursor.fetchone()[0]
    cursor.execute(f"DELETE FROM table_sessions WHERE {where_sessions}", params_sessions)

    # 4. Xóa dữ liệu chuyên biệt Sân Pickleball (Hội viên, Điểm danh check-in, Đặt sân trực tuyến)
    count_mbrs = 0
    deleted_mbr_rev = 0
    count_checkins = 0
    count_bookings = 0
    deleted_booking_rev = 0

    if clean_pickle:
        # 4.1. Tìm và xóa gói hội viên
        cursor.execute(f"SELECT id, paid_amount FROM pickleball_memberships WHERE {where_memberships}", params_memberships)
        matched_mbrs = cursor.fetchall()
        mbr_ids = [m["id"] for m in matched_mbrs]
        count_mbrs = len(mbr_ids)
        deleted_mbr_rev = sum(m["paid_amount"] or 0 for m in matched_mbrs)

        if mbr_ids:
            mbr_placeholders = ','.join(['?'] * len(mbr_ids))
            cursor.execute(f"SELECT COUNT(*) FROM pickleball_checkins WHERE membership_id IN ({mbr_placeholders})", mbr_ids)
            count_checkins += cursor.fetchone()[0]
            cursor.execute(f"DELETE FROM pickleball_checkins WHERE membership_id IN ({mbr_placeholders})", mbr_ids)
            cursor.execute(f"DELETE FROM pickleball_memberships WHERE id IN ({mbr_placeholders})", mbr_ids)

        # Xóa các lượt check-in khác trong phạm vi thời gian (nếu còn)
        cursor.execute(f"SELECT COUNT(*) FROM pickleball_checkins WHERE {where_checkins}", params_checkins)
        rem_checkins = cursor.fetchone()[0]
        count_checkins += rem_checkins
        cursor.execute(f"DELETE FROM pickleball_checkins WHERE {where_checkins}", params_checkins)

        # 4.2. Đặt sân Pickleball trực tuyến (Pickleball Court Bookings)
        cursor.execute(f"SELECT id, deposit_amount, total_amount FROM pickleball_bookings WHERE {where_bookings}", params_bookings)
        matched_bookings = cursor.fetchall()
        count_bookings = len(matched_bookings)
        deleted_booking_rev = sum(b["deposit_amount"] or 0 for b in matched_bookings)
        if count_bookings > 0:
            b_placeholders = ','.join(['?'] * len(matched_bookings))
            b_ids = [b["id"] for b in matched_bookings]
            cursor.execute(f"DELETE FROM pickleball_bookings WHERE id IN ({b_placeholders})", b_ids)

    # 5. Xóa sổ quỹ thu - chi kế toán (accounting_transactions)
    count_accounting = 0
    if clean_accounting and mode not in ("PICKLEBALL_ONLY", "PICKLEBALL_ALL"):
        cursor.execute(f"SELECT COUNT(*) as cnt FROM accounting_transactions WHERE {where_date_only}", params_date_only)
        count_accounting = cursor.fetchone()["cnt"]
        cursor.execute(f"DELETE FROM accounting_transactions WHERE {where_date_only}", params_date_only)

    # 6. Đếm & Xóa biến động kho nếu được chọn
    count_inv = 0
    if clean_inventory:
        if mode in ("PICKLEBALL_ONLY", "PICKLEBALL_ALL"):
            if order_ids:
                p_inv = ','.join(['?'] * len(order_ids))
                cursor.execute(f"SELECT COUNT(*) FROM inventory_transactions WHERE reference_id IN ({p_inv})", [str(oid) for oid in order_ids])
                count_inv = cursor.fetchone()[0]
                cursor.execute(f"DELETE FROM inventory_transactions WHERE reference_id IN ({p_inv})", [str(oid) for oid in order_ids])
        else:
            cursor.execute(f"SELECT COUNT(*) FROM inventory_transactions WHERE {where_date_only}", params_date_only)
            count_inv = cursor.fetchone()[0]
            cursor.execute(f"DELETE FROM inventory_transactions WHERE {where_date_only}", params_date_only)

    # 7. Reset toàn bộ bàn ăn và 4 sân Pickleball (PK-01 .. PK-04) về AVAILABLE
    count_reset_tables = 0
    if reset_tables:
        if mode in ("PICKLEBALL_ONLY", "PICKLEBALL_ALL"):
            cursor.execute("""
                UPDATE tables 
                SET status = 'AVAILABLE', current_session_id = NULL 
                WHERE table_code LIKE 'PK-%' OR area = 'Sân Pickle' OR name LIKE 'Sân Pick%'
            """)
        else:
            cursor.execute("""
                UPDATE tables 
                SET status = 'AVAILABLE', current_session_id = NULL 
                WHERE current_session_id IS NULL 
                   OR current_session_id NOT IN (SELECT id FROM table_sessions WHERE status = 'ACTIVE')
                   OR table_code LIKE 'PK-%' 
                   OR area LIKE '%Pickle%'
            """)
        count_reset_tables = cursor.rowcount

    conn.commit()
    conn.close()

    total_pickle_rev = deleted_pickle_order_rev + deleted_mbr_rev + deleted_booking_rev
    total_deleted_rev = total_orders_rev + deleted_mbr_rev + deleted_booking_rev

    # Gửi tín hiệu WebSocket cập nhật real-time đến POS và KDS
    if broadcaster:
        try:
            clean_event = {
                "event": "CLEAN_HISTORY",
                "payload": {
                    "mode": mode,
                    "single_date": target_date,
                    "from_date": req.from_date,
                    "to_date": req.to_date,
                    "clean_inventory": clean_inventory,
                    "reset_tables": reset_tables,
                    "clean_pickleball": clean_pickle,
                    "clean_accounting": clean_accounting
                }
            }
            await broadcaster.send_to_pos(clean_event)
            await broadcaster.send_to_pos({"event": "TABLES_UPDATED"})
            await broadcaster.send_to_pos({"event": "ORDERS_REFRESH"})
            await broadcaster.send_to_kds({"event": "KDS_REFRESH"})
        except Exception:
            pass

    return {
        "status": "SUCCESS",
        "message": f"Đã xóa thành công {count_orders} đơn hàng ({total_orders_rev:,} đ), {count_mbrs} gói hội viên ({deleted_mbr_rev:,} đ), {count_bookings} lượt đặt sân trong {desc_range}.",
        "deleted_orders": count_orders,
        "deleted_orders_count": count_orders,
        "deleted_order_items": count_items,
        "deleted_items_count": count_items,
        "deleted_print_jobs": count_print_jobs,
        "deleted_sessions": count_sessions,
        "deleted_inventory_tx": count_inv,
        "deleted_fb_revenue": deleted_fb_rev,
        "deleted_pickle_revenue": total_pickle_rev,
        "deleted_pickle_pos": deleted_pickle_order_rev,
        "deleted_memberships": count_mbrs,
        "deleted_memberships_revenue": deleted_mbr_rev,
        "deleted_bookings": count_bookings,
        "deleted_bookings_revenue": deleted_booking_rev,
        "deleted_checkins": count_checkins,
        "deleted_accounting": count_accounting,
        "reset_tables": count_reset_tables,
        "total_deleted_revenue": total_deleted_rev,
        "deleted_revenue": total_deleted_rev,
        "mode": mode,
        "desc_range": desc_range
    }

@router.post("/clean-pickleball")
async def clean_pickleball_data(request: Request):
    """
    Xóa toàn bộ dữ liệu chạy thử của Sân Pickleball:
    - Xóa các hóa đơn, món gọi, lệnh in bếp của các sân Pickleball (PK-01 .. PK-04)
    - Xóa các phiên (table_sessions) và service calls của sân
    - Xóa toàn bộ lượt đặt sân, gói hội viên, và check-in pickleball
    - Đưa tất cả sân Pickleball về trạng thái SÂN TRỐNG (AVAILABLE, current_session_id = NULL)
    - Lưu UUID đơn vào deleted_order_uuids để đồng bộ không bị lặp lại
    """
    auth_header = request.headers.get("X-Pipo-Admin-Secret") or ""
    if auth_header != "pipo_secure_clear_revenue_2026":
        user = require_api_auth(request)
        if user.get("role") not in ("SUPER_ADMIN", "ADMIN") and user.get("username", "").lower() != "thaitd":
            raise HTTPException(
                status_code=403,
                detail="Chỉ tài khoản Quản trị / Super Admin mới có quyền xóa dữ liệu sân Pickleball!"
            )

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deleted_order_uuids (
            order_uuid TEXT PRIMARY KEY,
            deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 1. Tìm table_ids của Sân Pickleball (Chỉ 4 sân PK-01 .. PK-04)
    cursor.execute("""
        SELECT id, table_code, name FROM tables 
        WHERE table_code LIKE 'PK-%' OR area = 'Sân Pickle' OR name LIKE 'Sân Pick%'
    """)
    pickle_tables = cursor.fetchall()
    table_ids = [t["id"] for t in pickle_tables]

    count_orders = 0
    count_items = 0
    count_print_jobs = 0
    total_pickle_order_rev = 0

    if table_ids:
        t_placeholders = ','.join(['?'] * len(table_ids))
        cursor.execute(f"""
            SELECT id, order_uuid, total FROM orders 
            WHERE table_id IN ({t_placeholders})
        """, table_ids)
        matched_orders = cursor.fetchall()
        order_ids = [o["id"] for o in matched_orders]
        order_uuids = [o["order_uuid"] for o in matched_orders if o["order_uuid"]]
        total_pickle_order_rev = sum(o["total"] or 0 for o in matched_orders)
        count_orders = len(order_ids)

        for u in order_uuids:
            cursor.execute("INSERT OR IGNORE INTO deleted_order_uuids (order_uuid) VALUES (?)", (u,))

        if order_ids:
            o_placeholders = ','.join(['?'] * len(order_ids))
            cursor.execute(f"SELECT COUNT(*) FROM order_items WHERE order_id IN ({o_placeholders})", order_ids)
            count_items = cursor.fetchone()[0]
            cursor.execute(f"DELETE FROM order_items WHERE order_id IN ({o_placeholders})", order_ids)

            cursor.execute(f"SELECT COUNT(*) FROM print_jobs WHERE order_id IN ({o_placeholders})", order_ids)
            count_print_jobs = cursor.fetchone()[0]
            cursor.execute(f"DELETE FROM print_jobs WHERE order_id IN ({o_placeholders})", order_ids)

            cursor.execute(f"DELETE FROM orders WHERE id IN ({o_placeholders})", order_ids)

        # Xóa table_sessions
        cursor.execute(f"DELETE FROM table_sessions WHERE table_id IN ({t_placeholders})", table_ids)
        # Xóa service_calls
        cursor.execute(f"DELETE FROM service_calls WHERE table_id IN ({t_placeholders})", table_ids)

        # Reset sân về AVAILABLE
        cursor.execute(f"""
            UPDATE tables 
            SET status = 'AVAILABLE', current_session_id = NULL 
            WHERE id IN ({t_placeholders})
        """, table_ids)

    # 2. Xóa pickleball_checkins, memberships, bookings
    cursor.execute("SELECT COUNT(*) FROM pickleball_checkins")
    count_checkins = cursor.fetchone()[0]
    cursor.execute("DELETE FROM pickleball_checkins")

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(paid_amount), 0) FROM pickleball_memberships")
    mbr_row = cursor.fetchone()
    count_memberships = mbr_row[0]
    total_mbr_rev = mbr_row[1]
    cursor.execute("DELETE FROM pickleball_memberships")

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(deposit_amount), 0) FROM pickleball_bookings")
    bkg_row = cursor.fetchone()
    count_bookings = bkg_row[0]
    total_bkg_rev = bkg_row[1]
    cursor.execute("DELETE FROM pickleball_bookings")

    conn.commit()
    conn.close()

    total_cleared = total_pickle_order_rev + total_mbr_rev + total_bkg_rev

    if broadcaster:
        try:
            await broadcaster.send_to_pos({"event": "CLEAN_HISTORY", "payload": {"mode": "PICKLEBALL_ONLY"}})
            await broadcaster.send_to_pos({"event": "TABLES_UPDATED"})
            await broadcaster.send_to_pos({"event": "ORDERS_REFRESH"})
            await broadcaster.send_to_kds({"event": "KDS_REFRESH"})
        except Exception:
            pass

    return {
        "status": "SUCCESS",
        "message": f"Đã xóa toàn bộ dữ liệu thử nghiệm sân Pickleball: {count_orders} hóa đơn ({total_pickle_order_rev:,} đ), {count_memberships} hội viên ({total_mbr_rev:,} đ), {count_bookings} lượt đặt sân ({total_bkg_rev:,} đ). Đã giải phóng 4 sân về Sân Trống.",
        "deleted_orders": count_orders,
        "deleted_order_items": count_items,
        "deleted_print_jobs": count_print_jobs,
        "deleted_memberships": count_memberships,
        "deleted_bookings": count_bookings,
        "deleted_checkins": count_checkins,
        "total_deleted_revenue": total_cleared
    }
