import sys, openpyxl, sqlite3, json, re, os
sys.stdout.reconfigure(encoding='utf-8')

db_path = "data/pipo_garden.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("[*] Bắt đầu đồng bộ menu từ Excel vào CSDL...")

# 1. ĐẢM BẢO CÁC DANH MỤC (CATEGORIES)
categories_config = [
    (1, "Khai Vị", "🥗", 1),
    (2, "Gà - Vịt", "🍗", 2),
    (3, "Heo - Bò", "🥩", 3),
    (4, "Hải Sản", "🦐", 4),
    (5, "Cơm - Mì", "🍚", 5),
    (6, "Đồ Uống", "🍹", 6),
    (7, "Hot BBQ", "🔥", 7),
    (8, "Dịch Vụ Sân Pickleball", "🎾", 8),
    (9, "Best Seller", "⭐", 9),
    (10, "Súp - Cháo", "🍲", 10),
    (11, "Món Lẩu", "🥘", 11)
]

for cid, cname, cicon, corder in categories_config:
    cur.execute("SELECT id FROM categories WHERE id = ? OR name = ?", (cid, cname))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE categories SET name = ?, icon = ?, display_order = ? WHERE id = ?", (cname, cicon, corder, row["id"]))
    else:
        cur.execute("INSERT INTO categories (id, name, icon, display_order) VALUES (?, ?, ?, ?)", (cid, cname, cicon, corder))
conn.commit()

# Lấy category map
cur.execute("SELECT id, name FROM categories")
cat_map = {}
for r in cur.fetchall():
    cat_map[r["name"].strip().lower()] = r["id"]

def find_category_id(cat_text):
    clean = re.sub(r'[^\w\s-]', '', cat_text).strip().lower()
    for c_name, c_id in cat_map.items():
        if c_name in clean or clean in c_name:
            return c_id
    if "khai vị" in clean: return 1
    if "gà" in clean or "vịt" in clean: return 2
    if "heo" in clean or "bò" in clean: return 3
    if "hải sản" in clean: return 4
    if "cơm" in clean or "mì" in clean: return 5
    if "uống" in clean or "bia" in clean: return 6
    if "bbq" in clean or "nướng" in clean: return 7
    if "sân" in clean or "pickle" in clean: return 8
    if "seller" in clean: return 9
    if "súp" in clean or "cháo" in clean: return 10
    if "lẩu" in clean: return 11
    return 1 # Default Khai vị

# 2. ĐỌC FILE EXCEL
wb = openpyxl.load_workbook("Menu_PiPo_Garden_Cap_Nhat.xlsx", data_only=True)
ws = wb.active
print(f"[+] Đã mở sheet: [{ws.title}], số dòng: {ws.max_row}")

static_dishes_dir = os.path.abspath("app/static/dishes")

# Map station
station_map = {
    "bếp nóng": "HOT_KITCHEN",
    "bếp lạnh": "COLD_KITCHEN",
    "quầy bar": "BAR",
    "sân pickleball": "PICKLE",
    "hot_kitchen": "HOT_KITCHEN",
    "cold_kitchen": "COLD_KITCHEN",
    "bar": "BAR",
    "pickle": "PICKLE"
}

# Lấy max ID hiện tại của inventory_items
cur.execute("SELECT MAX(id) FROM inventory_items")
max_inv_id = cur.fetchone()[0] or 0

dishes_imported = []
updated_count = 0
inserted_count = 0

for r in range(2, ws.max_row + 1):
    id_val = ws.cell(r, 1).value
    cat_raw = str(ws.cell(r, 2).value or "").strip()
    name = str(ws.cell(r, 3).value or "").strip()
    taste = str(ws.cell(r, 4).value or "").strip()
    portion = str(ws.cell(r, 5).value or "").strip()
    bom_str = str(ws.cell(r, 6).value or "").strip()
    price = ws.cell(r, 7).value or 0
    cost = ws.cell(r, 8).value or 0
    station_raw = str(ws.cell(r, 10).value or "Bếp Nóng").strip().lower()
    menu_type_raw = str(ws.cell(r, 11).value or "Nhà Hàng").strip()
    avail_raw = str(ws.cell(r, 12).value or "Đang bán").strip().lower()
    img_file = str(ws.cell(r, 13).value or "").strip()
    desc = str(ws.cell(r, 16).value or "").strip()

    if not name or name == "Tên món ăn / Dịch vụ":
        continue

    cat_id = find_category_id(cat_raw)
    station = station_map.get(station_raw, "HOT_KITCHEN")
    is_available = 1 if ("đang bán" in avail_raw or "1" in avail_raw) else 0

    try:
        price_int = int(float(price or 0))
    except Exception:
        price_int = 0

    try:
        cost_int = int(float(cost or 0))
    except Exception:
        cost_int = int(price_int * 0.4)

    # Xử lý hình ảnh: Món nào chưa có ảnh cứ để logo PiPO (/static/logo.png)
    image_url = "/static/logo.png"
    if img_file and img_file not in ["None", "", "(Chưa có ảnh)"]:
        clean_img = os.path.basename(img_file)
        if os.path.exists(os.path.join(static_dishes_dir, clean_img)):
            image_url = f"/static/dishes/{clean_img}"
        elif os.path.exists(os.path.join("app/static", clean_img)):
            image_url = f"/static/{clean_img}"
        else:
            image_url = "/static/logo.png"

    # Xử lý Vị / options_json
    options_json = "[]"
    if taste and taste.lower() != "tiêu chuẩn":
        options_list = [t.strip() for t in taste.split(",") if t.strip()]
        if options_list:
            options_json = json.dumps([{"name": "Cách chế biến / Vị", "options": options_list}], ensure_ascii=False)

    menu_type = "RESTAURANT"

    # Kiểm tra xem món đã có ID trong DB chưa
    existing_dish = None
    numeric_id = None
    try:
        if id_val and str(id_val).strip().isdigit():
            numeric_id = int(str(id_val).strip())
            cur.execute("SELECT id FROM menu_items WHERE id = ?", (numeric_id,))
            existing_dish = cur.fetchone()
    except Exception:
        existing_dish = None

    if not existing_dish:
        cur.execute("SELECT id FROM menu_items WHERE name = ?", (name,))
        existing_dish = cur.fetchone()

    dish_id = None
    if existing_dish:
        dish_id = existing_dish["id"]
        cur.execute("""
            UPDATE menu_items 
            SET category_id = ?, name = ?, price = ?, portion = ?, station = ?, 
                is_available = ?, options_json = ?, image_url = ?, main_menu_type = ?, description = ?
            WHERE id = ?
        """, (cat_id, name, price_int, portion, station, is_available, options_json, image_url, menu_type, desc, dish_id))
        updated_count += 1
    else:
        cur.execute("""
            INSERT INTO menu_items (
                category_id, name, price, portion, station, is_available, 
                options_json, image_url, main_menu_type, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cat_id, name, price_int, portion, station, is_available, options_json, image_url, menu_type, desc))
        dish_id = cur.lastrowid
        inserted_count += 1

    has_grill = bool(re.search(r'nướng|nuong|bbq', f"{taste} {name}", re.IGNORECASE))

    dishes_imported.append({
        "dish_id": dish_id,
        "name": name,
        "cat_id": cat_id,
        "price": price_int,
        "portion": portion,
        "station": station,
        "taste": taste,
        "options_json": options_json,
        "image_url": image_url,
        "bom_str": bom_str,
        "cost": cost_int,
        "desc": desc,
        "has_grill": has_grill
    })

    # 3. TỰ TẠO MÃ NVL CHO MÓN ĂN & THIẾT LẬP RECIPE_BOM
    # Tìm hoặc tạo NVL trong inventory_items
    cur.execute("SELECT id FROM inventory_items WHERE name = ?", (name,))
    inv_row = cur.fetchone()
    if not inv_row and bom_str and bom_str != "Chưa thiết lập BOM":
        # Thử tìm theo từ khóa chính trong BOM
        primary_name = bom_str.split(":")[0].split(",")[0].strip()
        cur.execute("SELECT id FROM inventory_items WHERE name LIKE ?", (f"%{primary_name}%",))
        inv_row = cur.fetchone()

    if inv_row:
        inv_id = inv_row["id"]
    else:
        max_inv_id += 1
        inv_code = f"NVL{max_inv_id:02d}"
        inv_name = f"Nguyên liệu {name}"
        inv_unit = "phần"
        if portion and any(u in portion.lower() for u in ["kg", "con", "đĩa", "dĩa", "bìa", "lon"]):
            for u in ["con", "bìa", "lon", "đĩa", "dĩa", "kg"]:
                if u in portion.lower():
                    inv_unit = u
                    break
        cur.execute("""
            INSERT INTO inventory_items (code, name, unit, stock_quantity, min_stock, cost_price, supplier)
            VALUES (?, ?, ?, 50.0, 5.0, ?, 'Nhà cung cấp tươi Phú Quốc')
        """, (inv_code, inv_name, inv_unit, cost_int))
        inv_id = cur.lastrowid

    # Liên kết vào recipe_bom nếu chưa có
    cur.execute("SELECT id FROM recipe_bom WHERE menu_item_id = ?", (dish_id,))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO recipe_bom (menu_item_id, ingredient_id, quantity)
            VALUES (?, ?, 1.0)
        """, (dish_id, inv_id))

conn.commit()
print(f"[+] Đã cập nhật {updated_count} món, tạo mới {inserted_count} món ăn vào CSDL.")

# 4. TỰ COPY CÁC MÓN CÓ VỊ NƯỚNG SANG NHÓM HOT BBQ (CAT_ID = 7)
print("[*] Tự động copy các món có vị Nướng sang nhóm Hot BBQ...")
# Dọn dẹp các món tạm "Coming soon" cũ trong Hot BBQ
cur.execute("DELETE FROM menu_items WHERE category_id = 7 AND (price = 0 OR is_available = 0)")
conn.commit()

hot_bbq_id = 7
bbq_copied = 0
for d in dishes_imported:
    if d["has_grill"]:
        # Kiểm tra xem món này đã có bản copy trong Hot BBQ chưa
        cur.execute("SELECT id FROM menu_items WHERE category_id = 7 AND name = ?", (d["name"],))
        bbq_item = cur.fetchone()
        if not bbq_item:
            cur.execute("""
                INSERT INTO menu_items (
                    category_id, name, price, portion, station, is_available,
                    options_json, image_url, main_menu_type, description
                ) VALUES (7, ?, ?, ?, 'HOT_KITCHEN', 1, ?, ?, 'RESTAURANT', ?)
            """, (d["name"], d["price"], d["portion"], d["options_json"], d["image_url"], d["desc"]))
            bbq_dish_id = cur.lastrowid
            
            # Gán recipe_bom cho bản copy BBQ
            cur.execute("SELECT ingredient_id, quantity FROM recipe_bom WHERE menu_item_id = ?", (d["dish_id"],))
            orig_bom = cur.fetchone()
            if orig_bom:
                cur.execute("INSERT OR IGNORE INTO recipe_bom (menu_item_id, ingredient_id, quantity) VALUES (?, ?, ?)", 
                            (bbq_dish_id, orig_bom["ingredient_id"], orig_bom["quantity"]))
            bbq_copied += 1
            print(f"  [+] Đã copy sang Hot BBQ: {d['name']} (Giá: {d['price']:,} đ)")

conn.commit()
print(f"[+] Hoàn tất copy {bbq_copied} món nướng sang nhóm Hot BBQ!")

# Đồng bộ file CSDL sang thungan
import shutil
thungan_db = "thungan/data/pipo_garden.db"
if os.path.exists(os.path.dirname(thungan_db)):
    shutil.copy2(db_path, thungan_db)
    print("[+] Đã đồng bộ CSDL sang máy thu ngân: thungan/data/pipo_garden.db")

conn.close()
print("[✔] Hoàn thành cập nhật thực đơn 100%!")
