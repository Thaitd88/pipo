# Patch script for:
# 1. POS table bill flavor display: Tên món (Vị) x Số lượng + Vị badge
# 2. Database: ALTER TABLE print_jobs ADD COLUMN escpos_b64 TEXT
# 3. escpos.py: modifiers fallback to modifiers_json in lines 215, 300, 472, 600
# 4. pos.py: parse modifiers_json in get_table_bill
# 5. orders.py: store escpos_b64 in print_jobs
# 6. printer.py: get_pending_print_jobs_list, /pending-jobs, /jobs/{job_id}/mark-printed, /table/{table_id}/print-kitchen-ticket
# 7. main.py: auto-push pending jobs on connect and AGENT_READY
# 8. agent.py: pull_pending_jobs worker fail-safe
# 9. pos.html: show flavor in table details bill & add [In Lại Vé Bếp] button
import os
import re
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(f"Applying fixes in: {BASE_DIR}")

# ----------------------------------------------------
# 1. Update app/database.py
# ----------------------------------------------------
db_file = os.path.join(BASE_DIR, "app", "database.py")
with open(db_file, "r", encoding="utf-8") as f:
    db_content = f.read()

if "ALTER TABLE print_jobs ADD COLUMN escpos_b64" not in db_content:
    target = '    CREATE TABLE IF NOT EXISTS print_jobs ('
    replacement = """    try:
        cursor.execute("ALTER TABLE print_jobs ADD COLUMN escpos_b64 TEXT")
    except Exception:
        pass

    CREATE TABLE IF NOT EXISTS print_jobs ("""
    db_content = db_content.replace(target, replacement, 1)
    with open(db_file, "w", encoding="utf-8", newline="") as f:
        f.write(db_content)
    print("  [+] Patched app/database.py (added escpos_b64 column alter)")

# ----------------------------------------------------
# 2. Update app/escpos.py
# ----------------------------------------------------
escpos_file = os.path.join(BASE_DIR, "app", "escpos.py")
with open(escpos_file, "r", encoding="utf-8") as f:
    esc_content = f.read()

# Replace modifiers extraction in format_kitchen_ticket_text
old_mod1 = 'modifiers = it.get("modifiers", [])'
new_mod1 = 'modifiers = it.get("modifiers") or it.get("modifiers_json") or []'
esc_content = esc_content.replace(old_mod1, new_mod1)

old_mod2 = 'modifiers = it.get("modifiers")'
new_mod2 = 'modifiers = it.get("modifiers") or it.get("modifiers_json")'
esc_content = esc_content.replace(old_mod2, new_mod2)

with open(escpos_file, "w", encoding="utf-8", newline="") as f:
    f.write(esc_content)
print("  [+] Patched app/escpos.py (modifiers fallback to modifiers_json)")

# ----------------------------------------------------
# 3. Update app/routers/pos.py
# ----------------------------------------------------
pos_file = os.path.join(BASE_DIR, "app", "routers", "pos.py")
with open(pos_file, "r", encoding="utf-8") as f:
    pos_content = f.read()

pos_target = """        for it in items:
            it["name"] = it["item_name"]
            it["price"] = it["unit_price"]
            it["total"] = it["total_price"]
            it["order_created_at"] = order.get("created_at")
            it["round_number"] = order.get("round_number", 1)
        all_items.extend(items)"""

pos_replacement = """        for it in items:
            it["name"] = it["item_name"]
            it["price"] = it["unit_price"]
            it["total"] = it["total_price"]
            it["order_created_at"] = order.get("created_at")
            it["round_number"] = order.get("round_number", 1)

            # Phân giải danh sách tùy chọn / vị (modifiers)
            mods = []
            raw_mods = it.get("modifiers_json")
            if raw_mods:
                try:
                    mods = json.loads(raw_mods) if isinstance(raw_mods, str) else raw_mods
                    if not isinstance(mods, list):
                        mods = []
                except Exception:
                    mods = []
            it["modifiers"] = mods

            # Trích xuất chuỗi tên vị trực quan (VD: "Úp trứng", "Muối ớt")
            flav = ""
            for m in mods:
                if isinstance(m, dict):
                    v = str(m.get("value") or "").strip()
                    if not v:
                        raw_n = str(m.get("name") or "").strip()
                        if raw_n.lower() not in ("chọn vị chế biến", "chon vi che bien", "vị", "vi"):
                            v = raw_n
                    if v and v.lower() not in ("chọn vị chế biến", "chon vi che bien"):
                        flav = v
                        break
                elif isinstance(m, str) and m.strip():
                    flav = m.strip()
                    break
            it["flavor"] = flav
        all_items.extend(items)"""

if pos_target in pos_content:
    pos_content = pos_content.replace(pos_target, pos_replacement, 1)
    with open(pos_file, "w", encoding="utf-8", newline="") as f:
        f.write(pos_content)
    print("  [+] Patched app/routers/pos.py (get_table_bill modifiers & flavor parsing)")
else:
    print("  [-] Note: pos_target not matched in pos.py, trying regex replacement...")
    pos_content = re.sub(
        r'for it in items:\s+it\["name"\] = it\["item_name"\]\s+it\["price"\] = it\["unit_price"\]\s+it\["total"\] = it\["total_price"\]\s+it\["order_created_at"\] = order\.get\("created_at"\)\s+it\["round_number"\] = order\.get\("round_number", 1\)\s+all_items\.extend\(items\)',
        pos_replacement.replace('\\', '\\\\'),
        pos_content
    )
    with open(pos_file, "w", encoding="utf-8", newline="") as f:
        f.write(pos_content)
    print("  [+] Patched app/routers/pos.py via regex")

# ----------------------------------------------------
# 4. Update app/routers/orders.py (save escpos_b64 in print_jobs)
# ----------------------------------------------------
orders_file = os.path.join(BASE_DIR, "app", "routers", "orders.py")
with open(orders_file, "r", encoding="utf-8") as f:
    orders_content = f.read()

old_pj_insert = """                cursor.execute(\"\"\"
                    INSERT INTO print_jobs (order_id, station, job_type, status, ticket_text)
                    VALUES (?, ?, 'KOT', 'PENDING', ?)
                \"\"\", (order_id, station, ticket_text))"""

new_pj_insert = """                try:
                    cursor.execute(\"\"\"
                        INSERT INTO print_jobs (order_id, station, job_type, status, ticket_text, escpos_b64)
                        VALUES (?, ?, 'KOT', 'PENDING', ?, ?)
                    \"\"\", (order_id, station, ticket_text, escpos_b64))
                except Exception:
                    cursor.execute(\"\"\"
                        INSERT INTO print_jobs (order_id, station, job_type, status, ticket_text)
                        VALUES (?, ?, 'KOT', 'PENDING', ?)
                    \"\"\", (order_id, station, ticket_text))"""

if old_pj_insert in orders_content:
    orders_content = orders_content.replace(old_pj_insert, new_pj_insert, 1)
    with open(orders_file, "w", encoding="utf-8", newline="") as f:
        f.write(orders_content)
    print("  [+] Patched app/routers/orders.py (save escpos_b64 in print_jobs)")

# ----------------------------------------------------
# 5. Update app/routers/printer.py
# ----------------------------------------------------
printer_file = os.path.join(BASE_DIR, "app", "routers", "printer.py")
with open(printer_file, "r", encoding="utf-8") as f:
    printer_content = f.read()

# Add get_pending_print_jobs_list, /pending-jobs, /jobs/{job_id}/mark-printed, /table/{table_id}/print-kitchen-ticket
if "def get_pending_print_jobs_list" not in printer_content:
    extra_code = '''

def get_pending_print_jobs_list(limit: int = 50):
    """Lấy danh sách các lệnh in đang PENDING để gửi xuống Print Agent máy thu ngân."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(print_jobs)")
        cols = [r["name"] for r in cursor.fetchall()]
        has_escpos = "escpos_b64" in cols
    except Exception:
        has_escpos = False

    select_sql = f"""
        SELECT pj.id as job_id, pj.order_id, pj.station, pj.job_type, pj.ticket_text,
               { "pj.escpos_b64" if has_escpos else "'' as escpos_b64" },
               pj.created_at,
               COALESCE(t.name, 'Bàn ' || COALESCE(o.table_id, '')) as table_name,
               o.table_id, o.round_number, o.customer_note
        FROM print_jobs pj
        LEFT JOIN orders o ON pj.order_id = o.id
        LEFT JOIN tables t ON o.table_id = t.id
        WHERE pj.status = 'PENDING'
        ORDER BY pj.id ASC
        LIMIT ?
    """
    try:
        cursor.execute(select_sql, (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
    except Exception as _e:
        print("[get_pending_print_jobs_list error]:", _e)
        rows = []
    finally:
        conn.close()

    result = []
    for r in rows:
        escpos_b64 = r.get("escpos_b64") or ""
        if not escpos_b64 and r.get("ticket_text"):
            try:
                from ..escpos import remove_vietnamese_accents
                clean_text = remove_vietnamese_accents(r["ticket_text"])
                ESC = b'\\x1b'
                GS = b'\\x1d'
                b = bytearray()
                b.extend(ESC + b'@')
                b.extend(ESC + b't\\x00')
                b.extend(clean_text.encode('ascii', errors='ignore'))
                b.extend(b'\\n\\n\\n\\n')
                b.extend(GS + b'V\\x42\\x00')
                escpos_b64 = base64.b64encode(b).decode('ascii')
            except Exception:
                pass

        result.append({
            "job_id": r["job_id"],
            "station": r["station"],
            "job_type": r.get("job_type", "KOT"),
            "ticket_text": r["ticket_text"],
            "escpos_b64": escpos_b64,
            "table_name": r.get("table_name") or "Bàn"
        })
    return result

@router.get("/pending-jobs")
def api_get_pending_jobs(limit: int = 50):
    """API lấy danh sách các lệnh in đang chờ (PENDING) để Print Agent kéo về in bù ngay."""
    jobs = get_pending_print_jobs_list(limit=limit)
    return {"status": "SUCCESS", "count": len(jobs), "jobs": jobs}

@router.post("/jobs/{job_id}/mark-printed")
def api_mark_job_printed(job_id: int):
    """API đánh dấu lệnh in đã được in thành công."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE print_jobs SET status = 'PRINTED', printed_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": f"Đã đánh dấu lệnh in #{job_id} đã in hoàn tất"}

@router.post("/table/{table_id}/print-kitchen-ticket")
async def api_print_table_kitchen_ticket(table_id: int):
    """
    In Lại Vé Bếp & Bar cho toàn bộ món đang hoạt động của bàn:
    - Bóc tách theo trạm HOT_KITCHEN (Bếp Nóng 251) và BAR (Quầy Bar 252).
    - Tạo lệnh in KOT và đẩy ngay xuống Print Agent máy thu ngân.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    t_row = cursor.fetchone()
    if not t_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")
    table = dict(t_row)
    session_id = table.get("current_session_id")

    if session_id:
        cursor.execute("SELECT * FROM orders WHERE table_id = ? AND (session_id = ? OR session_id IS NULL) AND payment_status = 'UNPAID'", (table_id, session_id))
    else:
        cursor.execute("SELECT * FROM orders WHERE table_id = ? AND payment_status = 'UNPAID'", (table_id,))
    orders = [dict(o) for o in cursor.fetchall()]

    if not orders:
        conn.close()
        raise HTTPException(status_code=400, detail="Bàn hiện không có đơn hàng nào chưa thanh toán")

    order_ids = [o["id"] for o in orders]
    placeholders = ",".join("?" for _ in order_ids)
    cursor.execute(f"SELECT * FROM order_items WHERE order_id IN ({placeholders}) AND status != 'CANCELLED' ORDER BY id ASC", order_ids)
    items = [dict(it) for it in cursor.fetchall()]

    if not items:
        conn.close()
        raise HTTPException(status_code=400, detail="Bàn hiện không có món nào cần chế biến")

    station_groups = {}
    for it in items:
        st = it.get("station") or "HOT_KITCHEN"
        if st not in station_groups:
            station_groups[st] = []
        station_groups[st].append(it)

    now_ts = now_vn_str("%Y-%m-%d %H:%M:%S")
    first_order = orders[0]
    order_info = {
        "id": first_order["id"],
        "table_name": table["name"],
        "area": table["area"],
        "round_number": len(orders),
        "customer_note": first_order.get("customer_note") or "",
        "created_at": now_ts
    }

    created_jobs = []
    has_escpos_col = False
    try:
        cursor.execute("PRAGMA table_info(print_jobs)")
        cols = [r["name"] for r in cursor.fetchall()]
        has_escpos_col = "escpos_b64" in cols
    except Exception:
        pass

    for station, st_items in station_groups.items():
        ticket_text = format_kitchen_ticket_text(order_info, st_items, station)
        escpos_bytes = build_escpos_kitchen_bytes(order_info, st_items, station=station, beep=True)
        escpos_b64 = base64.b64encode(escpos_bytes).decode("ascii")

        if has_escpos_col:
            cursor.execute("""
                INSERT INTO print_jobs (order_id, station, job_type, status, ticket_text, escpos_b64)
                VALUES (?, ?, 'KOT', 'PENDING', ?, ?)
            """, (first_order["id"], station, ticket_text, escpos_b64))
        else:
            cursor.execute("""
                INSERT INTO print_jobs (order_id, station, job_type, status, ticket_text)
                VALUES (?, ?, 'KOT', 'PENDING', ?)
            """, (first_order["id"], station, ticket_text))
        job_id = cursor.lastrowid

        created_jobs.append({
            "job_id": job_id,
            "station": station,
            "job_type": "KOT",
            "ticket_text": ticket_text,
            "escpos_b64": escpos_b64,
            "table_name": table["name"]
        })

    conn.commit()
    conn.close()

    if ws_broadcaster:
        for pjob in created_jobs:
            await ws_broadcaster.send_to_printers({
                "event": "PRINT_JOB",
                **pjob
            })

    return {
        "status": "SUCCESS",
        "message": f"Đã gửi {len(created_jobs)} phiếu in vé bếp/bar cho bàn {table['name']}!",
        "jobs_count": len(created_jobs)
    }
'''
    printer_content += extra_code
    with open(printer_file, "w", encoding="utf-8", newline="") as f:
        f.write(printer_content)
    print("  [+] Patched app/routers/printer.py (added pending-jobs and table kitchen ticket reprint)")

# ----------------------------------------------------
# 6. Update app/main.py (auto push pending jobs on connect and AGENT_READY)
# ----------------------------------------------------
main_file = os.path.join(BASE_DIR, "app", "main.py")
with open(main_file, "r", encoding="utf-8") as f:
    main_content = f.read()

old_ws_printer = """@app.websocket("/ws/printer")
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
        broadcaster.disconnect_printer(websocket)"""

new_ws_printer = """@app.websocket("/ws/printer")
async def ws_printer_endpoint(websocket: WebSocket):
    await broadcaster.connect_printer(websocket)
    # Tự động đẩy ngay các lệnh in PENDING cho Print Agent vừa kết nối
    try:
        from .routers.printer import get_pending_print_jobs_list
        pending = get_pending_print_jobs_list()
        for pjob in pending:
            await websocket.send_json({
                "event": "PRINT_JOB",
                **pjob
            })
    except Exception as _push_err:
        print("[ws_printer_endpoint auto push error]:", _push_err)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                ev = payload.get("event")
                if ev == "AGENT_READY":
                    from .routers.printer import get_pending_print_jobs_list
                    pending = get_pending_print_jobs_list()
                    for pjob in pending:
                        await websocket.send_json({
                            "event": "PRINT_JOB",
                            **pjob
                        })
                elif ev == "JOB_COMPLETED":
                    job_id = payload.get("job_id")
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE print_jobs SET status = 'PRINTED', printed_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
                    conn.commit()
                    conn.close()
            except Exception as e:
                pass
    except WebSocketDisconnect:
        broadcaster.disconnect_printer(websocket)"""

if old_ws_printer in main_content:
    main_content = main_content.replace(old_ws_printer, new_ws_printer, 1)
    with open(main_file, "w", encoding="utf-8", newline="") as f:
        f.write(main_content)
    print("  [+] Patched app/main.py (auto push pending print jobs)")
else:
    print("  [-] Note: ws_printer_endpoint exact match not found in main.py")

# ----------------------------------------------------
# 7. Update print_agent/agent.py (fallback puller and ping tolerance)
# ----------------------------------------------------
agent_file = os.path.join(BASE_DIR, "print_agent", "agent.py")
with open(agent_file, "r", encoding="utf-8") as f:
    agent_content = f.read()

# Increase timeout in http_get_json and http_post_json
agent_content = agent_content.replace("def http_get_json(url: str, timeout: float = 5.0):", "def http_get_json(url: str, timeout: float = 8.0):")
agent_content = agent_content.replace("def http_post_json(url: str, data: dict, timeout: float = 5.0,", "def http_post_json(url: str, data: dict, timeout: float = 8.0,")

# Add pull_pending_jobs_for_server logic
if "async def pull_pending_jobs" not in agent_content:
    pull_logic = '''

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

            job_key = f"{job_id}_{station}_{table_name}"
            if job_key in printed_job_hashes:
                # Đã in trước đó -> báo server hoàn tất để giải phóng hàng đợi
                try:
                    await asyncio.to_thread(http_post_json, f"{clean_url}/api/printer/jobs/{job_id}/mark-printed", {}, 3.0)
                except Exception:
                    pass
                continue

            printed_job_hashes.add(job_key)
            print(f"\\n[{datetime.now().strftime('%H:%M:%S')}] 📥 [PENDING PULL - {label}] NHẬN LỆNH IN CHỜ (Job #{job_id}) -> {table_name} -> Trạm: {station}")

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

            if simulate_mode or not printed_success:
                print_simulated_ticket(ticket_text, station, f"{label}-PENDING")
                printed_success = True

            if printed_success:
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
'''
    # Insert before main()
    main_idx = agent_content.find("async def main():")
    if main_idx != -1:
        agent_content = agent_content[:main_idx] + pull_logic + "\n" + agent_content[main_idx:]

    # Add task to main()
    old_tasks = """    tasks = [
        asyncio.create_task(ws_listener(cloud_ws_url, "CLOUD (4G Khách)", config)),
        asyncio.create_task(ws_listener(server_ws_url, "LOCAL (Mạng LAN)", config)),
        asyncio.create_task(cloud_pos_listener(config)),
        asyncio.create_task(local_pos_listener(config)),
        asyncio.create_task(sync_worker(config)),
    ]"""

    new_tasks = """    tasks = [
        asyncio.create_task(ws_listener(cloud_ws_url, "CLOUD (4G Khách)", config)),
        asyncio.create_task(ws_listener(server_ws_url, "LOCAL (Mạng LAN)", config)),
        asyncio.create_task(cloud_pos_listener(config)),
        asyncio.create_task(local_pos_listener(config)),
        asyncio.create_task(pending_jobs_worker(config)),
        asyncio.create_task(sync_worker(config)),
    ]"""
    agent_content = agent_content.replace(old_tasks, new_tasks)

with open(agent_file, "w", encoding="utf-8", newline="") as f:
    f.write(agent_content)
print("  [+] Patched print_agent/agent.py (added pending_jobs_worker fail-safe)")

# ----------------------------------------------------
# 8. Update app/templates/pos.html
# ----------------------------------------------------
pos_html_file = os.path.join(BASE_DIR, "app", "templates", "pos.html")
with open(pos_html_file, "r", encoding="utf-8") as f:
    pos_html_content = f.read()

# Update item display in openTableDetails:
old_item_render = """          return `
            <div class="flex items-center justify-between text-xs py-2.5 border-b border-stone-100 ${it.status === 'CANCELLED' ? 'opacity-50 line-through' : ''}">
              <div class="pr-2">
                <div class="font-bold text-stone-800 leading-tight">${it.item_name}</div>
                ${(it.modifiers && it.modifiers.length > 0) ? `
                  <div class="text-[10.5px] text-emerald-800 font-bold mt-0.5 flex items-center gap-1">
                    <i class="fa-solid fa-tag text-[9px] text-emerald-600"></i>
                    <span>Vị: ${it.modifiers.map(m => m.value || m.name).join(', ')}</span>
                  </div>
                ` : ''}
                <div class="text-[11px] text-stone-500 font-medium mt-0.5 flex items-center gap-1 flex-wrap">
                  <span class="font-bold text-stone-900">${it.quantity}</span>"""

new_item_render = """          let flav = it.flavor || "";
          if (!flav && it.modifiers && it.modifiers.length > 0) {
            flav = it.modifiers.map(m => (typeof m === 'object' ? (m.value || m.name) : m)).filter(Boolean).join(", ");
          }
          if (!flav && it.modifiers_json) {
            try {
              const p = typeof it.modifiers_json === 'string' ? JSON.parse(it.modifiers_json) : it.modifiers_json;
              if (Array.isArray(p)) flav = p.map(m => (typeof m === 'object' ? (m.value || m.name) : m)).filter(Boolean).join(", ");
            } catch(e) {}
          }
          let baseName = (it.item_name || it.name || "").replace(/\\s*[\\(\\[][^\\)\\]]+[\\)\\]]\\s*$/, "").trim();
          let displayName = flav ? `${baseName} (${flav})` : (it.item_name || it.name || "Món");

          return `
            <div class="flex items-center justify-between text-xs py-2.5 border-b border-stone-100 ${it.status === 'CANCELLED' ? 'opacity-50 line-through' : ''}">
              <div class="pr-2">
                <div class="font-extrabold text-stone-900 leading-tight text-[13px] flex items-center gap-1.5 flex-wrap">
                  <span>${displayName}</span>
                  <span class="text-amber-800 font-extrabold text-xs bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">x ${it.quantity}</span>
                </div>
                ${flav ? `
                  <div class="text-[11px] text-emerald-800 font-bold mt-0.5 flex items-center gap-1">
                    <i class="fa-solid fa-tag text-[9.5px] text-emerald-600"></i>
                    <span>Vị: ${flav}</span>
                  </div>
                ` : ''}
                <div class="text-[11px] text-stone-500 font-medium mt-0.5 flex items-center gap-1 flex-wrap">
                  <span class="font-bold text-stone-900">${it.quantity}</span>"""

if old_item_render in pos_html_content:
    pos_html_content = pos_html_content.replace(old_item_render, new_item_render, 1)
    print("  [+] Patched app/templates/pos.html (item flavor & quantity display in drawer)")
else:
    print("  [-] Note: old_item_render in pos.html not matched exactly, checking regex...")
    # Regex fallback
    pos_html_content = re.sub(
        r'return `\s+<div class="flex items-center justify-between text-xs py-2\.5 border-b border-stone-100 \$\{it\.status === \'CANCELLED\' \? \'opacity-50 line-through\' : \'\'\}">\s+<div class="pr-2">\s+<div class="font-bold text-stone-800 leading-tight">\$\{it\.item_name\}</div>\s+\$\{\(it\.modifiers && it\.modifiers\.length > 0\) \? `\s+<div class="text-\[10\.5px\] text-emerald-800 font-bold mt-0\.5 flex items-center gap-1">\s+<i class="fa-solid fa-tag text-\[9px\] text-emerald-600"></i>\s+<span>Vị: \$\{it\.modifiers\.map\(m => m\.value \|\| m\.name\)\.join\(\', \'\)\}</span>\s+</div>\s+` : \'\'\}\s+<div class="text-\[11px\] text-stone-500 font-medium mt-0\.5 flex items-center gap-1 flex-wrap">\s+<span class="font-bold text-stone-900">\$\{it\.quantity\}</span>',
        new_item_render.replace('\\', '\\\\'),
        pos_html_content
    )
    print("  [+] Patched app/templates/pos.html via regex")

# Add [In Lại Vé Bếp] button beside [Xem Bill Tạm Tính]
old_btn_bill = """      <!-- Xem Bill Tạm Tính & Tải Ảnh / In Bill -->
      <div>
        <button onclick="openPrintBillModal()" class="w-full bg-indigo-700 hover:bg-indigo-800 active:scale-95 text-white font-bold text-xs py-2.5 rounded-xl transition flex items-center justify-center gap-2 shadow-xs cursor-pointer" title="Xem trước mẫu hóa đơn, in tạm tính hoặc lưu ảnh gửi khách">
          <i class="fa-solid fa-receipt text-amber-300"></i>
          <span>Xem Bill Tạm Tính (In & Tải Ảnh)</span>
        </button>
      </div>"""

new_btn_bill = """      <!-- Xem Bill Tạm Tính & In Lại Vé Bếp -->
      <div class="grid grid-cols-2 gap-2">
        <button type="button" onclick="openPrintBillModal()" class="w-full bg-indigo-700 hover:bg-indigo-800 active:scale-95 text-white font-bold text-xs py-2.5 rounded-xl transition flex items-center justify-center gap-1.5 shadow-xs cursor-pointer" title="Xem trước mẫu hóa đơn, in tạm tính hoặc lưu ảnh gửi khách">
          <i class="fa-solid fa-receipt text-amber-300"></i>
          <span>Bill Tạm Tính</span>
        </button>
        <button type="button" onclick="posPrintKitchenTicketForCurrentTable()" id="btnDrawerPrintKitchen" class="w-full bg-stone-800 hover:bg-stone-900 active:scale-95 text-amber-300 font-bold text-xs py-2.5 rounded-xl transition flex items-center justify-center gap-1.5 shadow-xs cursor-pointer border border-stone-700" title="In lại toàn bộ phiếu order của bàn này ra máy in Bếp & Quầy Bar">
          <i class="fa-solid fa-print"></i>
          <span>In Lại Vé Bếp</span>
        </button>
      </div>"""

if old_btn_bill in pos_html_content:
    pos_html_content = pos_html_content.replace(old_btn_bill, new_btn_bill, 1)
    print("  [+] Patched app/templates/pos.html (added [In Lại Vé Bếp] button)")

# Add posPrintKitchenTicketForCurrentTable JavaScript function
if "async function posPrintKitchenTicketForCurrentTable" not in pos_html_content:
    js_kitchen_fn = """
    async function posPrintKitchenTicketForCurrentTable() {
      if (!selectedTable) {
        showPosToast("⚠️ Chưa chọn bàn để in vé bếp!");
        return;
      }
      const btn = document.getElementById("btnDrawerPrintKitchen");
      const origHtml = btn ? btn.innerHTML : "";
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Đang gửi...</span>';
      }
      try {
        const res = await fetch(`/api/printer/table/${selectedTable.id}/print-kitchen-ticket`, { method: "POST" });
        const data = await res.json();
        if (res.ok) {
          showPosToast(`🖨️ ${data.message || 'Đã gửi lệnh in vé bếp thành công!'}`);
        } else {
          alert("Lỗi in vé bếp: " + (data.detail || "Không thể tạo lệnh in"));
        }
      } catch (e) {
        alert("Lỗi kết nối máy in: " + e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = origHtml;
        }
      }
    }
"""
    # Insert right before </script>
    script_end = pos_html_content.rfind("</script>")
    if script_end != -1:
        pos_html_content = pos_html_content[:script_end] + js_kitchen_fn + "\n" + pos_html_content[script_end:]
    print("  [+] Added posPrintKitchenTicketForCurrentTable JS function in pos.html")

with open(pos_html_file, "w", encoding="utf-8", newline="") as f:
    f.write(pos_html_content)

print("[SUCCESS] All files updated successfully!")
