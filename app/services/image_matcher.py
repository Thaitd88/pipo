import os
import re
import urllib.parse
import unicodedata
from typing import Optional, Dict, Any, List

DISH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "dishes")
ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')

def normalize_text(text: str) -> str:
    """
    Chuẩn hóa tên món ăn hoặc tên file ảnh để so khớp chính xác:
    - Bỏ dấu tiếng Việt (đ/Đ -> d, các nguyên âm có dấu)
    - Thay thế các ký tự gạch nối, gạch dưới, dấu cộng bằng khoảng trắng
    - Bỏ số thứ tự ở đầu (ví dụ: '1.', '01_', '1 - ')
    - Chuyển chữ thường và loại bỏ khoảng trắng thừa
    """
    if not text:
        return ""
    # Chuẩn hóa Unicode
    text = unicodedata.normalize('NFKD', str(text))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = text.replace('đ', 'd').replace('Đ', 'd')
    # Thay thế các ký tự phân cách
    text = text.replace('_', ' ').replace('-', ' ').replace('+', ' ').replace('&', ' ')
    # Xóa số thứ tự ở đầu nếu có (VD: '1. ', '02 - ')
    text = re.sub(r'^\s*\d+[\s._\-–:]*', '', text)
    # Xóa các ký tự đặc biệt còn lại
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return ' '.join(text.split())

def get_folder_files() -> List[str]:
    """Lấy danh sách các file ảnh hợp lệ có trong thư mục dishes."""
    if not os.path.exists(DISH_DIR):
        return []
    try:
        return [
            f for f in os.listdir(DISH_DIR)
            if any(f.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)
        ]
    except Exception:
        return []

def find_matching_image(dish_name: str, current_image_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Tìm file ảnh phù hợp nhất trong thư mục dishes cho món ăn:
    1. Trùng khớp hoàn toàn tên đã chuẩn hóa (VD: 'Gỏi khoai môn hải sản.jpg' hoặc 'goi_khoai_mon_hai_san.jpg')
    2. File ảnh hiện tại trong DB nếu vẫn tồn tại trên ổ đĩa
    3. Trùng khớp tiền tố / hậu tố (VD: 'Ga hap mam nhi.jpg' khớp với 'Gà hấp mắm nhĩ + Lòng mề xào')
    4. Trùng khớp cụm từ chính
    Trả về thông tin file kèm tham số chống cache trình duyệt ?v={mtime}.
    """
    files = get_folder_files()
    if not files:
        return None

    dish_norm = normalize_text(dish_name)
    if not dish_norm:
        return None

    file_norms = {}
    for f in files:
        stem, ext = os.path.splitext(f)
        file_norms[f] = normalize_text(stem)

    best_file = None

    # Ưu tiên 1: Trùng khớp hoàn toàn tên chuẩn hóa
    for f, fn in file_norms.items():
        if fn == dish_norm:
            best_file = f
            break

    # Ưu tiên 2: Trùng khớp file hiện tại nếu file đó tồn tại
    if not best_file and current_image_url:
        try:
            curr_clean = current_image_url.split('?')[0]
            curr_base = urllib.parse.unquote(os.path.basename(curr_clean))
            if curr_base in file_norms:
                best_file = curr_base
        except Exception:
            pass

    # Ưu tiên 3: Tiền tố / hậu tố (ví dụ món có dấu + lòng mề xào)
    if not best_file:
        for f, fn in file_norms.items():
            if len(fn) >= 4 and (dish_norm.startswith(fn) or fn.startswith(dish_norm)):
                best_file = f
                break

    # Ưu tiên 4: Chứa toàn bộ cụm từ
    if not best_file:
        for f, fn in file_norms.items():
            if len(fn) >= 5 and (fn in dish_norm or dish_norm in fn):
                best_file = f
                break

    if best_file:
        full_path = os.path.join(DISH_DIR, best_file)
        try:
            mtime = int(os.path.getmtime(full_path))
        except Exception:
            mtime = 0
        encoded_name = urllib.parse.quote(best_file)
        return {
            "filename": best_file,
            "url": f"/static/dishes/{encoded_name}?v={mtime}",
            "base_url": f"/static/dishes/{encoded_name}",
            "mtime": mtime,
            "path": full_path
        }

    return None

def sync_all_dish_images(conn) -> Dict[str, Any]:
    """
    Quét toàn bộ thư mục ảnh và đồng bộ lại đường dẫn image_url cho từng món trong CSDL.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, image_url FROM menu_items")
    dishes = cursor.fetchall()

    files = get_folder_files()
    matched_files = set()
    matched_list = []
    unmatched_dishes = []

    for d in dishes:
        d_id = d["id"] if isinstance(d, dict) else d[0]
        d_name = d["name"] if isinstance(d, dict) else d[1]
        d_curr_img = d["image_url"] if isinstance(d, dict) else d[2]

        match = find_matching_image(d_name, d_curr_img)
        if match:
            matched_files.add(match["filename"])
            new_url = match["base_url"]
            cursor.execute("UPDATE menu_items SET image_url = ? WHERE id = ?", (new_url, d_id))
            matched_list.append({
                "id": d_id,
                "name": d_name,
                "filename": match["filename"],
                "url": match["url"]
            })
        else:
            unmatched_dishes.append({
                "id": d_id,
                "name": d_name
            })

    conn.commit()

    unmatched_files = [f for f in files if f not in matched_files]

    return {
        "status": "SUCCESS",
        "total_dishes": len(dishes),
        "matched_count": len(matched_list),
        "unmatched_count": len(unmatched_dishes),
        "folder_path": DISH_DIR,
        "total_files_in_folder": len(files),
        "matched_dishes": matched_list,
        "unmatched_dishes": unmatched_dishes,
        "unmatched_files": unmatched_files
    }

def get_dish_naming_guide(conn) -> List[Dict[str, Any]]:
    """
    Tạo bảng tra cứu tên file ảnh mẫu để người dùng dễ dàng lưu/thay thế file JPG.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.id, m.name, m.price, m.image_url, c.name as category_name
        FROM menu_items m
        JOIN categories c ON m.category_id = c.id
        ORDER BY c.display_order, m.id
    """)
    dishes = cursor.fetchall()

    guide = []
    for d in dishes:
        d_id = d["id"] if isinstance(d, dict) else d[0]
        d_name = d["name"] if isinstance(d, dict) else d[1]
        d_price = d["price"] if isinstance(d, dict) else d[2]
        d_img = d["image_url"] if isinstance(d, dict) else d[3]
        d_cat = d["category_name"] if isinstance(d, dict) else d[4]

        match = find_matching_image(d_name, d_img)
        slug_name = normalize_text(d_name).replace(' ', '_') + ".jpg"
        unicode_name = f"{d_name}.jpg"

        guide.append({
            "id": d_id,
            "name": d_name,
            "category": d_cat,
            "price": d_price,
            "recommended_filename_1": unicode_name,
            "recommended_filename_2": slug_name,
            "current_matched_file": match["filename"] if match else None,
            "current_image_url": match["url"] if match else (d_img or "/static/logo.png"),
            "has_image": bool(match)
        })

    return guide
