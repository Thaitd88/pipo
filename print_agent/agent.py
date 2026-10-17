"""
PiPo Garden - Local Kitchen Print & Cloud Sync Agent
Chương trình chạy ngầm tại máy thu ngân của nhà hàng.

Nhiệm vụ:
1. Lắng nghe WebSocket đa kênh (Cloud Vibe Host + Local Server LAN):
   - Khách dùng 4G quét QR -> Cloud đẩy lệnh in thẳng xuống máy in quán.
   - Quán mất Internet -> Khách/nhân viên dùng Wi-Fi nội bộ -> Local Server đẩy lệnh in.
2. Tự động in phiếu bếp (KOT) xuống máy in nhiệt LAN (Port 9100) hoặc máy in USB.
3. Đồng bộ dữ liệu 2 chiều (Cloud <-> Local Sync):
   - Tự động đẩy đơn hàng bán lúc offline lên Cloud ngay khi có mạng trở lại.
   - Đồng bộ đơn hàng từ Cloud về máy thu ngân để quản lý tập trung.
"""

import asyncio
import json
import os
import sys
import socket
import base64
import time
from datetime import datetime
import urllib.request
import urllib.error

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import websockets
except ImportError:
    print("[ERROR] Chưa cài thư viện websockets. Vui lòng chạy: pip install websockets")
    sys.exit(1)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "server_ws_url": "ws://127.0.0.1:8000/ws/printer",
        "cloud_ws_url": "wss://pipogarden.com/ws/printer",
        "cloud_api_url": "https://pipogarden.com",
        "local_api_url": "http://127.0.0.1:8000",
        "sync_interval_sec": 20,
        "reconnect_interval_sec": 3,
        "simulate_mode": True,
        "printers": {}
    }

def print_to_lan_printer(host: str, port: int, payload_bytes: bytes) -> bool:
    """Gửi dữ liệu ESC/POS trực tiếp tới máy in nhiệt qua socket mạng LAN nội bộ."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect((host, port))
        s.sendall(payload_bytes)
        s.close()
        return True
    except Exception as e:
        print(f"  [CẢNH BÁO] Không thể kết nối tới máy in LAN {host}:{port} - Lỗi: {e}")
        return False

def print_simulated_ticket(ticket_text: str, station: str, source_label: str = "SYSTEM"):
    """Giả lập in phiếu trực quan trên terminal khi quán chưa gắn máy in thật."""
    sep = "=" * 48
    print("\n" + sep)
    print(f"🖨️  [MÁY IN BẾP PIPO ĐANG IN] - TRẠM: {station} ({source_label})")
    print(f"🔔  [CÒI HÚ XP-C300H]: BÍP! BÍP! BÍP! (Cảnh báo món mới)")
    print(sep)
    for line in ticket_text.splitlines():
        print(f"│ {line:<44} │")
    print(sep)
    print("✂️  [DAO CẮT]: Tự động cắt giấy hoàn tất.\n")

# Bộ nhớ đệm chống in trùng đơn khi cả Cloud và Local cùng phát lệnh
printed_job_hashes = set()

async def ws_listener(url: str, label: str, config: dict):
    """Lắng nghe lệnh in từ 1 máy chủ (Cloud hoặc Local). Tự động kết nối lại nếu mất mạng."""
    reconnect_interval = config.get("reconnect_interval_sec", 3)
    simulate_mode = config.get("simulate_mode", True)
    printers = config.get("printers", {})

    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{label}] Đang kết nối tới: {url}...")
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{label}] ✅ KẾT NỐI THÀNH CÔNG! Sẵn sàng nhận lệnh in...")
                
                await ws.send(json.dumps({
                    "event": "AGENT_READY",
                    "client": f"Cashier-Agent-{label}",
                    "timestamp": datetime.now().isoformat()
                }))

                async for message in ws:
                    try:
                        data = json.loads(message)
                        event = data.get("event")

                        if event == "PRINT_JOB":
                            job_id = data.get("job_id")
                            station = data.get("station", "HOT_KITCHEN")
                            ticket_text = data.get("ticket_text", "")
                            table_name = data.get("table_name", "")
                            escpos_b64 = data.get("escpos_b64", "")
                            escpos_bytes = base64.b64decode(escpos_b64) if escpos_b64 else b""

                            # Kiểm tra chống in trùng
                            job_key = f"{job_id}_{station}_{table_name}"
                            if job_key in printed_job_hashes:
                                continue
                            printed_job_hashes.add(job_key)
                            if len(printed_job_hashes) > 1000:
                                printed_job_hashes.clear()

                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📥 [{label}] NHẬN LỆNH IN MỚI (Job #{job_id}) -> {table_name} -> Trạm: {station}")

                            printed_success = False

                            # Gửi máy in LAN vật lý nếu được bật
                            printer_cfg = printers.get(station)
                            if not printer_cfg:
                                if station in ["BAR", "CASHIER"]:
                                    printer_cfg = printers.get("BAR") or printers.get("CASHIER")
                                else:
                                    printer_cfg = printers.get("HOT_KITCHEN")

                            if printer_cfg and printer_cfg.get("enabled"):
                                host = printer_cfg.get("host")
                                port = printer_cfg.get("port", 9100)
                                if print_to_lan_printer(host, port, escpos_bytes):
                                    printed_success = True

                            # In giả lập ra màn hình nếu bật simulate_mode
                            if simulate_mode or not printed_success:
                                print_simulated_ticket(ticket_text, station, label)
                                printed_success = True

                            # Phản hồi hoàn tất cho Server
                            ack_payload = {
                                "event": "JOB_COMPLETED",
                                "job_id": job_id,
                                "station": station,
                                "success": printed_success,
                                "printed_at": datetime.now().isoformat()
                            }
                            await ws.send(json.dumps(ack_payload))

                        elif event == "PING":
                            await ws.send(json.dumps({"event": "PONG"}))

                    except Exception as ex:
                        print(f"[{label}] Lỗi khi xử lý thông điệp: {ex}")

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as e:
            # Rớt mạng Cloud hoặc Local Server chưa bật
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{label}] ⚠️ Mất kết nối ({e}). Thử lại sau {reconnect_interval}s...")
            await asyncio.sleep(reconnect_interval)
        except Exception as e:
            print(f"[{label}] Lỗi không xác định: {e}. Thử lại sau {reconnect_interval}s...")
            await asyncio.sleep(reconnect_interval)

def http_get_json(url: str, timeout: float = 5.0):
    req = urllib.request.Request(url, headers={"User-Agent": "PiPo-Sync-Agent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def http_post_json(url: str, data: dict, timeout: float = 5.0):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "PiPo-Sync-Agent/1.0"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

async def sync_worker(config: dict):
    """Tiến trình đồng bộ ngầm giữa Local Server và Cloud Server."""
    cloud_url = config.get("cloud_api_url", "https://pipo.n2.tinhgon.xyz").rstrip("/")
    local_url = config.get("local_api_url", "http://127.0.0.1:8000").rstrip("/")
    interval = config.get("sync_interval_sec", 20)

    last_sync_time = None
    internet_was_down = False

    await asyncio.sleep(5) # Đợi hệ thống khởi động

    while True:
        try:
            # 1. Kiểm tra Internet và kết nối Cloud
            cloud_status = await asyncio.to_thread(http_get_json, f"{cloud_url}/api/sync/status", 4.0)
            local_status = await asyncio.to_thread(http_get_json, f"{local_url}/api/sync/status", 2.0)

            if internet_was_down:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🌐 [SYNC] INTERNET ĐÃ ĐƯỢC KHÔI PHỤC! Đang đồng bộ bù toàn bộ đơn offline...")
                internet_was_down = False

            # 2. Đẩy đơn từ Local lên Cloud (những đơn bán offline lúc mất mạng)
            export_local = await asyncio.to_thread(http_get_json, f"{local_url}/api/sync/export-orders", 4.0)
            if export_local.get("count", 0) > 0:
                push_res = await asyncio.to_thread(http_post_json, f"{cloud_url}/api/sync/import-orders", {"orders": export_local["orders"]}, 5.0)
                if push_res.get("imported", 0) > 0 or push_res.get("updated", 0) > 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⬆️ [SYNC] Local -> Cloud: {push_res.get('message')}")

            # 3. Kéo đơn từ Cloud về Local (những đơn khách 4G đặt trực tiếp trên Cloud)
            export_cloud = await asyncio.to_thread(http_get_json, f"{cloud_url}/api/sync/export-orders", 5.0)
            if export_cloud.get("count", 0) > 0:
                pull_res = await asyncio.to_thread(http_post_json, f"{local_url}/api/sync/import-orders", {"orders": export_cloud["orders"]}, 4.0)
                if pull_res.get("imported", 0) > 0 or pull_res.get("updated", 0) > 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⬇️ [SYNC] Cloud -> Local: {pull_res.get('message')}")

        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if not internet_was_down:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ [SYNC] Không có kết nối tới Cloud Vibe Host (Mất Internet hoặc máy chủ bận). Chế độ OFFLINE nội bộ đang bảo vệ nhà hàng!")
                internet_was_down = True
        except Exception as e:
            pass

        await asyncio.sleep(interval)

async def main():
    config = load_config()
    server_ws_url = config.get("server_ws_url", "ws://127.0.0.1:8000/ws/printer")
    cloud_ws_url = config.get("cloud_ws_url", "wss://pipo.n2.tinhgon.xyz/ws/printer")

    print("==================================================================")
    print("🌿 PIPO GARDEN - HYBRID PRINT & DUAL SYNC AGENT")
    print("   Hệ thống Tự Động In Bếp & Đồng Bộ 2 Chiều (Cloud 4G + Local LAN)")
    print("==================================================================")
    print(f"[*] 1. Kênh Cloud (Khách dùng 4G quét QR)   : {cloud_ws_url}")
    print(f"[*] 2. Kênh Local (Thu ngân & LAN nội bộ)   : {server_ws_url}")
    print(f"[*] 3. Đồng bộ dữ liệu Cloud <-> Local      : Mỗi {config.get('sync_interval_sec', 20)} giây")
    print(f"[*] 4. Chế độ in bếp                       : {'Giả lập + LAN' if config.get('simulate_mode') else 'Chỉ gửi máy in LAN'}")
    print("==================================================================\n")

    tasks = [
        asyncio.create_task(ws_listener(cloud_ws_url, "CLOUD (4G Khách)", config)),
        asyncio.create_task(ws_listener(server_ws_url, "LOCAL (Mạng LAN)", config)),
        asyncio.create_task(sync_worker(config))
    ]

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOP] Đã dừng Print & Sync Agent.")
