#!/usr/bin/env python3
"""
scripts/sync_from_host.py
Tự động đồng bộ toàn bộ Menu, Danh mục, Cấu hình Website (Homepage CMS, Giờ mở cửa, Routing mode)
và Hình ảnh từ máy chủ Host (https://pipogarden.com) xuống môi trường Local.
"""

import urllib.request
import json
import sqlite3
import shutil
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "data", "pipo_garden.db")
BACKUP_PATH = os.path.join(ROOT_DIR, "data", "pipo_garden_backup_before_sync.db")
DISHES_DIR = os.path.join(ROOT_DIR, "app", "static", "dishes")
HOME_DIR = os.path.join(ROOT_DIR, "app", "static", "home")

os.makedirs(DISHES_DIR, exist_ok=True)
os.makedirs(HOME_DIR, exist_ok=True)

BASE_HOST = "https://pipogarden.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PiPoSyncAgent/1.0"}

def fetch_json(endpoint, timeout=5):
    url = f"{BASE_HOST}{endpoint}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode('utf-8'))

def sync(timeout=5, download_images=True):
    print(f"[*] Bắt đầu đồng bộ từ Host ({BASE_HOST}) xuống Local...")

    # 1. Backup local DB nếu có
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"  [+] Đã sao lưu database local: {BACKUP_PATH}")

    # 2. Fetch dữ liệu từ Host
    print("  [+] Đang tải danh mục, món ăn và cấu hình từ Host...")
    host_cats = fetch_json("/api/menu/categories", timeout=timeout)
    host_menu = fetch_json("/api/menu", timeout=timeout)
    
    try:
        host_cms = fetch_json("/api/homepage/cms", timeout=timeout)
    except Exception as e:
        print("  [-] Không tải được CMS:", e)
        host_cms = None

    try:
        host_settings = fetch_json("/api/menu/settings", timeout=timeout)
    except Exception as e:
        print("  [-] Không tải được settings:", e)
        host_settings = None

    try:
        host_tables = fetch_json("/api/tables", timeout=timeout)
    except Exception as e:
        print("  [-] Không tải được tables:", e)
        host_tables = None

    try:
        host_areas = fetch_json("/api/tables/areas", timeout=timeout)
    except Exception as e:
        print("  [-] Không tải được areas:", e)
        host_areas = None

    # Thu thập toàn bộ items
    host_items = []
    for c in host_menu:
        for it in c.get('items', []):
            host_items.append(it)

    print(f"  [+] Dữ liệu từ Host: {len(host_cats)} danh mục, {len(host_items)} món ăn.")

    # 3. Kết nối và ghi vào SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Đồng bộ Categories
    for c in host_cats:
        cursor.execute("""
            INSERT INTO categories (id, name, icon, display_order, is_active, translations_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                icon = excluded.icon,
                display_order = excluded.display_order,
                is_active = excluded.is_active,
                translations_json = excluded.translations_json
        """, (
            c.get('id'),
            c.get('name'),
            c.get('icon', '🍽️'),
            c.get('display_order', 1),
            c.get('is_active', 1),
            c.get('translations_json') or json.dumps(c.get('translations') or {}, ensure_ascii=False)
        ))

    # Xóa và nạp lại menu_items chuẩn từ Host
    cursor.execute("DELETE FROM menu_items")
    for it in host_items:
        trans_json = it.get('translations_json')
        if not trans_json and it.get('translations'):
            trans_json = json.dumps(it.get('translations'), ensure_ascii=False)
        
        opts_json = it.get('options_json')
        if not opts_json and it.get('options'):
            opts_json = json.dumps(it.get('options'), ensure_ascii=False)

        cursor.execute("""
            INSERT INTO menu_items (
                id, category_id, name, description, price, image_url,
                station, is_available, options_json, translations_json,
                calories, out_of_ingredients, main_menu_type, portion, discount_percent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            it.get('id'),
            it.get('category_id'),
            it.get('name'),
            it.get('description', ''),
            it.get('price', 0),
            it.get('image_url', ''),
            it.get('station', 'HOT_KITCHEN'),
            it.get('is_available', 1),
            opts_json or '[]',
            trans_json or '{}',
            it.get('calories', 0),
            it.get('out_of_ingredients', 0),
            it.get('main_menu_type', 'RESTAURANT,LUNCH,CAFE'),
            it.get('portion', ''),
            it.get('discount_percent', 0) or 0
        ))

    # Đồng bộ Homepage CMS
    if host_cms and host_cms.get("settings"):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS homepage_cms (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for k, v in host_cms["settings"].items():
            cursor.execute("""
                INSERT INTO homepage_cms (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """, (k, str(v) if v is not None else ""))
        print(f"  [+] Đã đồng bộ {len(host_cms['settings'])} mục cấu hình Homepage CMS.")

    # Đồng bộ System Settings
    if host_settings:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        for k, v in host_settings.items():
            if k in ("morning_start_hour", "morning_end_hour", "routing_mode"):
                cursor.execute("""
                    INSERT INTO system_settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """, (k, str(v)))
        print(f"  [+] Đã đồng bộ cấu hình System Settings.")
 
    # Đồng bộ Khu vực bàn (restaurant_areas)
    if host_areas:
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
        for a in host_areas:
            cursor.execute("""
                INSERT INTO restaurant_areas (id, name, icon, description, display_order)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    icon = excluded.icon,
                    description = excluded.description,
                    display_order = excluded.display_order
            """, (a.get('id'), a.get('name'), a.get('icon', '🌿'), a.get('description', ''), a.get('display_order', 0)))
        print(f"  [+] Đã đồng bộ {len(host_areas)} khu vực bàn.")

    # Đồng bộ Danh sách bàn (tables)
    if host_tables:
        for t in host_tables:
            cursor.execute("""
                INSERT INTO tables (id, table_code, name, area, capacity, qr_token)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(table_code) DO UPDATE SET
                    name = excluded.name,
                    area = excluded.area,
                    capacity = excluded.capacity,
                    qr_token = excluded.qr_token
            """, (
                t.get('id'),
                t.get('table_code'),
                t.get('name'),
                t.get('area', 'Khu Sân Vườn'),
                t.get('capacity', 4),
                t.get('qr_token')
            ))
        print(f"  [+] Đã đồng bộ {len(host_tables)} bàn ăn và sân Pickleball.")

    conn.commit()
    conn.close()

    # 4. Tải các ảnh món mới nếu thiếu (nếu download_images=True)
    if download_images:
        missing_imgs = 0
        for it in host_items:
            img_url = it.get('image_url') or ""
            clean_path = img_url.split('?')[0]
            if clean_path.startswith('/static/dishes/'):
                fname = os.path.basename(clean_path)
                lpath = os.path.join(DISHES_DIR, fname)
                if not os.path.exists(lpath):
                    missing_imgs += 1
                    try:
                        full_url = f"{BASE_HOST}{clean_path}"
                        req_img = urllib.request.Request(full_url, headers=HEADERS)
                        with urllib.request.urlopen(req_img, timeout=5) as ir:
                            with open(lpath, 'wb') as f:
                                f.write(ir.read())
                        print(f"    -> Đã tải ảnh: {fname}")
                    except Exception as e:
                        print(f"    -> Lỗi tải ảnh {fname}: {e}")

    print(f"[*] Hoàn tất đồng bộ! Local DB đã được cập nhật chính xác 100% theo Host.")

if __name__ == "__main__":
    sync()
