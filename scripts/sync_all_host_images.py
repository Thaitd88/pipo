# -*- coding: utf-8 -*-
"""
Script đồng bộ toàn bộ ảnh món ăn từ pipogarden.com về máy local,
tự động đổi tên các ảnh screenshot thành tên món chuẩn không dấu,
và cập nhật MENU_ITEMS trong app/menu_syncer.py cũng như CSDL SQLite local.
"""
import urllib.request
import json
import os
import re
import shutil
import sqlite3
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def slugify(text: str) -> str:
    if not text:
        return "dish"
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

# 1. Tải danh sách menu từ Host
url = "https://pipogarden.com/api/menu"
print(f"[*] Đang tải dữ liệu thực đơn từ {url}...")
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))

dishes_dir = os.path.join("app", "static", "dishes")
os.makedirs(dishes_dir, exist_ok=True)

# Thư mục sao lưu bền vững
backup_dir = os.path.join("data", "uploads")
os.makedirs(backup_dir, exist_ok=True)

downloaded_map = {} # dish_id -> clean_image_url

print("\n[*] Bắt đầu tải và chuẩn hóa tên ảnh...")
for cat in data:
    for it in cat.get('items', []):
        img_url = (it.get('image_url') or '').strip()
        if not img_url or img_url.endswith("logo.png"):
            continue

        clean_path = img_url.split("?")[0]
        raw_filename = os.path.basename(clean_path)
        full_host_url = f"https://pipogarden.com{clean_path}"

        # Xác định tên file chuẩn hóa
        ext = os.path.splitext(raw_filename)[1].lower() or ".webp"
        dish_slug = slugify(it['name'])
        
        # Nếu file gốc là screenshot hoặc có hash uuid lộn xộn -> đặt tên đẹp theo tên món
        if "screenshot" in raw_filename.lower() or "zalo" in raw_filename.lower():
            clean_filename = f"{dish_slug}{ext}"
        else:
            clean_filename = raw_filename

        clean_file_path = os.path.join(dishes_dir, clean_filename)
        raw_file_path = os.path.join(dishes_dir, raw_filename)

        # Tải file từ host
        try:
            temp_path = clean_file_path + ".tmp"
            urllib.request.urlretrieve(full_host_url, temp_path)
            # Di chuyển vào vị trí chính
            if os.path.exists(temp_path):
                shutil.move(temp_path, clean_file_path)
                # Sao lưu vào backup_dir
                shutil.copy2(clean_file_path, os.path.join(backup_dir, clean_filename))
                # Tạo file copy raw_filename để tương thích tuyệt đối nếu có ai đang dùng link cũ
                if raw_filename != clean_filename:
                    shutil.copy2(clean_file_path, raw_file_path)
                    shutil.copy2(clean_file_path, os.path.join(backup_dir, raw_filename))

                size_kb = round(os.path.getsize(clean_file_path) / 1024, 1)
                final_img_url = f"/static/dishes/{clean_filename}"
                downloaded_map[it['id']] = final_img_url
                print(f"  [+] Món #{it['id']} ({it['name']}): Đã lưu '{clean_filename}' ({size_kb} KB)")
        except Exception as e:
            print(f"  [-] Lỗi tải #{it['id']} ({it['name']}): {e}")

print(f"\n[+] Tổng cộng đã đồng bộ thành công {len(downloaded_map)} ảnh món ăn!")

# 2. Cập nhật MENU_ITEMS trong app/menu_syncer.py
print("\n[*] Cập nhật image_url vào app/menu_syncer.py...")
with open("app/menu_syncer.py", "r", encoding="utf-8") as f:
    syncer_content = f.read()

# Cập nhật từng món trong syncer
update_count = 0
for did, new_url in downloaded_map.items():
    # Tìm khối món có ID tương ứng
    pattern = rf'("id":\s*{did},[\s\S]*?"image_url":\s*)"[^"]*"'
    if re.search(pattern, syncer_content):
        syncer_content = re.sub(pattern, rf'\1"{new_url}"', syncer_content, count=1)
        update_count += 1

with open("app/menu_syncer.py", "w", encoding="utf-8") as f:
    f.write(syncer_content)
print(f"[+] Đã cập nhật {update_count} ảnh món vào app/menu_syncer.py")

# 3. Cập nhật SQLite local
for db_file in ["data/pipo_garden.db", "thungan/data/pipo_garden.db"]:
    if os.path.exists(db_file):
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        for did, new_url in downloaded_map.items():
            cur.execute("UPDATE menu_items SET image_url = ? WHERE id = ?", (new_url, did))
        conn.commit()
        conn.close()
        print(f"[+] Đã cập nhật CSDL local: {db_file}")

print("\n[*] ĐỒNG BỘ ẢNH HOÀN TẤT THÀNH CÔNG 100%!")
