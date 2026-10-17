"""
PiPo Garden - Thermal Printer Service Module (ESC/POS over TCP Socket)
Quản lý kết nối và in ấn trực tiếp tới 2 máy in nhiệt vật lý qua mạng LAN:
1. Máy in Bếp (KOT / Beeper): 192.168.31.251:9100
2. Máy in Thu ngân / Quầy Bar: 192.168.31.252:9100
"""

import socket
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from .database import get_db
from .escpos import (
    format_kitchen_ticket_text,
    format_receipt_ticket_text,
    build_escpos_bytes,
    build_escpos_kitchen_bytes,
    build_escpos_receipt_bytes
)

DEFAULT_KITCHEN_IP = "192.168.31.251"
DEFAULT_CASHIER_IP = "192.168.31.252"
DEFAULT_PORT = 9100

_PRINTER_CONFIG_CACHE = None

def get_printer_config(force_reload: bool = False) -> dict:
    """Lấy cấu hình IP và Port của 2 máy in từ CSDL system_settings (có in-memory cache chống lock SQLite)."""
    global _PRINTER_CONFIG_CACHE
    if _PRINTER_CONFIG_CACHE is not None and not force_reload:
        return _PRINTER_CONFIG_CACHE

    rows = {}
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM system_settings WHERE key LIKE 'printer_%'")
        rows = {r["key"]: r["value"] for r in cursor.fetchall()}
        conn.close()
    except Exception:
        pass

    cfg = {
        "kitchen_ip": rows.get("printer_kitchen_ip", DEFAULT_KITCHEN_IP),
        "kitchen_port": int(rows.get("printer_kitchen_port", DEFAULT_PORT)),
        "kitchen_enabled": rows.get("printer_kitchen_enabled", "1") == "1",
        "cashier_ip": rows.get("printer_cashier_ip", DEFAULT_CASHIER_IP),
        "cashier_port": int(rows.get("printer_cashier_port", DEFAULT_PORT)),
        "cashier_enabled": rows.get("printer_cashier_enabled", "1") == "1",
        "auto_kitchen": rows.get("printer_auto_kitchen", "1") == "1",
        "auto_cashier": rows.get("printer_auto_cashier", "1") == "1",
    }
    _PRINTER_CONFIG_CACHE = cfg
    return cfg

def save_printer_config(cfg: dict):
    """Lưu cấu hình máy in vào database và cập nhật cache tức thì."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    if "kitchen_ip" in cfg:
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('printer_kitchen_ip', ?)", (str(cfg["kitchen_ip"]),))
    if "kitchen_port" in cfg:
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('printer_kitchen_port', ?)", (str(cfg["kitchen_port"]),))
    if "kitchen_enabled" in cfg:
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('printer_kitchen_enabled', ?)", ("1" if cfg["kitchen_enabled"] else "0",))
    if "cashier_ip" in cfg:
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('printer_cashier_ip', ?)", (str(cfg["cashier_ip"]),))
    if "cashier_port" in cfg:
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('printer_cashier_port', ?)", (str(cfg["cashier_port"]),))
    if "cashier_enabled" in cfg:
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('printer_cashier_enabled', ?)", ("1" if cfg["cashier_enabled"] else "0",))
    if "auto_kitchen" in cfg:
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('printer_auto_kitchen', ?)", ("1" if cfg["auto_kitchen"] else "0",))
    if "auto_cashier" in cfg:
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('printer_auto_cashier', ?)", ("1" if cfg["auto_cashier"] else "0",))
    conn.commit()
    conn.close()
    get_printer_config(force_reload=True)

def send_escpos_to_printer(host: str, port: int, payload_bytes: bytes, timeout: float = 3.0) -> tuple[bool, str]:
    """Gửi dữ liệu ESC/POS trực tiếp tới máy in nhiệt qua TCP socket."""
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.sendall(payload_bytes)
        # Chờ socket flush
        time.sleep(0.05)
        s.close()
        return True, "Success"
    except Exception as e:
        if s:
            try:
                s.close()
            except Exception:
                pass
        return False, str(e)

def check_single_printer(host: str, port: int = 9100, timeout: float = 1.5) -> dict:
    """Kiểm tra trạng thái kết nối và đo độ trễ tới máy in."""
    t0 = time.time()
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        latency_ms = round((time.time() - t0) * 1000, 1)
        s.close()
        return {
            "status": "ONLINE",
            "host": host,
            "port": port,
            "latency_ms": latency_ms,
            "error": None
        }
    except Exception as e:
        if s:
            try:
                s.close()
            except Exception:
                pass
        return {
            "status": "OFFLINE",
            "host": host,
            "port": port,
            "latency_ms": None,
            "error": str(e)
        }

def get_printers_status() -> dict:
    """Kiểm tra đồng thời trạng thái 2 máy in."""
    cfg = get_printer_config()
    with ThreadPoolExecutor(max_workers=2) as pool:
        k_future = pool.submit(check_single_printer, cfg["kitchen_ip"], cfg["kitchen_port"])
        c_future = pool.submit(check_single_printer, cfg["cashier_ip"], cfg["cashier_port"])
        k_status = k_future.result()
        c_status = c_future.result()

    return {
        "kitchen": {
            "name": "Máy in Bếp (KOT / Beeper)",
            "role": "Bếp Nóng / Bếp Lạnh",
            **k_status,
            "enabled": cfg["kitchen_enabled"]
        },
        "cashier": {
            "name": "Máy in Thu ngân / Quầy Bar",
            "role": "Hóa đơn / Quầy Bar",
            **c_status,
            "enabled": cfg["cashier_enabled"]
        },
        "config": cfg,
        "timestamp": datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    }

def print_kitchen_order(order_info: dict, items: list, station: str = "HOT_KITCHEN", beep: bool = True) -> tuple[bool, str]:
    """In phiếu chế biến món ăn 80mm xuống Máy in Bếp 192.168.31.251 (kèm còi hú beeper 3 tiếng)."""
    cfg = get_printer_config()
    if not cfg["kitchen_enabled"]:
        return False, "Máy in bếp đang bị tắt trong cấu hình"

    escpos_bytes = build_escpos_kitchen_bytes(order_info, items, station=station, beep=beep)
    return send_escpos_to_printer(cfg["kitchen_ip"], cfg["kitchen_port"], escpos_bytes)

def print_cashier_receipt(table_info: dict, items: list, totals_info: dict = None) -> tuple[bool, str]:
    """
    In hóa đơn thanh toán / tạm tính 80mm xuống Máy in Thu ngân 192.168.31.252:
    Định dạng dòng 1 Tên món, dòng 2 SL x Đơn giá = Thành tiền.
    """
    cfg = get_printer_config()
    if not cfg["cashier_enabled"]:
        return False, "Máy in thu ngân đang bị tắt trong cấu hình"

    escpos_bytes = build_escpos_receipt_bytes(table_info, items, totals_info=totals_info)
    return send_escpos_to_printer(cfg["cashier_ip"], cfg["cashier_port"], escpos_bytes)

def test_kitchen_printer() -> tuple[bool, str]:
    """In phiếu test kiểm tra Máy in Bếp khổ 80mm kèm còi báo."""
    cfg = get_printer_config()
    sample_order = {
        "id": "TEST-80MM",
        "table_name": "BAN HO BOI 01",
        "area": "Khu Ho Boi",
        "round_number": 1,
        "customer_note": "KIEM TRA COI HU VA DAO CAT MAY IN T80W"
    }
    sample_items = [
        {"item_name": "Oc huong sot trung muoi", "quantity": 2, "note": "Kem 2 banh mi nong gion", "modifiers": []},
        {"item_name": "Muc trung chien mam nhi", "quantity": 1, "note": "It cay, gion rom", "modifiers": []},
        {"item_name": "Ga doi nuong muoi ot rung", "quantity": 1, "note": "Chat mieng vua an", "modifiers": []}
    ]
    payload = build_escpos_kitchen_bytes(sample_order, sample_items, station="HOT_KITCHEN", beep=True)
    return send_escpos_to_printer(cfg["kitchen_ip"], cfg["kitchen_port"], payload)

def test_cashier_printer() -> tuple[bool, str]:
    """In phiếu test kiểm tra Máy in Thu ngân / Quầy Bar khổ 80mm T80W."""
    cfg = get_printer_config()
    sample_table = {
        "name": "BAN HO BOI 01",
        "area": "Khu Ho Boi"
    }
    sample_items = [
        {"item_name": "Oc huong sot trung muoi", "quantity": 2, "unit_price": 165000, "total_price": 330000},
        {"item_name": "Suon heo nuong muoi ot", "quantity": 1, "unit_price": 185000, "total_price": 185000},
        {"item_name": "Tra Dao Cam Sa PiPo Special", "quantity": 2, "unit_price": 48000, "total_price": 96000}
    ]
    totals_info = {
        "title": "HOA DON TAM TINH (TEST 80MM)",
        "cashier_name": "Thu Ngan PiPo",
        "discount": 0,
        "vat": 0
    }
    payload = build_escpos_receipt_bytes(sample_table, sample_items, totals_info=totals_info)
    return send_escpos_to_printer(cfg["cashier_ip"], cfg["cashier_port"], payload)

async def async_dispatch_kitchen_print(order_info: dict, items: list, station: str = "HOT_KITCHEN", beep: bool = True):
    """Bắn lệnh in bếp bất đồng bộ trong background thread để không chặn API."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, print_kitchen_order, order_info, items, station, beep)

async def async_dispatch_cashier_print(table_info: dict, items: list, totals_info: dict = None):
    """Bắn lệnh in hóa đơn bất đồng bộ trong background thread để không chặn API."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, print_cashier_receipt, table_info, items, totals_info)
