"""
PiPo Garden - Server Launcher
Khởi chạy máy chủ Backend FastAPI + WebSockets
Cho phép các thiết bị trong mạng Wi-Fi (điện thoại khách, màn hình bếp, thu ngân) kết nối.
"""

import uvicorn
import socket
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

import os

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    print("==================================================================")
    print("🌿 HỆ THỐNG GỌI MÓN & TỰ ĐỘNG IN BẾP PIPO GARDEN")
    print("==================================================================")
    print(f"[*] Máy chủ đang chạy tại:")
    print(f"    - Cục bộ / Thu ngân     : http://localhost:{port}")
    print(f"    - Mạng nội bộ Wi-Fi quán: http://{local_ip}:{port}")
    print("------------------------------------------------------------------")
    print(f"    - Trang Chủ & Đăng Nhập : http://localhost:{port}/")
    print(f"    - Thu Ngân & Sơ Đồ Bàn  : http://localhost:{port}/pos")
    print(f"    - Không Gian Bếp & BOM  : http://localhost:{port}/kitchen")
    print(f"    - Màn Hình Bếp KDS      : http://localhost:{port}/kds")
    print(f"    - Phục Vụ Ra Món        : http://localhost:{port}/waiter")
    print(f"    - Quản Lý Kho NVL       : http://localhost:{port}/inventory")
    print("==================================================================")
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
