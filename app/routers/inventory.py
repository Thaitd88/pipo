# Inventory & Recipe BOM router for PiPo Garden
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from ..database import get_db
from .auth import require_api_auth

router = APIRouter(prefix="/api/inventory", tags=["Inventory & BOM"])

class IngredientCreate(BaseModel):
    code: str
    name: str
    unit: str
    stock_quantity: float = 0.0
    min_stock: float = 5.0
    cost_price: int = 0
    supplier: Optional[str] = ""

class IngredientUpdate(BaseModel):
    name: str
    unit: str
    min_stock: float
    cost_price: int
    supplier: Optional[str] = ""

class StockImport(BaseModel):
    ingredient_id: int
    quantity: float
    unit_price: int
    supplier: Optional[str] = ""
    note: Optional[str] = ""
    created_by: Optional[str] = "Thủ kho"

class RecipeItem(BaseModel):
    ingredient_id: int
    quantity: float

class RecipeSave(BaseModel):
    items: List[RecipeItem]

# ==========================================
# 1. QUẢN LÝ DANH MỤC NGUYÊN VẬT LIỆU
# ==========================================

@router.get("/items")
def list_ingredients():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *, 
               CASE WHEN stock_quantity <= min_stock THEN 1 ELSE 0 END as is_low_stock
        FROM inventory_items
        ORDER BY is_low_stock DESC, name ASC
    """)
    rows = cursor.fetchall()
    items = [dict(r) for r in rows]
    conn.close()
    return items

@router.post("/items")
def create_ingredient(req: IngredientCreate, request: Request):
    require_api_auth(request, allowed_roles=["ADMIN", "CHEF", "CASHIER"])
    conn = get_db()
    cursor = conn.cursor()
    code = req.code.strip().upper()
    cursor.execute("SELECT id FROM inventory_items WHERE code = ?", (code,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"Mã NVL '{code}' đã tồn tại")

    cursor.execute("""
        INSERT INTO inventory_items (code, name, unit, stock_quantity, min_stock, cost_price, supplier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (code, req.name.strip(), req.unit.strip(), req.stock_quantity, req.min_stock, req.cost_price, req.supplier))
    new_id = cursor.lastrowid

    # Nếu có tồn ban đầu, ghi nhận giao dịch nhập đầu kỳ
    if req.stock_quantity > 0:
        cursor.execute("""
            INSERT INTO inventory_transactions (ingredient_id, transaction_type, quantity, unit_price, note, created_by)
            VALUES (?, 'IMPORT', ?, ?, 'Tồn kho ban đầu khi tạo mã', 'Hệ thống')
        """, (new_id, req.stock_quantity, req.cost_price))

    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "Đã thêm nguyên vật liệu mới", "id": new_id}

@router.put("/items/{item_id}")
def update_ingredient(item_id: int, req: IngredientUpdate, request: Request):
    require_api_auth(request, allowed_roles=["ADMIN", "CHEF", "CASHIER"])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy nguyên vật liệu")

    cursor.execute("""
        UPDATE inventory_items 
        SET name = ?, unit = ?, min_stock = ?, cost_price = ?, supplier = ?
        WHERE id = ?
    """, (req.name.strip(), req.unit.strip(), req.min_stock, req.cost_price, req.supplier, item_id))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "Đã cập nhật nguyên vật liệu"}

@router.delete("/items/{item_id}")
def delete_ingredient(item_id: int, request: Request):
    require_api_auth(request, allowed_roles=["ADMIN"])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory_items WHERE id = ?", (item_id,))
    cursor.execute("DELETE FROM recipe_bom WHERE ingredient_id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": "Đã xóa nguyên vật liệu"}

# ==========================================
# 2. NHẬP KHO NGUYÊN VẬT LIỆU
# ==========================================

@router.post("/import")
def import_stock(req: StockImport, request: Request):
    user = require_api_auth(request, allowed_roles=["ADMIN", "CHEF", "CASHIER"])
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="Số lượng nhập phải lớn hơn 0")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory_items WHERE id = ?", (req.ingredient_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy nguyên vật liệu")

    # Tăng tồn kho
    cursor.execute("""
        UPDATE inventory_items 
        SET stock_quantity = stock_quantity + ?,
            cost_price = ?,
            supplier = COALESCE(NULLIF(?, ''), supplier)
        WHERE id = ?
    """, (req.quantity, req.unit_price, req.supplier, req.ingredient_id))

    # Ghi log lịch sử giao dịch kho
    cursor.execute("""
        INSERT INTO inventory_transactions (ingredient_id, transaction_type, quantity, unit_price, note, created_by)
        VALUES (?, 'IMPORT', ?, ?, ?, ?)
    """, (req.ingredient_id, req.quantity, req.unit_price, req.note or f"Nhập kho {item['name']}", req.created_by))

    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": f"Đã nhập kho thành công +{req.quantity} {item['unit']} {item['name']}"}

@router.get("/transactions")
def list_transactions(limit: int = 50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, i.name as ingredient_name, i.unit, i.code as ingredient_code
        FROM inventory_transactions t
        JOIN inventory_items i ON t.ingredient_id = i.id
        ORDER BY t.created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    txs = [dict(r) for r in rows]
    conn.close()
    return txs

# ==========================================
# 3. ĐỊNH LƯỢNG MÓN ĂN (RECIPE BOM)
# ==========================================

@router.get("/recipes/{menu_item_id}")
def get_recipe_for_dish(menu_item_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, station FROM menu_items WHERE id = ?", (menu_item_id,))
    dish = cursor.fetchone()
    if not dish:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy món ăn")

    cursor.execute("""
        SELECT rb.id as bom_id, rb.ingredient_id, rb.quantity,
               i.name as ingredient_name, i.code as ingredient_code, i.unit, i.cost_price,
               (rb.quantity * i.cost_price) as ingredient_cost
        FROM recipe_bom rb
        JOIN inventory_items i ON rb.ingredient_id = i.id
        WHERE rb.menu_item_id = ?
        ORDER BY i.name ASC
    """, (menu_item_id,))
    ingredients = [dict(r) for r in cursor.fetchall()]
    total_cost = sum(r["ingredient_cost"] for r in ingredients)
    conn.close()

    return {
        "dish": dict(dish),
        "ingredients": ingredients,
        "total_cost": total_cost,
        "profit_margin": dish["price"] - total_cost
    }

@router.post("/recipes/{menu_item_id}")
def save_recipe_for_dish(menu_item_id: int, req: RecipeSave, request: Request):
    require_api_auth(request, allowed_roles=["ADMIN", "CHEF"])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM menu_items WHERE id = ?", (menu_item_id,))
    dish = cursor.fetchone()
    if not dish:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy món ăn")

    # Xóa định lượng cũ và ghi lại định lượng mới
    cursor.execute("DELETE FROM recipe_bom WHERE menu_item_id = ?", (menu_item_id,))
    for it in req.items:
        if it.quantity > 0:
            cursor.execute("""
                INSERT INTO recipe_bom (menu_item_id, ingredient_id, quantity)
                VALUES (?, ?, ?)
            """, (menu_item_id, it.ingredient_id, it.quantity))

    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "message": f"Đã lưu định lượng BOM cho món '{dish['name']}' thành công"}

@router.get("/menu-with-bom")
def get_menu_with_bom():
    """Lấy danh sách món ăn kèm theo thông tin định lượng BOM và giá vốn dự kiến."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.id, m.name, m.price, m.station, m.is_available, m.image_url,
               c.name as category_name,
               (SELECT COUNT(*) FROM recipe_bom rb WHERE rb.menu_item_id = m.id) as ingredients_count,
               (SELECT COALESCE(SUM(rb.quantity * ii.cost_price), 0)
                FROM recipe_bom rb 
                JOIN inventory_items ii ON rb.ingredient_id = ii.id
                WHERE rb.menu_item_id = m.id) as estimated_cost
        FROM menu_items m
        JOIN categories c ON m.category_id = c.id
        ORDER BY c.display_order, m.id
    """)
    dishes = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return dishes
