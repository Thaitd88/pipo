import sys
import os
import time

# Thiết lập múi giờ Việt Nam (UTC+7 / GMT+7)
os.environ["TZ"] = "Asia/Ho_Chi_Minh"
if hasattr(time, "tzset"):
    try:
        time.tzset()
    except Exception:
        pass

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import os
import json
from typing import Dict, List, Set

from .database import init_db, get_db
from .routers import tables, menu, orders, pos, auth, reports, inventory, sync, reservations, homepage_cms, pickleball, printer, accounting
from .routers.auth import check_page_access, get_current_user_from_request

# Connection Broadcaster
class ConnectionBroadcaster:
    def __init__(self):
        self.printers: Set[WebSocket] = set()
        self.kds: Set[WebSocket] = set()
        self.pos: Set[WebSocket] = set()
        self.customers: Dict[int, Set[WebSocket]] = {} # table_id -> Set[WebSocket]

    # 1. Local Print Agent connections
    async def connect_printer(self, ws: WebSocket):
        await ws.accept()
        self.printers.add(ws)

    def disconnect_printer(self, ws: WebSocket):
        self.printers.discard(ws)

    async def send_to_printers(self, message: dict):
        dead = []
        for ws in self.printers:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.printers.discard(ws)

    # 2. Kitchen Display System (KDS) connections
    async def connect_kds(self, ws: WebSocket):
        await ws.accept()
        self.kds.add(ws)

    def disconnect_kds(self, ws: WebSocket):
        self.kds.discard(ws)

    async def send_to_kds(self, message: dict):
        dead = []
        for ws in self.kds:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.kds.discard(ws)

    # 3. Cashier POS connections
    async def connect_pos(self, ws: WebSocket):
        await ws.accept()
        self.pos.add(ws)

    def disconnect_pos(self, ws: WebSocket):
        self.pos.discard(ws)

    async def send_to_pos(self, message: dict):
        dead = []
        for ws in self.pos:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.pos.discard(ws)

    # 4. Customer Mobile Web connections
    async def connect_customer(self, table_id: int, ws: WebSocket):
        await ws.accept()
        if table_id not in self.customers:
            self.customers[table_id] = set()
        self.customers[table_id].add(ws)

    def disconnect_customer(self, table_id: int, ws: WebSocket):
        if table_id in self.customers:
            self.customers[table_id].discard(ws)
            if not self.customers[table_id]:
                del self.customers[table_id]

    async def send_to_customer(self, table_id: int, message: dict):
        if table_id in self.customers:
            dead = []
            for ws in self.customers[table_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.customers[table_id].discard(ws)

broadcaster = ConnectionBroadcaster()

# Dependency injection for routers
orders.set_broadcaster(broadcaster)
pos.set_broadcaster(broadcaster)
reservations.set_broadcaster(broadcaster)
sync.set_broadcaster(broadcaster)
printer.set_broadcaster(broadcaster)
reports.set_broadcaster(broadcaster)
try:
    accounting.set_broadcaster(broadcaster)
except Exception:
    pass
try:
    pickleball.set_broadcaster(broadcaster)
except Exception:
    pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo DB khi bật server
    init_db()
    try:
        from .menu_syncer import ensure_updated_menu
        from .database import get_db
        ensure_updated_menu(get_db())
    except Exception as e:
        print(f'[MenuSyncer] Error ensuring updated menu: {e}')
    # Tự động đồng bộ các ảnh upload bền vững từ persistent storage vào static/dishes
    try:
        from .database import DATA_DIR
        persistent_uploads = os.path.join(DATA_DIR, "uploads")
        dishes_dir = os.path.join(STATIC_DIR, "dishes")
        if os.path.exists(persistent_uploads) and os.path.exists(dishes_dir):
            import shutil
            for fname in os.listdir(persistent_uploads):
                src = os.path.join(persistent_uploads, fname)
                dst = os.path.join(dishes_dir, fname)
                if os.path.isfile(src) and not os.path.exists(dst):
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
    except Exception:
        pass
        # Dong bo receipts chung tu
        persistent_receipts = os.path.join(DATA_DIR, "uploads", "receipts")
        static_receipts = os.path.join(STATIC_DIR, "uploads", "receipts")
        os.makedirs(static_receipts, exist_ok=True)
        if os.path.exists(persistent_receipts):
            import shutil
            for fname in os.listdir(persistent_receipts):
                src = os.path.join(persistent_receipts, fname)
                dst = os.path.join(static_receipts, fname)
                if os.path.isfile(src) and not os.path.exists(dst):
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
    print("[PiPo Garden] Co so du lieu va du lieu mau da san sang!")
    yield
    print("[PiPo Garden] Server dang tat.")

app = FastAPI(title="PiPo Garden Restaurant System", lifespan=lifespan)
@app.get("/health")
def health_check():
    """Endpoint kiem tra tinh trang hoat dong phuc vu Health Check Reverse Proxy."""
    return {"status": "ok", "app": "PiPo Garden Restaurant System"}

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount static và templates
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Include API Routers
app.include_router(tables.router)
app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(pos.router)
app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(inventory.router)
app.include_router(sync.router)
app.include_router(reservations.router)
app.include_router(homepage_cms.router)
app.include_router(pickleball.router)
app.include_router(printer.router)
app.include_router(accounting.router)

# PWA Progressive Web App Endpoints
@app.get("/manifest.json")
def get_pwa_manifest():
    manifest_path = os.path.join(STATIC_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/manifest+json")
    return {"name": "PiPo Garden"}

@app.get("/sw.js")
def get_pwa_service_worker():
    sw_path = os.path.join(STATIC_DIR, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})
    return HTMLResponse("", status_code=404)

# ==========================================
# WEBSOCKET ENDPOINTS
# ==========================================

@app.websocket("/ws/printer")
async def ws_printer_endpoint(websocket: WebSocket):
    await broadcaster.connect_printer(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("event") == "JOB_COMPLETED":
                    job_id = payload.get("job_id")
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE print_jobs SET status = 'PRINTED', printed_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
                    conn.commit()
                    conn.close()
            except Exception as e:
                pass
    except WebSocketDisconnect:
        broadcaster.disconnect_printer(websocket)

@app.websocket("/ws/kds")
async def ws_kds_endpoint(websocket: WebSocket):
    await broadcaster.connect_kds(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect_kds(websocket)

@app.websocket("/ws/pos")
async def ws_pos_endpoint(websocket: WebSocket):
    await broadcaster.connect_pos(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect_pos(websocket)

@app.websocket("/ws/customer/{table_id}")
async def ws_customer_endpoint(websocket: WebSocket, table_id: int):
    await broadcaster.connect_customer(table_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect_customer(table_id, websocket)

# ==========================================
# HTML PAGE ROUTES
# ==========================================

@app.get("/", response_class=HTMLResponse)
def home_page(request: Request):
    """Trang chủ quảng bá thương hiệu đẳng cấp PiPo Garden Phú Quốc."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE table_code LIKE 'HB%' OR area LIKE '%Hồ Bơi%' ORDER BY id ASC LIMIT 1")
    nh_row = cursor.fetchone()
    if not nh_row:
        cursor.execute("SELECT * FROM tables ORDER BY id ASC LIMIT 1")
        nh_row = cursor.fetchone()

    cursor.execute("SELECT * FROM tables WHERE table_code LIKE 'S2%' OR area LIKE '%Sảnh 2%' ORDER BY id ASC LIMIT 1")
    cf_row = cursor.fetchone()
    if not cf_row:
        cursor.execute("SELECT * FROM tables ORDER BY id DESC LIMIT 1")
        cf_row = cursor.fetchone()

    cursor.execute("SELECT key, value FROM homepage_cms")
    cms_settings = {r["key"]: r["value"] for r in cursor.fetchall()}
    conn.close()

    user = get_current_user_from_request(request)

    return templates.TemplateResponse(
        request=request, 
        name="home.html", 
        context={
            "user": user,
            "nh_table": dict(nh_row) if nh_row else None,
            "cf_table": dict(cf_row) if cf_row else None,
            "cms": cms_settings
        }
    )

@app.get("/portal", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
def staff_portal_page(request: Request):
    """Cổng Đăng Nhập & Phân Quyền Vai Trò Nhân Viên PiPo Garden."""
    user = get_current_user_from_request(request)
    error = request.query_params.get("error")
    redirect_target = request.query_params.get("redirect")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE table_code LIKE 'HB%' OR area LIKE '%Hồ Bơi%' ORDER BY id ASC LIMIT 1")
    nh_row = cursor.fetchone()
    if not nh_row:
        cursor.execute("SELECT * FROM tables ORDER BY id ASC LIMIT 1")
        nh_row = cursor.fetchone()

    cursor.execute("SELECT * FROM tables WHERE table_code LIKE 'S2%' OR area LIKE '%Sảnh 2%' ORDER BY id ASC LIMIT 1")
    cf_row = cursor.fetchone()
    if not cf_row:
        cursor.execute("SELECT * FROM tables ORDER BY id DESC LIMIT 1")
        cf_row = cursor.fetchone()
    conn.close()

    return templates.TemplateResponse(
        request=request, 
        name="portal.html", 
        context={
            "user": user,
            "error": error,
            "redirect_target": redirect_target,
            "nh_table": dict(nh_row) if nh_row else None,
            "cf_table": dict(cf_row) if cf_row else None
        }
    )

@app.get("/pickleball", response_class=HTMLResponse)
def pickleball_page(request: Request):
    """Trang Đặt Sân Pickleball Trực Tuyến & Xem Lịch 4 Sân PiPo Garden."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM homepage_cms")
    cms_settings = {r["key"]: r["value"] for r in cursor.fetchall()}
    conn.close()
    user = get_current_user_from_request(request)
    return templates.TemplateResponse(
        request=request,
        name="pickleball.html",
        context={
            "user": user,
            "cms": cms_settings
        }
    )

@app.get("/menu", response_class=HTMLResponse)
def menu_shortcut_page(request: Request):
    """Đường dẫn thực đơn demo trên website pipogarden.com/menu: Tách khỏi bàn ăn, chế độ đặt món trước & giữ bàn."""
    table_param = request.query_params.get("table")
    if table_param:
        return customer_page(request, table_param)

    conn = get_db()
    menu.ensure_system_settings_table(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_settings")
    settings_rows = {r["key"]: r["value"] for r in cursor.fetchall()}
    conn.close()

    menu_settings = {
        "morning_start_hour": int(settings_rows.get("morning_start_hour", 6)),
        "morning_end_hour": int(settings_rows.get("morning_end_hour", 11)),
        "routing_mode": settings_rows.get("routing_mode", "TIME_AND_BRANCH")
    }

    dummy_table = {
        "id": 0,
        "name": "Thực Đơn Trực Tuyến",
        "table_code": "ONLINE",
        "area": "Đặt Món Trước & Giữ Bàn",
        "branch_type": "RESTAURANT",
        "qr_token": "ONLINE"
    }

    res = templates.TemplateResponse(
        request=request,
        name="customer.html",
        context={
            "table": dummy_table,
            "qr_token": "ONLINE",
            "menu_settings": menu_settings,
            "is_preorder": True
        }
    )
    res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    res.headers["Pragma"] = "no-cache"
    res.headers["Expires"] = "0"
    return res

@app.get("/c/{qr_token}", response_class=HTMLResponse)
@app.get("/table/{qr_token}", response_class=HTMLResponse)
def customer_page(request: Request, qr_token: str):
    """Trang gọi món tại bàn dành riêng cho thực khách quét mã QR."""
    conn = get_db()
    menu.ensure_system_settings_table(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE qr_token = ? OR UPPER(table_code) = UPPER(?)", (qr_token, qr_token))
    table = cursor.fetchone()
    if not table and (qr_token == "e6c08568cf3aaffa" or qr_token.startswith("NH") or qr_token.startswith("CF")):
        cursor.execute("SELECT * FROM tables ORDER BY id ASC LIMIT 1")
        table = cursor.fetchone()
    cursor.execute("SELECT key, value FROM system_settings")
    settings_rows = {r["key"]: r["value"] for r in cursor.fetchall()}
    conn.close()

    if not table:
        return HTMLResponse(content="<div style='text-align:center;padding:50px;font-family:sans-serif;'><h2>Mã QR không hợp lệ hoặc không tồn tại</h2><p>Vui lòng báo nhân viên phục vụ để được hỗ trợ.</p></div>", status_code=404)

    table_dict = dict(table)
    actual_qr_token = table_dict["qr_token"]
    area_str = (table_dict.get("area") or "").lower()
    code_str = (table_dict.get("table_code") or "").upper()
    name_str = (table_dict.get("name") or "").lower()
    if "cafe" in area_str or "sáng" in area_str or code_str.startswith("CF") or "cafe" in name_str:
        table_dict["branch_type"] = "CAFE"
    elif "pickle" in area_str or code_str.startswith("PK") or "pickle" in name_str:
        table_dict["branch_type"] = "PICKLE"
    else:
        table_dict["branch_type"] = "RESTAURANT"

    menu_settings = {
        "morning_start_hour": int(settings_rows.get("morning_start_hour", 6)),
        "morning_end_hour": int(settings_rows.get("morning_end_hour", 11)),
        "routing_mode": settings_rows.get("routing_mode", "TIME_AND_BRANCH")
    }

    res = templates.TemplateResponse(
        request=request,
        name="customer.html",
        context={
            "table": table_dict,
            "qr_token": actual_qr_token,
            "menu_settings": menu_settings,
            "is_preorder": False
        }
    )
    res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    res.headers["Pragma"] = "no-cache"
    res.headers["Expires"] = "0"
    return res

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard_page(request: Request):
    """Trang Dashboard Quản Trị Trung Tâm PiPo Garden: Bắt buộc đăng nhập, chỉ cho phép ADMIN."""
    auth_check = check_page_access(request, allowed_roles=["ADMIN"])
    if isinstance(auth_check, RedirectResponse):
        return auth_check
    return templates.TemplateResponse(request=request, name="admin.html", context={"user": auth_check})

@app.get("/kds", response_class=HTMLResponse)
def kds_page(request: Request):
    """Màn hình KDS: Bắt buộc đăng nhập, chỉ cho phép CHEF hoặc ADMIN."""
    auth_check = check_page_access(request, allowed_roles=["CHEF", "ADMIN"])
    if isinstance(auth_check, RedirectResponse):
        return auth_check
    return templates.TemplateResponse(request=request, name="kds.html", context={"user": auth_check})

@app.get("/kitchen", response_class=HTMLResponse)
def kitchen_hub_page(request: Request):
    """Không gian Bếp toàn diện: Bắt buộc đăng nhập, chỉ cho phép CHEF hoặc ADMIN."""
    auth_check = check_page_access(request, allowed_roles=["CHEF", "ADMIN"])
    if isinstance(auth_check, RedirectResponse):
        return auth_check
    return templates.TemplateResponse(request=request, name="kitchen.html", context={"user": auth_check})

@app.get("/waiter", response_class=HTMLResponse)
def waiter_page(request: Request):
    """Trang Phục vụ: Tạm thời chuyển hướng sang POS/Thu ngân."""
    return RedirectResponse(url="/pos", status_code=303)

@app.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request):
    """Trang Quản lý Kho: Bắt buộc đăng nhập, cho phép ADMIN, CHEF, CASHIER."""
    auth_check = check_page_access(request, allowed_roles=["ADMIN", "CHEF", "CASHIER"])
    if isinstance(auth_check, RedirectResponse):
        return auth_check
    return templates.TemplateResponse(request=request, name="inventory.html", context={"user": auth_check})

@app.get("/pos", response_class=HTMLResponse)
def pos_page(request: Request):
    """Trang Quản trị, Thu ngân & Phục vụ: Bắt buộc đăng nhập, cho phép ADMIN, CASHIER, WAITER, PICKLEBALL."""
    auth_check = check_page_access(request, allowed_roles=["ADMIN", "CASHIER", "WAITER", "PICKLEBALL"])
    if isinstance(auth_check, RedirectResponse):
        return auth_check
    return templates.TemplateResponse(request=request, name="pos.html", context={"user": auth_check})

@app.get("/pos-pickle", response_class=HTMLResponse)
def pos_pickle_page(request: Request):
    """Trang POS chuyên biệt Sân Pickleball: Bắt buộc đăng nhập, cho phép PICKLEBALL, CASHIER, ADMIN."""
    auth_check = check_page_access(request, allowed_roles=["ADMIN", "CASHIER", "PICKLEBALL"])
    if isinstance(auth_check, RedirectResponse):
        return auth_check
    return templates.TemplateResponse(request=request, name="pos_pickle.html", context={"user": auth_check})

@app.get("/print-qrcodes", response_class=HTMLResponse)
def print_qrcodes_page(request: Request):
    """Trang xuất và in toàn bộ mã QR của tất cả các bàn chuẩn khổ A4."""
    return templates.TemplateResponse(request=request, name="print_qrcodes.html", context={})

@app.get("/printer-monitor", response_class=HTMLResponse)
def printer_monitor_page(request: Request):
    """Máy in bếp ảo: Bắt buộc đăng nhập, cho phép ADMIN, CASHIER, CHEF."""
    auth_check = check_page_access(request, allowed_roles=["ADMIN", "CASHIER", "CHEF"])
    if isinstance(auth_check, RedirectResponse):
        return auth_check
    return templates.TemplateResponse(request=request, name="printer_monitor.html", context={"user": auth_check})
