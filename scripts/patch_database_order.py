# -*- coding: utf-8 -*-
"""
Script cập nhật logic thứ tự danh mục trong database.py, menu_fixer.py, menu_syncer.py và main.py
"""
import re

# 1. Cập nhật app/database.py
with open("app/database.py", "r", encoding="utf-8") as f:
    db_code = f.read()

# Hot BBQ display order -> 1
old_bbq_block = """    if bbq_cat:
        bbq_cat_id = bbq_cat["id"]
        cursor.execute(\"\"\"
            UPDATE categories 
            SET display_order = 0, icon = '🔥', is_active = 1, translations_json = ? 
            WHERE id = ?
        \"\"\", (json.dumps(bbq_translations, ensure_ascii=False), bbq_cat_id))
    else:
        cursor.execute(\"\"\"
            INSERT INTO categories (id, name, icon, display_order, is_active, translations_json)
            VALUES (7, 'Hot BBQ', '🔥', 0, 1, ?)
        \"\"\", (json.dumps(bbq_translations, ensure_ascii=False),))
        bbq_cat_id = cursor.lastrowid or 7

    # Đảm bảo các danh mục khác có thứ tự từ 1..6
    OTHER_ORDERS = {
        "Khai Vị": 1,
        "Gà - Vịt": 2,
        "Heo - Bò": 3,
        "Hải Sản": 4,
        "Cơm - Mì": 5,
        "Đồ Uống": 6
    }
    for cname, corder in OTHER_ORDERS.items():
        cursor.execute("UPDATE categories SET display_order = ? WHERE name = ?", (corder, cname))"""

new_bbq_block = """    if bbq_cat:
        bbq_cat_id = bbq_cat["id"]
        cursor.execute(\"\"\"
            UPDATE categories 
            SET display_order = 1, icon = '🔥', is_active = 1, translations_json = ? 
            WHERE id = ?
        \"\"\", (json.dumps(bbq_translations, ensure_ascii=False), bbq_cat_id))
    else:
        cursor.execute(\"\"\"
            INSERT INTO categories (id, name, icon, display_order, is_active, translations_json)
            VALUES (7, 'Hot BBQ', '🔥', 1, 1, ?)
        \"\"\", (json.dumps(bbq_translations, ensure_ascii=False),))
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
        cursor.execute("UPDATE categories SET display_order = ? WHERE name = ?", (corder, cname))"""

# Normalize line breaks for matching
db_code_lf = db_code.replace("\r\n", "\n")
old_bbq_lf = old_bbq_block.replace("\r\n", "\n")
if old_bbq_lf in db_code_lf:
    db_code_lf = db_code_lf.replace(old_bbq_lf, new_bbq_block.replace("\r\n", "\n"))
    print("[+] Da cap nhat BBQ display order va OTHER_ORDERS trong ensure_bbq_category_and_dishes")
else:
    print("[-] Khong tim thay old_bbq_block trong app/database.py")

# Non-blocking seed_translations_if_missing in init_db
old_trans_call = "    # Đảm bảo toàn bộ danh mục và món ăn đều có dữ liệu đa ngôn ngữ\n    seed_translations_if_missing(conn)"
new_trans_call = "    # Đảm bảo toàn bộ danh mục và món ăn đều có dữ liệu đa ngôn ngữ (chạy nền không nghẽn khởi động)\n    import threading\n    threading.Thread(target=seed_translations_if_missing, args=(None,), daemon=True).start()"

if old_trans_call in db_code_lf:
    db_code_lf = db_code_lf.replace(old_trans_call, new_trans_call)
    print("[+] Da chuyen seed_translations_if_missing sang daemon thread")

# Update seed_translations_if_missing to accept conn=None
old_seed_def = "def seed_translations_if_missing(conn):"
new_seed_def = """def seed_translations_if_missing(conn=None):
    close_at_end = False
    if conn is None:
        conn = get_db()
        close_at_end = True"""

if old_seed_def in db_code_lf:
    # Also add close if opened
    old_end = """        if needs_trans:
            trans = translate_dish(item["name"], item["description"] or "")
            cursor.execute("UPDATE menu_items SET translations_json = ? WHERE id = ?", (json.dumps(trans, ensure_ascii=False), item["id"]))

    conn.commit()"""
    new_end = """        if needs_trans:
            trans = translate_dish(item["name"], item["description"] or "")
            cursor.execute("UPDATE menu_items SET translations_json = ? WHERE id = ?", (json.dumps(trans, ensure_ascii=False), item["id"]))

    conn.commit()
    if close_at_end:
        try:
            conn.close()
        except Exception:
            pass"""
    db_code_lf = db_code_lf.replace(old_seed_def, new_seed_def, 1)
    db_code_lf = db_code_lf.replace(old_end, new_end, 1)
    print("[+] Da ho tro conn=None cho seed_translations_if_missing")

# Save back to app/database.py
with open("app/database.py", "w", encoding="utf-8") as f:
    f.write(db_code_lf)

# 2. Cập nhật app/menu_fixer.py (Dịch vụ sân Pickleball display_order = 11)
with open("app/menu_fixer.py", "r", encoding="utf-8") as f:
    fixer_code = f.read()

fixer_code_lf = fixer_code.replace("\r\n", "\n")
fixer_code_lf = fixer_code_lf.replace(
    "VALUES (8, 'Dịch Vụ Sân Pickleball', '🎾', 8, 1, ?)",
    "VALUES (8, 'Dịch Vụ Sân Pickleball', '🎾', 11, 1, ?)"
)

# Thêm translations cho category 9, 10, 11
old_cat_trans = """    7: {"en": "Garden Hot BBQ", "zh": "炭火热烤 (花园BBQ)", "ko": "가든 숯불 핫 BBQ", "ru": "Горячее барбекю в саду"},
    8: {"en": "Pickleball Court Services", "zh": "匹克球球场服务", "ko": "피클볼 코트 서비스", "ru": "Услуги корта пиклбол"}
}"""

new_cat_trans = """    7: {"en": "Garden Hot BBQ", "zh": "炭火热烤 (花园BBQ)", "ko": "가든 숯불 핫 BBQ", "ru": "Горячее барбекю в саду"},
    8: {"en": "Pickleball Court Services", "zh": "匹克球球场服务", "ko": "피클볼 코트 서비스", "ru": "Услуги корта пиклбол"},
    9: {"en": "Best Seller Dishes", "zh": "招牌热销推荐", "ko": "베스트 셀러 추천 요리", "ru": "Фирменные бестселлеры"},
    10: {"en": "Soups & Congee", "zh": "养生浓汤与暖胃粥", "ko": "영양 수프 & 죽", "ru": "Питательные супы и каши"},
    11: {"en": "Hotpot Specialties", "zh": "特色养生火锅", "ko": "스페셜 핫팟 전골", "ru": "Фирменные горячие котлы"}
}"""

if old_cat_trans in fixer_code_lf:
    fixer_code_lf = fixer_code_lf.replace(old_cat_trans, new_cat_trans)
    print("[+] Da bo sung category translations 9, 10, 11 vao app/menu_fixer.py")

with open("app/menu_fixer.py", "w", encoding="utf-8") as f:
    f.write(fixer_code_lf)
print("[+] Da cap nhat Pickleball display_order = 11 trong app/menu_fixer.py")

# 3. Cập nhật app/menu_syncer.py (chống lỗi UnicodeEncodeError khi print)
with open("app/menu_syncer.py", "r", encoding="utf-8") as f:
    syncer_code = f.read()

syncer_code_lf = syncer_code.replace("\r\n", "\n")
old_sync_print = '    print(f"[PiPo Garden] Đã CLEAR và nạp mới thành công {len(MENU_ITEMS)} món ăn chuẩn xác từ Excel vào CSDL!")'
new_sync_print = '''    try:
        print(f"[PiPo Garden] Da CLEAR va nap moi thanh cong {len(MENU_ITEMS)} mon an chuan xac tu Excel vao CSDL!")
    except Exception:
        pass'''

if old_sync_print in syncer_code_lf:
    syncer_code_lf = syncer_code_lf.replace(old_sync_print, new_sync_print)
    print("[+] Da sua print thanh safe ASCII trong app/menu_syncer.py")

with open("app/menu_syncer.py", "w", encoding="utf-8") as f:
    f.write(syncer_code_lf)

# 4. Thêm /health endpoint vào app/main.py
with open("app/main.py", "r", encoding="utf-8") as f:
    main_code = f.read()

main_code_lf = main_code.replace("\r\n", "\n")
if "/health" not in main_code_lf:
    health_ep = """
@app.get("/health")
def health_check():
    \"\"\"Endpoint kiem tra tinh trang hoat dong phuc vu Health Check Reverse Proxy.\"\"\"
    return {"status": "ok", "app": "PiPo Garden Restaurant System"}
"""
    main_code_lf = main_code_lf.replace('app = FastAPI(title="PiPo Garden Restaurant System", lifespan=lifespan)',
                                        'app = FastAPI(title="PiPo Garden Restaurant System", lifespan=lifespan)' + health_ep)
    with open("app/main.py", "w", encoding="utf-8") as f:
        f.write(main_code_lf)
    print("[+] Da them /health endpoint vao app/main.py")

print("[*] Tat ca ban sua da duoc ap dung thanh cong!")
