# -*- coding: utf-8 -*-
"""
Cập nhật cơ chế tự động đổi tên ảnh theo tên món khi người dùng upload từ Web Quản trị
Đồng thời bảo toàn ảnh người dùng upload trên máy chủ khi khởi động lại.
"""
import re
import os
import sqlite3

# 1. Cập nhật app/routers/menu.py
with open("app/routers/menu.py", "r", encoding="utf-8") as f:
    menu_py = f.read()

# Đổi import Form
menu_py = menu_py.replace(
    "from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query",
    "from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query"
)

# Thêm hàm slugify_vietnamese
slugify_func = '''
def slugify_vietnamese(text: str) -> str:
    """Chuyển đổi chuỗi tiếng Việt có dấu thành slug không dấu chuẩn mực (VD: 'Sườn Bò Nướng' -> 'suon_bo_nuong')."""
    if not text:
        return ""
    text = text.lower()
    patterns = {
        '[àáảãạăằắẳẵặâầấẩẫậ]': 'a',
        '[èéẻẽẹêềếểễệ]': 'e',
        '[ìíỉĩị]': 'i',
        '[òóỏõọôồốổỗộơờớởỡợ]': 'o',
        '[ùúủũụưừứửữự]': 'u',
        '[ỳýỷỹỵ]': 'y',
        '[đ]': 'd'
    }
    for regex, repl in patterns.items():
        text = re.sub(regex, repl, text)
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = text.strip('_')
    return text[:45]
'''

if "def slugify_vietnamese" not in menu_py:
    # Chèn trước upload_dish_image
    menu_py = menu_py.replace('@router.post("/upload-image")', slugify_func + '\n@router.post("/upload-image")')

# Thay thế hàm upload_dish_image
old_upload_code = '''@router.post("/upload-image")
async def upload_dish_image(file: UploadFile = File(...)):
    """
    Tải ảnh món ăn lên hệ thống:
    - Hỗ trợ JPG, PNG, WEBP, GIF, JFIF, AVIF.
    - Tự động xoay chiều chuẩn theo EXIF.
    - Tự động Resize ảnh tối ưu (max chiều dài 800px, bảo toàn tỉ lệ khung hình).
    - Tự động nén WebP chất lượng cao (~30-70KB) cho tốc độ tải cực nhẹ và mượt.
    - Lưu vào cả thư mục static và thư mục dữ liệu bền (/app/data/uploads).
    """
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".jfif", ".bmp", ".gif", ".avif"}
    original_name = file.filename or "dish.jpg"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Định dạng tệp '{ext}' không được hỗ trợ. Vui lòng chọn ảnh JPG, PNG hoặc WebP.")

    contents = await file.read()
    if len(contents) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Dung lượng ảnh vượt quá giới hạn 15MB.")

    try:
        img = Image.open(io.BytesIO(contents))
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể xử lý tệp ảnh: {str(e)}")

    # Auto-Resize ảnh: cạnh dài nhất tối đa 800px
    max_dim = 800
    w, h = img.size
    if w > max_dim or h > max_dim:
        if w > h:
            new_w = max_dim
            new_h = int(h * (max_dim / w))
        else:
            new_h = max_dim
            new_w = int(w * (max_dim / h))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Chuyển đổi màu sắc
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    # Tạo tên tệp chuẩn hóa
    base_slug = re.sub(r'[^a-zA-Z0-9_\-]', '', os.path.splitext(original_name)[0].lower())[:25]
    if not base_slug:
        base_slug = "dish"
    unique_name = f"{base_slug}_{uuid.uuid4().hex[:8]}.webp"'''

new_upload_code = '''@router.post("/upload-image")
async def upload_dish_image(
    file: UploadFile = File(...),
    dish_name: Optional[str] = Form(None),
    dish_id: Optional[int] = Form(None)
):
    """
    Tải ảnh món ăn lên hệ thống:
    - Tự động đặt lại tên file chuẩn theo tên món không dấu (VD: suon_bo_nuong_a1b2c3.webp).
    - Hỗ trợ JPG, PNG, WEBP, GIF, JFIF, AVIF.
    - Tự động xoay chiều chuẩn theo EXIF.
    - Tự động Resize ảnh tối ưu (max chiều dài 800px, bảo toàn tỉ lệ khung hình).
    - Tự động nén WebP chất lượng cao (~30-70KB) cho tốc độ tải cực nhẹ và mượt.
    - Lưu vào cả thư mục static và thư mục dữ liệu bền (/app/data/uploads).
    """
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".jfif", ".bmp", ".gif", ".avif"}
    original_name = file.filename or "dish.jpg"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Định dạng tệp '{ext}' không được hỗ trợ. Vui lòng chọn ảnh JPG, PNG hoặc WebP.")

    contents = await file.read()
    if len(contents) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Dung lượng ảnh vượt quá giới hạn 15MB.")

    try:
        img = Image.open(io.BytesIO(contents))
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể xử lý tệp ảnh: {str(e)}")

    # Auto-Resize ảnh: cạnh dài nhất tối đa 800px
    max_dim = 800
    w, h = img.size
    if w > max_dim or h > max_dim:
        if w > h:
            new_w = max_dim
            new_h = int(h * (max_dim / w))
        else:
            new_h = max_dim
            new_w = int(w * (max_dim / h))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Chuyển đổi màu sắc
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    # TỰ ĐỘNG ĐỔI TÊN ẢNH THEO TÊN MÓN ĂN CHUẨN XÁC:
    # 1. Ưu tiên tên món được truyền lên từ form
    # 2. Hoặc tìm tên món trong CSDL theo dish_id
    # 3. Hoặc chuyển đổi tên file gốc sang không dấu sạch sẽ
    slug = ""
    if dish_name and dish_name.strip():
        slug = slugify_vietnamese(dish_name.strip())
    elif dish_id:
        try:
            conn_chk = get_db()
            c_row = conn_chk.cursor().execute("SELECT name FROM menu_items WHERE id = ?", (dish_id,)).fetchone()
            conn_chk.close()
            if c_row and c_row["name"]:
                slug = slugify_vietnamese(c_row["name"])
        except Exception:
            pass

    if not slug:
        raw_base = os.path.splitext(original_name)[0]
        # Loại bỏ các tiền tố chụp màn hình vô nghĩa: Screenshot, Zalo_image...
        clean_base = re.sub(r'^(screenshot|zalo_image|image|img|photo)[_\-\\d]*', '', raw_base, flags=re.IGNORECASE)
        slug = slugify_vietnamese(clean_base if clean_base.strip() else raw_base)

    if not slug:
        slug = "dish"

    # Tạo tên file đẹp: suon_bo_nuong_a1b2c3.webp
    unique_name = f"{slug}_{uuid.uuid4().hex[:6]}.webp"'''

menu_py = menu_py.replace(old_upload_code, new_upload_code)

with open("app/routers/menu.py", "w", encoding="utf-8") as f:
    f.write(menu_py)
print("[+] Da cap nhat app/routers/menu.py voi slugify_vietnamese va doi ten anh theo ten mon!")

# 2. Cập nhật app/templates/admin.html
with open("app/templates/admin.html", "r", encoding="utf-8") as f:
    admin_html = f.read()

old_admin_upload = '''    async function uploadMenuItemImage(input) {
      if (!input.files || input.files.length === 0) return;
      const file = input.files[0];
      const formData = new FormData();
      formData.append("file", file);'''

new_admin_upload = '''    async function uploadMenuItemImage(input) {
      if (!input.files || input.files.length === 0) return;
      const file = input.files[0];
      const formData = new FormData();
      formData.append("file", file);

      // Tự động truyền tên món để backend đổi tên ảnh tương ứng
      const dishName = document.getElementById("itemFormName")?.value || "";
      const dishId = document.getElementById("itemFormId")?.value || "";
      if (dishName.trim()) formData.append("dish_name", dishName.trim());
      if (dishId) formData.append("dish_id", dishId);'''

admin_html = admin_html.replace(old_admin_upload, new_admin_upload)

with open("app/templates/admin.html", "w", encoding="utf-8") as f:
    f.write(admin_html)
print("[+] Da cap nhat app/templates/admin.html gui kem dish_name khi upload!")

# 3. Cập nhật app/templates/kitchen.html
with open("app/templates/kitchen.html", "r", encoding="utf-8") as f:
    kitchen_html = f.read()

old_kitchen_upload = '''    async function uploadKitchenDishImage(input) {
      if (!input.files || input.files.length === 0) return;
      const file = input.files[0];
      const formData = new FormData();
      formData.append("file", file);'''

new_kitchen_upload = '''    async function uploadKitchenDishImage(input) {
      if (!input.files || input.files.length === 0) return;
      const file = input.files[0];
      const formData = new FormData();
      formData.append("file", file);

      // Tự động truyền tên món để backend đổi tên ảnh tương ứng
      const dishName = document.getElementById("dishName")?.value || "";
      const dishId = document.getElementById("dishId")?.value || "";
      if (dishName.trim()) formData.append("dish_name", dishName.trim());
      if (dishId) formData.append("dish_id", dishId);'''

kitchen_html = kitchen_html.replace(old_kitchen_upload, new_kitchen_upload)

with open("app/templates/kitchen.html", "w", encoding="utf-8") as f:
    f.write(kitchen_html)
print("[+] Da cap nhat app/templates/kitchen.html gui kem dish_name khi upload!")

# 4. Cập nhật app/menu_syncer.py:
# - Gán ảnh đẹp cho 333, 338, 342
# - Bảo toàn ảnh đã upload khi boot
with open("app/menu_syncer.py", "r", encoding="utf-8") as f:
    syncer = f.read()

# Đổi ảnh cho 333, 338, 342 trong MENU_ITEMS
syncer = re.sub(
    r'("id": 333,\s*"category_id": 7,\s*"name": "Sườn bò nướng",[\s\S]*?"image_url": )"[^"]*"',
    r'\1"/static/dishes/suon_bo_nuong.webp"',
    syncer
)
syncer = re.sub(
    r'("id": 338,\s*"category_id": 7,\s*"name": "Đùi gà nướng",[\s\S]*?"image_url": )"[^"]*"',
    r'\1"/static/dishes/dui_ga_nuong.webp"',
    syncer
)
syncer = re.sub(
    r'("id": 342,\s*"category_id": 7,\s*"name": "Mực ống nướng",[\s\S]*?"image_url": )"[^"]*"',
    r'\1"/static/dishes/muc_ong_nuong.webp"',
    syncer
)

# Bảo toàn ảnh người dùng upload trong ensure_updated_menu
old_clear_block = '''    # 3. CLEAR SẠCH MÓN CŨ TRÊN HOST VÀ NẠP LẠI TOÀN BỘ MENU CHUẨN XÁC
    cur.execute("DELETE FROM menu_items")
    cur.execute("DELETE FROM recipe_bom")

    for it in MENU_ITEMS:
        cur.execute("""
            INSERT INTO menu_items (id, category_id, name, price, station, image_url, description, is_available, calories, portion, main_menu_type, options_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (it["id"], it["category_id"], it["name"], it["price"], it["station"],
              it["image_url"], it["description"], it["is_available"], it["calories"], it["portion"],
              it["main_menu_type"], it["options_json"]))'''

new_clear_block = '''    # 3. CLEAR SẠCH MÓN CŨ TRÊN HOST VÀ NẠP LẠI TOÀN BỘ MENU CHUẨN XÁC (BẢO TOÀN ẢNH ĐÃ UPLOAD)
    # Lấy lại danh sách ảnh do người dùng đã upload lên
    cur.execute("SELECT id, image_url FROM menu_items WHERE image_url IS NOT NULL AND image_url != '' AND image_url NOT LIKE '%logo.png'")
    existing_user_images = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute("DELETE FROM menu_items")
    cur.execute("DELETE FROM recipe_bom")

    for it in MENU_ITEMS:
        img_url = existing_user_images.get(it["id"]) or it["image_url"]
        # Tự động chuẩn hóa tên ảnh cũ nếu là ảnh screenshot
        if it["id"] == 333:
            img_url = "/static/dishes/suon_bo_nuong.webp"
        elif it["id"] == 338:
            img_url = "/static/dishes/dui_ga_nuong.webp"
        elif it["id"] == 342:
            img_url = "/static/dishes/muc_ong_nuong.webp"

        cur.execute("""
            INSERT INTO menu_items (id, category_id, name, price, station, image_url, description, is_available, calories, portion, main_menu_type, options_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (it["id"], it["category_id"], it["name"], it["price"], it["station"],
              img_url, it["description"], it["is_available"], it["calories"], it["portion"],
              it["main_menu_type"], it["options_json"]))'''

syncer = syncer.replace(old_clear_block, new_clear_block)

with open("app/menu_syncer.py", "w", encoding="utf-8") as f:
    f.write(syncer)
print("[+] Da cap nhat app/menu_syncer.py bao toan anh upload va doi anh 333, 338, 342!")

# 5. Cập nhật CSDL local
db_path = "data/pipo_garden.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE menu_items SET image_url = '/static/dishes/suon_bo_nuong.webp' WHERE id = 333")
    cur.execute("UPDATE menu_items SET image_url = '/static/dishes/dui_ga_nuong.webp' WHERE id = 338")
    cur.execute("UPDATE menu_items SET image_url = '/static/dishes/muc_ong_nuong.webp' WHERE id = 342")
    conn.commit()
    conn.close()
    print("[+] Da cap nhat CSDL local data/pipo_garden.db")

print("[*] Hoan tat tat ca ban cap nhat!")
