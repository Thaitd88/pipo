"""
PiPo Garden - Tu Dong Cap Nhat Code Moi Tu Host (Cloud / LAN)
Dung cho may thu ngan: Tai goi code cap nhat moi nhat tu Host va ghi de vao may thu ngan.
Khong bao gio ghi de hay anh huong toi CSDL don hang data/pipo_garden.db!
"""

import os
import sys
import io
import zipfile
import urllib.request
import urllib.error
import shutil

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR).lower() == "scripts" else CURRENT_DIR

CLOUD_URL = "https://pipogarden.com/api/sync/code-bundle"
DEV_LAN_URL = "http://192.168.31.67:8000/api/sync/code-bundle"

def download_code_bundle():
    print("==================================================================")
    print("🌿 PIPO GARDEN - CẬP NHẬT PHẦN MỀM TỪ MÁY CHỦ (HOST CLOUD / LAN)")
    print("==================================================================")
    print(f"[*] Thư mục cài đặt hiện tại: {BASE_DIR}")

    urls = [
        ("Cloud Host (pipogarden.com)", CLOUD_URL),
        ("Máy Dev Lập Trình (192.168.31.67)", DEV_LAN_URL)
    ]

    zip_bytes = None
    success_source = None

    for label, url in urls:
        print(f"\n[*] Đang kiểm tra nguồn: {label}...")
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "PiPo-Updater/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as res:
                if res.status == 200:
                    zip_bytes = res.read()
                    success_source = label
                    print(f"  [+] ✅ Đã tải thành công gói cập nhật ({len(zip_bytes) / 1024:.1f} KB) từ {label}!")
                    break
        except Exception as e:
            print(f"  [-] Nguồn {label} chưa sẵn sàng ({e}).")

    if not zip_bytes:
        print("\n[LỖI] Không thể tải gói cập nhật từ cả Cloud và máy Dev.")
        print("Vui lòng đảm bảo máy có kết nối Internet hoặc máy Dev đang bật!")
        return False

    # Sao lưu thư mục hiện tại trước khi cập nhật
    backup_dir = os.path.join(BASE_DIR, "_backup_before_update")
    print(f"\n[*] Đang tạo bản sao lưu an toàn tại: {backup_dir}...")
    try:
        os.makedirs(backup_dir, exist_ok=True)
        for d in ["app", "print_agent", "scripts"]:
            src_p = os.path.join(BASE_DIR, d)
            dst_p = os.path.join(backup_dir, d)
            if os.path.exists(src_p):
                if os.path.exists(dst_p):
                    shutil.rmtree(dst_p)
                shutil.copytree(src_p, dst_p)
        print("  [+] ✅ Đã sao lưu mã nguồn cũ an toàn!")
    except Exception as e:
        print(f"  [-] Lưu ý khi sao lưu: {e}")

    # Giải nén đè lên BASE_DIR
    print("\n[*] Đang áp dụng bản cập nhật mới vào hệ thống...")
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # Danh sách các file trong zip
            namelist = zf.namelist()
            print(f"  [+] Gói cập nhật gồm {len(namelist)} tệp tin.")
            for name in namelist:
                # Bảo vệ tối thượng: Tuyệt đối không ghi đè pipo_garden.db
                if "pipo_garden.db" in name.lower():
                    continue
                zf.extract(name, BASE_DIR)
        print("  [+] ✅ Đã giải nén và cập nhật toàn bộ file mới thành công!")
    except Exception as e:
        print(f"[LỖI] Quá trình giải nén cập nhật thất bại: {e}")
        return False

    print("\n==================================================================")
    print("🎉 CHÚC MỪNG! HỆ THỐNG ĐÃ ĐƯỢC CẬP NHẬT CODE MỚI NHẤT.")
    print("   Toàn bộ tính năng mới, sửa lỗi báo cáo và in ấn đã được áp dụng.")
    print("   Dữ liệu đơn hàng và doanh thu của quán vẫn được bảo toàn nguyên vẹn.")
    print("   Vui lòng khởi động lại hệ thống (chạy file 2_CHAY_HE_THONG.bat) để có hiệu lực!")
    print("==================================================================")
    return True

if __name__ == "__main__":
    download_code_bundle()
    print("\nBấm Enter để đóng...")
    try:
        input()
    except Exception:
        pass
