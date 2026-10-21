"""
PiPo Garden - Cau Hinh Tu Dong Khoi Dong Cung Windows
Dang ky he thong tu khoi dong moi khi bat may tinh thu ngan.
Ho tro 3 lop bao ve:
1. Windows Registry (HKCU Run Key)
2. Windows Startup Shortcut (.lnk)
3. Windows Startup Batch Script (.bat)
"""

import os
import sys
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def setup_autostart():
    print("==================================================================")
    print("🌿 PIPO GARDEN - CẤU HÌNH TỰ ĐỘNG KHỞI ĐỘNG CÙNG WINDOWS")
    print("==================================================================")

    # 1. Xác định đường dẫn
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Nếu script nằm trong thư mục scripts/, thư mục gốc là thư mục cha
    if os.path.basename(current_dir).lower() == "scripts":
        base_dir = os.path.dirname(current_dir)
    else:
        base_dir = current_dir

    python_exe = sys.executable
    run_server_py = os.path.join(base_dir, "run_server.py")

    if not os.path.exists(run_server_py):
        print(f"[LỖI] Không tìm thấy file run_server.py tại: {run_server_py}")
        return False

    print(f"[*] Thư mục hệ thống: {base_dir}")
    print(f"[*] Trình thông dịch Python: {python_exe}")
    print(f"[*] File khởi chạy: {run_server_py}")
    print("------------------------------------------------------------------")

    success_count = 0

    # 2. Đăng ký vào Windows Registry (HKCU\Software\Microsoft\Windows\CurrentVersion\Run)
    print("[1/3] Đang đăng ký vào Windows Registry (Khởi động tức thì)...")
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        reg_cmd = f'"{python_exe}" "{run_server_py}"'
        winreg.SetValueEx(key, "PiPoGardenPOS", 0, winreg.REG_SZ, reg_cmd)
        winreg.CloseKey(key)
        print("  [+] ✅ Đăng ký Windows Registry thành công!")
        success_count += 1
    except Exception as e:
        print(f"  [-] Lỗi Registry: {e}")

    # 3. Tạo file khởi chạy trong thư mục Startup
    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
    )

    if os.path.exists(startup_dir):
        # 3a. Tạo file batch PiPo_Garden_POS.bat (chờ 5s cho Wi-Fi kết nối trước khi chạy)
        print("[2/3] Đang tạo script dự phòng trong thư mục Startup...")
        try:
            bat_path = os.path.join(startup_dir, "PiPo_Garden_POS.bat")
            bat_content = f"""@echo off
:: PiPo Garden - Auto Start on Windows Login
title PiPo Garden POS Server Auto-Start
timeout /t 5 /nobreak > nul
cd /d "{base_dir}"
start "PiPo Garden POS" "{python_exe}" run_server.py
"""
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)
            print(f"  [+] ✅ Đã tạo file Startup: {bat_path}")
            success_count += 1
        except Exception as e:
            print(f"  [-] Lỗi tạo file batch Startup: {e}")

        # 3b. Tạo shortcut .lnk chuẩn Windows qua VBScript
        print("[3/3] Đang tạo Windows Shortcut (.lnk) trong thư mục Startup...")
        try:
            lnk_path = os.path.join(startup_dir, "PiPo_POS_Server.lnk")
            vbs_temp = os.path.join(base_dir, "_temp_shortcut.vbs")
            vbs_code = f'''
Set oWS = WScript.CreateObject("WScript.Shell")
Set oLink = oWS.CreateShortcut("{lnk_path}")
oLink.TargetPath = "{python_exe}"
oLink.Arguments = """{run_server_py}"""
oLink.WorkingDirectory = "{base_dir}"
oLink.Description = "PiPo Garden Local POS Server"
oLink.Save
'''
            with open(vbs_temp, "w", encoding="utf-8") as vf:
                vf.write(vbs_code)

            subprocess.run(["cscript", "//nologo", vbs_temp], check=True)
            if os.path.exists(vbs_temp):
                os.remove(vbs_temp)

            if os.path.exists(lnk_path):
                print(f"  [+] ✅ Đã tạo Windows Shortcut thành công: {lnk_path}")
                success_count += 1
            else:
                print("  [-] Chưa tạo được file .lnk")
        except Exception as e:
            print(f"  [-] Lỗi tạo Shortcut .lnk: {e}")
            if os.path.exists(vbs_temp):
                try:
                    os.remove(vbs_temp)
                except Exception:
                    pass

    print("==================================================================")
    if success_count > 0:
        print("🎉 HOÀN TẤT THÀNH CÔNG! ĐÃ ĐĂNG KÝ TỰ ĐỘNG KHỞI ĐỘNG.")
        print("   Từ bây giờ, mỗi khi máy tính thu ngân bật lên hoặc khởi động lại:")
        print("   1. Windows sẽ tự động kết nối Wi-Fi quán.")
        print("   2. Tự động đồng bộ Menu & Cài đặt mới nhất từ Host pipogarden.com.")
        print("   3. Tự động bật Print Agent để in phiếu bếp & in bill.")
        print("   4. Tự động mở màn hình POS bán hàng trên trình duyệt.")
        print("   -> Bạn không cần phải mở thủ công bất kỳ file nào nữa!")
    else:
        print("[-] Cảnh báo: Chưa thể đăng ký tự động khởi động. Vui lòng kiểm tra quyền người dùng.")
    print("==================================================================")
    return success_count > 0

if __name__ == "__main__":
    setup_autostart()
    print("\nBấm Enter để đóng...")
    try:
        input()
    except Exception:
        pass
