# -*- coding: utf-8 -*-
with open("app/main.py", "r", encoding="utf-8") as f:
    code = f.read()

code_lf = code.replace("\r\n", "\n")

target = """@app.get("/print-qrcodes", response_class=HTMLResponse)
def print_qrcodes_page(request: Request):
    \"\"\"Trang xuất và in toàn bộ mã QR của tất cả các bàn chuẩn khổ A4.\"\"\"
    return templates.TemplateResponse(request=request, name="print_qrcodes.html", context={})"""

replacement = """@app.get("/print-qrcodes", response_class=HTMLResponse)
def print_qrcodes_page(request: Request):
    \"\"\"Trang xuất và in toàn bộ mã QR của tất cả các bàn chuẩn khổ A4.\"\"\"
    return templates.TemplateResponse(request=request, name="print_qrcodes.html", context={})

@app.get("/print-menu", response_class=HTMLResponse)
def print_menu_page(request: Request):
    \"\"\"Trang xem và in Quyển Thực Đơn bản cứng A4 cao cấp (Chuẩn in ấn xưởng in & xuất PDF).\"\"\"
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories WHERE is_active = 1 ORDER BY display_order ASC")
    categories = [dict(c) for c in cursor.fetchall()]
    
    cursor.execute(\"\"\"
        SELECT m.*, c.name as category_name, c.icon as category_icon, c.display_order as cat_order
        FROM menu_items m
        JOIN categories c ON m.category_id = c.id
        WHERE m.is_available = 1
        ORDER BY c.display_order ASC, m.id ASC
    \"\"\")
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
    
    return templates.TemplateResponse(
        request=request,
        name="print_menu.html",
        context={
            "menu": organized_menu,
            "categories": categories
        }
    )"""

if target in code_lf:
    code_lf = code_lf.replace(target, replacement)
    with open("app/main.py", "w", encoding="utf-8") as f:
        f.write(code_lf)
    print("[+] Da them endpoint /print-menu vao app/main.py")
else:
    print("[-] Khong tim thay target trong app/main.py")
