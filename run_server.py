"""
PiPo Garden - All-in-One POS Server Launcher
Tự động đồng bộ Menu từ Host + Khởi chạy Print Agent + Máy chủ Local + Mở giao diện POS
"""

import os
import sys
import time
import socket
import threading
import subprocess
import atexit
import webbrowser

# Đảm bảo UTF-8 và tiêu đề trên Windows Console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW("🌿 PiPo Garden - Máy Chủ Thu Ngân & Tự Động In Bếp")
    except Exception:
        pass

# Thư mục gốc dự án
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# 1. TỰ ĐỘNG ĐỒNG BỘ MENU TỪ HOST (pipogarden.com) KHI KHỞI ĐỘNG
def auto_sync_from_host():
    if os.getenv("DISABLE_SYNC"):
        print("[*] Tùy chọn DISABLE_SYNC được bật, bỏ qua đồng bộ từ Host.")
        return

    print("[1/3] 🔄 Đang kiểm tra & đồng bộ Menu mới nhất từ Host (pipogarden.com)...")
    sync_script = os.path.join(BASE_DIR, "scripts", "sync_from_host.py")
    if not os.path.exists(sync_script):
        print("  [-] Không tìm thấy scripts/sync_from_host.py, bỏ qua đồng bộ.")
        return

    try:
        from scripts.sync_from_host import sync
        sync(timeout=5, download_images=True)
        print("  [+] ✅ Đã đồng bộ Menu, Danh mục, Bàn ăn thành công từ Host!")
    except Exception as e:
        print(f"  [-] Lưu ý: Không thể kết nối Host để đồng bộ ({e}).")
        print("  [+] ℹ️ Hệ thống tiếp tục sử dụng Menu & Cài đặt offline hiện có.")

# 2. KHỞI CHẠY PRINT AGENT CHẠY NGẦM
agent_proc = None

def start_print_agent():
    global agent_proc
    if os.getenv("DISABLE_AGENT"):
        print("[*] Tùy chọn DISABLE_AGENT được bật, bỏ qua khởi động Print Agent.")
        return

    agent_path = os.path.join(BASE_DIR, "print_agent", "agent.py")
    if not os.path.exists(agent_path):
        print("  [-] Không tìm thấy print_agent/agent.py")
        return

    print("[2/3] 🖨️  Đang khởi động Print Agent (Lắng nghe & In bếp 251 / Thu ngân 252)...")
    try:
        agent_proc = subprocess.Popen(
            [sys.executable, "-u", agent_path],
            cwd=BASE_DIR
        )
        print(f"  [+] ✅ Print Agent đã chạy ngầm (PID: {agent_proc.pid}).")
    except Exception as e:
        print(f"  [-] Lỗi khởi động Print Agent: {e}")

def cleanup_print_agent():
    global agent_proc
    if agent_proc and agent_proc.poll() is None:
        try:
            agent_proc.terminate()
            agent_proc.wait(timeout=2)
        except Exception:
            pass

atexit.register(cleanup_print_agent)

# 3. TỰ ĐỘNG MỞ TRÌNH DUYỆT POS KHI SERVER SẴN SÀNG
def auto_open_pos(port):
    if os.getenv("NO_BROWSER"):
        return

    def _open():
        time.sleep(2.0)
        pos_url = f"http://localhost:{port}/pos"
        print(f"[*] 🌐 Đang mở giao diện Thu Ngân: {pos_url}")
        try:
            webbrowser.open(pos_url)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    print("==================================================================")
    print("🌿 HỆ THỐNG GỌI MÓN & TỰ ĐỘNG IN BẾP PIPO GARDEN")
    print("==================================================================")

    # Bước 1: Đồng bộ Menu từ Host
    auto_sync_from_host()

    # Bước 2: Bật Print Agent
    start_print_agent()

    # Bước 3: Lên lịch mở trình duyệt POS
    auto_open_pos(port)

    print("\n[3/3] 🚀 Khởi chạy Máy chủ Local Web & WebSockets...")
    print(f"[*] Máy chủ đang chạy tại:")
    print(f"    - Cục bộ / Thu ngân     : http://localhost:{port}")
    print(f"    - Mạng nội bộ Wi-Fi quán: http://{local_ip}:{port}")
    print("------------------------------------------------------------------")
    print(f"    - Trang Chủ & Đăng Nhập : http://localhost:{port}/")
    print(f"    - Thu Ngân & Sơ Đồ Bàn  : http://localhost:{port}/pos")
    print(f"    - Không Gian Bếp & BOM  : http://localhost:{port}/kitchen")
    print(f"    - Màn Hình Bếp KDS      : http://localhost:{port}/kds")
    print(f"    - Phục Vụ Ra Món        : http://{local_ip}:{port}/waiter")
    print(f"    - Quản Lý Kho NVL       : http://localhost:{port}/inventory")
    print("==================================================================")
    print("LƯU Ý: Giữ cửa sổ này mở trong suốt ca bán hàng!\n")

    import uvicorn
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
