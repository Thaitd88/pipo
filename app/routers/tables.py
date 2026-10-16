# Table and QR Code management router for PiPo Garden
from fastapi import APIRouter, HTTPException, Depends, Response, Request
from pydantic import BaseModel
from typing import Optional, List
import io
import json
import qrcode
from ..database import get_db, generate_qr_token

router = APIRouter(prefix="/api/tables", tags=["Tables"])

class TableCreateRequest(BaseModel):
    table_code: str
    name: str
    area: str
    capacity: Optional[int] = 4

class TableUpdateRequest(BaseModel):
    table_code: Optional[str] = None
    name: Optional[str] = None
    area: Optional[str] = None
    capacity: Optional[int] = None

class AreaCreateRequest(BaseModel):
    name: str
    icon: Optional[str] = "🌿"
    description: Optional[str] = None

class AreaUpdateRequest(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None

@router.get("")
def list_tables(status: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT t.*, 
               s.id as active_session_id, s.session_token, s.guest_count, s.opened_at,
               (SELECT COUNT(*) FROM orders o WHERE o.table_id = t.id AND o.payment_status = 'UNPAID') as unpaid_orders_count,
               (SELECT COALESCE(SUM(total), 0) FROM orders o WHERE o.table_id = t.id AND o.payment_status = 'UNPAID') as current_bill_total
        FROM tables t
        LEFT JOIN table_sessions s ON t.id = s.table_id AND s.status = 'ACTIVE'
    """
    params = []
    if status:
        query += " WHERE UPPER(t.status) = ?"
        params.append(status.upper().strip())
    query += " ORDER BY t.area, t.table_code"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    tables = [dict(r) for r in rows]
    conn.close()
    return tables

@router.get("/areas")
def list_areas():
    """Lấy danh sách các khu vực bàn kèm số lượng bàn."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS restaurant_areas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        icon TEXT DEFAULT '🌿',
        description TEXT,
        display_order INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("SELECT DISTINCT area FROM tables WHERE area IS NOT NULL AND area != ''")
    table_areas = [r["area"] for r in cursor.fetchall()]
    for a in table_areas:
        cursor.execute("INSERT OR IGNORE INTO restaurant_areas (name) VALUES (?)", (a,))
    conn.commit()

    cursor.execute("""
        SELECT a.id, a.name, a.icon, a.description,
               COUNT(t.id) as table_count
        FROM restaurant_areas a
        LEFT JOIN tables t ON t.area = a.name
        GROUP BY a.id, a.name
        ORDER BY a.display_order, a.id
    """)
    rows = cursor.fetchall()
    areas = [dict(r) for r in rows]
    conn.close()
    return areas

@router.post("/areas")
def create_area(req: AreaCreateRequest):
    """Thêm khu vực bàn mới."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tên khu vực không được để trống")
    icon = req.icon.strip() if req.icon else "🌿"
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM restaurant_areas WHERE name = ?", (name,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"Khu vực '{name}' đã tồn tại")
    
    cursor.execute("INSERT INTO restaurant_areas (name, icon, description) VALUES (?, ?, ?)", 
                   (name, icon, req.description))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": f"Đã thêm khu vực '{name}' thành công", "area": {"id": new_id, "name": name, "icon": icon, "table_count": 0}}

@router.put("/areas/{area_id}")
def update_area(area_id: int, req: AreaUpdateRequest):
    """Đổi tên hoặc biểu tượng khu vực bàn, tự động cập nhật các bàn liên quan."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM restaurant_areas WHERE id = ?", (area_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Khu vực không tồn tại")
    
    old_name = existing["name"]
    new_name = req.name.strip() if req.name else old_name
    new_icon = req.icon.strip() if req.icon else (existing["icon"] or "🌿")
    new_desc = req.description if req.description is not None else existing["description"]

    if new_name != old_name:
        cursor.execute("SELECT id FROM restaurant_areas WHERE name = ? AND id != ?", (new_name, area_id))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail=f"Khu vực '{new_name}' đã tồn tại")
        cursor.execute("UPDATE tables SET area = ? WHERE area = ?", (new_name, old_name))

    cursor.execute("UPDATE restaurant_areas SET name = ?, icon = ?, description = ? WHERE id = ?", 
                   (new_name, new_icon, new_desc, area_id))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": f"Đã cập nhật khu vực '{new_name}' thành công", "area": {"id": area_id, "name": new_name, "icon": new_icon}}

@router.delete("/areas/{area_id}")
def delete_area(area_id: int):
    """Xóa khu vực bàn."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM restaurant_areas WHERE id = ?", (area_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Khu vực không tồn tại")
    
    area_name = existing["name"]
    cursor.execute("SELECT COUNT(*) as count FROM tables WHERE area = ?", (area_name,))
    cnt = cursor.fetchone()["count"]
    if cnt > 0:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Không thể xóa khu vực '{area_name}' vì đang có {cnt} bàn thuộc khu vực này! Hãy đổi khu vực các bàn trước khi xóa.")

    cursor.execute("DELETE FROM restaurant_areas WHERE id = ?", (area_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": f"Đã xóa khu vực '{area_name}' thành công"}

@router.post("")
def create_table(req: TableCreateRequest):
    """Thêm bàn ăn mới vào hệ thống kèm mã QR quét gọi món."""
    code = req.table_code.strip().upper()
    name = req.name.strip()
    area = req.area.strip()
    cap = req.capacity or 4

    if not code or not name or not area:
        raise HTTPException(status_code=400, detail="Vui lòng nhập đầy đủ mã bàn, tên bàn và khu vực")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tables WHERE table_code = ?", (code,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"Mã bàn '{code}' đã tồn tại trong hệ thống")

    qr_token = generate_qr_token(code)
    cursor.execute("""
        INSERT INTO tables (table_code, name, area, capacity, qr_token, status)
        VALUES (?, ?, ?, ?, ?, 'VACANT')
    """, (code, name, area, cap, qr_token))
    new_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM tables WHERE id = ?", (new_id,))
    created = dict(cursor.fetchone())
    conn.close()

    return {"status": "SUCCESS", "message": f"Đã thêm {name} thành công", "table": created}

@router.put("/{table_id}")
def update_table(table_id: int, req: TableUpdateRequest):
    """Chỉnh sửa thông tin bàn hoặc chuyển khu vực."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")

    curr = dict(existing)
    new_code = req.table_code.strip().upper() if req.table_code else curr["table_code"]
    new_name = req.name.strip() if req.name else curr["name"]
    new_area = req.area.strip() if req.area else curr["area"]
    new_cap = req.capacity if req.capacity is not None else curr["capacity"]

    # Kiểm tra mã bàn trùng
    if new_code != curr["table_code"]:
        cursor.execute("SELECT id FROM tables WHERE table_code = ? AND id != ?", (new_code, table_id))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail=f"Mã bàn '{new_code}' đã tồn tại")

    cursor.execute("""
        UPDATE tables 
        SET table_code = ?, name = ?, area = ?, capacity = ?
        WHERE id = ?
    """, (new_code, new_name, new_area, new_cap, table_id))
    conn.commit()

    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    updated = dict(cursor.fetchone())
    conn.close()

    return {"status": "SUCCESS", "message": f"Đã cập nhật {new_name} thành công", "table": updated}

@router.delete("/{table_id}")
def delete_table(table_id: int):
    """Xóa bàn khỏi hệ thống (chỉ cho phép xóa khi bàn không có khách hoặc hóa đơn chưa thanh toán)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    table = cursor.fetchone()
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")

    # Kiểm tra đơn chưa thanh toán
    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE table_id = ? AND payment_status = 'UNPAID'", (table_id,))
    if cursor.fetchone()["count"] > 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Không thể xóa bàn này vì đang có hóa đơn chưa thanh toán!")

    # Kiểm tra session active
    cursor.execute("SELECT COUNT(*) as count FROM table_sessions WHERE table_id = ? AND status = 'ACTIVE'", (table_id,))
    if cursor.fetchone()["count"] > 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Bàn đang có khách ngồi. Vui lòng đóng phiên bàn trước khi xóa!")

    cursor.execute("DELETE FROM tables WHERE id = ?", (table_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": f"Đã xóa bàn {table['name']} thành công"}

@router.get("/token/{qr_token}")
def get_table_by_token(qr_token: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE qr_token = ?", (qr_token,))
    table = cursor.fetchone()
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Mã QR không hợp lệ hoặc không tồn tại trong hệ thống")
    
    table_dict = dict(table)
    
    # Lấy phiên bàn hiện tại nếu có
    cursor.execute("SELECT * FROM table_sessions WHERE table_id = ? AND status = 'ACTIVE'", (table_dict["id"],))
    session = cursor.fetchone()
    
    conn.close()
    return {
        "table": table_dict,
        "active_session": dict(session) if session else None
    }

@router.post("/{table_code}/open-session")
def open_table_session(table_code: str, payload: dict = None):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tables WHERE table_code = ?", (table_code,))
    table = cursor.fetchone()
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy bàn")
    
    # Kiểm tra xem đã có session active chưa
    cursor.execute("SELECT * FROM table_sessions WHERE table_id = ? AND status = 'ACTIVE'", (table_id := table["id"],))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return {"status": "SUCCESS", "message": "Phiên bàn đã tồn tại", "session": dict(existing)}
    
    import uuid
    session_token = f"sess_{uuid.uuid4().hex[:12]}"
    guest_count = payload.get("guest_count", 2) if payload else 2
    
    cursor.execute("""
        INSERT INTO table_sessions (table_id, session_token, guest_count, status)
        VALUES (?, ?, ?, 'ACTIVE')
    """, (table["id"], session_token, guest_count))
    session_id = cursor.lastrowid
    
    cursor.execute("UPDATE tables SET status = 'OCCUPIED', current_session_id = ? WHERE id = ?", (session_id, table["id"]))
    conn.commit()
    
    cursor.execute("SELECT * FROM table_sessions WHERE id = ?", (session_id,))
    new_session = cursor.fetchone()
    conn.close()
    
    return {"status": "CREATED", "session": dict(new_session)}

@router.get("/{table_code}/qr-image")
def get_table_qr_image(table_code: str, request: Request, base_url: str = None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE table_code = ?", (table_code,))
    table = cursor.fetchone()
    conn.close()
    
    if not table:
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")
    
    # Xác định Base URL cho mã QR quét tại bàn
    import os
    if not base_url:
        env_base = os.getenv("BASE_URL")
        if env_base:
            base_url = env_base
        else:
            # Tự động nhận diện domain live thực tế từ request
            base_url = str(request.base_url).rstrip("/")

    base_url = base_url.rstrip("/")
    # URL mà điện thoại khách sẽ mở khi quét QR
    order_url = f"{base_url}/table/{table['qr_token']}"
    
    # Tạo hình ảnh QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(order_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e3a1e", back_color="#ffffff")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    return Response(content=buf.getvalue(), media_type="image/png")
