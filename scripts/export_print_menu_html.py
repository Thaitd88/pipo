# -*- coding: utf-8 -*-
"""
Xuất file HTML Menu bản cứng A4 độc lập (Standalone Print-Ready File)
Có thể mở bằng bất kỳ trình duyệt nào và bấm Ctrl + P để in hoặc Lưu thành PDF.
"""
import jinja2
import json
import sqlite3
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "data", "pipo_garden.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM categories WHERE is_active = 1 ORDER BY display_order ASC")
categories = [dict(c) for c in cursor.fetchall()]

cursor.execute("""
    SELECT m.*, c.name as category_name, c.icon as category_icon, c.display_order as cat_order
    FROM menu_items m
    JOIN categories c ON m.category_id = c.id
    WHERE m.is_available = 1
    ORDER BY c.display_order ASC, m.id ASC
""")
items = [dict(it) for it in cursor.fetchall()]
conn.close()

cat_map = {c["id"]: {**c, "items": []} for c in categories}
for it in items:
    if it.get("options_json"):
        try:
            it["options"] = json.loads(it["options_json"])
        except Exception:
            it["options"] = []
    else:
        it["options"] = []
        
    if it["category_id"] in cat_map:
        cat_map[it["category_id"]]["items"].append(it)
        
organized_menu = list(cat_map.values())

# Render Jinja2 template
template_path = os.path.join(ROOT_DIR, "app", "templates")
env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_path))
template = env.get_template("print_menu.html")

output_html = template.render(
    menu=organized_menu,
    categories=categories
)

# Đường dẫn lưu file
out_file_project = os.path.join(ROOT_DIR, "Menu_Ban_Cung_A4_PiPo_Garden.html")
with open(out_file_project, "w", encoding="utf-8") as f:
    f.write(output_html)

print(f"[+] Da xuat file Menu ban cung thanh cong tai: {out_file_project}")
