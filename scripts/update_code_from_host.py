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

def update_code(timeout: int = 6, interactive: bool = False) -> bool:
    print("==================================================================")
    print("🌿 PIPO GARDEN - CẬP NHẬT PHẦN MỀM TỰ ĐỘNG TỪ CLOUD HOST")
    print("==================================================================")
    print(f"[*] Thư mục hệ thống: {BASE_DIR}")

    urls = [
        ("Cloud Host (pipogarden.com)", CLOUD_URL),
        ("Máy Dev Lập Trình LAN (192.168.31.67)", DEV_LAN_URL)
    ]

    zip_bytes = None
    success_source = None

    for label, url in urls:
        print(f"[*] Đang kiểm tra cập nhật từ: {label}...")
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "PiPo-Updater/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as res:
                if res.status == 200:
                    zip_bytes = res.read()
                    success_source = label
                    print(f"  [+] ✅ Đã nhận gói cập nhật ({len(zip_bytes) / 1024:.1f} KB) từ {label}!")
                    break
        except Exception as e:
            print(f"  [-] Chưa thể kết nối tới {label} ({e}).")

    if not zip_bytes:
        print("  [-] Không thể tải gói cập nhật từ máy chủ (có thể mất Internet hoặc máy chủ bận).")
        print("  [+] Hệ thống sẽ tiếp tục sử dụng phiên bản phần mềm hiện tại.")
        if interactive:
            print("\nBấm Enter để đóng...")
            try:
                input()
            except Exception:
                pass
        return False

    # Kiểm tra tính toàn vẹn của tệp zip trước khi giải nén
    try:
        zf_test = zipfile.ZipFile(io.BytesIO(zip_bytes))
        if zf_test.testzip() is not None:
            print("  [-] Gói cập nhật bị lỗi cấu trúc nén. Bỏ qua cập nhật.")
            return False
    except Exception as e:
        print(f"  [-] Lỗi kiểm tra gói nén: {e}")
        return False

    # Sao lưu an toàn trước khi ghi đè
    backup_dir = os.path.join(BASE_DIR, "_backup_before_update")
    try:
        os.makedirs(backup_dir, exist_ok=True)
        for d in ["app", "print_agent", "scripts"]:
            src_p = os.path.join(BASE_DIR, d)
            dst_p = os.path.join(backup_dir, d)
            if os.path.exists(src_p):
                if os.path.exists(dst_p):
                    shutil.rmtree(dst_p)
                shutil.copytree(src_p, dst_p)
    except Exception as e:
        print(f"  [-] Lưu ý khi sao lưu: {e}")

    # Áp dụng bản cập nhật vào BASE_DIR
    extracted_count = 0
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for member in zf.infolist():
                name = member.filename
                # BẢO VỆ TUYỆT ĐỐI CƠ SỞ DỮ LIỆU ĐƠN HÀNG VÀ DOANH THU
                if name.lower().endswith(".db") or "pipo_garden.db" in name.lower() or name.startswith("data/"):
                    continue
                zf.extract(member, BASE_DIR)
                extracted_count += 1
        print(f"  [+] ✅ Đã cập nhật thành công {extracted_count} tệp tin mã nguồn mới!")
    except Exception as e:
        print(f"  [-] Quá trình giải nén cập nhật thất bại: {e}")
        return False

    print("==================================================================")
    print("🎉 HOÀN TẤT CẬP NHẬT CODE MỚI NHẤT CHO MÁY THU NGÂN!")
    print("==================================================================\n")

    if interactive:
        print("Bấm Enter để đóng...")
        try:
            input()
        except Exception:
            pass
    return True

if __name__ == "__main__":
    update_code(timeout=10, interactive=True)
