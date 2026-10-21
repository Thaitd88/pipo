import os
import shutil
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = os.path.abspath("d:/AI/Restaurant")
DEST_DIR = os.path.join(ROOT_DIR, "thungan")

def copy_tree_clean(src, dst):
    def ignore_patterns(path, names):
        ignored = []
        for name in names:
            if name in ("__pycache__", ".git", ".idea", ".pytest_cache", ".user_uploaded"):
                ignored.append(name)
            elif name.endswith((".pyc", ".pyo", ".log", ".tmp")):
                ignored.append(name)
        return ignored

    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore_patterns)

def prepare_thungan():
    print(f"[*] Bắt đầu đóng gói thư mục Thu Ngân tại: {DEST_DIR}")

    os.makedirs(DEST_DIR, exist_ok=True)

    # 1. Copy app
    print("  [+] Sao chép thư mục app/...")
    copy_tree_clean(os.path.join(ROOT_DIR, "app"), os.path.join(DEST_DIR, "app"))

    # 2. Copy print_agent
    print("  [+] Sao chép thư mục print_agent/...")
    copy_tree_clean(os.path.join(ROOT_DIR, "print_agent"), os.path.join(DEST_DIR, "print_agent"))

    # 3. Copy scripts
    print("  [+] Sao chép thư mục scripts/...")
    copy_tree_clean(os.path.join(ROOT_DIR, "scripts"), os.path.join(DEST_DIR, "scripts"))

    # 4. Copy data (chỉ lấy pipo_garden.db sạch)
    print("  [+] Sao chép CSDL data/pipo_garden.db...")
    os.makedirs(os.path.join(DEST_DIR, "data"), exist_ok=True)
    src_db = os.path.join(ROOT_DIR, "data", "pipo_garden.db")
    dst_db = os.path.join(DEST_DIR, "data", "pipo_garden.db")
    if os.path.exists(src_db):
        shutil.copy2(src_db, dst_db)

    # 5. Copy root files
    root_files = [
        "run_server.py",
        "run_agent.py",
        "requirements.txt"
    ]
    for rf in root_files:
        s = os.path.join(ROOT_DIR, rf)
        d = os.path.join(DEST_DIR, rf)
        if os.path.exists(s):
            shutil.copy2(s, d)
            print(f"  [+] Đã copy file: {rf}")

    # 6. Tạo các file BAT và hướng dẫn
    print("  [+] Tạo các tập lệnh vận hành (.bat)...")

    # Đoạn mã tìm Python dùng chung cho tất cả các file .bat
    py_detect_snippet = """set "PY_CMD="
py -3 --version >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD (
    python --version >nul 2>&1 && set "PY_CMD=python"
)
if not defined PY_CMD (
    for /d %%d in ("%LOCALAPPDATA%\\Programs\\Python\\Python3*") do (
        if exist "%%d\\python.exe" set "PY_CMD=%%d\\python.exe"
    )
)
if not defined PY_CMD (
    for /d %%d in ("%ProgramFiles%\\Python3*") do (
        if exist "%%d\\python.exe" set "PY_CMD=%%d\\python.exe"
    )
    for /d %%d in ("C:\\Python3*") do (
        if exist "%%d\\python.exe" set "PY_CMD=%%d\\python.exe"
    )
)"""

    # 1_CAI_DAT_LAN_DAU.bat
    bat_cai_dat = f"""@echo off
chcp 65001 > nul
title PiPo Garden - Cai Dat Ban Dau Cho May Thu Ngan
color 0A
echo ===================================================================
echo     HE THONG QUAN LY NHA HANG PIPO GARDEN - CAI DAT BAN DAU
echo     (May thu ngan Local Server - IP: 192.168.31.253)
echo ===================================================================
echo.

cd /d "%~dp0"

echo [1/4] Kiem tra moi truong Python tren may thu ngan...
{py_detect_snippet}

if not defined PY_CMD (
    echo.
    echo [LOI] May tinh chua cai dat Python hoac chua tick "Add python.exe to PATH"!
    echo Vui long tai va cai dat Python (ban 3.10 tro len) tu https://www.python.org/
    echo LUU Y KHI CAI: Nho tick chon vao o [x] "Add python.exe to PATH" o man hinh dau tien!
    echo.
    pause
    exit /b 1
)

echo [+] Da tim thay Python: %PY_CMD%
%PY_CMD% --version
echo.

echo [2/4] Dang cai dat cac thu vien he thong (FastAPI, Uvicorn, Websockets...)...
%PY_CMD% -m pip install --upgrade pip
%PY_CMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [CANH BAO] Co loi khi cai dat thu vien qua pip. Vui long kiem tra lai ket noi Internet.
    pause
    exit /b 1
)
echo.

echo [3/4] Mo cong Firewall 8000 de dien thoai nhan vien / khach ket noi qua Wi-Fi...
netsh advfirewall firewall delete rule name="PiPo POS Server (Port 8000)" > nul 2>&1
netsh advfirewall firewall add rule name="PiPo POS Server (Port 8000)" dir=in action=allow protocol=TCP localport=8000 > nul 2>&1
if %errorlevel% equ 0 (
    echo [+] Da mo cong 8000 tren Windows Firewall thanh cong!
) else (
    echo [-] Khong the tu dong sua Firewall (Can quyen Administrator).
    echo     Neu can mo, vui long chuot phai vao file nay va chon "Run as administrator".
)
echo.

echo [4/4] Tu dong dang ky khoi dong cung Windows...
%PY_CMD% scripts\\setup_autostart.py

echo.
echo ===================================================================
echo   🎉 CAI DAT HOAN TAT 100%%!
echo   He thong da duoc thiet lap tu dong khoi dong moi khi bat may tinh.
echo   De chay thu ngay bay gio, ban chi can nhap dup: 2_CHAY_HE_THONG.bat
echo ===================================================================
echo.
pause
"""
    with open(os.path.join(DEST_DIR, "1_CAI_DAT_LAN_DAU.bat"), "w", encoding="utf-8") as f:
        f.write(bat_cai_dat)

    # 2_CHAY_HE_THONG.bat
    bat_chay = f"""@echo off
chcp 65001 > nul
title PiPo Garden - Khoi Dong POS Thu Ngan & Server Local
color 0B

cd /d "%~dp0"

{py_detect_snippet}

if not defined PY_CMD (
    echo [LOI] Khong tim thay Python tren may thu ngan!
    echo Vui long chuot phai vao file run_server.py va chon "Open with -> Python".
    pause
    exit /b 1
)

echo ===================================================================
echo     🌿 HE THONG NHA HANG PIPO GARDEN - MAY THU NGAN LOCAL
echo     Dang khoi chay qua: %PY_CMD%
echo ===================================================================
echo.

%PY_CMD% run_server.py
pause
"""
    with open(os.path.join(DEST_DIR, "2_CHAY_HE_THONG.bat"), "w", encoding="utf-8") as f:
        f.write(bat_chay)

    # 3_DONG_BO_MENU_TU_HOST.bat
    bat_dong_bo = f"""@echo off
chcp 65001 > nul
title PiPo Garden - Dong Bo Menu Tu Host (pipogarden.com)
color 0E
echo ===================================================================
echo   🌿 DONG BO DU LIEU MENU, BAN AN & CAI DAT TU HOST PIPOGARDEN.COM
echo ===================================================================
echo.

cd /d "%~dp0"

{py_detect_snippet}

if not defined PY_CMD (
    echo [LOI] Khong tim thay Python tren may!
    pause
    exit /b 1
)

echo [*] Dang ket noi toi Host https://pipogarden.com de dong bo...
%PY_CMD% scripts\\sync_from_host.py

echo.
echo ===================================================================
echo   Hoan tat! Menu va cai dat tren may nay da dong bo 100%% voi Host.
echo ===================================================================
echo.
pause
"""
    with open(os.path.join(DEST_DIR, "3_DONG_BO_MENU_TU_HOST.bat"), "w", encoding="utf-8") as f:
        f.write(bat_dong_bo)

    # 4_TU_DONG_KHOI_DONG_CUNG_MAY.bat
    bat_startup = f"""@echo off
chcp 65001 > nul
title PiPo Garden - Cau Hinh Tu Khoi Dong Cung Windows
color 0D

cd /d "%~dp0"

{py_detect_snippet}

if not defined PY_CMD (
    echo [LOI] Khong tim thay Python tren may!
    echo Ban co the chuot phai vao scripts\\setup_autostart.py va chon Open with Python.
    pause
    exit /b 1
)

%PY_CMD% scripts\\setup_autostart.py
"""
    with open(os.path.join(DEST_DIR, "4_TU_DONG_KHOI_DONG_CUNG_MAY.bat"), "w", encoding="utf-8") as f:
        f.write(bat_startup)

    # 5_CAP_NHAT_CODE_MOI.bat
    bat_update_code = f"""@echo off
chcp 65001 > nul
title PiPo Garden - Cap Nhat Code Phan Mem Tu Host
color 0B

cd /d "%~dp0"

{py_detect_snippet}

if not defined PY_CMD (
    echo [LOI] Khong tim thay Python tren may!
    echo Ban co the chuot phai vao scripts\\update_code_from_host.py va chon Open with Python.
    pause
    exit /b 1
)

%PY_CMD% scripts\\update_code_from_host.py
"""
    with open(os.path.join(DEST_DIR, "5_CAP_NHAT_CODE_MOI.bat"), "w", encoding="utf-8") as f:
        f.write(bat_update_code)

    # HUONG_DAN_CAI_DAT_VA_VAN_HANH.txt
    huong_dan = """===============================================================================
🌿 HƯỚNG DẪN CÀI ĐẶT VÀ VẬN HÀNH MÁY THU NGÂN LOCAL - PIPO GARDEN
===============================================================================

I. THÔNG SỐ KỸ THUẬT MẠNG NHÀ HÀNG:
-------------------------------------------------------------------------------
1. IP Máy thu ngân (Local Server): 192.168.31.253 (Cổng: 8000)
2. IP Máy in Bếp (Xprinter 80mm) : 192.168.31.251 (Cổng: 9100)
3. IP Máy in Thu ngân (80mm)     : 192.168.31.252 (Cổng: 9100)
4. Tên miền Cloud / Quét QR 4G   : https://pipogarden.com

II. CÁC TẬP LỆNH CHÍNH TRONG THƯ MỤC NÀY:
-------------------------------------------------------------------------------
1. [1_CAI_DAT_LAN_DAU.bat]           : Cài đặt thư viện, mở tường lửa và ĐĂNG KÝ
                                       TỰ ĐỘNG KHỞI ĐỘNG CÙNG WINDOWS.
2. [2_CHAY_HE_THONG.bat]             : Chạy toàn bộ hệ thống ngay lập tức
                                       (Đồng bộ menu + Print Agent + Server + Mở POS).
3. [3_DONG_BO_MENU_TU_HOST.bat]      : Cập nhật thủ công Menu mới nhất từ pipogarden.com.
4. [4_TU_DONG_KHOI_DONG_CUNG_MAY.bat]: Đăng ký hoặc cập nhật lại tính năng tự động
                                       khởi động khi bật máy tính thu ngân.
5. [run_server.py]                   : File Python cốt lõi - Bạn có thể mở trực tiếp
                                       bằng Python (Open with -> Python) nếu muốn!

III. TÍNH NĂNG TỰ ĐỘNG THÔNG MINH MỚI:
-------------------------------------------------------------------------------
- MỖI KHI BẬT MÁY THU NGÂN:
  Windows sẽ tự khởi động ngầm toàn bộ:
  1. Chờ Wi-Fi kết nối ổn định (5 giây).
  2. Tự động kiểm tra và tải Menu mới nhất từ Host https://pipogarden.com.
     (Nếu mất mạng ngoài, hệ thống sẽ tự động dùng Menu offline mà không bị lỗi).
  3. Tự động bật Print Agent để in bếp 251 và in bill thu ngân 252.
  4. Tự động bật trình duyệt hiển thị màn hình bán hàng POS: http://localhost:8000/pos.
  -> Thu ngân mở máy lên là sẵn sàng bán hàng ngay!
===============================================================================
"""
    with open(os.path.join(DEST_DIR, "HUONG_DAN_CAI_DAT_VA_VAN_HANH.txt"), "w", encoding="utf-8") as f:
        f.write(huong_dan)

    print("\n[+] Đóng gói hoàn tất thành công 100%!")
    print(f"[*] Thư mục sẵn sàng tại: {DEST_DIR}")

if __name__ == "__main__":
    prepare_thungan()
