import sqlite3
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

def clear_db(db_path):
    if not os.path.exists(db_path):
        print(f"[SKIP] DB not found: {db_path}")
        return
    
    print(f"\n=== CLEANING PICKLEBALL DATA IN: {db_path} ===")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deleted_order_uuids (
            order_uuid TEXT PRIMARY KEY,
            deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 1. Tìm table_ids của Sân Pickleball (Chỉ 4 sân PK-01 .. PK-04, không lẫn Sảnh 2)
    cursor.execute("""
        SELECT id, table_code, name, area FROM tables 
        WHERE table_code LIKE 'PK-%' OR area = 'Sân Pickle' OR name LIKE 'Sân Pick%'
    """)
    pickle_tables = cursor.fetchall()
    table_ids = [t["id"] for t in pickle_tables]
    print(f"Found {len(table_ids)} Pickleball courts: {[dict(t) for t in pickle_tables]}")

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
        print(f"Found {count_orders} orders totaling {total_pickle_order_rev:,} đ")

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
        print(f"Reset {cursor.rowcount} Pickleball courts to AVAILABLE, current_session_id = NULL")

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

    print(f"SUCCESS: Cleared {count_orders} orders ({total_pickle_order_rev:,} đ), {count_items} items, {count_print_jobs} print jobs.")
    print(f"         Cleared {count_memberships} memberships ({total_mbr_rev:,} đ), {count_bookings} bookings ({total_bkg_rev:,} đ), {count_checkins} checkins.")

if __name__ == '__main__':
    clear_db('data/pipo_garden.db')
    clear_db('thungan/data/pipo_garden.db')
