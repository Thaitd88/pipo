import os
import shutil
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
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

    # 1_CAI_DAT_LAN_DAU.bat
    bat_cai_dat = """@echo off
chcp 65001 > nul
title PiPo Garden - Cai Dat Ban Dau Cho May Thu Ngan
color 0A
echo ===================================================================
echo     HE THONG QUAN LY NHA HANG PIPO GARDEN - CAI DAT BAN DAU
echo     (May thu ngan Local Server - IP: 192.168.31.253)
echo ===================================================================
echo.

cd /d "%~dp0"

echo [1/3] Kiem tra moi truong Python tren may thu ngan...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [LOI] May tinh chua cai dat Python hoac chua tick "Add python.exe to PATH"!
    echo Vui long tai va cai dat Python (ban 3.10 tro len) tu https://www.python.org/
    echo LUU Y KHI CAI: Nho tick chon vao o [x] "Add python.exe to PATH" o man hinh dau tien!
    echo.
    pause
    exit /b 1
)
python --version
echo.

echo [2/3] Dang cai dat cac thu vien he thong (FastAPI, Uvicorn, Websockets...)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [CANH BAO] Co loi khi cai dat thu vien qua pip. Vui long kiem tra lai ket noi Internet.
    pause
    exit /b 1
)
echo.

echo [3/3] Mo cong Firewall 8000 de dien thoai nhan vien / khach ket noi qua Wi-Fi...
netsh advfirewall firewall delete rule name="PiPo POS Server (Port 8000)" > nul 2>&1
netsh advfirewall firewall add rule name="PiPo POS Server (Port 8000)" dir=in action=allow protocol=TCP localport=8000 > nul 2>&1
if %errorlevel% equ 0 (
    echo [+] Da mo cong 8000 tren Windows Firewall thanh cong!
) else (
    echo [-] Khong the tu dong sua Firewall (Can quyen Administrator).
    echo     Neu dien thoai khong truy cap duoc http://192.168.31.253:8000, 
    echo     vui long chuot phai vao file nay va chon "Run as administrator".
)

echo.
echo ===================================================================
echo   CAI DAT HOAN TAT!
echo   Bay gio ban chi can nhap dup vao: 2_CHAY_HE_THONG.bat de su dung!
echo ===================================================================
echo.
pause
"""
    with open(os.path.join(DEST_DIR, "1_CAI_DAT_LAN_DAU.bat"), "w", encoding="utf-8") as f:
        f.write(bat_cai_dat)

    # 2_CHAY_HE_THONG.bat
    bat_chay = """@echo off
chcp 65001 > nul
title PiPo Garden - Khoi Dong POS Thu Ngan & Server Local
color 0B
echo ===================================================================
echo     🌿 HE THONG NHA HANG PIPO GARDEN - MAY THU NGAN LOCAL
echo     IP May Thu Ngan: 192.168.31.253 | Cong: 8000
echo ===================================================================
echo.

cd /d "%~dp0"

echo [*] 1. Khoi chay Server Local (FastAPI & WebSockets)...
start "PiPo Server Local (Port 8000)" cmd /k "title PiPo Server Local & cd /d %~dp0 & python run_server.py"

echo [*] 2. Khoi chay Print Agent (In Bep 251 & Thu Ngan 252)...
start "PiPo Print Agent" cmd /k "title PiPo Print Agent & cd /d %~dp0 & python run_agent.py"

echo [*] 3. Dang doi he thong san sang trong 3 giay...
timeout /t 3 /nobreak > nul

echo [*] 4. Dang mo giao dien Thu Ngan POS tren trinh duyet...
start http://localhost:8000/pos

echo.
echo ===================================================================
echo   ✅ HE THONG DA SAN SANG HOAT DONG!
echo.
echo   * MAY THU NGAN NAY     : http://localhost:8000/pos
echo   * DIEN THOAI PHUC VU   : http://192.168.31.253:8000/waiter
echo   * MAN HINH BEP KDS     : http://192.168.31.253:8000/kds
echo   * QUAN TRI ADMIN       : http://192.168.31.253:8000/admin
echo.
echo   LUU Y: Giu 2 cua so mau den (Server va Print Agent) chay ngam!
echo   Khong dong 2 cua so do khi quan dang ban hang.
echo ===================================================================
echo.
"""
    with open(os.path.join(DEST_DIR, "2_CHAY_HE_THONG.bat"), "w", encoding="utf-8") as f:
        f.write(bat_chay)

    # 3_DONG_BO_MENU_TU_HOST.bat
    bat_dong_bo = """@echo off
chcp 65001 > nul
title PiPo Garden - Dong Bo Menu Tu Host (pipogarden.com)
color 0E
echo ===================================================================
echo   🌿 DONG BO DU LIEU MENU, BAN AN & CAI DAT TU HOST PIPOGARDEN.COM
echo ===================================================================
echo.

cd /d "%~dp0"

echo [*] Dang ket noi toi Host https://pipogarden.com de dong bo...
python scripts\\sync_from_host.py

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
    bat_startup = """@echo off
chcp 65001 > nul
title PiPo Garden - Cau Hinh Tu Khoi Dong Cung Windows
color 0D
echo ===================================================================
echo   🌿 CAU HINH TU DONG KHOI DONG HE THONG CUNG WINDOWS
echo ===================================================================
echo.

cd /d "%~dp0"

set "TARGET_BAT=%~dp02_CHAY_HE_THONG.bat"
set "SHORTCUT_PATH=%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\PiPo_Garden_POS.lnk"

echo [*] Dang tao loi tat tu khoi dong trong thu muc Startup...

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%TARGET_BAT%'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'PiPo Garden Local POS Server'; $s.Save()"

if %errorlevel% equ 0 (
    echo.
    echo [+] THANH CONG! Da dang ky tu khoi dong cung Windows.
    echo     Tu gio, moi khi bat may tinh thu ngan len, he thong se tu dong chay
    echo     va mo giao dien POS ma thu ngan khong can phai thao tac gi them!
) else (
    echo.
    echo [-] Co loi khi tao loi tat.
)

echo.
pause
"""
    with open(os.path.join(DEST_DIR, "4_TU_DONG_KHOI_DONG_CUNG_MAY.bat"), "w", encoding="utf-8") as f:
        f.write(bat_startup)

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

II. CÁCH CÀI ĐẶT LẦN ĐẦU TRÊN MÁY THU NGÂN (CHỈ LÀM 1 LẦN):
-------------------------------------------------------------------------------
Bước 1: Copy toàn bộ thư mục [thungan] này vào ổ C:\\ hoặc D:\\ máy thu ngân
        (Ví dụ đặt tại: C:\\thungan hoặc D:\\thungan).

Bước 2: Cài đặt Python trên máy thu ngân:
        - Tải Python (bản 3.10 hoặc 3.11/3.12) từ https://www.python.org/downloads/
        - RẤT QUAN TRỌNG: Ở màn hình cài đặt đầu tiên, PHẢI TÍCH CHỌN VÀO Ô:
          [x] "Add python.exe to PATH" rồi mới bấm "Install Now".

Bước 3: Chuột phải vào file [1_CAI_DAT_LAN_DAU.bat] -> Chọn "Run as administrator":
        - File này sẽ tự động cài các thư viện: FastAPI, Uvicorn, Websockets...
        - Tự động mở cổng tường lửa Windows 8000 để các máy khác bắt Wi-Fi truy cập được.

Bước 4 (Tùy chọn nhưng KHUYÊN DÙNG):
        - Nhấp đúp vào file [4_TU_DONG_KHOI_DONG_CUNG_MAY.bat].
        - Từ nay mỗi khi bật máy thu ngân lên, hệ thống sẽ tự động chạy và bật POS.

III. CÁCH VẬN HÀNH HÀNG NGÀY:
-------------------------------------------------------------------------------
1. Bật máy thu ngân:
   - Nhấp đúp vào file: [2_CHAY_HE_THONG.bat]
   - Màn hình sẽ bật 2 cửa sổ nền đen (Server và Print Agent) và tự động mở trình
     duyệt web tại địa chỉ: http://localhost:8000/pos
   - Thu ngân đăng nhập tài khoản:
     + Tài khoản: thungan  | Mật khẩu: 123456
     + Hoặc tài khoản Admin: Thaitd | Mật khẩu: 123456

2. Điện thoại nhân viên phục vụ / Order tại bàn:
   - Kết nối vào Wi-Fi nhà hàng PiPo Garden.
   - Mở trình duyệt web trên điện thoại gõ: http://192.168.31.253:8000/waiter
     (hoặc http://192.168.31.253:8000/pos)
   - Đăng nhập: phucvu | pass: 123456
   - Bấm gọi món -> Phiếu bếp sẽ in ngay lập tức tại máy in 192.168.31.251 (<0.1 giây)!

3. Màn hình Bếp KDS (nếu bếp dùng máy tính bảng hoặc màn hình phụ):
   - Mở trình duyệt gõ: http://192.168.31.253:8000/kds

IV. KHI BẠN SỬA MENU TRÊN HOST HOẶC MÁY CỦA BẠN:
-------------------------------------------------------------------------------
Khi bạn thêm món mới, sửa giá, hoặc thêm khu vực trên Host (pipogarden.com):
- Tại máy thu ngân, chỉ cần nhấp đúp vào file: [3_DONG_BO_MENU_TU_HOST.bat]
- Hệ thống sẽ tự động kéo toàn bộ danh mục, món ăn, giá bán và hình ảnh mới nhất
  từ Host về CSDL máy thu ngân trong vài giây!

V. CƠ CHẾ HOẠT ĐỘNG SONG SONG VÀ CHỐNG MẤT MẠNG:
-------------------------------------------------------------------------------
- BÌNH THƯỜNG: Print Agent kết nối cả Cloud (pipogarden.com) và Local (127.0.0.1:8000).
  Khách dùng 4G quét QR trên bàn gọi món -> Máy in tại quán vẫn in bình thường.
  Thu ngân/phục vụ bấm trên mạng nội bộ -> In ngay lập tức.
  Đơn hàng tự động đồng bộ 2 chiều giữa máy thu ngân và Cloud mỗi 20 giây.

- KHI ĐỨT CÁP / MẤT INTERNET NGOÀI:
  Nhà hàng VẪN BÁN HÀNG 100% BÌNH THƯỜNG!
  Máy thu ngân và điện thoại nhân viên phục vụ kết nối Wi-Fi nội bộ không cần Internet.
  In hóa đơn, in phiếu bếp, thanh toán diễn ra trơn tru.
  Khi có mạng lại, hệ thống sẽ tự động đồng bộ bù các đơn hàng lên Cloud.

VI. HỖ TRỢ XỬ LÝ SỰ CỐ NHANH:
-------------------------------------------------------------------------------
1. Nếu điện thoại nhân viên không vào được http://192.168.31.253:8000:
   - Kiểm tra điện thoại đã kết nối đúng Wi-Fi của quán chưa.
   - Chuột phải vào file 1_CAI_DAT_LAN_DAU.bat chọn "Run as administrator" để mở Firewall.

2. Nếu máy in không in:
   - Kiểm tra đèn mạng trên 2 máy in (Bếp: 192.168.31.251, Thu ngân: 192.168.31.252).
   - Kiểm tra giấy in và khởi động lại máy in nếu bị kẹt giấy.
===============================================================================
"""
    with open(os.path.join(DEST_DIR, "HUONG_DAN_CAI_DAT_VA_VAN_HANH.txt"), "w", encoding="utf-8") as f:
        f.write(huong_dan)

    print(f"\n[HOÀN TẤT] Đã đóng gói thành công thư mục: {DEST_DIR}")
    print(f"Bây giờ bạn chỉ cần copy thư mục [thungan] này sang máy thu ngân!")

if __name__ == "__main__":
    prepare_thungan()
