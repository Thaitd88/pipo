# Router for Homepage CMS (Content Management System)
import os
import shutil
import time
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
from ..database import get_db

router = APIRouter(prefix="/api/homepage", tags=["Homepage CMS"])

HOME_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "home")
os.makedirs(HOME_STATIC_DIR, exist_ok=True)

class CMSUpdatePayload(BaseModel):
    settings: Dict[str, Any]

@router.get("/cms")
def get_homepage_cms():
    """Lấy toàn bộ nội dung cấu hình trang chủ."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM homepage_cms")
    rows = cursor.fetchall()
    conn.close()
    
    settings = {r["key"]: r["value"] for r in rows}
    return {
        "status": "SUCCESS",
        "settings": settings
    }

@router.post("/cms")
def update_homepage_cms(payload: CMSUpdatePayload):
    """Cập nhật các mục nội dung trang chủ."""
    if not payload.settings:
        raise HTTPException(status_code=400, detail="Dữ liệu cập nhật không được để trống.")
    
    conn = get_db()
    cursor = conn.cursor()
    for key, val in payload.settings.items():
        val_str = str(val) if val is not None else ""
        cursor.execute("""
            INSERT INTO homepage_cms (key, value, updated_at) 
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """, (key, val_str))
    
    conn.commit()
    
    cursor.execute("SELECT key, value FROM homepage_cms")
    all_rows = {r["key"]: r["value"] for r in cursor.fetchall()}
    conn.close()
    
    return {
        "status": "SUCCESS",
        "message": "Đã lưu cài đặt trang chủ thành công!",
        "settings": all_rows
    }

@router.post("/cms/upload")
async def upload_homepage_image(file: UploadFile = File(...)):
    """Tải lên hình ảnh banner hoặc hình ảnh không gian trang chủ."""
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".svg", ".avif"}
    filename = file.filename or "upload.jpg"
    _, ext = os.path.splitext(filename.lower())
    
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Định dạng file không hỗ trợ. Vui lòng tải file ảnh (.jpg, .png, .webp, .svg).")
    
    # Tạo tên file an toàn kèm timestamp
    clean_stem = "".join(c for c in os.path.splitext(filename)[0] if c.isalnum() or c in ("-", "_"))[:30]
    safe_name = f"{clean_stem}_{int(time.time())}{ext}"
    target_path = os.path.join(HOME_STATIC_DIR, safe_name)
    
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể lưu ảnh: {str(e)}")
        
    public_url = f"/static/home/{safe_name}"
    return {
        "status": "SUCCESS",
        "message": "Tải ảnh lên thành công!",
        "url": public_url,
        "filename": safe_name
    }
