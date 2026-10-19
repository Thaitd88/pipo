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
        "today": {"revenue": today_rev, "orders": today_orders},
        "this_month": {"revenue": month_rev, "orders": month_orders},
        "this_year": {"revenue": year_rev, "orders": year_orders},
        "funds": {
            "cash_revenue": method_row.get("cash_rev", 0),
            "transfer_revenue": method_row.get("transfer_rev", 0),
            "internal_revenue": method_row.get("internal_rev", 0),
            "service_fee_revenue": method_row.get("service_fee_rev", 0)
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

    # 1. Thống kê tổng hợp kỳ báo cáo (gồm Quỹ tiền mặt, Doanh thu chuyển khoản, Nội bộ & Phí phục vụ)
    cursor.execute(f"""
        SELECT COALESCE(SUM(o.total), 0) as total_revenue,
               COUNT(o.id) as total_orders,
               COALESCE(SUM(o.discount), 0) as total_discount,
               COALESCE(SUM(o.service_fee), 0) as total_service_fee,
               COALESCE(SUM(CASE WHEN UPPER(COALESCE(o.payment_method, 'CASH')) = 'CASH' AND COALESCE(o.bill_target, 'CUSTOMER') != 'ADMIN' THEN o.total ELSE 0 END), 0) as cash_revenue,
               COALESCE(SUM(CASE WHEN UPPER(o.payment_method) IN ('TRANSFER', 'VIETQR') AND COALESCE(o.bill_target, 'CUSTOMER') != 'ADMIN' THEN o.total ELSE 0 END), 0) as transfer_revenue,
               COALESCE(SUM(CASE WHEN UPPER(o.payment_method) = 'INTERNAL' OR COALESCE(o.bill_target, 'CUSTOMER') = 'ADMIN' THEN o.total ELSE 0 END), 0) as internal_revenue
        FROM orders o
        WHERE o.payment_status = 'PAID' AND {where_clause}
    """, (param,))
    summary = dict(cursor.fetchone() or {})

    # 2. Lấy danh sách từng hóa đơn chi tiết
    cursor.execute(f"""
        SELECT o.id, o.round_number, o.subtotal, o.discount, o.service_fee, o.total,
               o.payment_method, o.bill_target, o.billed_admin_name, o.created_at, o.completed_at,
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

@router.post("/clean-history")
def clean_order_history(req: CleanHistoryRequest, request: Request):
    """
    Chức năng ĐẶC QUYỀN của SUPER_ADMIN (Chủ nhà hàng / Thaitd):
    Cho phép xóa doanh thu, lịch sử đơn hàng, bán hàng:
    - Xóa theo 1 ngày cụ thể
    - Xóa từ một ngày nào đó trở đi
    - Xóa trong khoảng từ ngày A đến ngày B
    - Hoặc xóa sạch để thử nghiệm tính năng mới mà không ảnh hưởng CSDL gốc.
    """
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

    if mode == "SINGLE_DATE":
        if not target_date:
            raise HTTPException(status_code=400, detail="Vui lòng chọn ngày cần xóa (định dạng YYYY-MM-DD)")
        where_cond = "DATE(created_at) = ?"
        where_sessions = "DATE(opened_at) = ?"
        params = (target_date,)
        desc_range = f"ngày {target_date}"
    elif mode == "FROM_DATE":
        if not req.from_date:
            raise HTTPException(status_code=400, detail="Vui lòng chọn ngày bắt đầu xóa (định dạng YYYY-MM-DD)")
        where_cond = "DATE(created_at) >= ?"
        where_sessions = "DATE(opened_at) >= ?"
        params = (req.from_date,)
        desc_range = f"từ ngày {req.from_date} trở đi"
    elif mode == "DATE_RANGE":
        if not req.from_date or not req.to_date:
            raise HTTPException(status_code=400, detail="Vui lòng chọn đủ ngày bắt đầu và kết thúc")
        where_cond = "DATE(created_at) >= ? AND DATE(created_at) <= ?"
        where_sessions = "DATE(opened_at) >= ? AND DATE(opened_at) <= ?"
        params = (req.from_date, req.to_date)
        desc_range = f"từ ngày {req.from_date} đến ngày {req.to_date}"
    elif mode == "ALL":
        where_cond = "1=1"
        where_sessions = "1=1"
        params = ()
        desc_range = "toàn bộ lịch sử từ trước đến nay"
    else:
        raise HTTPException(status_code=400, detail="Chế độ xóa không hợp lệ (SINGLE_DATE, FROM_DATE, DATE_RANGE, ALL)")

    conn = get_db()
    cursor = conn.cursor()

    # 1. Thu thập danh sách orders cần xóa
    cursor.execute(f"SELECT id, total FROM orders WHERE {where_cond}", params)
    matched_orders = cursor.fetchall()
    order_ids = [r["id"] for r in matched_orders]
    total_rev_deleted = sum(r["total"] for r in matched_orders)
    count_orders = len(order_ids)

    count_items = 0
    count_print_jobs = 0
    if order_ids:
        placeholders = ','.join(['?'] * len(order_ids))
        # Đếm và xóa order_items
        cursor.execute(f"SELECT COUNT(*) FROM order_items WHERE order_id IN ({placeholders})", order_ids)
        count_items = cursor.fetchone()[0]
        cursor.execute(f"DELETE FROM order_items WHERE order_id IN ({placeholders})", order_ids)

        # Đếm và xóa print_jobs liên quan
        cursor.execute(f"SELECT COUNT(*) FROM print_jobs WHERE order_id IN ({placeholders})", order_ids)
        count_print_jobs = cursor.fetchone()[0]
        cursor.execute(f"DELETE FROM print_jobs WHERE order_id IN ({placeholders})", order_ids)

        # Xóa orders
        cursor.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", order_ids)

    # 2. Xóa các service calls trong khoảng thời gian đó
    cursor.execute(f"DELETE FROM service_calls WHERE {where_cond}", params)

    # 3. Đếm & Xóa các table_sessions trong khoảng thời gian đó
    cursor.execute(f"SELECT COUNT(*) FROM table_sessions WHERE {where_sessions}", params)
    count_sessions = cursor.fetchone()[0]
    cursor.execute(f"DELETE FROM table_sessions WHERE {where_sessions}", params)

    # 4. Đếm & Xóa biến động kho nếu được chọn
    count_inv = 0
    if clean_inventory:
        cursor.execute(f"SELECT COUNT(*) FROM inventory_transactions WHERE {where_cond}", params)
        count_inv = cursor.fetchone()[0]
        cursor.execute(f"DELETE FROM inventory_transactions WHERE {where_cond}", params)

    # 5. Reset các bàn đang bị kẹt về AVAILABLE
    count_reset_tables = 0
    if reset_tables:
        cursor.execute("""
            UPDATE tables 
            SET status = 'AVAILABLE', current_session_id = NULL 
            WHERE current_session_id IS NULL 
               OR current_session_id NOT IN (SELECT id FROM table_sessions WHERE status = 'ACTIVE')
        """)
        count_reset_tables = cursor.rowcount

    conn.commit()
    conn.close()

    # Gửi tín hiệu WebSocket cập nhật real-time đến POS và KDS
    if broadcaster:
        import asyncio
        try:
            asyncio.create_task(broadcaster.send_to_pos({"event": "TABLES_UPDATED"}))
            asyncio.create_task(broadcaster.send_to_pos({"event": "ORDERS_REFRESH"}))
            asyncio.create_task(broadcaster.send_to_kds({"event": "KDS_REFRESH"}))
        except Exception:
            pass

    return {
        "status": "SUCCESS",
        "message": f"Đã xóa thành công {count_orders} đơn hàng ({count_items} món) với tổng doanh thu {total_rev_deleted:,} đ trong {desc_range}.",
        "deleted_orders": count_orders,
        "deleted_orders_count": count_orders,
        "deleted_order_items": count_items,
        "deleted_items_count": count_items,
        "deleted_print_jobs": count_print_jobs,
        "deleted_sessions": count_sessions,
        "deleted_inventory_tx": count_inv,
        "reset_tables": count_reset_tables,
        "deleted_revenue": total_rev_deleted,
        "mode": mode,
        "desc_range": desc_range
    }
