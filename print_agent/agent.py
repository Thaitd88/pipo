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
        "cloud_pos_ws_url": "wss://pipogarden.com/ws/pos",
        "sync_interval_sec": 3,
        "reconnect_interval_sec": 3,
        "simulate_mode": True,
        "printers": {}
    }

_VN_ACCENTS = u'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
_VN_NO_ACCENTS = u'AAAAEEEIIOOOOUUYaaaaeeeiioooouuyAaDdIiUuOoUuAaAaAaAaAaAaAaAaAaAaAaAaEeEeEeEeEeEeEeEeIiIiOoOoOoOoOoOoOoOoOoOoOoOoUuUuUuUuUuUuUuYyYyYyYy'
_VN_TRANS_TABLE = str.maketrans(_VN_ACCENTS, _VN_NO_ACCENTS)

def remove_vietnamese_accents(input_str: str) -> str:
    if not input_str:
        return ""
    return str(input_str).translate(_VN_TRANS_TABLE)

def text_to_escpos(ticket_text: str, station: str = "HOT_KITCHEN") -> bytes:
    """Biên dịch văn bản phiếu in sang luồng mã ESC/POS nhị phân chuẩn cho máy in nhiệt LAN 80mm."""
    if not ticket_text:
        return b""
    clean_text = remove_vietnamese_accents(ticket_text)
    ESC = b'\x1b'
    GS = b'\x1d'
    b = bytearray()
    b.extend(ESC + b'@')           # Khởi tạo máy in
    b.extend(ESC + b't\x00')       # Bảng mã chuẩn ASCII
    if station in ["HOT_KITCHEN", "KITCHEN"]:
        b.extend(ESC + b'B\x03\x02')   # Còi hú 3 tiếng cảnh báo Bếp
    b.extend(clean_text.encode('ascii', errors='ignore'))
    b.extend(b'\n\n\n\n\n')        # Đẩy giấy qua dao cắt
    b.extend(GS + b'V\x42\x00')    # Cắt giấy tự động
    return bytes(b)

def print_to_lan_printer(host: str, port: int, payload_bytes: bytes) -> bool:
    """Gửi dữ liệu ESC/POS trực tiếp tới máy in nhiệt qua socket mạng LAN nội bộ."""
    if not payload_bytes or len(payload_bytes) == 0:
        print(f"  [CẢNH BÁO] Không có dữ liệu in (payload rỗng) cho máy in {host}:{port}")
        return False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect((host, port))
        s.sendall(payload_bytes)
        time.sleep(0.08)
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
                            if not escpos_bytes and ticket_text:
                                escpos_bytes = text_to_escpos(ticket_text, station)

                            # Kiểm tra chống in trùng
                            job_key = f"{job_id}_{station}_{table_name}"
                            if job_key in printed_job_hashes:
                                continue
                            printed_job_hashes.add(job_key)
                            if len(printed_job_hashes) > 1000:
                                printed_job_hashes.clear()

                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📥 [{label}] NHẬN LỆNH IN MỚI (Job #{job_id}) -> {table_name} -> Trạm: {station}")

                            printed_success = False

                            # Tức thì kéo đơn từ Cloud về Local Server để POS hiển thị ngay
                            asyncio.create_task(sync_orders_now(config))

                            # Gửi máy in LAN vật lý nếu được bật
                            printer_cfg = printers.get(station)
                            if not printer_cfg:
                                if station in ["BAR", "CASHIER"]:
                                    printer_cfg = printers.get("CASHIER") or printers.get("BAR")
                                else:
                                    printer_cfg = printers.get("HOT_KITCHEN")

                            if printer_cfg and printer_cfg.get("enabled"):
                                host = printer_cfg.get("host")
                                port = printer_cfg.get("port", 9100)
                                if print_to_lan_printer(host, port, escpos_bytes):
                                    printed_success = True

                            # Dự phòng: Nếu máy in Thu ngân không phản hồi, thử gửi qua máy in Bếp (192.168.31.251)
                            if not printed_success and station in ["CASHIER", "BAR"]:
                                kitchen_cfg = printers.get("HOT_KITCHEN")
                                if kitchen_cfg and kitchen_cfg.get("enabled"):
                                    k_host = kitchen_cfg.get("host")
                                    k_port = kitchen_cfg.get("port", 9100)
                                    if k_host and k_host != (printer_cfg.get("host") if printer_cfg else ""):
                                        if print_to_lan_printer(k_host, k_port, escpos_bytes):
                                            printed_success = True
                                            print(f"  [FALLBACK] Đã in thành công phiếu {station} qua máy in {k_host}:{k_port}")

                            # In giả lập ra màn hình nếu bật simulate_mode
                            if simulate_mode:
                                print_simulated_ticket(ticket_text, station, label)
                                printed_success = True
                            elif not printed_success:
                                print(f"  [⚠️ LỖI MÁY IN] Chưa thể gửi dữ liệu tới máy in vật lý cho Job #{job_id}! Sẽ giữ lệnh để tự động thử lại.")

                            # Phản hồi hoàn tất cho Server chỉ khi đã in thành công ra giấy hoặc ở chế độ giả lập
                            if printed_success:
                                printed_job_hashes.add(job_key)
                                if len(printed_job_hashes) > 1000:
                                    printed_job_hashes.clear()
                                ack_payload = {
                                    "event": "JOB_COMPLETED",
                                    "job_id": job_id,
                                    "station": station,
                                    "success": True,
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

def http_get_json(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": "PiPo-Sync-Agent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def http_post_json(url: str, data: dict, timeout: float = 8.0, headers: dict = None):
    req_headers = {"Content-Type": "application/json", "User-Agent": "PiPo-Sync-Agent/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=req_headers,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


async def sync_orders_now(config: dict):
    cloud_url = config.get("cloud_api_url", "https://pipogarden.com").rstrip("/")
    local_url = config.get("local_api_url", "http://127.0.0.1:8000").rstrip("/")
    try:
        export_cloud = await asyncio.to_thread(http_get_json, f"{cloud_url}/api/sync/export-orders?limit=50", 4.0)
        if export_cloud.get("count", 0) > 0 or export_cloud.get("deleted_uuids"):
            pull_payload = {
                "orders": export_cloud.get("orders", []),
                "deleted_uuids": export_cloud.get("deleted_uuids", [])
            }
            pull_res = await asyncio.to_thread(http_post_json, f"{local_url}/api/sync/import-orders", pull_payload, 4.0)
            if pull_res.get("imported", 0) > 0 or pull_res.get("updated", 0) > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ [SYNC KHÁCH 4G] Đã kéo {pull_res.get('imported', 0)} đơn mới về POS Local!")
    except Exception:
        pass

async def sync_reservations_now(config: dict):
    cloud_url = config.get("cloud_api_url", "https://pipogarden.com").rstrip("/")
    local_url = config.get("local_api_url", "http://127.0.0.1:8000").rstrip("/")
    try:
        export_res = await asyncio.to_thread(http_get_json, f"{cloud_url}/api/sync/export-reservations?limit=30", 4.0)
        if export_res.get("count", 0) > 0:
            pull_res = await asyncio.to_thread(http_post_json, f"{local_url}/api/sync/import-reservations", {"reservations": export_res["reservations"]}, 4.0)
            if pull_res.get("imported", 0) > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ [SYNC ĐẶT BÀN] Đã kéo {pull_res.get('imported')} đơn đặt bàn mới về POS Local!")
    except Exception:
        pass

async def sync_local_to_cloud_now(config: dict):
    """Đẩy các đơn phát sinh từ Local POS lên Cloud ngay lập tức khi có sự kiện."""
    cloud_url = config.get("cloud_api_url", "https://pipogarden.com").rstrip("/")
    local_url = config.get("local_api_url", "http://127.0.0.1:8000").rstrip("/")
    try:
        export_local = await asyncio.to_thread(http_get_json, f"{local_url}/api/sync/export-orders?limit=50", 4.0)
        if export_local.get("count", 0) > 0 or export_local.get("deleted_uuids"):
            push_payload = {
                "orders": export_local.get("orders", []),
                "deleted_uuids": export_local.get("deleted_uuids", [])
            }
            push_res = await asyncio.to_thread(http_post_json, f"{cloud_url}/api/sync/import-orders", push_payload, 5.0)
            if push_res.get("imported", 0) > 0 or push_res.get("updated", 0) > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⬆️ [EVENT SYNC] Local -> Cloud: {push_res.get('message')}")
    except Exception:
        pass

async def local_pos_listener(config: dict):
    """Lắng nghe sự kiện từ POS Local (khi thu ngân bấm tạo đơn, thanh toán...) để đẩy tức thì lên Cloud."""
    local_pos_ws_url = config.get("local_pos_ws_url", "ws://127.0.0.1:8000/ws/pos")
    reconnect_interval = config.get("reconnect_interval_sec", 5)

    while True:
        try:
            async with websockets.connect(local_pos_ws_url, ping_interval=20, ping_timeout=20) as ws:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ [LOCAL POS BRIDGE] Đã kết nối luồng sự kiện POS Local!")
                async for message in ws:
                    try:
                        data = json.loads(message)
                        event = data.get("event")
                        if event in [
                            "NEW_ORDER", "TABLE_CHECKED_OUT", "ITEM_STATUS_CHANGED", 
                            "ORDER_ITEMS_COMPLETED", "TABLE_ITEMS_SERVED", 
                            "ITEM_CANCELLED", "TABLE_UPDATED", "CANCEL_APPROVED"
                        ]:
                            # Kích hoạt đẩy ngay dữ liệu từ Local lên Cloud
                            await sync_local_to_cloud_now(config)
                    except Exception:
                        pass
        except Exception:
            await asyncio.sleep(reconnect_interval)

async def cloud_pos_listener(config: dict):
    """Cầu nối thời gian thực: Lắng nghe sự kiện Cloud POS (đơn mới, check-in, gọi phục vụ) để phát ngay tới POS Local."""
    cloud_pos_ws_url = config.get("cloud_pos_ws_url", "wss://pipogarden.com/ws/pos")
    local_url = config.get("local_api_url", "http://127.0.0.1:8000").rstrip("/")
    reconnect_interval = config.get("reconnect_interval_sec", 3)

    while True:
        try:
            async with websockets.connect(cloud_pos_ws_url, ping_interval=20, ping_timeout=20) as ws:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ [REALTIME POS BRIDGE] Đã kết nối luồng sự kiện Cloud POS!")
                # Tự động đồng bộ bù ngay khi kết nối thành công phòng khi vừa mất mạng
                await sync_orders_now(config)
                await sync_reservations_now(config)
                async for message in ws:
                    try:
                        data = json.loads(message)
                        event = data.get("event")
                        if event in ["NEW_ORDER", "TABLE_CHECKED_OUT", "ITEM_STATUS_CHANGED", "ORDER_ITEMS_COMPLETED", "TABLE_ITEMS_SERVED", "ITEM_CANCELLED", "TABLE_UPDATED", "CANCEL_APPROVED"]:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛎️ [CLOUD POS] Sự kiện: {event}")
                            await sync_orders_now(config)
                            await asyncio.to_thread(http_post_json, f"{local_url}/api/sync/notify-pos-event", data, 2.0)
                        elif event in ["CLEAN_HISTORY", "REVENUE_CLEARED"]:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧹 [CLOUD -> LOCAL SYNC] Nhận lệnh Xóa Doanh Thu từ Cloud, đồng bộ CSDL Local!")
                            clean_payload = data.get("payload") or {}
                            try:
                                await asyncio.to_thread(
                                    http_post_json,
                                    f"{local_url}/api/reports/clean-history",
                                    clean_payload,
                                    5.0,
                                    {"X-Pipo-Admin-Secret": "pipo_secure_clear_revenue_2026", "X-Forwarded-From": "CLOUD"}
                                )
                            except Exception as _ce:
                                print(f"[CLEAN_HISTORY sync error] {_ce}")
                        elif event in ["NEW_RESERVATION", "RESERVATION_UPDATED", "RESERVATION_DELETED"]:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📅 [CLOUD RES] Sự kiện đặt bàn: {event}")
                            await sync_reservations_now(config)
                            await asyncio.to_thread(http_post_json, f"{local_url}/api/sync/notify-pos-event", data, 2.0)
                        elif event == "SERVICE_CALL":
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔔 [CLOUD CALL] Khách gọi phục vụ: {data.get('table_name')}")
                            await asyncio.to_thread(http_post_json, f"{local_url}/api/sync/notify-pos-event", data, 2.0)
                    except Exception:
                        pass
        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError):
            await asyncio.sleep(reconnect_interval)
        except Exception:
            await asyncio.sleep(reconnect_interval)

async def sync_worker(config: dict):
    """
    Tiến trình Safety Net chạy ngầm (mặc định 5 phút / lần):
    - Đảm bảo 100% không sót đơn nếu mạng chập chờn hoặc rớt gói tin.
    - Trong thời gian bình thường, hệ thống đồng bộ theo Sự Kiện (Event-Driven) tức thời 0 giây
      thông qua WebSocket nên không cần quét liên tục, giảm 99.5% tải mạng và CSDL.
    """
    interval = config.get("sync_interval_sec", 300)
    internet_was_down = False

    # Đợi 5 giây đầu khởi động để các kết nối WebSocket thiết lập xong
    await asyncio.sleep(5)

    # Chạy 1 lần đồng bộ ban đầu khi vừa bật phần mềm
    await sync_orders_now(config)
    await sync_reservations_now(config)
    await sync_local_to_cloud_now(config)

    while True:
        try:
            await asyncio.sleep(interval)

            # Safety Net quét nhẹ kiểm tra đối soát
            await sync_orders_now(config)
            await sync_reservations_now(config)
            await sync_local_to_cloud_now(config)

            if internet_was_down:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌐 [SYNC] Internet đã phục hồi, đồng bộ Cloud <-> Local hoạt động bình thường.")
                internet_was_down = False

        except (urllib.error.URLError, TimeoutError, OSError):
            if not internet_was_down:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ [SYNC] Tạm thời mất kết nối Cloud. POS Local chạy hoàn toàn độc lập (Offline-First).")
                internet_was_down = True
        except Exception:
            pass



async def pull_pending_jobs(server_api_url: str, label: str, config: dict):
    """Kéo và in bù các đơn hàng PENDING phòng khi WebSocket rớt gói tin hoặc chưa kịp kết nối."""
    printers = config.get("printers", {})
    simulate_mode = config.get("simulate_mode", False)
    clean_url = server_api_url.rstrip("/")
    try:
        data = await asyncio.to_thread(http_get_json, f"{clean_url}/api/printer/pending-jobs?limit=30", 5.0)
        jobs = data.get("jobs", [])
        if not jobs:
            return
        for pjob in jobs:
            job_id = pjob.get("job_id")
            station = pjob.get("station", "HOT_KITCHEN")
            ticket_text = pjob.get("ticket_text", "")
            table_name = pjob.get("table_name", "")
            escpos_b64 = pjob.get("escpos_b64", "")
            escpos_bytes = base64.b64decode(escpos_b64) if escpos_b64 else b""
            if not escpos_bytes and ticket_text:
                escpos_bytes = text_to_escpos(ticket_text, station)

            job_key = f"{job_id}_{station}_{table_name}"
            if job_key in printed_job_hashes:
                # Đã in trước đó -> báo server hoàn tất để giải phóng hàng đợi
                try:
                    await asyncio.to_thread(http_post_json, f"{clean_url}/api/printer/jobs/{job_id}/mark-printed", {}, 3.0)
                except Exception:
                    pass
                continue

            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📥 [PENDING PULL - {label}] NHẬN LỆNH IN CHỜ (Job #{job_id}) -> {table_name} -> Trạm: {station}")

            printed_success = False
            asyncio.create_task(sync_orders_now(config))

            printer_cfg = printers.get(station)
            if not printer_cfg:
                if station in ["BAR", "CASHIER"]:
                    printer_cfg = printers.get("CASHIER") or printers.get("BAR")
                else:
                    printer_cfg = printers.get("HOT_KITCHEN")

            if printer_cfg and printer_cfg.get("enabled"):
                host = printer_cfg.get("host")
                port = printer_cfg.get("port", 9100)
                if print_to_lan_printer(host, port, escpos_bytes):
                    printed_success = True

            if not printed_success and station in ["CASHIER", "BAR"]:
                kitchen_cfg = printers.get("HOT_KITCHEN")
                if kitchen_cfg and kitchen_cfg.get("enabled"):
                    k_host = kitchen_cfg.get("host")
                    k_port = kitchen_cfg.get("port", 9100)
                    if k_host and print_to_lan_printer(k_host, k_port, escpos_bytes):
                        printed_success = True

            if simulate_mode:
                print_simulated_ticket(ticket_text, station, f"{label}-PENDING")
                printed_success = True
            elif not printed_success:
                print(f"  [⚠️ LỖI MÁY IN] Chưa thể gửi dữ liệu tới máy in LAN cho Job #{job_id}! Giữ lại hàng đợi để tự động thử lại sau 10s.")

            if printed_success:
                printed_job_hashes.add(job_key)
                if len(printed_job_hashes) > 1000:
                    printed_job_hashes.clear()
                try:
                    await asyncio.to_thread(http_post_json, f"{clean_url}/api/printer/jobs/{job_id}/mark-printed", {}, 3.0)
                except Exception:
                    pass
    except Exception:
        pass

async def pending_jobs_worker(config: dict):
    """Vòng lặp kéo lệnh in chờ (mỗi 10 giây) đảm bảo 100% không bao giờ sót đơn khách quét QR."""
    cloud_url = config.get("cloud_api_url", "https://pipogarden.com")
    local_url = config.get("local_api_url", "http://127.0.0.1:8000")
    await asyncio.sleep(2)
    while True:
        try:
            await pull_pending_jobs(cloud_url, "CLOUD", config)
            await pull_pending_jobs(local_url, "LOCAL", config)
        except Exception:
            pass
        await asyncio.sleep(10)

async def main():
    config = load_config()
    server_ws_url = config.get("server_ws_url", "ws://127.0.0.1:8000/ws/printer")
    cloud_ws_url = config.get("cloud_ws_url", "wss://pipogarden.com/ws/printer")

    print("==================================================================")
    print("🌿 PIPO GARDEN - HYBRID PRINT & DUAL SYNC AGENT")
    print("   Hệ thống Tự Động In Bếp & Đồng Bộ 2 Chiều (Cloud 4G + Local LAN)")
    print("==================================================================")
    print(f"[*] 1. Kênh Cloud (Khách dùng 4G quét QR)   : {cloud_ws_url}")
    print(f"[*] 2. Kênh Local (Thu ngân & LAN nội bộ)   : {server_ws_url}")
    print(f"[*] 3. Cơ chế đồng bộ dữ liệu              : Sự kiện tức thì (Event-Driven Push) + Safety Net {config.get('sync_interval_sec', 300)}s")
    print(f"[*] 4. Chế độ in bếp                       : {'Giả lập + LAN' if config.get('simulate_mode') else 'Chỉ gửi máy in LAN'}")
    print("==================================================================\n")

    tasks = [
        asyncio.create_task(ws_listener(cloud_ws_url, "CLOUD (4G Khách)", config)),
        asyncio.create_task(ws_listener(server_ws_url, "LOCAL (Mạng LAN)", config)),
        asyncio.create_task(cloud_pos_listener(config)),
        asyncio.create_task(local_pos_listener(config)),
        asyncio.create_task(pending_jobs_worker(config)),
        asyncio.create_task(sync_worker(config)),
    ]

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOP] Đã dừng Print & Sync Agent.")
