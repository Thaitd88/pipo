import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://pipogarden.com/api/menu"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))

print(f"Tổng số danh mục: {len(data)}")
all_items = []
for cat in data:
    for it in cat.get('items', []):
        all_items.append((cat['name'], it))

print(f"Tổng số món ăn: {len(all_items)}")
print("\n--- CÁC MÓN CÓ ẢNH ĐƯỢC CẬP NHẬT HOẶC MỚI UP ---")
for cat_name, it in all_items:
    img = it.get('image_url') or ''
    # Tìm các ảnh upload mới (webp, hoặc có chuỗi upload, hoặc đuôi webp / jpg mới)
    if 'webp' in img or not (img.endswith('logo.png') or img == ''):
        print(f"ID: {it['id']:<4} | Món: {it['name']:<25} | Nhóm: {cat_name:<15} | Ảnh: {img}")
