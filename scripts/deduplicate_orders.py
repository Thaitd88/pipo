import sys
import uuid
import re
sys.path.insert(0, '.')
from app.database import get_db

with get_db() as conn:
    cursor = conn.cursor()

    # 1. Đảm bảo cột order_uuid tồn tại
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN order_uuid TEXT")
    except Exception:
        pass
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_uuid ON orders(order_uuid)")
    except Exception:
        pass

    # 2. Xóa các đơn rỗng 0đ do checkout bàn trống (không có món và total = 0)
    cursor.execute("""
        DELETE FROM orders 
        WHERE total = 0 
          AND subtotal = 0 
          AND service_fee = 0 
          AND id NOT IN (SELECT DISTINCT order_id FROM order_items)
    """)
    zero_del_cnt = cursor.rowcount
    print(f"[*] Deleted {zero_del_cnt} empty 0-VND ghost orders without items.")

    # 3. Tìm các nhóm đơn hàng bị nhân bản trùng lặp (cùng table_id, cùng total, cùng created_at)
    cursor.execute("""
        SELECT table_id, total, created_at, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
        FROM orders
        GROUP BY table_id, total, created_at
        HAVING COUNT(*) > 1
    """)
    dup_groups = [dict(r) for r in cursor.fetchall()]
    print(f"[*] Found {len(dup_groups)} duplicate groups.")

    total_deleted = 0
    cleaned_kept = 0

    for g in dup_groups:
        id_strs = g['ids'].split(',')
        ids = [int(x) for x in id_strs]
        ids.sort() # Sắp xếp tăng dần

        keep_id = ids[0]
        del_ids = ids[1:]

        # Dọn dẹp customer_note của đơn giữ lại (loại bỏ chuỗi [REF:SYNC_...] chồng chất)
        cursor.execute("SELECT customer_note, order_uuid FROM orders WHERE id = ?", (keep_id,))
        keep_order = cursor.fetchone()
        raw_note = keep_order["customer_note"] or ""
        clean_note = re.sub(r'\s*\[REF:SYNC_[^\]]+\]', '', raw_note).strip()
        curr_uuid = keep_order["order_uuid"] or f"ord_{uuid.uuid4().hex}"

        cursor.execute("UPDATE orders SET customer_note = ?, order_uuid = ? WHERE id = ?", (clean_note, curr_uuid, keep_id))
        cleaned_kept += 1

        # Xóa các đơn trùng lặp và các dữ liệu liên quan
        placeholders = ','.join('?' for _ in del_ids)
        cursor.execute(f"DELETE FROM order_items WHERE order_id IN ({placeholders})", tuple(del_ids))
        cursor.execute(f"DELETE FROM print_jobs WHERE order_id IN ({placeholders})", tuple(del_ids))
        cursor.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", tuple(del_ids))
        total_deleted += len(del_ids)

    # 4. Gán order_uuid cho tất cả các đơn còn lại nếu chưa có
    cursor.execute("SELECT id, customer_note, order_uuid FROM orders WHERE order_uuid IS NULL")
    no_uuid_orders = cursor.fetchall()
    for o in no_uuid_orders:
        new_uid = f"ord_{uuid.uuid4().hex}"
        raw_note = o["customer_note"] or ""
        clean_note = re.sub(r'\s*\[REF:SYNC_[^\]]+\]', '', raw_note).strip()
        cursor.execute("UPDATE orders SET order_uuid = ?, customer_note = ? WHERE id = ?", (new_uid, clean_note, o["id"]))

    conn.commit()

    # 5. Thống kê kết quả sau khi làm sạch
    cursor.execute("SELECT COUNT(*) as cnt, SUM(total) as sum_total FROM orders")
    res = dict(cursor.fetchone())
    print("==================================================")
    print(f"[+] DEDUPLICATION COMPLETED SUCCESSFULLY!")
    print(f"[*] Cleaned and kept: {cleaned_kept} authentic orders.")
    print(f"[*] Deleted redundant duplicate orders: {total_deleted}")
    print(f"[*] Final remaining clean orders: {res['cnt']}")
    print(f"[*] Final authentic revenue: {res['sum_total']} VND")
    print("==================================================")
