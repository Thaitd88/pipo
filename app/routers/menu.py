# Menu router for PiPo Garden with Multi-Language Support
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
import os
import io
import re
import uuid
from PIL import Image, ImageOps
from ..database import get_db, DATA_DIR
from ..services.translator import translate_dish, translate_category_name
from ..services.image_matcher import find_matching_image, sync_all_dish_images, get_dish_naming_guide

router = APIRouter(prefix="/api/menu", tags=["Menu"])

DISHES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "dishes")
os.makedirs(DISHES_DIR, exist_ok=True)

PERSISTENT_UPLOADS = os.path.join(DATA_DIR, "uploads")
os.makedirs(PERSISTENT_UPLOADS, exist_ok=True)

class TranslateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

class MenuItemCreate(BaseModel):
    category_id: int
    name: str
    description: Optional[str] = ""
    price: int
    image_url: Optional[str] = ""
    station: Optional[str] = "HOT_KITCHEN"
    options_json: Optional[str] = "[]"
    translations_json: Optional[str] = None
    translations: Optional[Dict[str, Any]] = None
    is_available: Optional[int] = 1
    calories: Optional[int] = 0
    out_of_ingredients: Optional[int] = 0
    main_menu_type: Optional[str] = "RESTAURANT,LUNCH,CAFE"

class MenuItemUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    image_url: Optional[str] = None
    station: Optional[str] = None
    options_json: Optional[str] = None
    translations_json: Optional[str] = None
    translations: Optional[Dict[str, Any]] = None
    is_available: Optional[int] = None
    calories: Optional[int] = None
    out_of_ingredients: Optional[int] = None
    main_menu_type: Optional[str] = None

class BulkMenuImportRequest(BaseModel):
    raw_text: Optional[str] = ""
    default_category_id: Optional[int] = 1
    default_station: Optional[str] = "HOT_KITCHEN"
    items: Optional[List[Dict[str, Any]]] = None

@router.get("")
def get_full_menu():
    """Lấy danh mục và toàn bộ món ăn kèm dữ liệu đa ngôn ngữ."""
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Lấy danh mục đang kích hoạt
    cursor.execute("SELECT * FROM categories WHERE is_active = 1 ORDER BY display_order")
    categories = [dict(c) for c in cursor.fetchall()]
    
    # 2. Lấy toàn bộ món ăn
    cursor.execute("""
        SELECT m.*, c.name as category_name
        FROM menu_items m
        JOIN categories c ON m.category_id = c.id
        ORDER BY c.display_order, m.id
    """)
    items = [dict(it) for it in cursor.fetchall()]
    conn.close()
    
    # Tổ chức theo cấu trúc danh mục
    cat_dict = {}
    for c in categories:
        if c.get("translations_json"):
            try:
                c["translations"] = json.loads(c["translations_json"])
            except Exception:
                c["translations"] = {}
        else:
            c["translations"] = {}
        cat_dict[c["id"]] = {**c, "items": []}

    for item in items:
        # Tự động nhận diện ảnh mới nhất từ thư mục dishes theo tên món
        match = find_matching_image(item["name"], item.get("image_url"))
        if match:
            item["image_url"] = match["url"]

        # Parse options JSON
        if item.get("options_json"):
            try:
                item["options"] = json.loads(item["options_json"])
            except Exception:
                item["options"] = []
        else:
            item["options"] = []
            
        # Parse translations JSON
        if item.get("translations_json"):
            try:
                item["translations"] = json.loads(item["translations_json"])
            except Exception:
                item["translations"] = {}
        else:
            item["translations"] = {}

        if item["category_id"] in cat_dict:
            cat_dict[item["category_id"]]["items"].append(item)
            
    return list(cat_dict.values())

@router.get("/categories")
def get_categories():
    """Lấy danh sách các danh mục phục vụ chọn khi tạo/sửa món."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories WHERE is_active = 1 ORDER BY display_order")
    cats = [dict(c) for c in cursor.fetchall()]
    conn.close()
    for c in cats:
        if c.get("translations_json"):
            try:
                c["translations"] = json.loads(c["translations_json"])
            except Exception:
                c["translations"] = {}
        else:
            c["translations"] = {}
    return cats

@router.post("/auto-translate")
def auto_translate_endpoint(req: TranslateRequest):
    """
    API Dịch Tự Động thông minh cho món ăn:
    Nhận tên món và mô tả tiếng Việt -> trả về bản dịch 4 thứ tiếng (en, zh, ko, ru).
    """
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập tên món ăn tiếng Việt để dịch")
    
    translations = translate_dish(req.name.strip(), (req.description or "").strip())
    return {
        "status": "SUCCESS",
        "original": {
            "name": req.name.strip(),
            "description": (req.description or "").strip()
        },
        "translations": translations
    }

@router.post("/upload-image")
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
    unique_name = f"{base_slug}_{uuid.uuid4().hex[:8]}.webp"

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=82, method=6)
    webp_bytes = buf.getvalue()

    # 1. Lưu vào static/dishes
    target_path = os.path.join(DISHES_DIR, unique_name)
    with open(target_path, "wb") as f:
        f.write(webp_bytes)

    # 2. Lưu vào persistent storage (/app/data/uploads)
    try:
        with open(os.path.join(PERSISTENT_UPLOADS, unique_name), "wb") as f:
            f.write(webp_bytes)
    except Exception:
        pass

    size_kb = round(len(webp_bytes) / 1024, 1)
    return {
        "status": "SUCCESS",
        "image_url": f"/static/dishes/{unique_name}",
        "file_name": unique_name,
        "width": img.size[0],
        "height": img.size[1],
        "size_kb": size_kb,
        "message": f"Tối ưu ảnh thành công: {size_kb} KB ({img.size[0]}x{img.size[1]})"
    }

@router.post("/item")
@router.post("/items")
def create_menu_item(item: MenuItemCreate):
    """
    Tạo món ăn mới.
    Nếu translations_json chưa có hoặc rỗng -> tự động dịch sang 4 ngôn ngữ và lưu.
    """
    translations_str = item.translations_json
    if item.translations and not translations_str:
        translations_str = json.dumps(item.translations, ensure_ascii=False)
    if not translations_str or translations_str.strip() in ("", "{}", "null"):
        # Tự động dịch sang 4 thứ tiếng
        trans = translate_dish(item.name.strip(), (item.description or "").strip())
        translations_str = json.dumps(trans, ensure_ascii=False)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO menu_items (category_id, name, description, price, image_url, station, options_json, translations_json, is_available, calories, out_of_ingredients, main_menu_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item.category_id,
        item.name.strip(),
        (item.description or "").strip(),
        item.price,
        item.image_url or "",
        item.station or "HOT_KITCHEN",
        item.options_json or "[]",
        translations_str,
        item.is_available if item.is_available is not None else 1,
        item.calories or 0,
        item.out_of_ingredients or 0,
        item.main_menu_type or "RESTAURANT,LUNCH,CAFE"
    ))
    new_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM menu_items WHERE id = ?", (new_id,))
    created = dict(cursor.fetchone())
    conn.close()

    try:
        created["translations"] = json.loads(created.get("translations_json") or "{}")
    except Exception:
        created["translations"] = {}

    return {"status": "SUCCESS", "message": "Đã thêm món ăn mới thành công", "item": created}

@router.put("/item/{item_id}")
@router.put("/items/{item_id}")
def update_menu_item(item_id: int, item: MenuItemUpdate):
    """Cập nhật thông tin món ăn và bản dịch đa ngôn ngữ."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy món ăn")

    existing_dict = dict(existing)
    category_id = item.category_id if item.category_id is not None else existing_dict["category_id"]
    name = item.name.strip() if item.name is not None else existing_dict["name"]
    description = item.description if item.description is not None else existing_dict["description"]
    price = item.price if item.price is not None else existing_dict["price"]
    image_url = item.image_url if item.image_url is not None else existing_dict["image_url"]
    station = item.station if item.station is not None else existing_dict["station"]
    options_json = item.options_json if item.options_json is not None else existing_dict["options_json"]
    is_available = item.is_available if item.is_available is not None else existing_dict["is_available"]
    calories = item.calories if item.calories is not None else existing_dict.get("calories", 0)
    out_of_ingredients = item.out_of_ingredients if item.out_of_ingredients is not None else existing_dict.get("out_of_ingredients", 0)
    main_menu_type = item.main_menu_type if item.main_menu_type is not None else existing_dict.get("main_menu_type", "RESTAURANT,LUNCH,CAFE")

    translations_str = item.translations_json
    if item.translations is not None and not translations_str:
        translations_str = json.dumps(item.translations, ensure_ascii=False)

    if translations_str is None:
        translations_str = existing_dict.get("translations_json", "{}")
    elif translations_str.strip() in ("", "{}", "null"):
        # Người dùng yêu cầu dịch tự động lại
        trans = translate_dish(name, description or "")
        translations_str = json.dumps(trans, ensure_ascii=False)

    cursor.execute("""
        UPDATE menu_items
        SET category_id = ?, name = ?, description = ?, price = ?, image_url = ?, station = ?, options_json = ?, translations_json = ?, is_available = ?, calories = ?, out_of_ingredients = ?, main_menu_type = ?
        WHERE id = ?
    """, (category_id, name, description, price, image_url, station, options_json, translations_str, is_available, calories, out_of_ingredients, main_menu_type, item_id))
    conn.commit()

    cursor.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,))
    updated = dict(cursor.fetchone())
    conn.close()

    try:
        updated["translations"] = json.loads(updated.get("translations_json") or "{}")
    except Exception:
        updated["translations"] = {}

    return {"status": "SUCCESS", "message": "Đã cập nhật món ăn thành công", "item": updated}

@router.delete("/item/{item_id}")
@router.delete("/items/{item_id}")
def delete_menu_item(item_id: int):
    """Xóa món ăn khỏi thực đơn."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy món ăn")

    # Kiểm tra xem có order nào đang QUEUED hoặc COOKING chứa món này không
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM order_items 
        WHERE item_id = ? AND status IN ('QUEUED', 'COOKING')
    """, (item_id,))
    active_count = cursor.fetchone()["count"]
    if active_count > 0:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Không thể xóa món này vì đang có {active_count} đơn hàng chờ chế biến trong bếp!")

    cursor.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "Đã xóa món ăn thành công"}

@router.post("/item/{item_id}/toggle-stock")
def toggle_item_stock(item_id: int):
    """Bật/tắt trạng thái còn hàng / hết hàng."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT is_available, out_of_ingredients FROM menu_items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Món ăn không tồn tại")
    
    new_status = 0 if item["is_available"] == 1 else 1
    # Nếu bật lại còn hàng thì reset luôn out_of_ingredients
    new_out = 0 if new_status == 1 else item["out_of_ingredients"]
    cursor.execute("UPDATE menu_items SET is_available = ?, out_of_ingredients = ? WHERE id = ?", (new_status, new_out, item_id))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "item_id": item_id, "is_available": new_status, "out_of_ingredients": new_out}

@router.post("/item/{item_id}/toggle-out-of-ingredients")
def toggle_out_of_ingredients(item_id: int):
    """
    Bếp bật/tắt báo hết nguyên vật liệu (NVL) cho món ăn.
    Khi out_of_ingredients = 1: món tạm hết NVL và tự động chuyển is_available = 0.
    Khi out_of_ingredients = 0: món đã có lại NVL và tự động chuyển is_available = 1.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, is_available, out_of_ingredients FROM menu_items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Món ăn không tồn tại")
    
    current_out = item["out_of_ingredients"] or 0
    new_out = 0 if current_out == 1 else 1
    new_available = 0 if new_out == 1 else 1
    
    cursor.execute("""
        UPDATE menu_items 
        SET out_of_ingredients = ?, is_available = ? 
        WHERE id = ?
    """, (new_out, new_available, item_id))
    conn.commit()
    conn.close()
    
    return {
        "status": "SUCCESS",
        "item_id": item_id,
        "dish_name": item["name"],
        "out_of_ingredients": new_out,
        "is_available": new_available,
        "message": f"Món '{item['name']}' đã được đánh dấu: {'TẠM HẾT NGUYÊN LIỆU' if new_out == 1 else 'ĐÃ CÓ LẠI NGUYÊN LIỆU'}"
    }

def _parse_price(raw_price: Any) -> int:
    """Chuyển đổi chuỗi giá (VD: '85000', '85.000', '85,000', '85k', '85K') sang số nguyên VNĐ."""
    if isinstance(raw_price, (int, float)):
        val = int(raw_price)
        return val * 1000 if 0 < val < 1000 else val
    s = str(raw_price or "").strip().lower()
    if not s:
        return 0
    is_k = "k" in s
    s = s.replace("vnđ", "").replace("vnd", "").replace("đ", "").replace("k", "").replace(".", "").replace(",", "").replace(" ", "").strip()
    try:
        val = int(float(s))
        if is_k or (0 < val < 1000):
            val *= 1000
        return val
    except Exception:
        return 0

def _normalize_station(raw_station: str, default_station: str = "HOT_KITCHEN") -> str:
    s = (raw_station or "").strip().upper()
    if not s:
        return default_station
    if s in ("HOT_KITCHEN", "COLD_KITCHEN", "BAR"):
        return s
    s_low = s.lower()
    if "bar" in s_low or "uống" in s_low or "nước" in s_low or "bia" in s_low or "rượu" in s_low or "cafe" in s_low:
        return "BAR"
    if "lạnh" in s_low or "cold" in s_low or "gỏi" in s_low or "salad" in s_low or "tráng miệng" in s_low:
        return "COLD_KITCHEN"
    return "HOT_KITCHEN"

@router.post("/bulk-import")
def bulk_import_menu(req: BulkMenuImportRequest):
    """
    Nhập thực đơn hàng loạt từ danh sách văn bản (Excel/Text copy-paste) hoặc JSON.
    Định dạng mỗi dòng: Tên món | Giá | Danh mục (tùy chọn) | Trạm (tùy chọn) | Mô tả (tùy chọn)
    Tự động tạo danh mục mới nếu chưa có và tự động dịch sang 4 ngôn ngữ (EN, ZH, KO, RU).
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM categories WHERE is_active = 1 ORDER BY display_order")
    existing_cats = [dict(c) for c in cursor.fetchall()]
    cat_map = {c["name"].strip().lower(): c["id"] for c in existing_cats}
    max_order = max([c.get("display_order") or 0 for c in existing_cats], default=0)

    def get_or_create_category(cat_name: str) -> int:
        nonlocal max_order
        clean_name = (cat_name or "").strip()
        if not clean_name:
            return req.default_category_id or (existing_cats[0]["id"] if existing_cats else 1)
        key = clean_name.lower()
        if key in cat_map:
            return cat_map[key]
        # Tạo danh mục mới kèm dịch đa ngôn ngữ
        max_order += 1
        cat_trans = translate_category_name(clean_name)
        cursor.execute(
            "INSERT INTO categories (name, icon, display_order, is_active, translations_json) VALUES (?, ?, ?, 1, ?)",
            (clean_name, "🍽️", max_order, json.dumps(cat_trans, ensure_ascii=False))
        )
        new_cat_id = cursor.lastrowid
        cat_map[key] = new_cat_id
        return new_cat_id

    rows_to_process = []
    if req.items:
        rows_to_process.extend(req.items)

    if req.raw_text and req.raw_text.strip():
        for line in req.raw_text.strip().splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            # Hỗ trợ phân tách bằng dấu '|' hoặc phím Tab (copy từ Excel) hoặc dấu ';'
            if "|" in line_str:
                parts = [p.strip() for p in line_str.split("|")]
            elif "\t" in line_str:
                parts = [p.strip() for p in line_str.split("\t")]
            elif ";" in line_str:
                parts = [p.strip() for p in line_str.split(";")]
            else:
                # Nếu chỉ có "Tên món - Giá"
                if " - " in line_str:
                    parts = [p.strip() for p in line_str.rsplit(" - ", 1)]
                else:
                    continue

            if len(parts) < 2:
                continue
            # Bỏ qua dòng tiêu đề nếu có
            if parts[0].lower() in ("tên món", "ten mon", "name", "món ăn"):
                continue

            rows_to_process.append({
                "name": parts[0],
                "price": parts[1],
                "category_name": parts[2] if len(parts) > 2 else "",
                "station": parts[3] if len(parts) > 3 else "",
                "description": parts[4] if len(parts) > 4 else "",
                "image_url": parts[5] if len(parts) > 5 else "",
            })

    if not rows_to_process:
        conn.close()
        raise HTTPException(status_code=400, detail="Không tìm thấy dòng dữ liệu hợp lệ nào để nhập. Vui lòng kiểm tra lại định dạng!")

    imported_count = 0
    for row in rows_to_process:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        price = _parse_price(row.get("price", 0))
        cat_id = row.get("category_id") or get_or_create_category(row.get("category_name", ""))
        station = _normalize_station(row.get("station", ""), req.default_station or "HOT_KITCHEN")
        desc = (row.get("description") or "").strip()
        img = (row.get("image_url") or "").strip()

        trans = translate_dish(name, desc)
        trans_json = json.dumps(trans, ensure_ascii=False)

        cursor.execute("""
            INSERT INTO menu_items (category_id, name, description, price, image_url, station, options_json, translations_json, is_available)
            VALUES (?, ?, ?, ?, ?, ?, '[]', ?, 1)
        """, (cat_id, name, desc, price, img, station, trans_json))
        imported_count += 1

    conn.commit()
    conn.close()
    return {
        "status": "SUCCESS",
        "imported_count": imported_count,
        "message": f"Đã nhập thành công {imported_count} món ăn kèm bản dịch 5 ngôn ngữ!"
    }

class MenuSettingsUpdate(BaseModel):
    morning_start_hour: int = 6
    morning_end_hour: int = 11
    routing_mode: str = "TIME_AND_BRANCH" # TIME_AND_BRANCH, BRANCH_ONLY, TIME_ONLY

def ensure_system_settings_table(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    defaults = {
        "morning_start_hour": "6",
        "morning_end_hour": "11",
        "routing_mode": "TIME_AND_BRANCH"
    }
    for k, v in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()

@router.get("/settings")
def get_menu_settings():
    """Lấy cấu hình khung giờ tự động mở Menu Cafe/Ăn sáng (6h-11h) và Menu Nhà Hàng (11h-tối)."""
    from datetime import datetime
    conn = get_db()
    ensure_system_settings_table(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_settings")
    rows = {r["key"]: r["value"] for r in cursor.fetchall()}
    conn.close()

    start_h = int(rows.get("morning_start_hour", 6))
    end_h = int(rows.get("morning_end_hour", 11))
    mode = rows.get("routing_mode", "TIME_AND_BRANCH")
    now_h = datetime.now().hour
    is_morning = (start_h <= now_h < end_h)

    return {
        "morning_start_hour": start_h,
        "morning_end_hour": end_h,
        "routing_mode": mode,
        "current_hour": now_h,
        "is_morning_window": is_morning,
        "default_category_by_time": 2 if is_morning else 1
    }

@router.put("/settings")
def update_menu_settings(req: MenuSettingsUpdate):
    """Cập nhật cấu hình khung giờ tự động chuyển đổi Menu Cafe/Ăn sáng và Menu Nhà Hàng."""
    conn = get_db()
    ensure_system_settings_table(conn)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('morning_start_hour', ?)", (str(req.morning_start_hour),))
    cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('morning_end_hour', ?)", (str(req.morning_end_hour),))
    cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('routing_mode', ?)", (req.routing_mode,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "Đã lưu cấu hình khung giờ và điều hướng Menu thành công!"}

@router.post("/sync-folder-images")
def api_sync_folder_images():
    """Quét thư mục app/static/dishes và tự động đồng bộ ảnh món ăn theo tên."""
    conn = get_db()
    res = sync_all_dish_images(conn)
    conn.close()
    return res

@router.get("/folder-images-guide")
def api_get_folder_images_guide():
    """Lấy danh sách hướng dẫn đặt tên file ảnh (.jpg) cho từng món."""
    conn = get_db()
    guide = get_dish_naming_guide(conn)
    conn.close()
    return {
        "folder_path": r"D:\AI\Restaurant\app\static\dishes",
        "total_dishes": len(guide),
        "dishes": guide
    }
