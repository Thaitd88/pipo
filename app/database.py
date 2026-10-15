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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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

    # 15. Quản Trị Nội Dung Trang Chủ (Homepage CMS)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS homepage_cms (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

    # Seed initial staff users if empty
    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()["count"] == 0:
        seed_default_users(conn)

    # Seed initial tables and menu if empty
    cursor.execute("SELECT COUNT(*) as count FROM tables")
    if cursor.fetchone()["count"] == 0:
        seed_sample_data(conn)

    # Seed initial inventory items & BOM recipes if empty
    cursor.execute("SELECT COUNT(*) as count FROM inventory_items")
    if cursor.fetchone()["count"] == 0:
        seed_inventory_and_bom(conn)

    # Seed sample historical revenue data if orders count is low
    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE payment_status = 'PAID'")
    if cursor.fetchone()["count"] < 10:
        seed_historical_revenue(conn)

    # Tự động đồng bộ và di chuyển sang 6 nhóm danh mục chuẩn
    ensure_six_categories(conn)

    # Tự động phân loại 3 Nhóm Thực Đơn Lớn (Nhà Hàng, Cơm Trưa, Cafe / Ăn Sáng)
    ensure_main_menu_classification(conn)

    # Tự động tính toán và đồng bộ chỉ số Calo theo định lượng NVL (BOM)
    sync_dish_calories(conn)

    # Tự động bổ sung các bàn theo mặt bằng resort thực tế
    ensure_resort_tables(conn)

    # Đảm bảo toàn bộ danh mục và món ăn đều có dữ liệu đa ngôn ngữ
    seed_translations_if_missing(conn)

    conn.close()

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
        ("admin", hash_password("admin123"), "Nguyễn Văn Quản Lý", "ADMIN", "0901234567"),
        ("thungan", hash_password("123456"), "Trần Thị Thu Ngân", "CASHIER", "0912345678"),
        ("bep", hash_password("123456"), "Lê Hoàng Bếp Trưởng", "CHEF", "0923456789"),
        ("phucvu", hash_password("123456"), "Phạm Minh Phục Vụ", "WAITER", "0934567890"),
    ]
    for username, pwd_hash, full_name, role, phone in default_staff:
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, password_hash, full_name, role, phone)
            VALUES (?, ?, ?, ?, ?)
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

def seed_translations_if_missing(conn):
    """Tự động kiểm tra và bổ sung bản dịch 4 ngôn ngữ (en, zh, ko, ru) cho categories và menu_items."""
    try:
        from .services.translator import translate_dish, translate_category_name
    except Exception as e:
        print("[PiPo Multi-Lang] Chua the import translator:", e)
        return

    cursor = conn.cursor()
    # 1. Categories
    cursor.execute("SELECT id, name, translations_json FROM categories")
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
            trans = translate_category_name(cat["name"])
            cursor.execute("UPDATE categories SET translations_json = ? WHERE id = ?", (json.dumps(trans, ensure_ascii=False), cat["id"]))

    # 2. Menu Items
    cursor.execute("SELECT id, name, description, translations_json FROM menu_items")
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
            trans = translate_dish(item["name"], item["description"] or "")
            cursor.execute("UPDATE menu_items SET translations_json = ? WHERE id = ?", (json.dumps(trans, ensure_ascii=False), item["id"]))

    conn.commit()

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
        ("NVL19", "Lá Giang, Sả Cây & Hành Lá Tươi", "kg", 20.0, 4.0, 35000, "Vườn Rau Sạch PiPo"),
        ("NVL20", "Gạo Thơm ST25 (Nấu Cơm)", "kg", 50.0, 10.0, 32000, "Đại Lý Gạo Sóc Trăng"),
        ("NVL21", "Mì Vàng Tươi / Mì Trứng", "vắt", 150.0, 30.0, 5000, "Lò Mì Tươi Gia Truyền"),
        ("NVL22", "Phô Mai Mozzarella & Bơ Lạt Anchor", "kg", 12.0, 3.0, 190000, "New Zealand Dairy"),
        ("NVL23", "Trứng Muối & Trứng Gà Tươi", "quả", 180.0, 30.0, 4500, "CP Foods Vietnam"),
        ("NVL24", "Gói Thảo Dược Thuốc Bắc Tiềm", "gói", 40.0, 8.0, 20000, "Tiệm Thuốc Bắc Đồng Xuân"),
        ("NVL25", "Tỏi Lý Sơn, Ớt Hiểm, Riềng Mẻ & Thảo Mộc", "kg", 15.0, 3.0, 65000, "Gia Vị Việt"),
        ("NVL26", "Nước Mắm Nhĩ Phú Quốc & Sốt Tổng Hợp (Dầu hào, Sa tế, Chao, Tiêu)", "lít", 25.0, 5.0, 80000, "Nhà Thùng Nước Mắm Phú Quốc"),
        ("NVL27", "Trà Lài & Trà Olong Thượng Hạng", "kg", 10.0, 2.0, 180000, "Trà Bảo Lộc"),
        ("NVL28", "Đào Ngâm & Mãng Cầu Xiêm Tươi", "kg", 20.0, 4.0, 65000, "Thực Phẩm Pha Chế"),
        ("NVL29", "Dưa Hấu & Trái Cây Tươi", "kg", 35.0, 8.0, 22000, "Nông Sản Miền Tây"),
        ("NVL30", "Syrup Đường Mía & Cam Sả Pha Chế", "lít", 15.0, 3.0, 55000, "Monin Vietnam"),
        ("NVL100", "Mực Ống Tươi Phú Quốc", "kg", 25.0, 5.0, 180000, "Vựa Hải Sản Hàm Ninh"),
        ("NVL31", "Ốc Móng Tay Tươi Sống", "kg", 30.0, 6.0, 110000, "Vựa Hải Sản Hàm Ninh"),
        ("NVL32", "Cánh Gà Tươi Chọn Lọc", "kg", 25.0, 5.0, 85000, "CP Foods Vietnam"),
        ("NVL33", "Thịt Ghẹ Tươi Bóc Sẵn Phú Quốc", "kg", 15.0, 3.0, 290000, "Hải Sản Đảo Ngọc"),
        ("NVL34", "Tóp Mỡ Giòn Thơm", "kg", 15.0, 3.0, 80000, "Bếp PiPo Garden"),
        ("NVL35", "Cà Rốt Đà Lạt Tươi", "kg", 20.0, 4.0, 22000, "Nông Trại Đà Lạt"),
        ("NVL36", "Bánh Mì Đặc Ruột Nóng Giòn", "ổ", 60.0, 15.0, 4000, "Lò Bánh Mì Truyền Thống"),
        ("NVL37", "Gói Bò Xuyên Tiêu Chuẩn Bị Sẵn", "gói", 30.0, 6.0, 85000, "Thực Phẩm Chế Biến Sẵn"),
        ("NVL38", "Gia Vị Mắc Khén & Hạt Dổi Tây Bắc", "kg", 8.0, 2.0, 190000, "Gia Vị Núi Rừng"),
        ("NVL39", "Bún Tươi Phú Quốc", "kg", 35.0, 8.0, 16000, "Lò Bún Phú Quốc"),
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
        ("Gỏi khoai môn hải sản", [("NVL13", 0.30), ("NVL100", 0.06), ("NVL01", 0.06), ("NVL26", 0.03)]),
        ("Khoai tây chiên", [("NVL14", 0.30), ("NVL22", 0.01)]),
        ("Đậu hũ tẩm hành", [("NVL15", 3.0), ("NVL19", 0.10), ("NVL34", 0.10)]),
        ("Gỏi xoài tôm khô", [("NVL16", 0.30), ("NVL35", 0.07), ("NVL06", 0.04), ("NVL19", 0.03), ("NVL26", 0.02)]),
        ("Rau muống xào tỏi", [("NVL17", 0.40), ("NVL25", 0.04), ("NVL26", 0.03)]),
        ("Cải thìa sốt dầu hào", [("NVL18", 0.40), ("NVL25", 0.02), ("NVL26", 0.03)]),
        ("Bò xuyên tiêu", [("NVL37", 1.0)]),
        ("Đậu hũ chiên giòn", [("NVL15", 4.0), ("NVL26", 0.03)]),
        ("Khoai môn chiên nước mắm", [("NVL13", 0.35), ("NVL26", 0.03)]),
        ("Gà hấp mắm nhĩ + Lòng mề xào", [("NVL07", 1.30), ("NVL26", 0.07), ("NVL19", 0.05)]),
        ("Gà nướng muối ớt + Lòng mề xào", [("NVL07", 1.30), ("NVL25", 0.06), ("NVL26", 0.04)]),
        ("Gà chiên mắm + Lòng mề xào", [("NVL07", 1.30), ("NVL26", 0.08), ("NVL25", 0.04)]),
        ("Gà hấp hành + Lòng mề xào", [("NVL07", 1.30), ("NVL19", 0.15), ("NVL26", 0.04)]),
        ("Lẩu gà lá giang", [("NVL07", 1.20), ("NVL19", 0.25), ("NVL39", 0.40), ("NVL26", 0.05)]),
        ("Lẩu gà thuốc bắc", [("NVL07", 1.20), ("NVL24", 1.0), ("NVL39", 0.30), ("NVL19", 0.05)]),
        ("Gà nướng tây bắc + Lòng mề xào", [("NVL07", 1.30), ("NVL38", 0.03), ("NVL25", 0.04), ("NVL26", 0.04)]),
        ("Cánh gà chiên mắm", [("NVL32", 0.40), ("NVL26", 0.04), ("NVL25", 0.03)]),
        ("Cánh gà nướng muối ớt", [("NVL32", 0.40), ("NVL25", 0.04), ("NVL26", 0.03)]),
        ("Cánh gà nướng tây bắc", [("NVL32", 0.40), ("NVL38", 0.02), ("NVL25", 0.03)]),
        ("Vịt quay thảo mộc", [("NVL09", 0.90), ("NVL25", 0.08), ("NVL26", 0.04)]),
        ("Chân gà nướng", [("NVL08", 0.35), ("NVL25", 0.04), ("NVL26", 0.03)]),
        ("Heo nướng giềng mẻ", [("NVL11", 0.35), ("NVL25", 0.08), ("NVL26", 0.03)]),
        ("Nầm nướng sa tế", [("NVL12", 0.35), ("NVL25", 0.04), ("NVL26", 0.04)]),
        ("Nầm nướng chao", [("NVL12", 0.35), ("NVL26", 0.06), ("NVL19", 0.03)]),
        ("Hàu nướng phô mai", [("NVL04", 1.0), ("NVL22", 0.02)]),
        ("Hàu nướng mỡ hành", [("NVL04", 1.0), ("NVL19", 0.02), ("NVL26", 0.01)]),
        ("Nghêu hấp sả", [("NVL05", 0.35), ("NVL19", 0.06), ("NVL25", 0.02)]),
        ("Nghêu hấp Thái", [("NVL05", 0.35), ("NVL26", 0.05), ("NVL19", 0.04)]),
        ("Tôm sốt bơ tỏi", [("NVL01", 0.30), ("NVL22", 0.04), ("NVL25", 0.04)]),
        ("Tôm hấp", [("NVL01", 0.30), ("NVL19", 0.05)]),
        ("Tôm nướng muối ớt", [("NVL01", 0.30), ("NVL25", 0.04), ("NVL26", 0.02)]),
        ("Ốc hương sốt trứng muối - bánh mì", [("NVL02", 0.20), ("NVL23", 2.0), ("NVL22", 0.05), ("NVL36", 1.0)]),
        ("Ốc hương hấp sả", [("NVL02", 0.23), ("NVL19", 0.06), ("NVL25", 0.02)]),
        ("Ốc hương cháy tỏi", [("NVL02", 0.23), ("NVL25", 0.07), ("NVL22", 0.02)]),
        ("Ốc móng tay cháy tỏi", [("NVL31", 0.40), ("NVL25", 0.07), ("NVL22", 0.02)]),
        ("Ốc móng tay nướng mỡ hành", [("NVL31", 0.40), ("NVL19", 0.05), ("NVL26", 0.02)]),
        ("Ốc móng tay xào rau muống", [("NVL31", 0.40), ("NVL17", 0.20), ("NVL25", 0.03), ("NVL26", 0.03)]),
        ("Bạch tuộc xào cay", [("NVL03", 0.40), ("NVL25", 0.05), ("NVL26", 0.04)]),
        ("Bạch tuộc nướng muối ớt", [("NVL03", 0.40), ("NVL25", 0.05), ("NVL26", 0.03)]),
        ("Bạch tuộc hấp hành gừng", [("NVL03", 0.40), ("NVL19", 0.10), ("NVL26", 0.03)]),
        ("Cơm chiên hải sản", [("NVL20", 0.25), ("NVL100", 0.05), ("NVL01", 0.05), ("NVL23", 1.0)]),
        ("Cơm chiên bò", [("NVL20", 0.25), ("NVL10", 0.08), ("NVL23", 1.0)]),
        ("Cơm chiên ghẹ", [("NVL20", 0.25), ("NVL33", 0.07), ("NVL23", 1.0)]),
        ("Mì xào hải sản", [("NVL21", 1.5), ("NVL100", 0.05), ("NVL01", 0.05), ("NVL18", 0.10)]),
        ("Mì xào bò", [("NVL21", 1.5), ("NVL10", 0.08), ("NVL18", 0.10)]),
        ("Trà Đào Cam Sả PiPo Special", [("NVL27", 0.015), ("NVL28", 0.12), ("NVL30", 0.05)]),
        ("Trà Mãng Cầu Xiêm Nhiệt Đới", [("NVL27", 0.015), ("NVL28", 0.15), ("NVL30", 0.05)]),
        ("Nước Ép Dưa Hấu Bạc Hà", [("NVL29", 0.45), ("NVL19", 0.02), ("NVL30", 0.03)]),
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

    # Tra cứu BOM của món ăn
    cursor.execute("""
        SELECT rb.ingredient_id, rb.quantity as bom_qty, ii.name as ing_name, ii.unit, ii.cost_price
        FROM recipe_bom rb
        JOIN inventory_items ii ON rb.ingredient_id = ii.id
        WHERE rb.menu_item_id = ?
    """, (menu_item_id,))
    recipes = cursor.fetchall()

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

    cursor.execute("""
        SELECT rb.ingredient_id, rb.quantity as bom_qty, ii.name as ing_name, ii.unit, ii.cost_price
        FROM recipe_bom rb
        JOIN inventory_items ii ON rb.ingredient_id = ii.id
        WHERE rb.menu_item_id = ?
    """, (menu_item_id,))
    recipes = cursor.fetchall()

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
        "hero_badge": "TROPICAL RESORT & POOL BAR",
        "hero_title_1": "Pipo Garden Phú Quốc",
        "hero_title_2": "Tinh Hoa Ẩm Thực & Thư Giãn Giữa Lòng Đảo Ngọc",
        "hero_subtitle": "Trải nghiệm không gian sân vườn nhiệt đới thoáng mát, ẩm thực hải sản biển tươi ngon, hồ bơi ngoài trời thư giãn và cụm sân thể thao Pickleball có mái che hiện đại tại Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, Phú Quốc.",
        "hero_image_url": "/static/home/hero_twilight.jpg",
        "address": "Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, Phú Quốc",
        "phone": "0838993316",
        "phone_display": "0838.993.316",
        "opening_hours": "06:30 - 23:00 hàng ngày",
        "about_story": "Tọa lạc tại Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, TP. Phú Quốc, PiPo Garden sở hữu không gian Tropical Resort & Garden ấn tượng với hồ bơi uốn lượn trung tâm, các nhà chòi mái lá mộc mạc lung linh đèn lồng, kết hợp khu ẩm thực - cà phê và cụm sân thể thao Pickleball hiện đại.",
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
    
    # Cập nhật địa chỉ và số điện thoại mới nếu đang là giá trị mẫu cũ
    cursor.execute("UPDATE homepage_cms SET value = ? WHERE key = 'address' AND (value LIKE '%Suối Mây%' OR value LIKE '%Tổ 1%')", 
                   ("Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, Phú Quốc",))
    cursor.execute("UPDATE homepage_cms SET value = ? WHERE key = 'hero_subtitle' AND (value LIKE '%Suối Mây%' OR value LIKE '%Dương Tơ%')", 
                   ("Trải nghiệm không gian sân vườn nhiệt đới thoáng mát, ẩm thực hải sản biển tươi ngon, hồ bơi ngoài trời thư giãn và cụm sân thể thao Pickleball có mái che hiện đại tại Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, Phú Quốc.",))
    cursor.execute("UPDATE homepage_cms SET value = ? WHERE key = 'about_story' AND (value LIKE '%Suối Mây%' OR value LIKE '%Dương Tơ%')", 
                   ("Tọa lạc tại Khu Tiện Ích Bể Bơi SV02, Sonasea, Bãi Trường, TP. Phú Quốc, PiPo Garden sở hữu không gian Tropical Resort & Garden ấn tượng với hồ bơi uốn lượn trung tâm, các nhà chòi mái lá mộc mạc lung linh đèn lồng, kết hợp khu ẩm thực - cà phê và cụm sân thể thao Pickleball hiện đại.",))
    cursor.execute("UPDATE homepage_cms SET value = ? WHERE key = 'phone' AND value LIKE '09%'", ("0838993316",))
    cursor.execute("UPDATE homepage_cms SET value = ? WHERE key = 'phone_display' AND value LIKE '09%'", ("0838.993.316",))
    conn.commit()

def ensure_resort_tables(conn):
    """Bổ sung các bàn theo bản vẽ thiết kế mặt bằng Resort PiPo Garden (Ven Hồ Bơi, Nhà Chòi 1 & 2, VIP)."""
    cursor = conn.cursor()
    resort_tables = [
        # Bàn ven hồ bơi (Poolside)
        ("P01", "Bàn Hồ Bơi 01", "Ven Bể Bơi (Poolside)", 4),
        ("P02", "Bàn Hồ Bơi 02", "Ven Bể Bơi (Poolside)", 4),
        ("P03", "Bàn Hồ Bơi 03", "Ven Bể Bơi (Poolside)", 6),
        ("P04", "Bàn Hồ Bơi 04", "Ven Bể Bơi (Poolside)", 4),
        ("P05", "Bàn Hồ Bơi 05", "Ven Bể Bơi (Poolside)", 6),
        ("P06", "Bàn Hồ Bơi 06", "Ven Bể Bơi (Poolside)", 8),
        # Nhà chòi Khu 1 (gần bar & bếp)
        ("K1-01", "Chòi Khu 1 - Bàn 01", "Nhà Chòi Gỗ Khu 1", 6),
        ("K1-02", "Chòi Khu 1 - Bàn 02", "Nhà Chòi Gỗ Khu 1", 6),
        ("K1-03", "Chòi Khu 1 - Bàn 03", "Nhà Chòi Gỗ Khu 1", 8),
        ("K1-04", "Chòi Khu 1 - Bàn 04", "Nhà Chòi Gỗ Khu 1", 10),
        # Nhà chòi Khu 2 (gần Pickleball)
        ("K2-01", "Chòi Khu 2 - Bàn 01", "Nhà Chòi Gỗ Khu 2", 6),
        ("K2-02", "Chòi Khu 2 - Bàn 02", "Nhà Chòi Gỗ Khu 2", 6),
        ("K2-03", "Chòi Khu 2 - Bàn 03", "Nhà Chòi Gỗ Khu 2", 8),
        ("K2-04", "Chòi Khu 2 - Bàn 04", "Nhà Chòi Gỗ Khu 2", 10),
        # Khu VIP Bờ Hồ Sân Vườn
        ("VIP01", "Phòng VIP Bờ Hồ 01", "Khu VIP Sân Vườn", 12),
        ("VIP02", "Phòng VIP Bờ Hồ 02", "Khu VIP Sân Vườn", 16),
    ]
    for code, name, area, cap in resort_tables:
        cursor.execute("SELECT id FROM tables WHERE UPPER(table_code) = UPPER(?)", (code,))
        if not cursor.fetchone():
            token = generate_qr_token(code)
            cursor.execute(
                "INSERT INTO tables (table_code, name, area, capacity, qr_token, status) VALUES (?, ?, ?, ?, ?, 'AVAILABLE')",
                (code, name, area, cap, token)
            )
    conn.commit()

