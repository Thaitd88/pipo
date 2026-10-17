import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data/pipo_garden.db')
cursor = conn.cursor()

# Cập nhật tất cả các món thuộc nhóm Đồ Uống (category_id = 6) có chứa PICKLE trong main_menu_type
cursor.execute("SELECT id, name, category_id, main_menu_type FROM menu_items WHERE category_id = 6")
drinks = cursor.fetchall()

for d in drinks:
    d_id, name, cat_id, m_type = d
    m_type = m_type or ""
    parts = [p.strip().upper() for p in m_type.split(",") if p.strip()]
    if "PICKLE" not in parts:
        parts.append("PICKLE")
    new_type = ",".join(parts)
    cursor.execute("UPDATE menu_items SET main_menu_type = ? WHERE id = ?", (new_type, d_id))
    print(f"Updated item #{d_id} ({name}) -> main_menu_type = '{new_type}'")

# Thêm món ăn nhẹ phù hợp sân thể thao nếu có
cursor.execute("SELECT id, name, main_menu_type FROM menu_items WHERE name LIKE '%Khoai tây chiên%' OR name LIKE '%Bò xuyên tiêu%'")
snacks = cursor.fetchall()
for s in snacks:
    s_id, name, m_type = s
    m_type = m_type or ""
    parts = [p.strip().upper() for p in m_type.split(",") if p.strip()]
    if "PICKLE" not in parts:
        parts.append("PICKLE")
    new_type = ",".join(parts)
    cursor.execute("UPDATE menu_items SET main_menu_type = ? WHERE id = ?", (new_type, s_id))
    print(f"Updated snack #{s_id} ({name}) -> main_menu_type = '{new_type}'")

conn.commit()
conn.close()
print("Done updating PICKLE menu items!")
