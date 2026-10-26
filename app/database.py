# Database models, schema and initialization for PiPo Garden
import sqlite3
import os
import json
import hashlib
from datetime import datetime, timedelta
import random

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(DATA_DIR, "pipo_garden.db"))

# Tự động sao chép CSDL cũ từ thư mục gốc vào thư mục dữ liệu bền nếu chưa có
OLD_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pipo_garden.db")
if not os.path.exists(DB_PATH) and os.path.exists(OLD_DB_PATH):
    import shutil
    try:
        shutil.copy2(OLD_DB_PATH, DB_PATH)
    except Exception as _e:
        pass

SECRET_SALT = "PiPoGarden_Secret_Salt_2026_xYz"

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn

def hash_password(password: str) -> str:
    """Băm mật khẩu bằng SHA-256 kèm salt bí mật của PiPo Garden."""
    salted = f"{password}_{SECRET_SALT}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()

def generate_qr_token(table_code: str) -> str:
    msg = f"{table_code}_{SECRET_SALT}".encode()
    return hashlib.sha256(msg).hexdigest()[:16]

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Dining Tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        area TEXT NOT NULL DEFAULT 'Khu Sân Vườn',
        capacity INTEGER DEFAULT 4,
        qr_token TEXT NOT NULL,
        status TEXT DEFAULT 'AVAILABLE', -- AVAILABLE, OCCUPIED, BILLING
        current_session_id INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 17. Quản Lý Hội Viên & Khách Đặt Sân Cố Định Pickleball
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pickleball_memberships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_code TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        membership_type TEXT NOT NULL,
        court_id INTEGER,
        time_slots_desc TEXT DEFAULT '',
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        price INTEGER NOT NULL DEFAULT 0,
        paid_amount INTEGER NOT NULL DEFAULT 0,
        payment_status TEXT DEFAULT 'PAID',
        payment_method TEXT DEFAULT 'CASH',
        checkin_count INTEGER DEFAULT 0,
        last_checkin_at DATETIME,
        status TEXT DEFAULT 'ACTIVE',
        notes TEXT DEFAULT '',
        created_by TEXT DEFAULT '',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 18. Lịch Sử Điểm Danh / Check-in Vào Sân Pickleball
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pickleball_checkins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        membership_id INTEGER NOT NULL,
        member_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        membership_type TEXT NOT NULL,
        checked_in_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        checked_in_by TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        FOREIGN KEY (membership_id) REFERENCES pickleball_memberships(id)
    )
    """)

    # 19. Sổ Quỹ Thu - Chi Kế Toán (Capex & Opex)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounting_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_code TEXT UNIQUE NOT NULL,
        transaction_type TEXT NOT NULL,
        cost_category TEXT NOT NULL,
        department TEXT NOT NULL,
        expense_type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        payment_method TEXT DEFAULT 'CASH',
        recipient_payer TEXT DEFAULT '',
        description TEXT NOT NULL,
        receipt_url TEXT DEFAULT '',
        created_by TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Table Sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS table_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_id INTEGER NOT NULL,
        session_token TEXT UNIQUE NOT NULL,
        pin_code TEXT,
        status TEXT DEFAULT 'ACTIVE', -- ACTIVE, CLOSED
        guest_count INTEGER DEFAULT 1,
        opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        closed_at DATETIME,
        FOREIGN KEY (table_id) REFERENCES tables(id)
    )
    """)

    # 3. Menu Categories
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        icon TEXT DEFAULT '🍽️',
        display_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        translations_json TEXT DEFAULT '{}'
    )
    """)

    # 4. Menu Items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        image_url TEXT,
        station TEXT DEFAULT 'HOT_KITCHEN', -- HOT_KITCHEN, COLD_KITCHEN, BAR
        is_available INTEGER DEFAULT 1,
        options_json TEXT DEFAULT '[]',
        translations_json TEXT DEFAULT '{}',
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )
    """)

    # 5. Orders
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        table_id INTEGER NOT NULL,
        round_number INTEGER DEFAULT 1,
        subtotal INTEGER NOT NULL,
        discount INTEGER DEFAULT 0,
        service_fee INTEGER DEFAULT 0,
        total INTEGER NOT NULL,
        status TEXT DEFAULT 'CONFIRMED', -- PENDING, CONFIRMED, PREPARING, READY, SERVED, COMPLETED, CANCELLED
        payment_status TEXT DEFAULT 'UNPAID', -- UNPAID, PAID
        payment_method TEXT DEFAULT 'CASH', -- CASH, VIETQR, CARD
        customer_note TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME,
        FOREIGN KEY (session_id) REFERENCES table_sessions(id),
        FOREIGN KEY (table_id) REFERENCES tables(id)
    )
    """)

    # 6. Order Items (có cột updated_at)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price INTEGER NOT NULL,
        total_price INTEGER NOT NULL,
        station TEXT DEFAULT 'HOT_KITCHEN',
        note TEXT,
        modifiers_json TEXT DEFAULT '[]',
        status TEXT DEFAULT 'QUEUED', -- QUEUED, COOKING, READY, SERVED, CANCELLED
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )
    """)

    # Tự động migrate thêm cột updated_at nếu bảng cũ đã tồn tại
    try:
        cursor.execute("ALTER TABLE order_items ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'CASH'")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN completed_at DATETIME")
    except Exception:
        pass

    # Migrate các cột hỗ trợ Trả món / Hủy món
    cancel_cols = [
        ("cancel_reason", "TEXT"),
        ("cancel_requested_by", "TEXT"),
        ("cancel_requested_at", "DATETIME"),
        ("cancelled_by", "TEXT"),
        ("cancelled_at", "DATETIME"),
        ("cancel_rejection_reason", "TEXT"),
    ]
    for col_name, col_type in cancel_cols:
        try:
            cursor.execute(f"ALTER TABLE order_items ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass

    # Migrate translations_json cho categories & menu_items
    try:
        cursor.execute("ALTER TABLE categories ADD COLUMN translations_json TEXT DEFAULT '{}'")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN translations_json TEXT DEFAULT '{}'")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN out_of_ingredients INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN main_menu_type TEXT DEFAULT 'RESTAURANT,LUNCH,CAFE'")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN discount_percent INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN portion TEXT DEFAULT ''")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN calories INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE order_items ADD COLUMN discount_percent INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE order_items ADD COLUMN original_price INTEGER DEFAULT 0")
    except Exception:
        pass

    # Migrate các cột hỗ trợ Giảm giá tổng bill & Tính bill với Admin
    order_billing_cols = [
        ("discount_reason", "TEXT"),
        ("bill_target", "TEXT DEFAULT 'CUSTOMER'"),
        ("billed_admin_id", "INTEGER"),
        ("billed_admin_name", "TEXT"),
        ("service_fee", "INTEGER DEFAULT 0"),
    ]
    for col_name, col_type in order_billing_cols:
        try:
            cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass

    # 7. Print Jobs (KOT)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS print_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        station TEXT NOT NULL,
        job_type TEXT DEFAULT 'KOT',
        status TEXT DEFAULT 'PENDING',
        ticket_text TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        printed_at DATETIME,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )
    """)

    # 8. Service Calls
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS service_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_id INTEGER NOT NULL,
        table_name TEXT NOT NULL,
        call_type TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 9. Staff / Users Table (Quản Trị & Đăng Nhập Nhân Viên)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL, -- ADMIN (Quản lý), CASHIER (Thu ngân), CHEF (Bếp trưởng), WAITER (Phục vụ)
        phone TEXT,
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 10. Kho Nguyên Vật Liệu (Inventory Items)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        unit TEXT NOT NULL,
        stock_quantity REAL DEFAULT 0,
        min_stock REAL DEFAULT 5,
        cost_price INTEGER DEFAULT 0,
        supplier TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 11. Định Lượng Món Ăn - BOM (Bill of Materials)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recipe_bom (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        menu_item_id INTEGER NOT NULL,
        ingredient_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE CASCADE,
        FOREIGN KEY (ingredient_id) REFERENCES inventory_items(id) ON DELETE CASCADE,
        UNIQUE (menu_item_id, ingredient_id)
    )
    """)

    # 12. Lịch Sử Biến Động Kho (Inventory Transactions)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ingredient_id INTEGER NOT NULL,
        transaction_type TEXT NOT NULL, -- IMPORT, ORDER_DEDUCT, ADJUSTMENT
        quantity REAL NOT NULL,
        unit_price INTEGER DEFAULT 0,
        reference_id INTEGER,
        note TEXT,
        created_by TEXT DEFAULT 'Hệ thống',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ingredient_id) REFERENCES inventory_items(id)
    )
    """)

    # 13. Khu Vực Bàn Ăn (Restaurant Areas)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS restaurant_areas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        icon TEXT DEFAULT '🌿',
        description TEXT,
        display_order INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 14. Đặt Bàn & Đặt Sân Trực Tuyến (Online Reservations)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        booking_date TEXT NOT NULL,
        booking_time TEXT NOT NULL,
        guest_count INTEGER DEFAULT 2,
        service_type TEXT DEFAULT 'DINING', -- DINING, BIRTHDAY_EVENT, PICKLEBALL, POOL_PARTY
        table_id INTEGER,
        table_code TEXT,
        area TEXT,
        preorder_items_json TEXT DEFAULT '[]',
        total_estimated INTEGER DEFAULT 0,
        assigned_at DATETIME,
        assigned_by TEXT,
        note TEXT,
        status TEXT DEFAULT 'PENDING', -- PENDING, CONFIRMED, CANCELLED
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Migrate thêm các cột cho bảng reservations nếu đã tồn tại từ trước
    res_cols = [
        ("table_id", "INTEGER"),
        ("table_code", "TEXT"),
        ("area", "TEXT"),
        ("preorder_items_json", "TEXT DEFAULT '[]'"),
        ("total_estimated", "INTEGER DEFAULT 0"),
        ("assigned_at", "DATETIME"),
        ("assigned_by", "TEXT"),
    ]
    for col_name, col_type in res_cols:
        try:
            cursor.execute(f"ALTER TABLE reservations ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass

    # Tự động chuẩn hóa tên món trong preorder_items_json của các đơn đã tạo trước đó
    try:
        cursor.execute("SELECT id, preorder_items_json FROM reservations WHERE preorder_items_json IS NOT NULL AND preorder_items_json != '[]'")
        for r_id, p_json in cursor.fetchall():
            try:
                items = json.loads(p_json or '[]')
                changed = False
                for it in items:
                    raw = it.get('raw_item', {}) if isinstance(it.get('raw_item'), dict) else {}
                    if not it.get('name'):
                        it['name'] = raw.get('name')
                        if not it['name'] and it.get('item_id'):
                            cursor.execute("SELECT name FROM menu_items WHERE id = ?", (it['item_id'],))
                            d_row = cursor.fetchone()
                            if d_row: it['name'] = d_row[0]
                        changed = True
                if changed:
                    cursor.execute("UPDATE reservations SET preorder_items_json = ? WHERE id = ?", (json.dumps(items, ensure_ascii=False), r_id))
            except Exception:
                pass
    except Exception:
        pass

    # 15. Quản Trị Nội Dung Trang Chủ (Homepage CMS)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS homepage_cms (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 16. Đặt Sân Pickleball Trực Tuyến (Pickleball Court Bookings)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pickleball_bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_code TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        booking_date TEXT NOT NULL,
        court_id INTEGER NOT NULL,
        court_name TEXT NOT NULL,
        time_slots_json TEXT NOT NULL,
        court_fee INTEGER NOT NULL DEFAULT 0,
        addons_json TEXT NOT NULL DEFAULT '[]',
        addons_fee INTEGER NOT NULL DEFAULT 0,
        total_amount INTEGER NOT NULL DEFAULT 0,
        deposit_percentage INTEGER NOT NULL DEFAULT 50,
        deposit_amount INTEGER NOT NULL DEFAULT 0,
        payment_status TEXT NOT NULL DEFAULT 'PENDING',
        notes TEXT,
        qr_token TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 20. Bang luu danh sach order_uuid da bi Super Admin xoa (Chong Ping-Pong Loop khi sync Cloud <-> Local)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS deleted_order_uuids (
        order_uuid TEXT PRIMARY KEY,
        deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()

    # Seed Homepage CMS default settings
    seed_homepage_cms(conn)

    # Seed initial areas if empty
    cursor.execute("SELECT COUNT(*) as count FROM restaurant_areas")
    if cursor.fetchone()["count"] == 0:
        cursor.execute("SELECT DISTINCT area FROM tables WHERE area IS NOT NULL AND area != ''")
        existing_areas = [r["area"] for r in cursor.fetchall()]
        if not existing_areas:
            existing_areas = ["Khu Sân Vườn", "Khu Máy Lạnh", "Tầng Lửng Chill"]
        for idx, a in enumerate(existing_areas):
            icon = "🌿"
            if "Máy Lạnh" in a or "Lạnh" in a: icon = "❄️"
            elif "Lửng" in a or "Chill" in a: icon = "🍷"
            elif "VIP" in a: icon = "⭐"
            cursor.execute("INSERT OR IGNORE INTO restaurant_areas (name, icon, display_order) VALUES (?, ?, ?)", (a, icon, idx))
        conn.commit()

    # Đảm bảo tài khoản Super Admin (Thaitd) và nhân viên mặc định luôn tồn tại
    seed_default_users(conn)

    # Seed initial tables and menu if empty
    cursor.execute("SELECT COUNT(*) as count FROM tables")
    if cursor.fetchone()["count"] == 0:
        seed_sample_data(conn)

    # Seed initial inventory items & BOM recipes if empty
    cursor.execute("SELECT COUNT(*) as count FROM inventory_items")
    if cursor.fetchone()["count"] == 0:
        seed_inventory_and_bom(conn)

    # Bỏ seed dữ liệu chạy thử giả lập để đảm bảo dữ liệu đơn hàng sạch sẽ theo yêu cầu
    # cursor.execute("SELECT COUNT(*) as count FROM orders WHERE payment_status = 'PAID'")
    # if cursor.fetchone()["count"] < 10:
    #     seed_historical_revenue(conn)

    # Tự động đồng bộ và di chuyển sang 6 nhóm danh mục chuẩn
    ensure_six_categories(conn)

    # Đảm bảo danh mục Hot BBQ đứng đầu và 5 món BBQ sân vườn chuẩn vị kèm vị & BOM
    ensure_bbq_category_and_dishes(conn)

    # Tự động phân loại 3 Nhóm Thực Đơn Lớn (Nhà Hàng, Cơm Trưa, Cafe / Ăn Sáng)
    ensure_main_menu_classification(conn)

    # Tự động tính toán và đồng bộ chỉ số Calo theo định lượng NVL (BOM)
    sync_dish_calories(conn)

    # Tự động chuẩn hóa 31 bàn theo 4 phân khu chuẩn (Hồ bơi 12, Sảnh 1: 5, Sảnh 2: 10, Sân Pickle: 4)
    ensure_standard_27_tables(conn)

    # Đảm bảo toàn bộ danh mục và món ăn đều có dữ liệu đa ngôn ngữ (chạy nền không nghẽn khởi động)
    import threading
    threading.Thread(target=seed_translations_if_missing, args=(None,), daemon=True).start()

    # Đảm bảo ảnh của các món đồ uống, bia và đặc sản luôn chuẩn và không bị mất
    ensure_fixed_dish_images(conn)

    # Đảm bảo định lượng món đơn giản, chuẩn xác cho bếp nhìn trực quan
    ensure_simple_dish_portions(conn)

    # Gom món theo loại nguyên liệu và tạo tùy chọn vị chế biến
    consolidate_menu_items_with_options(conn)

    # Xóa vĩnh viễn các món con thừa/ẩn, xóa NVL phụ trong kho/BOM, clear món Sân Pickle
    clean_redundant_dishes_and_secondary_bom(conn)

    # Đảm bảo các món ăn nhanh sân Pickleball (Trứng gà luộc, Ngô luộc - Coming Soon)
    ensure_pickleball_snack_dishes(conn)

    # Áp dụng chuẩn hóa menu, định lượng, BOM và bản dịch 4 thứ tiếng cho 40 món
    try:
        from .menu_fixer import apply_menu_bom_and_translations_fix
        apply_menu_bom_and_translations_fix(conn)
    except Exception as _e:
        print("[PiPo Menu Fixer] Loi:", _e)

    # Khử trùng và chuẩn hóa mã định danh order_uuid cho toàn bộ đơn hàng
    ensure_order_deduplication(conn)

    # Tối ưu hóa hiệu năng truy vấn CSDL (Database Performance Indexes)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_menu_items_cat_avail ON menu_items(category_id, is_available);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_table_status ON orders(table_id, status, payment_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_calls_status ON service_calls(status, table_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipe_bom_menu_item ON recipe_bom(menu_item_id, ingredient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reservations_date_status ON reservations(booking_date, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_print_jobs_status ON print_jobs(status, station);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tables_status ON tables(status, area);")
    conn.commit()

    conn.close()

def ensure_order_deduplication(conn):
    """
    Tự động chuẩn hóa mã định danh order_uuid cho mọi đơn hàng,
    và khử trùng triệt để các đơn hàng bị nhân bản trùng lặp do cơ chế đồng bộ hoặc lỗi click đúp.
    """
    cursor = conn.cursor()
    import uuid
    import re

    # 1. Thêm cột order_uuid và index nếu chưa có
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

    # 3. Dọn dẹp và khử trùng table_sessions (chống nhân bản bàn / sân do nhiều session active)
    # Đóng tất cả các session ACTIVE của bàn đang AVAILABLE hoặc không có đơn UNPAID
    cursor.execute("""
        UPDATE table_sessions 
        SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP
        WHERE status = 'ACTIVE' 
          AND table_id IN (
              SELECT id FROM tables WHERE status = 'AVAILABLE' OR current_session_id IS NULL
          )
    """)
    # Đảm bảo mỗi bàn có tối đa 1 session ACTIVE duy nhất (giữ session mới nhất, đóng các session cũ)
    cursor.execute("""
        UPDATE table_sessions
        SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP
        WHERE status = 'ACTIVE'
          AND id NOT IN (
              SELECT MAX(id) FROM table_sessions WHERE status = 'ACTIVE' GROUP BY table_id
          )
    """)

    # 4. Khử trùng các đơn bị nhân bản (cùng table_id, cùng total, cùng created_at)
    cursor.execute("""
        SELECT table_id, total, created_at, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
        FROM orders
        GROUP BY table_id, total, created_at
        HAVING COUNT(*) > 1
    """)
    dup_groups = [dict(r) for r in cursor.fetchall()]

    for g in dup_groups:
        id_strs = g['ids'].split(',')
        ids = [int(x) for x in id_strs]
        ids.sort()
        keep_id = ids[0]
        del_ids = ids[1:]

        cursor.execute("SELECT customer_note, order_uuid FROM orders WHERE id = ?", (keep_id,))
        row = cursor.fetchone()
        raw_note = (row["customer_note"] or "") if row else ""
        clean_note = re.sub(r'\s*\[REF:SYNC_[^\]]+\]', '', raw_note).strip()
        curr_uuid = (row["order_uuid"] or f"ord_{uuid.uuid4().hex}") if row else f"ord_{uuid.uuid4().hex}"

        cursor.execute("UPDATE orders SET customer_note = ?, order_uuid = ? WHERE id = ?", (clean_note, curr_uuid, keep_id))

        placeholders = ','.join('?' for _ in del_ids)
        cursor.execute(f"DELETE FROM order_items WHERE order_id IN ({placeholders})", tuple(del_ids))
        cursor.execute(f"DELETE FROM print_jobs WHERE order_id IN ({placeholders})", tuple(del_ids))
        cursor.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", tuple(del_ids))

    # 4. Gán order_uuid cho mọi đơn còn lại chưa có
    cursor.execute("SELECT id, customer_note, order_uuid FROM orders WHERE order_uuid IS NULL")
    for row in cursor.fetchall():
        new_uuid = f"ord_{uuid.uuid4().hex}"
        raw_note = row["customer_note"] or ""
        clean_note = re.sub(r'\s*\[REF:SYNC_[^\]]+\]', '', raw_note).strip()
        cursor.execute("UPDATE orders SET order_uuid = ?, customer_note = ? WHERE id = ?", (new_uuid, clean_note, row["id"]))

    conn.commit()


def ensure_printer_settings(conn):
    """Đảm bảo cấu hình mặc định cho 2 máy in nhiệt mạng LAN (Bếp 251 và Thu ngân 252)."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    defaults = {
        "printer_kitchen_ip": "192.168.31.251",
        "printer_kitchen_port": "9100",
        "printer_kitchen_enabled": "1",
        "printer_cashier_ip": "192.168.31.252",
        "printer_cashier_port": "9100",
        "printer_cashier_enabled": "1",
        "printer_auto_kitchen": "1",
        "printer_auto_cashier": "1",
    }
    for k, v in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()

def clear_all_test_data(conn=None):
    """Xóa sạch 100% dữ liệu chạy thử nghiệm để hệ thống bắt đầu mới hoàn toàn."""
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True
    cursor = conn.cursor()
    cursor.execute("DELETE FROM order_items")
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM print_jobs")
    cursor.execute("DELETE FROM service_calls")
    cursor.execute("DELETE FROM table_sessions")
    cursor.execute("DELETE FROM inventory_transactions")
    cursor.execute("DELETE FROM reservations")
    cursor.execute("DELETE FROM pickleball_bookings")
    cursor.execute("UPDATE tables SET status = 'AVAILABLE', current_session_id = NULL")
    try:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('orders', 'order_items', 'print_jobs', 'service_calls', 'table_sessions', 'inventory_transactions', 'reservations', 'pickleball_bookings')")
    except Exception:
        pass
    conn.commit()
    if should_close:
        conn.close()


def ensure_fixed_dish_images(conn):
    """Đảm bảo các món đồ uống, bia và món đặc sản luôn có đường dẫn ảnh chuẩn.
    
    CHỈ ghi đè khi ảnh đang trống, NULL, hoặc là URL ngoài (.webp) — 
    KHÔNG bao giờ ghi đè ảnh admin đã upload vào /static/dishes/*.
    """
    cursor = conn.cursor()
    FIXED_ITEMS = {
        "Bia Bivina": "/static/dishes/bia_bivina.jpg",
        "Bia Sài Gòn": "/static/dishes/bia_sai_gon.jpg",
        "Bia Heineken": "/static/dishes/bia_heineken.jpg",
        "Revive": "/static/dishes/revive.jpg",
        "Aquarius": "/static/dishes/aquarius.jpg",
        "Coca Cola": "/static/dishes/coca_cola.jpg",
        "Pepsi": "/static/dishes/pepsi.jpg",
        "Nước suối": "/static/dishes/nuoc_suoi.jpg",
        "Sườn heo nướng muối ớt": "/static/dishes/suon_heo_nuong_muoi_ot.jpg",
        "Bò Xuyên Tiêu": "/static/dishes/bo_xuyen_tieu.jpg",
        "Gà nướng tây bắc + Lòng mề xào": "/static/dishes/ga_nuong_tay_bac_long_me_xao.jpg",
        "Gà hấp mắm nhĩ + Lòng mề xào": "/static/dishes/ga_hap_mam_nhi_long_me_xao.jpg",
        "Hàu nướng phô mai": "/static/dishes/hau_nuong_pho_mai.jpg",
        "Ốc hương sốt trứng muối - bánh mì": "/static/dishes/oc_huong_sot_trung_muoi_banh_mi.jpg"
    }
    for name, path in FIXED_ITEMS.items():
        # Chỉ ghi đè khi ảnh đang trống hoặc là URL ngoài không ổn định (webp/http)
        cursor.execute("""
            UPDATE menu_items 
            SET image_url = ? 
            WHERE name = ? 
            AND (
                image_url IS NULL 
                OR image_url = '' 
                OR image_url LIKE 'http%'
                OR image_url LIKE '%.webp'
                OR image_url LIKE '%unsplash%'
                OR image_url LIKE '%cdn.%'
                OR image_url LIKE '%khaisanfood%'
                OR image_url LIKE '%heineken-vietnam%'
                OR image_url LIKE '%hstatic%'
            )
        """, (path, name))
    conn.commit()


def ensure_simple_dish_portions(conn):
    """Cập nhật định lượng NVL cốt lõi, ngắn gọn, chuẩn xác cho từng món ăn (ví dụ: Ốc hương 250g, Đậu phụ 3 bìa...)."""
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN portion TEXT DEFAULT ''")
    except Exception:
        pass

    PORTIONS = {
        # Khai Vị & Ăn Nhẹ
        "Khoai tây chiên": "Khoai tây 300g",
        "Đậu hũ tẩm hành": "Đậu phụ 3 bìa",
        "Rau muống xào tỏi": "Rau muống 400g",
        "Cải thìa sốt dầu hào": "Cải thìa 400g",
        "Đậu hũ chiên giòn": "Đậu phụ 4 bìa",
        "Khoai môn chiên nước mắm": "Khoai môn 350g",
        "Bánh Mì Ốp La Xúc Xích Pate": "1 bánh mì + 2 trứng + xúc xích",
        
        # Gà - Vịt
        "Gà đen nguyên con": "Gà H'Mông 1 con (1.3kg)",
        "Gà hấp mắm nhĩ + Lòng mề xào": "Gà ta 1 con (1.3kg) + lòng mề",
        "Gà nướng muối ớt + Lòng mề xào": "Gà ta 1 con (1.3kg) + lòng mề",
        "Gà chiên mắm + Lòng mề xào": "Gà ta 1 con (1.3kg) + lòng mề",
        "Gà hấp hành + Lòng mề xào": "Gà ta 1 con (1.3kg) + lòng mề",
        "Lẩu gà lá giang": "Gà ta 1 con (1.3kg) + bún rau",
        "Gà nướng tây bắc + Lòng mề xào": "Gà ta 1 con (1.3kg) + lòng mề",
        "Cánh gà chiên mắm": "Cánh gà 3 cái",
        "Cánh gà nướng muối ớt": "Cánh gà 3 cái",
        "Cánh gà nướng tây bắc": "Cánh gà 3 cái",
        "Vịt quay thảo mộc": "Vịt 1/2 con (900g)",
        "Chân gà nướng": "Chân gà 5 cặp",
        
        # Heo - Bò
        "Bò xuyên tiêu": "Thịt bò 250g",
        "Heo nướng giềng mẻ": "Thịt ba chỉ 350g",
        "Bò Kho Bánh Mì Đặc Biệt": "Bò nạm 250g + 1 bánh mì",
        
        # Hải Sản
        "Gỏi khoai môn hải sản": "Khoai môn 300g, hải sản 120g",
        "Gỏi xoài tôm khô": "Xoài 300g, tôm khô 40g",
        "Lẩu gà thuốc bắc": "Gà ta 1 con (1.3kg) + thuốc bắc",
        "Hàu nướng phô mai": "Hàu sữa 1 con",
        "Hàu nướng mỡ hành": "Hàu sữa 1 con",
        "Nghêu hấp sả": "Nghêu 500g",
        "Nghêu hấp Thái": "Nghêu 500g",
        "Tôm sốt bơ tỏi": "Tôm sú 250g",
        "Tôm hấp": "Tôm sú 250g",
        "Tôm nướng muối ớt": "Tôm sú 250g",
        "Ốc hương sốt trứng muối - bánh mì": "Ốc hương 250g + 1 bánh mì",
        "Ốc hương hấp sả": "Ốc hương 250g",
        "Ốc hương cháy tỏi": "Ốc hương 250g",
        "Ốc móng tay cháy tỏi": "Ốc móng tay 300g",
        "Ốc móng tay nướng mỡ hành": "Ốc móng tay 300g",
        "Ốc móng tay xào rau muống": "Ốc móng tay 200g, rau muống 200g",
        "Bạch tuộc xào cay": "Bạch tuộc 300g",
        "Bạch tuộc nướng muối ớt": "Bạch tuộc 300g",
        "Bạch tuộc hấp hành gừng": "Bạch tuộc 300g",
        
        # Cơm - Mì
        "Cơm chiên hải sản": "Cơm 250g, hải sản 100g",
        "Cơm chiên bò": "Cơm 250g, thịt bò 100g",
        "Cơm chiên ghẹ": "Cơm 250g, thịt ghẹ 80g",
        "Cơm chiên": "Cơm 250g, Ghẹ / Hải sản / Bò 80-100g",
        "Mì xào hải sản": "Mì 2 vắt, hải sản 100g",
        "Mì xào bò": "Mì 2 vắt, thịt bò 100g",
        "Mì xào": "Mì 2 vắt, Bò hoặc Hải sản 100g",
        
        # Đồ Uống
        "Trà Đào Cam Sả PiPo Special": "1 ly (500ml)",
        "Trà Mãng Cầu Xiêm Nhiệt Đới": "1 ly (500ml)",
        "Nước Ép Dưa Hấu Bạc Hà": "1 ly (350ml)",
        "Nước suối": "1 chai (500ml)",
        "Coca Cola": "1 lon (320ml)",
        "Pepsi": "1 lon (320ml)",
        "Aquarius": "1 chai (390ml)",
        "Revive": "1 chai (500ml)",
        "Bia Bivina": "1 lon (330ml)",
        "Bia Sài Gòn": "1 lon (330ml)",
        "Bia Heineken": "1 lon (250ml)",
        "Cà Phê Đen Pha Phin": "1 ly",
        "Cà Phê Sữa Đá Sài Gòn": "1 ly",
        "Bạc Xỉu Kem Béo PiPo": "1 ly",
    }
    for name, portion in PORTIONS.items():
        cursor.execute("UPDATE menu_items SET portion = ? WHERE name = ? AND (portion IS NULL OR portion = '')", (portion, name))
    conn.commit()


def consolidate_menu_items_with_options(conn):
    """
    Gom các món ăn cùng loại nguyên liệu thành một món chính kèm tùy chọn vị chế biến (options_json):
    1. Ốc hương (Sốt trứng muối, Cháy tỏi, Hấp sả)
    2. Ốc móng tay (Cháy tỏi, Nướng mỡ hành, Xào rau muống)
    3. Bạch tuộc (Nướng muối ớt, Xào cay, Hấp hành gừng)
    4. Tôm sú (Hấp nước dừa / sả, Nướng muối ớt, Sốt bơ tỏi)
    5. Nghêu (Hấp sả, Hấp Thái)
    6. Gà ta nguyên con + Lòng mề xào (Nướng muối ớt, Hấp mắm nhĩ, Chiên mắm, Hấp hành, Nướng Tây Bắc)
    7. Cánh gà (Nướng muối ớt, Chiên mắm, Nướng Tây Bắc)
    8. Đậu hũ (Chiên giòn, Tẩm hành)
    """
    cursor = conn.cursor()

    # Kiểm tra an toàn: Nếu các món chính đã có tùy chọn vị (options_json) thì không ghi đè lại,
    # bảo vệ 100% các chỉnh sửa thủ công của chủ quán trên giao diện Admin.
    cursor.execute("SELECT COUNT(*) FROM menu_items WHERE options_json IS NOT NULL AND options_json != '[]' AND options_json != ''")
    has_options = cursor.fetchone()[0]
    if has_options > 0:
        return

    CONSOLIDATIONS = [
        {
            "parent_id": 169,
            "name": "Ốc hương",
            "price": 150000,
            "portion": "Ốc hương 250g",
            "description": "Ốc hương tươi sống Phú Quốc giòn ngọt đậm đà, tùy chọn xào sốt trứng muối béo ngậy kèm bánh mì, cháy tỏi thơm lừng hoặc hấp sả thanh ngọt.",
            "options": [
                {
                    "name": "Chọn vị chế biến",
                    "options": ["Sốt trứng muối (kèm bánh mì)", "Cháy tỏi", "Hấp sả"]
                }
            ],
            "translations": {
                "en": {
                    "name": "Sweet Snails (Choose Preparation/Flavor)",
                    "description": "Fresh sweet snails with choice of rich salted egg sauce & baguette, fragrant crispy garlic, or steamed with lemongrass."
                },
                "zh": {
                    "name": "香螺 (选择口味/做法)",
                    "description": "新鲜香螺，可选金沙咸蛋黄酱配法棍、金蒜爆炒或原味清蒸香茅。"
                },
                "ko": {
                    "name": "골뱅이 / 향고둥 (조리 방식/맛 선택)",
                    "description": "신선한 골뱅이 요리. 솔티드 에그 소스(바게트 포함), 마늘 볶음, 레몬그라스 찜 중 선택."
                },
                "ru": {
                    "name": "Морские улитки (выберите вкус)",
                    "description": "Свежие улитки на выбор: в соусе из соленого желтка с багетом, с хрустящим чесноком или на пару с лемонграссом."
                }
            },
            "deactivate_ids": [170, 171]
        },
        {
            "parent_id": 172,
            "name": "Ốc móng tay",
            "price": 99000,
            "portion": "Ốc móng tay 300g",
            "description": "Ốc móng tay tươi dày thịt giòn ngọt, tùy chọn cháy tỏi thơm nức, nướng mỡ hành đậu phộng hoặc xào rau muống giòn ngon.",
            "options": [
                {
                    "name": "Chọn vị chế biến",
                    "options": ["Cháy tỏi", "Nướng mỡ hành", "Xào rau muống"]
                }
            ],
            "translations": {
                "en": {
                    "name": "Razor Clams (Choose Preparation/Flavor)",
                    "description": "Tender razor clams with choice of crispy garlic, grilled scallion oil & peanuts, or stir-fried with morning glory."
                },
                "zh": {
                    "name": "竹蛏 (选择口味/做法)",
                    "description": "鲜嫩竹蛏，可选金蒜爆炒、葱油炭烤配花生或蒜炒空心菜。"
                },
                "ko": {
                    "name": "맛조개 요리 (조리 방식/맛 선택)",
                    "description": "쫄깃한 맛조개 요리. 마늘 볶음, 파기름 숯불구이, 모닝글로리 볶음 중 선택."
                },
                "ru": {
                    "name": "Морские черенки (выберите вкус)",
                    "description": "Нежные морские черенки: с чесноком, на гриле с зеленым луком и арахисом или с водяным шпинатом."
                }
            },
            "deactivate_ids": [173, 174]
        },
        {
            "parent_id": 176,
            "name": "Bạch tuộc",
            "price": 150000,
            "portion": "Bạch tuộc 300g",
            "description": "Bạch tuộc tươi giòn sần sật, tùy chọn nướng muối ớt than hoa cay giòn, xào cay đậm vị hoặc hấp hành gừng thơm lừng.",
            "options": [
                {
                    "name": "Chọn vị chế biến",
                    "options": ["Nướng muối ớt", "Xào cay", "Hấp hành gừng"]
                }
            ],
            "translations": {
                "en": {
                    "name": "Fresh Octopus (Choose Preparation/Flavor)",
                    "description": "Crisp and succulent octopus with choice of chili salt BBQ, spicy stir-fry, or steamed with ginger & scallions."
                },
                "zh": {
                    "name": "鲜章鱼 (选择口味/做法)",
                    "description": "鲜嫩弹牙章鱼，可选椒盐炭烤、香辣爆炒或葱姜清蒸。"
                },
                "ko": {
                    "name": "문어 요리 (조리 방식/맛 선택)",
                    "description": "쫄깃한 생문어 요리. 칠리 솔트 숯불구이, 매콤 볶음, 생강파 찜 중 선택."
                },
                "ru": {
                    "name": "Свежий осьминог (выберите вкус)",
                    "description": "Хрустящий осьминог на выбор: на гриле с чили и солью, острый вок или на пару с имбирем и луком."
                }
            },
            "deactivate_ids": [175, 177]
        },
        {
            "parent_id": 167,
            "name": "Tôm sú",
            "price": 179000,
            "portion": "Tôm sú 250g",
            "description": "Tôm sú tươi sống chắc thịt ngọt nước, tùy chọn hấp nước dừa sả thanh mát, nướng than hoa muối ớt cay giòn hoặc sốt bơ tỏi thơm ngậy.",
            "options": [
                {
                    "name": "Chọn vị chế biến",
                    "options": ["Hấp nước dừa / sả", "Nướng muối ớt", "Sốt bơ tỏi"]
                }
            ],
            "translations": {
                "en": {
                    "name": "Tiger Prawns (Choose Preparation/Flavor)",
                    "description": "Fresh juicy tiger prawns with choice of coconut & lemongrass steam, charcoal chili salt BBQ, or rich garlic butter sauce."
                },
                "zh": {
                    "name": "黑虎虾 (选择口味/做法)",
                    "description": "紧致鲜甜黑虎虾，可选椰汁香茅清蒸、椒盐炭烤或浓香蒜蓉黄油炒。"
                },
                "ko": {
                    "name": "블랙 타이거 새우 (조리 방식/맛 선택)",
                    "description": "통통하고 달콤한 새우 요리. 코코넛 레몬그라스 찜, 칠리 솔트 숯불구이, 갈릭버터 소스 중 선택."
                },
                "ru": {
                    "name": "Тигровые креветки (выберите вкус)",
                    "description": "Свежие сочные креветки на выбор: на пару с кокосом и лемонграссом, на гриле с чили или в чесночно-сливочном соусе."
                }
            },
            "deactivate_ids": [166, 168]
        },
        {
            "parent_id": 164,
            "name": "Nghêu",
            "price": 79000,
            "portion": "Nghêu 500g",
            "description": "Nghêu tươi sống béo ngọt, tùy chọn hấp sả thơm thanh ngọt nước hoặc hấp Thái chua cay đậm đà ấm nồng.",
            "options": [
                {
                    "name": "Chọn vị chế biến",
                    "options": ["Hấp sả", "Hấp Thái"]
                }
            ],
            "translations": {
                "en": {
                    "name": "Fresh Clams (Choose Preparation/Flavor)",
                    "description": "Fresh sweet clams with choice of fragrant lemongrass steam or spicy sour Tom Yum Thai style."
                },
                "zh": {
                    "name": "鲜蛤蜊 (选择口味/做法)",
                    "description": "鲜美饱满蛤蜊，可选原味香茅清蒸或酸辣开胃泰式冬阴风味。"
                },
                "ko": {
                    "name": "조개 요리 (조리 방식/맛 선택)",
                    "description": "신선한 조개 요리. 향긋한 레몬그라스 맑은 찜 또는 칼칼한 똠얌 태국식 찜 중 선택."
                },
                "ru": {
                    "name": "Свежие моллюски (выберите вкус)",
                    "description": "Свежие моллюски на выбор: на пару с ароматным лемонграссом или в остро-кислом тайском бульоне."
                }
            },
            "deactivate_ids": [165]
        },
        {
            "parent_id": 150,
            "name": "Gà ta nguyên con + Lòng mề xào",
            "price": 350000,
            "portion": "Gà ta 1 con (1.3kg) + lòng mề",
            "description": "Gà ta thả vườn Phú Quốc nguyên con thịt chắc ngọt da giòn kèm đĩa lòng mề xào mướp thơm nức. Tùy chọn 5 kiểu chế biến thượng hạng.",
            "options": [
                {
                    "name": "Chọn vị chế biến",
                    "options": ["Nướng muối ớt", "Hấp mắm nhĩ", "Chiên mắm", "Hấp hành", "Nướng Tây Bắc"]
                }
            ],
            "translations": {
                "en": {
                    "name": "Whole Free-Range Chicken + Sautéed Giblets (Choose Cooking Style)",
                    "description": "Whole free-range chicken (~1.3kg) + sautéed giblets. Choice of Chili Salt BBQ, Phú Quốc Fish Sauce Steam, Crispy Fish Sauce Fried, Steamed with Scallions, or Northwest Herb Grilled."
                },
                "zh": {
                    "name": "整只走地土鸡 + 爆炒鸡杂 (选择做法)",
                    "description": "整只散养土鸡（约1.3公斤）搭配爆炒鸡杂。可选椒盐炭烤、鱼露原汁蒸、香脆鱼露炸、鲜葱清蒸或西北香草风味炭烤。"
                },
                "ko": {
                    "name": "토종 통닭 요리 + 닭똥집 볶음 (조리 방식 선택)",
                    "description": "토종 통닭 한 마리(~1.3kg)와 닭똥집 볶음 세트. 칠리 솔트 숯불구이, 피시소스 찜, 바삭한 피시소스 튀김, 파 찜, 서북 허브 숯불구이 중 선택."
                },
                "ru": {
                    "name": "Целая домашняя курица + потроха (выберите способ приготовления)",
                    "description": "Целая домашняя курица (~1.3 кг) с жареными потрошками. На выбор: на гриле с солью и чили, на пару с рыбным соусом, хрустящая жареная, на пару с луком или пряная по-северозападному."
                }
            },
            "deactivate_ids": [149, 151, 152, 155]
        },
        {
            "parent_id": 157,
            "name": "Cánh gà",
            "price": 99000,
            "portion": "Cánh gà 3 cái",
            "description": "Cánh gà tươi giòn rụm bên ngoài mọng nước bên trong, tùy chọn nướng muối ớt than hoa cay nhẹ, chiên nước mắm mặn ngọt đậm đà hoặc nướng Tây Bắc mắc khén thơm nồng.",
            "options": [
                {
                    "name": "Chọn vị chế biến",
                    "options": ["Nướng muối ớt", "Chiên mắm", "Nướng Tây Bắc"]
                }
            ],
            "translations": {
                "en": {
                    "name": "Chicken Wings (Choose Preparation/Flavor)",
                    "description": "Crispy juicy chicken wings with choice of Chili Salt BBQ, Glazed Fish Sauce, or Aromatic Northwest Pepper BBQ."
                },
                "zh": {
                    "name": "鸡翅 (选择口味/做法)",
                    "description": "外酥里嫩鸡翅，可选椒盐炭烤、金牌鱼露酱炒或西北特色野胡椒风味。"
                },
                "ko": {
                    "name": "닭날개 요리 (조리 방식/맛 선택)",
                    "description": "겉바속촉 닭날개 요리. 칠리 솔트 숯불구이, 단짠 피시소스 튀김, 향긋한 서북 허브 구이 중 선택."
                },
                "ru": {
                    "name": "Куриные крылышки (выберите вкус)",
                    "description": "Сочные крылышки с хрустящей корочкой: на гриле с чили и солью, в карамельном рыбном соусе или с пряными травами."
                }
            },
            "deactivate_ids": [156, 158]
        },
        {
            "parent_id": 146,
            "name": "Đậu hũ",
            "price": 79000,
            "portion": "Đậu phụ 4 bìa",
            "description": "Đậu hũ non vàng ươm thanh đạm, ngoài giòn rụm trong mềm mịn tan chảy, tùy chọn chiên giòn chấm mắm tôm/nước tương hoặc nhúng mỡ hành béo thơm kiểu truyền thống.",
            "options": [
                {
                    "name": "Chọn vị chế biến",
                    "options": ["Chiên giòn", "Tẩm hành"]
                }
            ],
            "translations": {
                "en": {
                    "name": "Fresh Tofu (Choose Style)",
                    "description": "Crispy golden exterior, silky melt-in-mouth tofu. Choose classic Golden Crispy or Tossed with Scallion Oil."
                },
                "zh": {
                    "name": "鲜豆腐 (选择做法)",
                    "description": "外脆里嫩手工鲜豆腐，可选金黄脆炸或传统葱油浸香做法。"
                },
                "ko": {
                    "name": "두부 요리 (조리 방식 선택)",
                    "description": "겉은 바삭하고 속은 부드러운 두부 요리. 바삭한 황금 튀김 또는 고소한 파기름 양념 중 선택."
                },
                "ru": {
                    "name": "Тофу (выберите стиль)",
                    "description": "Нежный тофу с хрустящей золотистой корочкой. На выбор: хрустящий жареный или с зеленым луком в масле."
                }
            },
            "deactivate_ids": [141]
        }
    ]

    for item in CONSOLIDATIONS:
        opts_str = json.dumps(item["options"], ensure_ascii=False)
        trans_str = json.dumps(item["translations"], ensure_ascii=False)
        cursor.execute("""
            UPDATE menu_items
            SET name = ?, price = ?, portion = ?, description = ?, options_json = ?, translations_json = ?, is_available = 1
            WHERE id = ?
        """, (item["name"], item["price"], item["portion"], item["description"], opts_str, trans_str, item["parent_id"]))

        for did in item["deactivate_ids"]:
            cursor.execute("DELETE FROM recipe_bom WHERE menu_item_id = ?", (did,))
            cursor.execute("DELETE FROM menu_items WHERE id = ?", (did,))

    conn.commit()


def clean_redundant_dishes_and_secondary_bom(conn):
    """
    1. Xóa vĩnh viễn các món con thừa/đã ẩn sau khi gom món theo nguyên liệu chính và vị.
    2. Xóa toàn bộ NVL phụ (tỏi, ớt, nước mắm, sốt, gia vị, bơ phụ, hành...) chỉ giữ lại NVL chính của từng món.
    3. Clear toàn bộ các món đang chọn cho Sân Pickle để người dùng tự tick thủ công.
    """
    cursor = conn.cursor()

    # Kiểm tra an toàn: Nếu các món con thừa đã được dọn sạch thì không chạy lại,
    # tránh reset lại phân loại món Sân Pickle người dùng đã tick thủ công.
    DELETED_CHILD_DISH_IDS = [141, 149, 151, 152, 155, 156, 158, 165, 166, 168, 170, 171, 173, 174, 175, 177]
    cursor.execute(f"SELECT COUNT(*) FROM menu_items WHERE id IN ({','.join(['?']*len(DELETED_CHILD_DISH_IDS))})", DELETED_CHILD_DISH_IDS)
    if cursor.fetchone()[0] == 0:
        return

    # 1. Xóa các món con thừa (các món đã gom vào món chính với tùy chọn vị)
    cursor.execute(f"DELETE FROM recipe_bom WHERE menu_item_id IN ({','.join(['?']*len(DELETED_CHILD_DISH_IDS))})", DELETED_CHILD_DISH_IDS)
    cursor.execute(f"DELETE FROM menu_items WHERE id IN ({','.join(['?']*len(DELETED_CHILD_DISH_IDS))})", DELETED_CHILD_DISH_IDS)

    # 2. Xóa toàn bộ NVL phụ (gia vị, hành sả, tỏi ớt, mắm muối, bơ phụ...)
    SECONDARY_CODES = ['NVL19', 'NVL22', 'NVL24', 'NVL25', 'NVL26', 'NVL30', 'NVL34', 'NVL35', 'NVL36', 'NVL38', 'NVL39']
    cursor.execute(f"""
        DELETE FROM recipe_bom 
        WHERE ingredient_id IN (SELECT id FROM inventory_items WHERE code IN ({','.join(['?']*len(SECONDARY_CODES))}))
    """, SECONDARY_CODES)
    cursor.execute(f"""
        DELETE FROM inventory_items 
        WHERE code IN ({','.join(['?']*len(SECONDARY_CODES))})
    """, SECONDARY_CODES)

    # 3. Clear tất cả các món đang chọn cho Sân Pickle (chuyển về RESTAURANT để người dùng tự tick)
    cursor.execute("""
        UPDATE menu_items
        SET main_menu_type = 'RESTAURANT'
        WHERE main_menu_type LIKE '%PICKLE%'
    """)

def ensure_pickleball_snack_dishes(conn):
    """
    Đảm bảo các món ăn nhẹ Sân Pickleball:
    - Trứng gà luộc (10.000 đ, sẵn sàng để bán)
    - Ngô luộc - Coming Soon (0 đ, để hết hàng)
    """
    cursor = conn.cursor()
    # 1. Trứng gà luộc
    cursor.execute("SELECT id FROM menu_items WHERE name = 'Trứng gà luộc'")
    egg = cursor.fetchone()
    egg_translations = {
        "en": {"name": "Boiled Chicken Egg", "description": "Fresh soft-boiled egg, rich in natural protein for athletes."},
        "zh": {"name": "水煮土鸡蛋", "description": "精选新鲜水煮鸡蛋，营养丰富，快速补充运动能量。"},
        "ko": {"name": "삶은 계란", "description": "신선한 삶은 달걀, 피클볼 경기 중 빠른 단백질 보충 간식."},
        "ru": {"name": "Вареное яйцо", "description": "Свежее вареное яйцо, отличный источник белка для спортсменов."}
    }
    if not egg:
        cursor.execute("""
            INSERT INTO menu_items (
                category_id, name, price, portion, description, image_url,
                station, options_json, translations_json, is_available,
                out_of_ingredients, main_menu_type
            ) VALUES (1, 'Trứng gà luộc', 10000, '1 quả', 'Trứng gà ta luộc thơm ngon, giàu protein bổ sung năng lượng nhanh chóng cho người chơi thể thao tại sân Pickleball.', '/static/logo.png', 'HOT_KITCHEN', '[]', ?, 1, 0, 'RESTAURANT,PICKLE')
        """, (json.dumps(egg_translations, ensure_ascii=False),))
    else:
        cursor.execute("""
            UPDATE menu_items 
            SET price = 10000, is_available = 1, out_of_ingredients = 0,
                main_menu_type = CASE WHEN main_menu_type LIKE '%PICKLE%' THEN main_menu_type ELSE main_menu_type || ',PICKLE' END
            WHERE id = ?
        """, (egg["id"],))

    # 2. Ngô luộc - Coming Soon
    cursor.execute("SELECT id FROM menu_items WHERE name = 'Ngô luộc - Coming Soon' OR name = 'Ngô luộc'")
    corn = cursor.fetchone()
    corn_translations = {
        "en": {"name": "Boiled Sweet Corn (Coming Soon)", "description": "Freshly boiled sweet corn (Coming soon)."},
        "zh": {"name": "香甜水煮玉米 (即将推出)", "description": "新鲜香甜水煮玉米 (敬请期待)。"},
        "ko": {"name": "삶은 옥수수 (출시 예정)", "description": "달콤하고 고소한 찐 옥수수 (출시 예정)."},
        "ru": {"name": "Вареная кукуруза (Скоро в меню)", "description": "Сладкая вареная кукуруза (Скоро появится)."}
    }
    if not corn:
        cursor.execute("""
            INSERT INTO menu_items (
                category_id, name, price, portion, description, image_url,
                station, options_json, translations_json, is_available,
                out_of_ingredients, main_menu_type
            ) VALUES (1, 'Ngô luộc - Coming Soon', 0, '1 bắp', 'Bắp ngô ngọt luộc nóng hổi, thơm bùi tự nhiên (Món sắp ra mắt - Coming Soon).', '/static/logo.png', 'HOT_KITCHEN', '[]', ?, 0, 1, 'RESTAURANT,PICKLE')
        """, (json.dumps(corn_translations, ensure_ascii=False),))
    else:
        cursor.execute("""
            UPDATE menu_items 
            SET name = 'Ngô luộc - Coming Soon', price = 0, is_available = 0, out_of_ingredients = 1,
                main_menu_type = CASE WHEN main_menu_type LIKE '%PICKLE%' THEN main_menu_type ELSE main_menu_type || ',PICKLE' END
            WHERE id = ?
        """, (corn["id"],))

    conn.commit()

def ensure_bbq_category_and_dishes(conn):
    """
    Đảm bảo danh mục 'Hot BBQ' đứng đầu tiên trên thực đơn (display_order = 0)
    và thêm 5 món BBQ nướng sân vườn đặc sắc kèm tùy chọn vị và định lượng BOM.
    """
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN portion TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN calories INTEGER DEFAULT 0")
    except Exception:
        pass

    # 1. Tạo hoặc cập nhật Category Hot BBQ
    cursor.execute("SELECT id, display_order FROM categories WHERE name = 'Hot BBQ'")
    bbq_cat = cursor.fetchone()

    bbq_translations = {
        "en": "Garden Hot BBQ",
        "zh": "炭火热烤 (花园BBQ)",
        "ko": "가든 숯불 핫 BBQ",
        "ru": "Горячее барбекю в саду"
    }

    if bbq_cat:
        bbq_cat_id = bbq_cat["id"]
        cursor.execute("""
            UPDATE categories 
            SET display_order = 1, icon = '🔥', is_active = 1, translations_json = ? 
            WHERE id = ?
        """, (json.dumps(bbq_translations, ensure_ascii=False), bbq_cat_id))
    else:
        cursor.execute("""
            INSERT INTO categories (id, name, icon, display_order, is_active, translations_json)
            VALUES (7, 'Hot BBQ', '🔥', 1, 1, ?)
        """, (json.dumps(bbq_translations, ensure_ascii=False),))
        bbq_cat_id = cursor.lastrowid or 7

    # Đảm bảo thứ tự hiển thị chuẩn của toàn bộ danh mục Menu (Hot BBQ & Best Seller dẫn đầu)
    OTHER_ORDERS = {
        "Hot BBQ": 1,
        "Best Seller": 2,
        "Khai Vị": 3,
        "Gà - Vịt": 4,
        "Heo - Bò": 5,
        "Hải Sản": 6,
        "Cơm - Mì": 7,
        "Súp - Cháo": 8,
        "Món Lẩu": 9,
        "Đồ Uống": 10,
        "Dịch Vụ Sân Pickleball": 11
    }
    for cname, corder in OTHER_ORDERS.items():
        cursor.execute("UPDATE categories SET display_order = ? WHERE name = ?", (corder, cname))

    # 2. Thêm 5 món Garden BBQ chuẩn phong cách sân vườn PiPo Garden
    BBQ_DISHES = [
        {
            "name": "Dẻ sườn bò Mỹ nướng sốt BBQ",
            "price": 225000,
            "portion": "Dẻ sườn bò 350g",
            "description": "Dẻ sườn bò Mỹ vân mỡ đều nướng thơm xì xèo trên than hoa ngoài trời, thịt mềm ngọt đậm đà, ăn kèm rau củ nướng.",
            "image_url": "/static/dishes/bo_xuyen_tieu.jpg",
            "options": [
                {"name": "Chọn vị sốt nướng", "options": ["Sốt BBQ cay ngọt", "Nướng muối ớt", "Sốt tiêu đen"]}
            ],
            "translations": {
                "en": {
                    "name": "Grilled US Beef Ribs (Choose Sauce)",
                    "description": "Tender grilled US beef ribs on open flame garden BBQ, served with choice of Sweet Spicy BBQ sauce, Chili Salt, or Black Pepper sauce."
                },
                "zh": {
                    "name": "炭烤美式牛肋条 (选风味酱汁)",
                    "description": "精选美式牛肋条，炭火慢烤香嫩多汁，可选甜辣BBQ酱、椒盐香烤或黑椒浓汁。"
                },
                "ko": {
                    "name": "미국산 소갈비살 숯불구이 (소스 선택)",
                    "description": "숯불에 직접 구워 풍미 가득한 소갈비살. 스위트 스파이시 BBQ, 칠리 솔트, 블랙페퍼 소스 중 선택."
                },
                "ru": {
                    "name": "Говяжьи ребрышки на гриле (выберите соус)",
                    "description": "Нежные говяжьи ребрышки на открытом огне барбекю: сладкий BBQ, острый с солью и чили или черный перец."
                }
            },
            "bom": [("NVL10", 0.35)]
        },
        {
            "name": "Sườn heo que nướng mật ong thảo mộc",
            "price": 165000,
            "portion": "Sườn heo que 400g",
            "description": "Từng dẻ sườn que nướng than hoa vàng rộm, mọng nước, dậy hương thơm mật ong hoa rừng và thảo mộc Phú Quốc.",
            "image_url": "/static/dishes/suon_heo_nuong_muoi_ot.jpg",
            "options": [
                {"name": "Chọn vị sốt nướng", "options": ["Ướp mật ong thảo mộc", "Nướng muối ớt", "Sốt BBQ cay nhẹ"]}
            ],
            "translations": {
                "en": {
                    "name": "Honey Herb Grilled Pork Ribs (Choose Flavor)",
                    "description": "Juicy grilled pork ribs with crispy golden crust, wild honey and island herbs. Choose Honey Herb, Chili Salt, or Mild BBQ sauce."
                },
                "zh": {
                    "name": "秘制蜜汁香草烤猪排 (选风味)",
                    "description": "炭火烤制猪排骨，外焦里嫩，可选野生蜂蜜香草、招牌椒盐或温和BBQ酱。"
                },
                "ko": {
                    "name": "허브 꿀 양념 돼지등갈비 구이 (맛 선택)",
                    "description": "천연 꿀과 허브로 숯불에 노릇하게 구워낸 등갈비. 허니 허브, 칠리 솔트, 마일드 BBQ 중 선택."
                },
                "ru": {
                    "name": "Свиные ребрышки с медом и травами (выберите вкус)",
                    "description": "Сочные свиные ребрышки на гриле: с диким медом и травами, с солью и чили или с мягким соусом BBQ."
                }
            },
            "bom": [("NVL11", 0.4)]
        },
        {
            "name": "Bò cuộn nấm kim châm nướng sốt BBQ",
            "price": 145000,
            "portion": "Bò cuộn nấm 250g (6 cuộn)",
            "description": "Thịt bò thăn thái lát cuộn nấm kim châm tươi giòn ngọt, quết đẫm sốt BBQ nướng than hoa xì xèo đậm đà.",
            "image_url": "/static/dishes/bo_xuyen_tieu.jpg",
            "options": [
                {"name": "Chọn vị sốt nướng", "options": ["Sốt BBQ cay ngọt", "Sốt tiêu đen", "Nướng muối ớt"]}
            ],
            "translations": {
                "en": {
                    "name": "Grilled Beef Rolls with Enoki Mushrooms",
                    "description": "Thinly sliced tender beef rolled with crisp enoki mushrooms, glazed with rich BBQ sauce on charcoal grill."
                },
                "zh": {
                    "name": "肥牛金针菇卷炭火烤 (选酱汁)",
                    "description": "鲜嫩牛肉片包裹爽脆金针菇，刷上秘制烤肉酱炭火炙烤。"
                },
                "ko": {
                    "name": "팽이버섯 소고기말이 숯불구이",
                    "description": "부드러운 소고기로 감싼 아삭한 팽이버섯 숯불구이. 스위트 BBQ, 블랙페퍼, 칠리 솔트 중 선택."
                },
                "ru": {
                    "name": "Рулетики из говядины с грибами эноки на гриле",
                    "description": "Тонкие ломтики говядины с грибами эноки на гриле, глазированные соусом BBQ."
                }
            },
            "bom": [("NVL10", 0.25)]
        },
        {
            "name": "Xiên nướng tổng hợp PiPo Garden",
            "price": 135000,
            "portion": "Xiên nướng 4 xiên lớn (300g)",
            "description": "Xiên nướng tổng hợp gồm thịt heo, bò, ớt chuông và hành tây nướng than hoa thơm lừng chuẩn phong cách BBQ dã ngoại.",
            "image_url": "/static/dishes/suon_heo_nuong_muoi_ot.jpg",
            "options": [
                {"name": "Chọn vị sốt nướng", "options": ["Sốt BBQ cay ngọt", "Muối ớt Tây Bắc", "Sốt bơ tỏi"]}
            ],
            "translations": {
                "en": {
                    "name": "PiPo Garden Mixed BBQ Skewers (4 Skewers)",
                    "description": "Mixed outdoor skewers with marinated pork, beef, bell peppers and onions grilled over hot charcoal."
                },
                "zh": {
                    "name": "PiPo花园特色综合烤串 (4大串)",
                    "description": "花园露营风味综合肉串，包含猪肉、牛肉、甜椒与洋葱，炭香浓郁。"
                },
                "ko": {
                    "name": "피포 가든 모듬 꼬치구이 (4꼬치)",
                    "description": "돼지고기, 소고기, 파프리카, 양파를 숯불에 구워낸 야외 바베큐 스타일 모듬 꼬치."
                },
                "ru": {
                    "name": "Ассорти шашлычков PiPo Garden (4 шпажки)",
                    "description": "Шашлычки из свинины, говядины, болгарского перца и лука на гриле в стиле садового барбекю."
                }
            },
            "bom": [("NVL11", 0.15), ("NVL10", 0.15)]
        },
        {
            "name": "Hàu nướng chén sốt BBQ",
            "price": 119000,
            "portion": "Hàu sữa 5 chén",
            "description": "Hàu sữa đại dương béo múp nướng trong từng chén nhôm trên bếp than hoa, sốt phô mai thơm ngậy hoặc mỡ hành tóp mỡ giòn tan.",
            "image_url": "/static/dishes/hau_nuong_pho_mai.jpg",
            "options": [
                {"name": "Chọn vị nướng", "options": ["Phô mai tan chảy", "Mỡ hành tóp mỡ", "Trứng cút sốt cay BBQ"]}
            ],
            "translations": {
                "en": {
                    "name": "Grilled Cup Oysters (5 Cups - Choose Flavor)",
                    "description": "Plump ocean oysters grilled in foil cups over charcoal flame. Choice of Melted Cheese, Scallion Oil & Crispy Pork Rind, or Quail Egg Spicy BBQ."
                },
                "zh": {
                    "name": "锡纸炭烤生蚝小盅 (5盅 - 选口味)",
                    "description": "肥美海生蚝置于锡纸盅炭烤，可选浓郁拉丝芝士、香脆葱油猪油渣或鹌鹑蛋甜辣酱。"
                },
                "ko": {
                    "name": "은박컵 숯불 생굴구이 (5개 - 토핑 선택)",
                    "description": "숯불 위 은박컵에서 지글지글 익어가는 신선한 굴. 녹아내리는 치즈, 대파 기름 & 돼지껍데기, 메추리알 매콤 BBQ 중 선택."
                },
                "ru": {
                    "name": "Запеченные устрицы в чашечках (5 шт)",
                    "description": "Свежие устрицы на углях в чашечках: с расплавленным сыром, луковым маслом со шкварками или острым BBQ с перепелиным яйцом."
                }
            },
            "bom": [("NVL04", 5.0)]
        }
    ]

    cursor.execute("SELECT COUNT(*) as cnt FROM menu_items WHERE category_id = ?", (bbq_cat_id,))
    existing_bbq_count = cursor.fetchone()["cnt"]

    # Chỉ khởi tạo các món BBQ mẫu nếu nhóm Hot BBQ hoàn toàn chưa có món nào
    if existing_bbq_count == 0:
        for dish in BBQ_DISHES:
            cursor.execute("SELECT id FROM menu_items WHERE name = ?", (dish["name"],))
            existing_dish = cursor.fetchone()
            opts_str = json.dumps(dish["options"], ensure_ascii=False)
            trans_str = json.dumps(dish["translations"], ensure_ascii=False)

            if not existing_dish:
                cursor.execute("""
                    INSERT INTO menu_items (
                        category_id, name, price, portion, description, image_url,
                        station, options_json, translations_json, is_available,
                        out_of_ingredients, main_menu_type
                    ) VALUES (?, ?, ?, ?, ?, ?, 'HOT_KITCHEN', ?, ?, 1, 0, 'RESTAURANT')
                """, (bbq_cat_id, dish["name"], dish["price"], dish["portion"], dish["description"], dish["image_url"], opts_str, trans_str))
                dish_id = cursor.lastrowid

                # Gán định lượng NVL cốt lõi (BOM)
                for ing_code, qty in dish["bom"]:
                    cursor.execute("SELECT id FROM inventory_items WHERE code = ?", (ing_code,))
                    ing_row = cursor.fetchone()
                    if ing_row:
                        ing_id = ing_row["id"]
                        cursor.execute("""
                            INSERT OR REPLACE INTO recipe_bom (menu_item_id, ingredient_id, quantity)
                            VALUES (?, ?, ?)
                        """, (dish_id, ing_id, qty))

    conn.commit()


def sync_dish_calories(conn):
    """Tính toán và đồng bộ chỉ số Calo cho toàn bộ món ăn dựa theo định lượng NVL (BOM)."""
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN calories INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE inventory_items ADD COLUMN calories_per_unit REAL DEFAULT 0")
    except Exception:
        pass

    ING_CALORIES = {
        'NVL01': 850, 'NVL02': 820, 'NVL03': 860, 'NVL04': 65, 'NVL05': 480,
        'NVL06': 2690, 'NVL07': 1650, 'NVL08': 2150, 'NVL09': 2800, 'NVL10': 2450,
        'NVL11': 2900, 'NVL12': 2300, 'NVL13': 1120, 'NVL14': 1600, 'NVL15': 85,
        'NVL16': 580, 'NVL17': 230, 'NVL18': 170, 'NVL19': 320, 'NVL20': 1750,
        'NVL21': 280, 'NVL22': 4200, 'NVL23': 78, 'NVL24': 110, 'NVL25': 480,
        'NVL26': 950, 'NVL27': 10, 'NVL28': 820, 'NVL29': 310, 'NVL30': 2600,
        'NVL31': 780, 'NVL32': 2150, 'NVL33': 840, 'NVL34': 7200, 'NVL35': 360,
        'NVL36': 240, 'NVL37': 380, 'NVL38': 300, 'NVL39': 1100, 'NVL40': 1580,
        'NVL41': 0, 'NVL42': 139, 'NVL43': 145, 'NVL44': 86, 'NVL45': 95,
        'NVL46': 142, 'NVL47': 145, 'NVL48': 105, 'NVL100': 880
    }

    for code, cal in ING_CALORIES.items():
        cursor.execute("UPDATE inventory_items SET calories_per_unit = ? WHERE code = ?", (cal, code))

    cursor.execute("SELECT id, name FROM menu_items")
    dishes = cursor.fetchall()
    for d in dishes:
        mid = d["id"]
        cursor.execute("""
            SELECT i.code, r.quantity, i.calories_per_unit
            FROM recipe_bom r
            JOIN inventory_items i ON r.ingredient_id = i.id
            WHERE r.menu_item_id = ?
        """, (mid,))
        bom_items = cursor.fetchall()
        total_cal = 0
        for b in bom_items:
            qty = b["quantity"]
            c_unit = b["calories_per_unit"] or ING_CALORIES.get(b["code"], 500)
            total_cal += qty * c_unit

        cursor.execute("UPDATE menu_items SET calories = ? WHERE id = ?", (round(total_cal), mid))

    conn.commit()

def ensure_six_categories(conn):
    """Đảm bảo có đủ 6 nhóm danh mục chuẩn nếu cơ sở dữ liệu chưa có danh mục nào."""
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) as cnt FROM categories")
    count = cursor.fetchone()["cnt"]

    if count == 0:
        SIX_CATEGORIES = [
            (1, "Khai Vị", "🥗", 1, {"en": "Appetizers & Starters", "zh": "精选开胃前菜", "ko": "에피타이저 (전채요리)", "ru": "Аппетитные закуски"}),
            (2, "Gà - Vịt", "🍗", 2, {"en": "Poultry (Chicken & Duck)", "zh": "特色家禽 (土鸡/烤鸭)", "ko": "닭 & 오리 특선 요리", "ru": "Блюда из птицы (курица, утка)"}),
            (3, "Heo - Bò", "🥩", 3, {"en": "Pork & Beef Specialties", "zh": "经典猪肉 & 牛肉", "ko": "돼지고기 & 소고기 요리", "ru": "Мясные блюда (свинина, говядина)"}),
            (4, "Hải Sản", "🦐", 4, {"en": "Fresh Seafood", "zh": "鲜美海鲜特撰", "ko": "신선한 해산물 요리", "ru": "Свежие морепродукты"}),
            (5, "Cơm - Mì", "🍚", 5, {"en": "Rice & Noodles", "zh": "主食精选 (黄金炒饭/炒面)", "ko": "식사류 (볶음밥 & 볶음面)", "ru": "Рис и жареная лапша"}),
            (6, "Đồ Uống", "🍹", 6, {"en": "Beverages & Drinks", "zh": "冷饮果汁 & 啤酒", "ko": "시원한 음료 & 맥주", "ru": "Прохладительные напитки и пиво"})
        ]

        for cat_id, name, icon, order, trans in SIX_CATEGORIES:
            cursor.execute("""
                INSERT OR IGNORE INTO categories (id, name, icon, display_order, is_active, translations_json)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (cat_id, name, icon, order, json.dumps(trans, ensure_ascii=False)))
        conn.commit()

def ensure_main_menu_classification(conn):
    """
    Đảm bảo các cột phân loại 3 Nhóm Thực Đơn Lớn tồn tại.
    Chỉ thiết lập mặc định RESTAURANT cho các món chưa có giá trị, bảo toàn tuyệt đối mọi chỉnh sửa của người dùng.
    """
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN out_of_ingredients INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE menu_items ADD COLUMN main_menu_type TEXT DEFAULT 'RESTAURANT'")
    except Exception:
        pass

    # Chỉ gán RESTAURANT cho món nào chưa có main_menu_type (NULL hoặc rỗng), bảo toàn chỉnh sửa của người dùng
    cursor.execute("""
        UPDATE menu_items 
        SET main_menu_type = 'RESTAURANT'
        WHERE main_menu_type IS NULL OR main_menu_type = ''
    """)
    conn.commit()

def seed_default_users(conn):
    cursor = conn.cursor()
    default_staff = [
        ("Thaitd", hash_password("123456"), "Thái TD", "SUPER_ADMIN", "0838993316"),
        ("admin", hash_password("admin123"), "Nguyễn Văn Quản Lý", "ADMIN", "0901234567"),
        ("thungan", hash_password("123456"), "Trần Thị Thu Ngân", "CASHIER", "0912345678"),
        ("bep", hash_password("123456"), "Lê Hoàng Bếp Trưởng", "CHEF", "0923456789"),
        ("phucvu", hash_password("123456"), "Phạm Minh Phục Vụ", "WAITER", "0934567890"),
        ("sanpick", hash_password("123456"), "Quản Trị Sân Pickleball", "PICKLEBALL", "0838993316"),
    ]
    for username, pwd_hash, full_name, role, phone in default_staff:
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, phone)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash,
                role = excluded.role
        """, (username, pwd_hash, full_name, role, phone))
    conn.commit()

def seed_sample_data(conn):
    cursor = conn.cursor()

    sample_tables = [
        ("V01", "Bàn Vườn 01", "Khu Sân Vườn", 4),
        ("V02", "Bàn Vườn 02", "Khu Sân Vườn", 4),
        ("V03", "Bàn Vườn 03", "Khu Sân Vườn", 6),
        ("V04", "Bàn Vườn 04", "Khu Sân Vườn", 8),
        ("VIP01", "Phòng VIP 01", "Khu Máy Lạnh", 10),
        ("VIP02", "Phòng VIP 02", "Khu Máy Lạnh", 12),
        ("L01", "Bàn Lầu 01", "Tầng Lửng Chill", 4),
        ("L02", "Bàn Lầu 02", "Tầng Lửng Chill", 4),
    ]

    for code, name, area, cap in sample_tables:
        token = generate_qr_token(code)
        cursor.execute(
            "INSERT INTO tables (table_code, name, area, capacity, qr_token) VALUES (?, ?, ?, ?, ?)",
            (code, name, area, cap, token)
        )

    categories = [
        ("Khai Vị", "🥗", 1),
        ("Gà - Vịt", "🍗", 2),
        ("Heo - Bò", "🥩", 3),
        ("Hải Sản", "🦐", 4),
        ("Cơm - Mì", "🍚", 5),
        ("Đồ Uống", "🍹", 6),
    ]

    cat_map = {}
    for name, icon, order in categories:
        cursor.execute("INSERT INTO categories (name, icon, display_order) VALUES (?, ?, ?)", (name, icon, order))
        cat_map[name] = cursor.lastrowid

    menu_items = [
        (cat_map["Món Nướng Sân Vườn"], "Bò Fuji Nướng Đá Núi Lửa", "Thịt bò Fuji thơm mềm nướng xèo xèo trên đá nham thạch tự nhiên, chấm sốt tiêu đen.", 195000, "https://images.unsplash.com/photo-1544025162-d76694265947?w=600", "HOT_KITCHEN", json.dumps([{"name": "Mức độ chín", "options": ["Tái (Rare)", "Vừa (Medium)", "Chín kỹ (Well-done)"]}])),
        (cat_map["Món Nướng Sân Vườn"], "Sườn Cây Nướng Sốt BBQ PiPo", "Sườn heo nguyên cây ướp sốt mật ong BBQ thảo mộc nướng vàng thơm lừng.", 185000, "https://images.unsplash.com/photo-1529193591184-b1d58069ecdd?w=600", "HOT_KITCHEN", "[]"),
        (cat_map["Món Nướng Sân Vườn"], "Gà Nướng Mắc Khén Tây Bắc", "Gà ta thả đồi nướng than hoa thơm mùi hạt mắc khén và hạt dổi rừng, da giòn rụm.", 220000, "https://images.unsplash.com/photo-1598515214211-89d3c73ae83b?w=600", "HOT_KITCHEN", "[]"),
        (cat_map["Món Nướng Sân Vườn"], "Mực Trứng Nướng Sa Tế", "Mực trứng tươi rói ôm trứng béo ngậy nướng sa tế cay the kích thích vị giác.", 165000, "https://images.unsplash.com/photo-1533777857889-4be7c70b33f7?w=600", "HOT_KITCHEN", json.dumps([{"name": "Độ cay", "options": ["Ít cay", "Cay vừa", "Cay nồng"]}])),
        (cat_map["Món Lẩu & Hầm Đặc Sản"], "Lẩu Thái Hải Sản Tomyum Sân Vườn", "Nước dùng chua cay đậm đà cốt dừa béo ngậy, tôm càng, mực, nghêu và nấm tươi.", 320000, "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=600", "HOT_KITCHEN", json.dumps([{"name": "Độ cay", "options": ["Chua cay vừa", "Cay đậm đà"]}])),
        (cat_map["Món Lẩu & Hầm Đặc Sản"], "Lẩu Bò Nhúng Mẻ Tây Nam Bộ", "Bò hoa tươi nhúng nước mẻ thanh mát ăn kèm bắp chuối, rau rừng tươi xanh.", 290000, "https://images.unsplash.com/photo-1547592180-85f173990554?w=600", "HOT_KITCHEN", "[]"),
        (cat_map["Khai Vị & Ăn Nhẹ"], "Gỏi Cuốn Tôm Thịt PiPo Garden", "Rau thơm trồng tại vườn cuốn bánh tráng phơi sương, chấm tương đen đậu phộng bùi bùi.", 75000, "https://images.unsplash.com/photo-1541544741938-0af808871cc0?w=600", "COLD_KITCHEN", "[]"),
        (cat_map["Khai Vị & Ăn Nhẹ"], "Khoai Tây Chiên Lắc Phô Mai", "Khoai tây cọng giòn rụm lắc đẫm bột phô mai béo ngọt.", 55000, "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=600", "COLD_KITCHEN", "[]"),
        (cat_map["Khai Vị & Ăn Nhẹ"], "Salad Cá Hồi Xông Khói Sốt Chanh Leo", "Cá hồi xông khói Na Uy kết hợp xà lách Romaine hữu cơ sốt chanh dây thanh mát.", 135000, "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=600", "COLD_KITCHEN", "[]"),
        (cat_map["Trà Trái Cây & Nước Ép"], "Trà Đào Cam Sả PiPo Special", "Trà lài ủ lạnh thơm nức cùng miếng đào giòn và sả cây thanh lọc cơ thể.", 48000, "https://images.unsplash.com/photo-1556881286-fc6915169721?w=600", "BAR", json.dumps([{"name": "Mức đường", "options": ["100% Đường", "70% Đường", "50% Đường", "Không đường"]}, {"name": "Mức đá", "options": ["100% Đá", "50% Đá", "Không đá"]}])),
        (cat_map["Trà Trái Cây & Nước Ép"], "Trà Mãng Cầu Xiêm Nhiệt Đới", "Mãng cầu xiêm chua ngọt tự nhiên hòa quyện trà olong hảo hạng sảng khoái.", 45000, "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=600", "BAR", json.dumps([{"name": "Mức đường", "options": ["100% Đường", "70% Đường", "50% Đường"]}])),
        (cat_map["Trà Trái Cây & Nước Ép"], "Nước Ép Dưa Hấu Bạc Hà", "Dưa hấu tươi ép nguyên chất 100% thêm lá bạc hà tươi vườn PiPo.", 42000, "https://images.unsplash.com/photo-1622597467836-f3285f2131b8?w=600", "BAR", "[]"),
        (cat_map["Bia & Đồ Uống Chill"], "Bia Thủ Công Hoegaarden Rosee (Chai)", "Bia lúa mì vị dâu rừng dịu nhẹ nồng độ 3% thích hợp tiệc ngoài trời.", 55000, "https://images.unsplash.com/photo-1608270190824-3402436f56df?w=600", "BAR", "[]"),
        (cat_map["Bia & Đồ Uống Chill"], "Bia Corona Extra (Ướp Lạnh Kèm Chanh)", "Bia Mexico phục vụ ướp xô đá kèm lát chanh vàng và muối biển chuẩn vị.", 52000, "https://images.unsplash.com/photo-1618886614638-80e3c15cd819?w=600", "BAR", "[]"),
    ]

    for cat_id, name, desc, price, img, station, options in menu_items:
        cursor.execute("""
            INSERT INTO menu_items (category_id, name, description, price, image_url, station, options_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cat_id, name, desc, price, img, station, options))

    conn.commit()

def seed_translations_if_missing(conn=None):
    """Tự động kiểm tra và bổ sung bản dịch 4 ngôn ngữ (en, zh, ko, ru) cho categories và menu_items (Không giữ khóa CSDL khi dịch)."""
    try:
        from .services.translator import translate_dish, translate_category_name
    except Exception as e:
        print("[PiPo Multi-Lang] Chua the import translator:", e)
        return

    try:
        read_conn = get_db()
        cursor = read_conn.cursor()
        
        # 1. Categories
        cursor.execute("SELECT id, name, translations_json FROM categories")
        cat_updates = []
        for cat in cursor.fetchall():
            trans_str = cat["translations_json"]
            needs_trans = False
            if not trans_str or trans_str in ("{}", '""', "null"):
                needs_trans = True
            else:
                try:
                    parsed = json.loads(trans_str)
                    if not isinstance(parsed, dict) or "en" not in parsed:
                        needs_trans = True
                except Exception:
                    needs_trans = True
            if needs_trans:
                cat_updates.append((cat["id"], cat["name"]))

        # 2. Menu Items
        cursor.execute("SELECT id, name, description, translations_json FROM menu_items")
        item_updates = []
        for item in cursor.fetchall():
            trans_str = item["translations_json"]
            needs_trans = False
            if not trans_str or trans_str in ("{}", '""', "null"):
                needs_trans = True
            else:
                try:
                    parsed = json.loads(trans_str)
                    if not isinstance(parsed, dict) or "en" not in parsed:
                        needs_trans = True
                except Exception:
                    needs_trans = True
            if needs_trans:
                item_updates.append((item["id"], item["name"], item["description"] or ""))

        read_conn.close()

        if not cat_updates and not item_updates:
            return

        # Dịch in-memory hoàn toàn KHÔNG giữ khóa CSDL
        cat_payloads = []
        for cid, cname in cat_updates:
            trans = translate_category_name(cname)
            cat_payloads.append((json.dumps(trans, ensure_ascii=False), cid))

        item_payloads = []
        for iid, iname, idesc in item_updates:
            trans = translate_dish(iname, idesc)
            item_payloads.append((json.dumps(trans, ensure_ascii=False), iid))

        # Ghi vào CSDL cực nhanh
        write_conn = get_db()
        w_cur = write_conn.cursor()
        for trans_json, cid in cat_payloads:
            w_cur.execute("UPDATE categories SET translations_json = ? WHERE id = ?", (trans_json, cid))
        for trans_json, iid in item_payloads:
            w_cur.execute("UPDATE menu_items SET translations_json = ? WHERE id = ?", (trans_json, iid))
        write_conn.commit()
        write_conn.close()
    except Exception as err:
        print("[PiPo Multi-Lang] Loi seed translations:", err)

def seed_historical_revenue(conn):
    """Tạo dữ liệu doanh thu mẫu 30 ngày gần nhất để phần báo cáo trực quan ngay lập tức."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, price, name, station FROM menu_items")
    items = [dict(r) for r in cursor.fetchall()]
    if not items:
        return

    cursor.execute("SELECT id FROM tables")
    table_ids = [r[0] for r in cursor.fetchall()]
    if not table_ids:
        return

    now = datetime.now()
    methods = ["VIETQR", "CASH", "VIETQR", "CARD"]

    # Tạo 45 đơn hàng trải đều 30 ngày qua
    for days_ago in range(30, -1, -1):
        order_date = now - timedelta(days=days_ago)
        daily_order_count = random.randint(1, 4) if days_ago > 0 else 2

        for _ in range(daily_order_count):
            t_id = random.choice(table_ids)
            hour = random.randint(10, 21)
            minute = random.randint(0, 59)
            dt_str = order_date.replace(hour=hour, minute=minute).strftime("%Y-%m-%d %H:%M:%S")

            # Tạo session giả
            cursor.execute("""
                INSERT INTO table_sessions (table_id, session_token, status, guest_count, opened_at, closed_at)
                VALUES (?, ?, 'CLOSED', ?, ?, ?)
            """, (t_id, f"sess_hist_{random.randint(10000, 99999)}", random.randint(2, 6), dt_str, dt_str))
            sess_id = cursor.lastrowid

            # Chọn 2-4 món
            chosen_items = random.sample(items, k=random.randint(2, 4))
            subtotal = 0
            order_items_data = []

            for ci in chosen_items:
                qty = random.randint(1, 3)
                line_total = ci["price"] * qty
                subtotal += line_total
                order_items_data.append((ci["id"], ci["name"], qty, ci["price"], line_total, ci["station"]))

            total = subtotal
            pay_method = random.choice(methods)

            cursor.execute("""
                INSERT INTO orders (session_id, table_id, round_number, subtotal, total, status, payment_status, payment_method, created_at, completed_at)
                VALUES (?, ?, 1, ?, ?, 'COMPLETED', 'PAID', ?, ?, ?)
            """, (sess_id, t_id, subtotal, total, pay_method, dt_str, dt_str))
            ord_id = cursor.lastrowid

            for item_id, item_name, qty, u_price, t_price, station in order_items_data:
                cursor.execute("""
                    INSERT INTO order_items (order_id, item_id, item_name, quantity, unit_price, total_price, station, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'SERVED', ?, ?)
                """, (ord_id, item_id, item_name, qty, u_price, t_price, station, dt_str, dt_str))

    conn.commit()

def seed_inventory_and_bom(conn):
    """Khởi tạo kho nguyên vật liệu và định lượng mẫu (BOM) chuẩn hóa theo thực đơn PiPo Garden."""
    cursor = conn.cursor()

    ingredients = [
        ("NVL01", "Tôm Sú / Tôm Thẻ Tươi Phú Quốc", "kg", 35.0, 8.0, 220000, "Vựa Hải Sản Hàm Ninh"),
        ("NVL02", "Ốc Hương Tươi Sống", "kg", 25.0, 5.0, 250000, "Vựa Hải Sản Hàm Ninh"),
        ("NVL03", "Bạch Tuộc Tươi Phú Quốc", "kg", 28.0, 6.0, 160000, "Hải Sản Đảo Ngọc"),
        ("NVL04", "Hàu Sữa Tươi Đại Dương", "con", 200.0, 40.0, 7000, "Hải Sản Đảo Ngọc"),
        ("NVL05", "Nghêu Lụa Tươi Sống", "kg", 30.0, 6.0, 65000, "Vựa Hải Sản Hàm Ninh"),
        ("NVL06", "Tôm Khô Phú Quốc Loại 1", "kg", 8.0, 2.0, 450000, "Đặc Sản Dương Đông"),
        ("NVL07", "Gà Ta Thả Vườn Làm Sạch", "kg", 45.0, 10.0, 82000, "Trang Trại Gà Đồi Phú Quốc"),
        ("NVL08", "Chân Gà Tươi Chọn Lọc", "kg", 18.0, 4.0, 80000, "CP Foods Vietnam"),
        ("NVL09", "Vịt Tươi Nguyên Con", "kg", 25.0, 5.0, 78000, "Trang Trại Gia Cầm Sạch"),
        ("NVL10", "Thịt Bò Thăn Mềm Tươi", "kg", 22.0, 5.0, 260000, "Thực Phẩm Bò Tơ"),
        ("NVL11", "Thịt Chân Giò / Ba Chỉ Heo", "kg", 25.0, 5.0, 125000, "CP Foods Vietnam"),
        ("NVL12", "Nầm Heo Tươi Chọn Lọc", "kg", 18.0, 4.0, 145000, "CP Foods Vietnam"),
        ("NVL13", "Khoai Môn Cao Sản", "kg", 20.0, 5.0, 35000, "Nông Sản Miền Tây"),
        ("NVL14", "Khoai Tây Cọng Đông Lạnh", "kg", 35.0, 8.0, 52000, "Lutosa Imports"),
        ("NVL15", "Đậu Hũ Non / Đậu Hũ Trắng", "bìa", 120.0, 25.0, 4000, "Làng Đậu Truyền Thống"),
        ("NVL16", "Xoài Xanh Keo Giòn", "kg", 20.0, 5.0, 28000, "Nông Sản Miền Tây"),
        ("NVL17", "Rau Muống Tươi Nhặt Sẵn", "kg", 25.0, 5.0, 20000, "Vườn Rau Sạch PiPo"),
        ("NVL18", "Cải Thìa Đà Lạt", "kg", 25.0, 5.0, 25000, "Nông Trại Đà Lạt"),
        ("NVL20", "Gạo Thơm ST25 (Nấu Cơm)", "kg", 50.0, 10.0, 32000, "Đại Lý Gạo Sóc Trăng"),
        ("NVL21", "Mì Vàng Tươi / Mì Trứng", "vắt", 150.0, 30.0, 5000, "Lò Mì Tươi Gia Truyền"),
        ("NVL23", "Trứng Muối & Trứng Gà Tươi", "quả", 180.0, 30.0, 4500, "CP Foods Vietnam"),
        ("NVL27", "Trà Lài & Trà Olong Thượng Hạng", "kg", 10.0, 2.0, 180000, "Trà Bảo Lộc"),
        ("NVL28", "Đào Ngâm & Mãng Cầu Xiêm Tươi", "kg", 20.0, 4.0, 65000, "Thực Phẩm Pha Chế"),
        ("NVL29", "Dưa Hấu & Trái Cây Tươi", "kg", 35.0, 8.0, 22000, "Nông Sản Miền Tây"),
        ("NVL100", "Mực Ống Tươi Phú Quốc", "kg", 25.0, 5.0, 180000, "Vựa Hải Sản Hàm Ninh"),
        ("NVL31", "Ốc Móng Tay Tươi Sống", "kg", 30.0, 6.0, 110000, "Vựa Hải Sản Hàm Ninh"),
        ("NVL32", "Cánh Gà Tươi Chọn Lọc", "kg", 25.0, 5.0, 85000, "CP Foods Vietnam"),
        ("NVL33", "Thịt Ghẹ Tươi Bóc Sẵn Phú Quốc", "kg", 15.0, 3.0, 290000, "Hải Sản Đảo Ngọc"),
        ("NVL37", "Gói Bò Xuyên Tiêu Chuẩn Bị Sẵn", "gói", 30.0, 6.0, 85000, "Thực Phẩm Chế Biến Sẵn"),
    ]

    ing_map = {}
    for code, name, unit, stock, min_s, cost, sup in ingredients:
        cursor.execute("""
            INSERT OR IGNORE INTO inventory_items (code, name, unit, stock_quantity, min_stock, cost_price, supplier)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (code, name, unit, stock, min_s, cost, sup))
        cursor.execute("SELECT id FROM inventory_items WHERE code = ?", (code,))
        ing_map[code] = cursor.fetchone()[0]

    cursor.execute("SELECT id, name FROM menu_items")
    menu_map = {r["name"]: r["id"] for r in cursor.fetchall()}

    bom_recipes = [
        ("Gỏi khoai môn hải sản", [("NVL13", 0.30), ("NVL100", 0.06), ("NVL01", 0.06)]),
        ("Khoai tây chiên", [("NVL14", 0.30)]),
        ("Đậu hũ", [("NVL15", 4.0)]),
        ("Đậu hũ tẩm hành", [("NVL15", 4.0)]),
        ("Đậu hũ chiên giòn", [("NVL15", 4.0)]),
        ("Gỏi xoài tôm khô", [("NVL16", 0.30), ("NVL06", 0.04)]),
        ("Rau muống xào tỏi", [("NVL17", 0.40)]),
        ("Cải thìa sốt dầu hào", [("NVL18", 0.40)]),
        ("Bò xuyên tiêu", [("NVL37", 1.0)]),
        ("Khoai môn chiên nước mắm", [("NVL13", 0.35)]),
        ("Gà ta nguyên con + Lòng mề xào", [("NVL07", 1.30)]),
        ("Gà hấp mắm nhĩ + Lòng mề xào", [("NVL07", 1.30)]),
        ("Lẩu gà lá giang", [("NVL07", 1.20)]),
        ("Lẩu gà thuốc bắc", [("NVL07", 1.20)]),
        ("Cánh gà", [("NVL32", 0.40)]),
        ("Vịt quay thảo mộc", [("NVL09", 0.90)]),
        ("Chân gà", [("NVL08", 0.35)]),
        ("Chân gà nướng", [("NVL08", 0.35)]),
        ("Heo nướng giềng mẻ", [("NVL11", 0.35)]),
        ("Nầm heo", [("NVL12", 0.35)]),
        ("Hàu sữa tươi", [("NVL04", 1.0)]),
        ("Nghêu lụa", [("NVL05", 0.35)]),
        ("Tôm sú Phú Quốc", [("NVL01", 0.30)]),
        ("Ốc hương", [("NVL02", 0.23)]),
        ("Ốc móng tay", [("NVL31", 0.40)]),
        ("Bạch tuộc tươi Phú Quốc", [("NVL03", 0.40)]),
        ("Cơm chiên hải sản", [("NVL20", 0.25), ("NVL100", 0.05), ("NVL01", 0.05), ("NVL23", 1.0)]),
        ("Cơm chiên bò", [("NVL20", 0.25), ("NVL10", 0.08), ("NVL23", 1.0)]),
        ("Cơm chiên ghẹ", [("NVL20", 0.25), ("NVL33", 0.07), ("NVL23", 1.0)]),
        ("Mì xào hải sản", [("NVL21", 1.5), ("NVL100", 0.05), ("NVL01", 0.05), ("NVL18", 0.10)]),
        ("Mì xào bò", [("NVL21", 1.5), ("NVL10", 0.08), ("NVL18", 0.10)]),
        ("Trà Đào Cam Sả PiPo Special", [("NVL27", 0.015), ("NVL28", 0.12)]),
        ("Trà Mãng Cầu Xiêm Nhiệt Đới", [("NVL27", 0.015), ("NVL28", 0.15)]),
        ("Nước Ép Dưa Hấu Bạc Hà", [("NVL29", 0.45)]),
    ]

    for dish_name, ing_list in bom_recipes:
        m_id = menu_map.get(dish_name)
        if m_id:
            for ing_code, qty in ing_list:
                ing_id = ing_map.get(ing_code)
                if ing_id:
                    cursor.execute("""
                        INSERT OR IGNORE INTO recipe_bom (menu_item_id, ingredient_id, quantity)
                        VALUES (?, ?, ?)
                    """, (m_id, ing_id, qty))

    conn.commit()

def get_dynamic_bom_for_item(cursor, menu_item_id: int, modifiers_json: str = None, item_name: str = "") -> list:
    """
    Trả về danh sách định lượng NVL thực tế theo tùy chọn/vị được khách chọn:
    Ví dụ: Mì xào chọn vị Bò -> Trừ thịt bò (NVL10) + mì vắt (NVL21), KHÔNG trừ hải sản!
    """
    mod_text = ""
    try:
        raw_mods = json.loads(modifiers_json or "[]") if isinstance(modifiers_json, str) else (modifiers_json or [])
        for m in raw_mods:
            if isinstance(m, dict):
                v = str(m.get("value") or "").strip()
                if v:
                    mod_text += " " + v.lower()
            elif isinstance(m, str):
                mod_text += " " + m.lower()
    except Exception:
        pass

    full_check = (str(item_name or "").lower() + " " + mod_text).strip()

    # 0. Vé Social Chiều Sân Pickleball (16h-22h kèm nước) -> Trừ 1 đồ uống được gán trong cấu hình!
    if "social" in full_check and ("chiều" in full_check or "chieu" in full_check or "tối" in full_check or "toi" in full_check or "16" in full_check or "kèm nước" in full_check or "kem nuoc" in full_check):
        cursor.execute("SELECT value FROM system_settings WHERE key = 'pickle_social_included_drink_id'")
        cfg_row = cursor.fetchone()
        drink_id = 183
        if cfg_row and cfg_row["value"]:
            try:
                drink_id = int(cfg_row["value"])
            except Exception:
                drink_id = 183

        cursor.execute("""
            SELECT rb.ingredient_id, rb.quantity as bom_qty, ii.name as ing_name, ii.unit, ii.cost_price
            FROM recipe_bom rb
            JOIN inventory_items ii ON rb.ingredient_id = ii.id
            WHERE rb.menu_item_id = ?
        """, (drink_id,))
        recipes = cursor.fetchall()
        if recipes:
            return [dict(r) for r in recipes]

        cursor.execute("SELECT id, name, unit, cost_price FROM inventory_items WHERE code = 'NVL41' OR name LIKE '%Nước Suối%' LIMIT 1")
        ing_row = cursor.fetchone()
        if ing_row:
            return [{
                "ingredient_id": ing_row["id"],
                "bom_qty": 1.0,
                "ing_name": ing_row["name"],
                "unit": ing_row["unit"],
                "cost_price": ing_row["cost_price"] or 4000
            }]
        return []

# 0b. Thuê Sân Theo Giờ (ID 304 hoặc chứa 'thuê sân' / 'thue san') -> Tặng 2 chai nước suối (trừ 2 chai NVL41)
    if menu_item_id == 304 or ("thuê sân" in full_check or "thue san" in full_check) and ("giờ" in full_check or "gio" in full_check or "200" in full_check):
        cursor.execute("SELECT id, name, unit, cost_price FROM inventory_items WHERE code = 'NVL41' OR name LIKE '%Nước Suối%' LIMIT 1")
        ing_row = cursor.fetchone()
        if ing_row:
            return [{
                "ingredient_id": ing_row["id"],
                "bom_qty": 2.0,
                "ing_name": ing_row["name"],
                "unit": ing_row["unit"],
                "cost_price": ing_row["cost_price"] or 4000
            }]
        return []

    # 1. Mì xào (ID 181)
    if menu_item_id == 181 or "mì xào" in full_check or "mi xao" in full_check or "mỳ xào" in full_check:
        if "bò" in full_check or "bo" in full_check:
            # NVL21: Mì vàng tươi (2 vắt), NVL10: Thịt bò thăn mềm (0.1 kg)
            ing_ids = [(21, 2.0), (10, 0.1)]
        else:
            # Mặc định hải sản: NVL21: Mì vàng tươi (2 vắt), NVL01: Tôm sú (0.05 kg), NVL100: Mực ống (0.05 kg)
            ing_ids = [(21, 2.0), (1, 0.05), (31, 0.05)]

        res = []
        for ing_id, qty in ing_ids:
            cursor.execute("SELECT id, name, unit, cost_price FROM inventory_items WHERE id = ?", (ing_id,))
            row = cursor.fetchone()
            if row:
                res.append({
                    "ingredient_id": row["id"],
                    "bom_qty": qty,
                    "ing_name": row["name"],
                    "unit": row["unit"],
                    "cost_price": row["cost_price"] or 0
                })
        return res

    # 2. Cơm chiên (ID 180)
    if menu_item_id == 180 or "cơm chiên" in full_check or "com chien" in full_check:
        if "bò" in full_check or "bo" in full_check:
            # Gạo ST25 0.25kg, Trứng 1 quả, Thịt bò 0.1kg
            ing_ids = [(20, 0.25), (23, 1.0), (10, 0.1)]
        elif "hải sản" in full_check or "hai san" in full_check:
            # Gạo ST25 0.25kg, Trứng 1 quả, Tôm sú 0.05kg, Mực ống 0.05kg
            ing_ids = [(20, 0.25), (23, 1.0), (1, 0.05), (31, 0.05)]
        else:
            # Mặc định ghẹ: Gạo ST25 0.25kg, Trứng 1 quả, Thịt ghẹ 0.07kg
            ing_ids = [(20, 0.25), (23, 1.0), (34, 0.07)]

        res = []
        for ing_id, qty in ing_ids:
            cursor.execute("SELECT id, name, unit, cost_price FROM inventory_items WHERE id = ?", (ing_id,))
            row = cursor.fetchone()
            if row:
                res.append({
                    "ingredient_id": row["id"],
                    "bom_qty": qty,
                    "ing_name": row["name"],
                    "unit": row["unit"],
                    "cost_price": row["cost_price"] or 0
                })
        return res

    # Các món thông thường khác: lấy từ bảng recipe_bom
    cursor.execute("""
        SELECT rb.ingredient_id, rb.quantity as bom_qty, ii.name as ing_name, ii.unit, ii.cost_price
        FROM recipe_bom rb
        JOIN inventory_items ii ON rb.ingredient_id = ii.id
        WHERE rb.menu_item_id = ?
    """, (menu_item_id,))
    return [dict(r) for r in cursor.fetchall()]


def deduct_inventory_for_order_item(conn, order_item_id: int):

    """
    Tự động tra cứu định lượng BOM và TRỪ TỒN KHO khi bếp bắt đầu nấu hoặc hoàn tất món.
    Đảm bảo mỗi món trong đơn chỉ bị trừ kho đúng 1 lần duy nhất.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT oi.*, o.id as order_num, t.name as table_name
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN tables t ON o.table_id = t.id
        WHERE oi.id = ?
    """, (order_item_id,))
    item = cursor.fetchone()
    if not item:
        return

    # Nếu đã trừ kho rồi thì bỏ qua (chống trừ lặp)
    if item["inventory_deducted"] == 1:
        return

    menu_item_id = item["item_id"]
    item_qty = item["quantity"]

    # Tra cứu BOM của món ăn (tự động phân nhánh theo vị)
    recipes = get_dynamic_bom_for_item(cursor, menu_item_id, item["modifiers_json"], item["item_name"])

    for r in recipes:
        ing_id = r["ingredient_id"]
        total_deduct = r["bom_qty"] * item_qty

        # Trừ tồn kho
        cursor.execute("""
            UPDATE inventory_items
            SET stock_quantity = stock_quantity - ?
            WHERE id = ?
        """, (total_deduct, ing_id))

        # Ghi log lịch sử biến động kho
        cursor.execute("""
            INSERT INTO inventory_transactions 
            (ingredient_id, transaction_type, quantity, unit_price, reference_id, note, created_by)
            VALUES (?, 'ORDER_DEDUCT', ?, ?, ?, ?, 'Bếp PiPo Garden')
        """, (
            ing_id,
            -total_deduct,
            r["cost_price"],
            item["order_id"],
            f"Trừ kho tự động: {item['item_name']} x{item_qty} (Đơn #{item['order_id']} - {item['table_name']})"
        ))

    # Đánh dấu đã trừ kho
    cursor.execute("UPDATE order_items SET inventory_deducted = 1 WHERE id = ?", (order_item_id,))
    conn.commit()

def restore_inventory_for_order_item(conn, order_item_id: int, reason: str = "Hủy món"):
    """Hoàn lại nguyên vật liệu vào kho khi hủy/trả món ăn đã trừ kho."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT oi.*, o.id as order_id, t.name as table_name
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN tables t ON o.table_id = t.id
        WHERE oi.id = ?
    """, (order_item_id,))
    item = cursor.fetchone()
    if not item:
        return

    # Chỉ hoàn kho nếu món này đã từng bị trừ kho
    if item["inventory_deducted"] != 1:
        return

    menu_item_id = item["item_id"]
    item_qty = item["quantity"]

    recipes = get_dynamic_bom_for_item(cursor, menu_item_id, item["modifiers_json"], item["item_name"])

    for r in recipes:
        ing_id = r["ingredient_id"]
        total_restore = r["bom_qty"] * item_qty

        # Cộng lại tồn kho
        cursor.execute("""
            UPDATE inventory_items
            SET stock_quantity = stock_quantity + ?
            WHERE id = ?
        """, (total_restore, ing_id))

        # Ghi log lịch sử biến động kho (Giao dịch hoàn kho)
        cursor.execute("""
            INSERT INTO inventory_transactions 
            (ingredient_id, transaction_type, quantity, unit_price, reference_id, note, created_by)
            VALUES (?, 'CANCEL_RESTORE', ?, ?, ?, ?, 'Bếp PiPo Garden')
        """, (
            ing_id,
            total_restore,
            r["cost_price"],
            item["order_id"],
            f"Hoàn kho do hủy món: {item['item_name']} x{item_qty} (Đơn #{item['order_id']} - {item['table_name']}) - Lý do: {reason}"
        ))

    # Đánh dấu đã hoàn kho
    cursor.execute("UPDATE order_items SET inventory_deducted = 0 WHERE id = ?", (order_item_id,))
    conn.commit()

def seed_homepage_cms(conn):
    """Khởi tạo và cập nhật các thông số quản trị nội dung trang chủ (CMS)."""
    cursor = conn.cursor()
    default_cms = {
        "hero_badge": "RESTAURANT • CAFE • POOL BAR",
        "hero_title_1": "PiPo Garden Phú Quốc",
        "hero_title_2": "Restaurant • Cafe • Pool Bar",
        "hero_subtitle": "Không gian sân vườn nhiệt đới thoáng mát, hải sản tươi ngon, hồ bơi ngoài trời và cụm sân Pickleball có mái che tại Sonasea, Bãi Trường.",
        "hero_image_url": "/static/home/hero_twilight.jpg",
        "address": "Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, Phú Quốc",
        "phone": "0838993316",
        "phone_display": "0838.993.316",
        "opening_hours": "06:30 - 23:00 hàng ngày",
        "about_story": "Tọa lạc tại Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, TP. Phú Quốc, PiPo Garden sở hữu không gian sân vườn nhiệt đới thoáng mát với hồ bơi uốn lượn trung tâm, các nhà chòi mái lá mộc mạc lung linh đèn lồng, kết hợp khu ẩm thực - cà phê và cụm sân thể thao Pickleball hiện đại.",
        "feature_1_title": "Ẩm Thực Sân Vườn & Hải Sản",
        "feature_1_desc": "Hải sản Phú Quốc tươi sống bắt tại bể, hải sản nướng than hoa đậm vị cùng thực đơn đa dạng từ cơm trưa đến tiệc tối.",
        "feature_2_title": "Hồ Bơi Uốn Lượn & Pool Bar",
        "feature_2_desc": "Không gian thư giãn cực chill bên hồ bơi uốn lượn, khu vực check-in sống ảo sang trọng cùng cocktail nhiệt đới.",
        "feature_3_title": "Cụm Sân Pickleball Có Mái Che",
        "feature_3_desc": "Tổ hợp 4 sân Pickleball hiện đại theo tiêu chuẩn thi đấu, mặt sân cao cấp phục vụ ngày lẫn đêm.",
        "feature_4_title": "Tiệc Sinh Nhật & Sự Kiện Bờ Hồ",
        "feature_4_desc": "Nhận đặt tiệc sinh nhật, Gala dinner, tiệc công ty ngoài trời bên hồ bơi với âm thanh ánh sáng lung linh.",
        "google_map_embed_url": "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3926.8523318281144!2d103.97828557451066!3d10.192770289922572!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x31a78dc1e0a811c7%3A0xe5a363720743b342!2sSonasea%20Villas%20%26%20Resort!5e0!3m2!1sen!2s!4v1710000000000!5m2!1sen!2s"
    }
    for key, val in default_cms.items():
        cursor.execute("INSERT OR IGNORE INTO homepage_cms (key, value) VALUES (?, ?)", (key, val))
    
    # Cập nhật địa chỉ, tiêu đề và số điện thoại mới nhất
    cursor.execute("UPDATE homepage_cms SET value = 'RESTAURANT • CAFE • POOL BAR' WHERE key = 'hero_badge'")
    cursor.execute("UPDATE homepage_cms SET value = 'Restaurant • Cafe • Pool Bar' WHERE key = 'hero_title_2'")
    cursor.execute("UPDATE homepage_cms SET value = 'Không gian sân vườn nhiệt đới thoáng mát, hải sản tươi ngon, hồ bơi ngoài trời và cụm sân Pickleball có mái che tại Sonasea, Bãi Trường.' WHERE key = 'hero_subtitle'")
    cursor.execute("UPDATE homepage_cms SET value = ? WHERE key = 'address' AND (value LIKE '%Suối Mây%' OR value LIKE '%Tổ 1%')", 
                   ("Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, Phú Quốc",))
    cursor.execute("UPDATE homepage_cms SET value = ? WHERE key = 'about_story' AND (value LIKE '%Suối Mây%' OR value LIKE '%Resort%')", 
                   ("Tọa lạc tại Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, TP. Phú Quốc, PiPo Garden sở hữu không gian sân vườn nhiệt đới thoáng mát với hồ bơi uốn lượn trung tâm, các nhà chòi mái lá mộc mạc lung linh đèn lồng, kết hợp khu ẩm thực - cà phê và cụm sân thể thao Pickleball hiện đại.",))
    cursor.execute("UPDATE homepage_cms SET value = ? WHERE key = 'phone' AND value LIKE '09%'", ("0838993316",))
    cursor.execute("UPDATE homepage_cms SET value = ? WHERE key = 'phone_display' AND value LIKE '09%'", ("0838.993.316",))
    conn.commit()

def ensure_standard_27_tables(conn):
    """
    Chuẩn hóa cấu trúc 31 bàn ăn nhà hàng PiPo Garden theo 4 phân khu chuẩn:
    - Khu hồ bơi: 12 bàn (HB01 -> HB12)
    - Sảnh 1 (Chính Giữa): 5 bàn (S1-01 -> S1-05)
    - Sảnh 2 (Cạnh Sân Pickleball): 10 bàn (S2-01 -> S2-10)
    - Sân Pickle: 4 bàn (PK-01 -> PK-04)
    """
    cursor = conn.cursor()

    # 1. Cập nhật 4 khu vực chuẩn trong restaurant_areas
    standard_areas = [
        ("Khu Hồ Bơi", "🏊", 1),
        ("Sảnh 1 (Chính Giữa)", "✨", 2),
        ("Sảnh 2 (Cạnh Sân Pickleball)", "🎾", 3),
        ("Sân Pickle", "🏓", 4)
    ]
    for name, icon, order in standard_areas:
        cursor.execute("SELECT id FROM restaurant_areas WHERE name = ?", (name,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO restaurant_areas (name, icon, display_order) VALUES (?, ?, ?)", (name, icon, order))
        else:
            cursor.execute("UPDATE restaurant_areas SET icon = ?, display_order = ? WHERE name = ?", (icon, order, name))

    # Xóa các khu vực cũ không còn dùng (bảo lưu 4 khu vực chuẩn)
    cursor.execute("DELETE FROM restaurant_areas WHERE name NOT IN ('Khu Hồ Bơi', 'Sảnh 1 (Chính Giữa)', 'Sảnh 2 (Cạnh Sân Pickleball)', 'Sân Pickle')")

    # 2. Định nghĩa danh sách 31 bàn chuẩn
    STANDARD_31_TABLES = [
        # Khu hồ bơi: 12 bàn (HB01 - HB12)
        ("HB01", "Bàn Hồ Bơi 01", "Khu Hồ Bơi", 4),
        ("HB02", "Bàn Hồ Bơi 02", "Khu Hồ Bơi", 4),
        ("HB03", "Bàn Hồ Bơi 03", "Khu Hồ Bơi", 4),
        ("HB04", "Bàn Hồ Bơi 04", "Khu Hồ Bơi", 4),
        ("HB05", "Bàn Hồ Bơi 05", "Khu Hồ Bơi", 6),
        ("HB06", "Bàn Hồ Bơi 06", "Khu Hồ Bơi", 6),
        ("HB07", "Bàn Hồ Bơi 07", "Khu Hồ Bơi", 6),
        ("HB08", "Bàn Hồ Bơi 08", "Khu Hồ Bơi", 6),
        ("HB09", "Bàn Hồ Bơi 09", "Khu Hồ Bơi", 8),
        ("HB10", "Bàn Hồ Bơi 10", "Khu Hồ Bơi", 8),
        ("HB11", "Bàn Hồ Bơi 11", "Khu Hồ Bơi", 8),
        ("HB12", "Bàn Hồ Bơi 12", "Khu Hồ Bơi", 10),

        # Sảnh 1 (Chính Giữa): 5 bàn (S1-01 - S1-05)
        ("S1-01", "Sảnh 1 - Bàn 01", "Sảnh 1 (Chính Giữa)", 6),
        ("S1-02", "Sảnh 1 - Bàn 02", "Sảnh 1 (Chính Giữa)", 6),
        ("S1-03", "Sảnh 1 - Bàn 03", "Sảnh 1 (Chính Giữa)", 8),
        ("S1-04", "Sảnh 1 - Bàn 04", "Sảnh 1 (Chính Giữa)", 10),
        ("S1-05", "Sảnh 1 - Bàn 05", "Sảnh 1 (Chính Giữa)", 12),

        # Sảnh 2 (Cạnh Sân Pickleball): 10 bàn (S2-01 - S2-10)
        ("S2-01", "Sảnh 2 - Bàn 01", "Sảnh 2 (Cạnh Sân Pickleball)", 4),
        ("S2-02", "Sảnh 2 - Bàn 02", "Sảnh 2 (Cạnh Sân Pickleball)", 4),
        ("S2-03", "Sảnh 2 - Bàn 03", "Sảnh 2 (Cạnh Sân Pickleball)", 4),
        ("S2-04", "Sảnh 2 - Bàn 04", "Sảnh 2 (Cạnh Sân Pickleball)", 4),
        ("S2-05", "Sảnh 2 - Bàn 05", "Sảnh 2 (Cạnh Sân Pickleball)", 6),
        ("S2-06", "Sảnh 2 - Bàn 06", "Sảnh 2 (Cạnh Sân Pickleball)", 6),
        ("S2-07", "Sảnh 2 - Bàn 07", "Sảnh 2 (Cạnh Sân Pickleball)", 6),
        ("S2-08", "Sảnh 2 - Bàn 08", "Sảnh 2 (Cạnh Sân Pickleball)", 6),
        ("S2-09", "Sảnh 2 - Bàn 09", "Sảnh 2 (Cạnh Sân Pickleball)", 8),
        ("S2-10", "Sảnh 2 - Bàn 10", "Sảnh 2 (Cạnh Sân Pickleball)", 10),

        # Sân Pickle: 4 sân (PK-01 - PK-04)
        ("PK-01", "Sân Pick 01", "Sân Pickle", 4),
        ("PK-02", "Sân Pick 02", "Sân Pickle", 4),
        ("PK-03", "Sân Pick 03", "Sân Pickle", 4),
        ("PK-04", "Sân Pick 04", "Sân Pickle", 4),
    ]

    # Cập nhật hoặc thêm mới từng bàn dựa theo table_code
    valid_codes = set()
    for code, name, area, cap in STANDARD_31_TABLES:
        valid_codes.add(code)
        cursor.execute("SELECT id FROM tables WHERE table_code = ?", (code,))
        row = cursor.fetchone()
        if row:
            cursor.execute("""
                UPDATE tables 
                SET name = ?, area = ?, capacity = ?
                WHERE id = ?
            """, (name, area, cap, row["id"]))
        else:
            token = generate_qr_token(code)
            cursor.execute(
                "INSERT INTO tables (table_code, name, area, capacity, qr_token, status) VALUES (?, ?, ?, ?, ?, 'AVAILABLE')",
                (code, name, area, cap, token)
            )

    conn.commit()

