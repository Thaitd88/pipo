import hmac
import hashlib
import time
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from ..database import get_db, hash_password

router = APIRouter(prefix="/api/auth", tags=["Auth & Staff"])

AUTH_SECRET = "pipo_garden_secure_hmac_secret_2026_key!"

def generate_session_token(username: str) -> str:
    """Tạo chữ ký HMAC-SHA256 chống giả mạo cookie."""
    ts = str(int(time.time()))
    payload = f"{username}:{ts}"
    sig = hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"

def verify_session_token(token: str) -> Optional[str]:
    """Kiểm tra tính hợp lệ của token chữ ký số."""
    if not token or ":" not in token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    username, ts, sig = parts[0], parts[1], parts[2]
    expected_payload = f"{username}:{ts}"
    expected_sig = hmac.new(AUTH_SECRET.encode(), expected_payload.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected_sig):
        return username
    return None

def get_current_user_from_request(request: Request) -> Optional[dict]:
    """Lấy thông tin người dùng từ cookie đã ký số hoặc cookie pipo_user."""
    username = None
    
    # 1. Thử giải mã token HMAC từ cookie pipo_session
    session_token = request.cookies.get("pipo_session")
    if session_token:
        username = verify_session_token(session_token)

    # 2. Dự phòng cookie pipo_user
    if not username:
        raw_user = request.cookies.get("pipo_user")
        if raw_user:
            username = raw_user.strip()

    # 3. Thử lấy từ Authorization header (Bearer token)
    if not username:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token_val = auth_header[7:].strip()
            verified = verify_session_token(token_val)
            username = verified or token_val

    if not username:
        return None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, full_name, role, phone, is_active 
        FROM users 
        WHERE username = ? AND is_active = 1
    """, (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def check_page_access(request: Request, allowed_roles: Optional[List[str]] = None):
    """
    Kiểm tra bảo mật khi truy cập các trang nội bộ:
    1. Chưa đăng nhập -> Chuyển hướng ngay về /?error=unauthorized&redirect=<path>
    2. Sai vai trò -> Chuyển hướng về trang đúng của vai trò đó kèm ?error=denied
    3. Đúng vai trò -> Trả về thông tin user
    """
    user = get_current_user_from_request(request)
    if not user:
        target_path = request.url.path
        return RedirectResponse(
            url=f"/login?error=unauthorized&redirect={target_path}",
            status_code=303
        )

    # Quyền tối cao (SUPER_ADMIN hoặc tài khoản Thaitd) luôn được phép truy cập tất cả các trang
    if user.get("role") == "SUPER_ADMIN" or user.get("username", "").lower() == "thaitd":
        return user

    if allowed_roles and user["role"] not in allowed_roles:
        role_default_pages = {
            "SUPER_ADMIN": "/admin",
            "ADMIN": "/admin",
            "CASHIER": "/pos",
            "CHEF": "/kitchen",
            "WAITER": "/pos"
        }
        dest = role_default_pages.get(user["role"], "/")
        return RedirectResponse(
            url=f"{dest}?error=denied",
            status_code=303
        )

    return user

def require_api_auth(request: Request, allowed_roles: Optional[List[str]] = None) -> dict:
    """Dependency bảo vệ các API nội bộ nhạy cảm."""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Yêu cầu đăng nhập để thực hiện thao tác này")
    
    # Quyền tối cao (SUPER_ADMIN hoặc tài khoản Thaitd) luôn có quyền thực hiện tất cả API
    if user.get("role") == "SUPER_ADMIN" or user.get("username", "").lower() == "thaitd":
        return user

    if allowed_roles and user["role"] not in allowed_roles:
        raise HTTPException(status_code=403, detail="Tài khoản không có quyền thực hiện thao tác này")
    return user

class LoginRequest(BaseModel):
    username: str
    password: str

class StaffCreateRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str # ADMIN, CASHIER, CHEF, WAITER
    phone: Optional[str] = ""

class StaffUpdateRequest(BaseModel):
    full_name: str
    role: str
    phone: Optional[str] = ""
    is_active: Optional[int] = 1
    new_password: Optional[str] = None

# ==========================================
# 1. ĐĂNG NHẬP / ĐĂNG XUẤT NHÂN VIÊN
# ==========================================

@router.post("/login")
def login(req: LoginRequest, response: Response, request: Request):
    username = req.username.strip()
    pwd_hash = hash_password(req.password)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, full_name, role, phone, is_active 
        FROM users 
        WHERE LOWER(username) = LOWER(?) AND password_hash = ?
    """, (username, pwd_hash))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không chính xác")

    if user["is_active"] != 1:
        raise HTTPException(status_code=403, detail="Tài khoản nhân viên này đã bị tạm khóa")

    user_dict = dict(user)
    
    # Tạo Token chữ ký HMAC-SHA256 an toàn
    token = generate_session_token(user["username"])
    
    # Đặt cookie bảo mật
    response.set_cookie(
        key="pipo_session",
        value=token,
        httponly=True,
        max_age=86400 * 7,
        samesite="lax",
        path="/"
    )
    response.set_cookie(
        key="pipo_user",
        value=user["username"],
        httponly=False,
        max_age=86400 * 7,
        samesite="lax",
        path="/"
    )

    role_redirects = {
        "SUPER_ADMIN": "/admin",
        "ADMIN": "/admin",
        "CASHIER": "/pos",
        "CHEF": "/kitchen",
        "WAITER": "/pos"
    }
    redirect_url = role_redirects.get(user["role"], "/admin")

    return {
        "status": "SUCCESS",
        "message": f"Chào mừng {user['full_name']} quay trở lại!",
        "redirect_url": redirect_url,
        "token": token,
        "user": user_dict
    }

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("pipo_session", path="/")
    response.delete_cookie("pipo_user", path="/")
    return {"status": "SUCCESS", "message": "Đã đăng xuất"}

@router.get("/me")
def get_current_user(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}

# ==========================================
# 2. QUẢN TRỊ DANH SÁCH NHÂN VIÊN (CRUD)
# ==========================================

@router.get("/staff")
def list_staff(request: Request):
    require_api_auth(request, allowed_roles=["ADMIN"])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, full_name, role, phone, is_active, created_at 
        FROM users 
        ORDER BY role, id ASC
    """)
    rows = cursor.fetchall()
    staff_list = [dict(r) for r in rows]
    conn.close()
    return staff_list

@router.post("/staff")
def create_staff(req: StaffCreateRequest, request: Request):
    require_api_auth(request, allowed_roles=["ADMIN"])
    username = req.username.strip().lower()
    if not username or not req.password or not req.full_name:
        raise HTTPException(status_code=400, detail="Vui lòng điền đầy đủ thông tin bắt buộc")

    valid_roles = ["ADMIN", "CASHIER", "CHEF", "WAITER"]
    if req.role not in valid_roles:
        raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"Tên đăng nhập '{username}' đã tồn tại")

    pwd_hash = hash_password(req.password)
    cursor.execute("""
        INSERT INTO users (username, password_hash, full_name, role, phone, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (username, pwd_hash, req.full_name.strip(), req.role, req.phone))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {"status": "SUCCESS", "message": "Đã tạo nhân viên mới thành công", "id": new_id}

@router.put("/staff/{user_id}")
def update_staff(user_id: int, req: StaffUpdateRequest, request: Request):
    require_api_auth(request, allowed_roles=["ADMIN"])
    valid_roles = ["ADMIN", "CASHIER", "CHEF", "WAITER"]
    if req.role not in valid_roles:
        raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")

    if req.new_password and req.new_password.strip():
        pwd_hash = hash_password(req.new_password.strip())
        cursor.execute("""
            UPDATE users 
            SET full_name = ?, role = ?, phone = ?, is_active = ?, password_hash = ?
            WHERE id = ?
        """, (req.full_name.strip(), req.role, req.phone, req.is_active, pwd_hash, user_id))
    else:
        cursor.execute("""
            UPDATE users 
            SET full_name = ?, role = ?, phone = ?, is_active = ?
            WHERE id = ?
        """, (req.full_name.strip(), req.role, req.phone, req.is_active, user_id))

    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "Đã cập nhật thông tin nhân viên"}

@router.delete("/staff/{user_id}")
def delete_staff(user_id: int, request: Request):
    require_api_auth(request, allowed_roles=["ADMIN"])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")

    if user["username"].lower() in ("admin", "thaitd"):
        conn.close()
        raise HTTPException(status_code=400, detail="Không thể xóa tài khoản Quản trị viên tối cao (Thaitd / admin)")

    # Xóa nhân viên
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "Đã xóa nhân viên thành công"}
