# Revenue Reports router for PiPo Garden
from fastapi import APIRouter, HTTPException, Query, Request
from datetime import datetime, timedelta
from ..database import get_db
from .auth import require_api_auth

router = APIRouter(prefix="/api/reports", tags=["Revenue Reports"])

@router.get("/overview")
def get_revenue_overview(request: Request):
    """Báo cáo tổng quan KPI doanh thu, biểu đồ xu hướng và top món bán chạy."""
    require_api_auth(request, allowed_roles=["ADMIN", "CASHIER"])
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    this_month_str = now.strftime("%Y-%m")
    this_year_str = now.strftime("%Y")

    # 1. Doanh thu hôm nay
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as rev, COUNT(*) as orders_cnt
        FROM orders 
        WHERE payment_status = 'PAID' AND DATE(created_at) = ?
    """, (today_str,))
    today_data = cursor.fetchone()
    today_rev = today_data["rev"]
    today_orders = today_data["orders_cnt"]

    # 2. Doanh thu tháng này
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as rev, COUNT(*) as orders_cnt
        FROM orders 
        WHERE payment_status = 'PAID' AND strftime('%Y-%m', created_at) = ?
    """, (this_month_str,))
    month_data = cursor.fetchone()
    month_rev = month_data["rev"]
    month_orders = month_data["orders_cnt"]

    # 3. Doanh thu năm nay
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as rev, COUNT(*) as orders_cnt
        FROM orders 
        WHERE payment_status = 'PAID' AND strftime('%Y', created_at) = ?
    """, (this_year_str,))
    year_data = cursor.fetchone()
    year_rev = year_data["rev"]
    year_orders = year_data["orders_cnt"]

    # 4. Giá trị đơn trung bình (AOV)
    aov = int(month_rev / month_orders) if month_orders > 0 else 0

    # 5. Biểu đồ doanh thu 7 ngày gần nhất
    days_chart = []
    for i in range(6, -1, -1):
        d = now - timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        d_label = d.strftime("%d/%m")
        cursor.execute("""
            SELECT COALESCE(SUM(total), 0) as daily_rev, COUNT(*) as daily_orders
            FROM orders 
            WHERE payment_status = 'PAID' AND DATE(created_at) = ?
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
            WHERE payment_status = 'PAID' AND strftime('%Y-%m', created_at) = ?
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

    # 9. Doanh thu theo phương thức thanh toán
    cursor.execute("""
        SELECT COALESCE(payment_method, 'VIETQR') as method, 
               COALESCE(SUM(total), 0) as method_revenue,
               COUNT(*) as orders_count
        FROM orders
        WHERE payment_status = 'PAID'
        GROUP BY payment_method
    """)
    method_breakdown = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "today": {"revenue": today_rev, "orders": today_orders},
        "this_month": {"revenue": month_rev, "orders": month_orders},
        "this_year": {"revenue": year_rev, "orders": year_orders},
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
    date_val: str = Query(None) # YYYY-MM-DD nếu DAY, YYYY-MM nếu MONTH, YYYY nếu YEAR
):
    """Báo cáo chi tiết danh sách hóa đơn theo ngày, tháng hoặc năm."""
    require_api_auth(request, allowed_roles=["ADMIN", "CASHIER"])
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now()
    if not date_val:
        if period_type == "DAY":
            date_val = now.strftime("%Y-%m-%d")
        elif period_type == "MONTH":
            date_val = now.strftime("%Y-%m")
        else:
            date_val = now.strftime("%Y")

    # Xây dựng điều kiện truy vấn
    if period_type == "DAY":
        where_clause = "DATE(o.created_at) = ?"
        param = date_val
    elif period_type == "MONTH":
        where_clause = "strftime('%Y-%m', o.created_at) = ?"
        param = date_val
    else: # YEAR
        where_clause = "strftime('%Y', o.created_at) = ?"
        param = date_val

    # 1. Thống kê tổng hợp kỳ báo cáo
    cursor.execute(f"""
        SELECT COALESCE(SUM(o.total), 0) as total_revenue,
               COUNT(o.id) as total_orders,
               COALESCE(SUM(o.discount), 0) as total_discount
        FROM orders o
        WHERE o.payment_status = 'PAID' AND {where_clause}
    """, (param,))
    summary = dict(cursor.fetchone())

    # 2. Lấy danh sách từng hóa đơn chi tiết
    cursor.execute(f"""
        SELECT o.id, o.round_number, o.subtotal, o.discount, o.total,
               o.payment_method, o.created_at, o.completed_at,
               t.name as table_name, t.table_code, t.area
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        WHERE o.payment_status = 'PAID' AND {where_clause}
        ORDER BY o.created_at DESC
    """, (param,))
    orders_rows = cursor.fetchall()
    orders_list = []

    total_dishes_count = 0
    for o in orders_rows:
        order_dict = dict(o)
        cursor.execute("""
            SELECT item_name, quantity, unit_price, total_price, station, note
            FROM order_items
            WHERE order_id = ?
        """, (order_dict["id"],))
        items = [dict(it) for it in cursor.fetchall()]
        order_dict["items"] = items
        order_dict["items_count"] = sum(it["quantity"] for it in items)
        total_dishes_count += order_dict["items_count"]
        orders_list.append(order_dict)

    summary["total_dishes_count"] = total_dishes_count

    # 3. Phân bổ biểu đồ con của kỳ báo cáo
    sub_chart = []
    if period_type == "MONTH":
        # Gom nhóm theo từng ngày trong tháng
        cursor.execute("""
            SELECT DATE(created_at) as sub_key, 
                   strftime('%d/%m', created_at) as sub_label,
                   COALESCE(SUM(total), 0) as sub_rev,
                   COUNT(*) as sub_cnt
            FROM orders
            WHERE payment_status = 'PAID' AND strftime('%Y-%m', created_at) = ?
            GROUP BY DATE(created_at)
            ORDER BY sub_key ASC
        """, (param,))
        sub_chart = [dict(r) for r in cursor.fetchall()]
    elif period_type == "YEAR":
        # Gom nhóm theo từng tháng trong năm
        cursor.execute("""
            SELECT strftime('%Y-%m', created_at) as sub_key,
                   'Tháng ' || strftime('%m', created_at) as sub_label,
                   COALESCE(SUM(total), 0) as sub_rev,
                   COUNT(*) as sub_cnt
            FROM orders
            WHERE payment_status = 'PAID' AND strftime('%Y', created_at) = ?
            GROUP BY strftime('%Y-%m', created_at)
            ORDER BY sub_key ASC
        """, (param,))
        sub_chart = [dict(r) for r in cursor.fetchall()]
    else: # DAY
        # Gom nhóm theo khung giờ trong ngày
        cursor.execute("""
            SELECT strftime('%H:00', created_at) as sub_key,
                   strftime('%H:00', created_at) as sub_label,
                   COALESCE(SUM(total), 0) as sub_rev,
                   COUNT(*) as sub_cnt
            FROM orders
            WHERE payment_status = 'PAID' AND DATE(created_at) = ?
            GROUP BY strftime('%H:00', created_at)
            ORDER BY sub_key ASC
        """, (param,))
        sub_chart = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "period_type": period_type,
        "date_val": date_val,
        "summary": summary,
        "sub_chart": sub_chart,
        "orders": orders_list
    }
