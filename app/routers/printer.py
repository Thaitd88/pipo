# Thermal Printer Management & Control Router for PiPo Garden
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from ..printer_service import (
    get_printers_status,
    get_printer_config,
    save_printer_config,
    test_kitchen_printer,
    test_cashier_printer,
    print_cashier_receipt,
    async_dispatch_cashier_print
)
from ..database import get_db

router = APIRouter(prefix="/api/printer", tags=["Printer Control"])

class PrinterConfigPayload(BaseModel):
    kitchen_ip: Optional[str] = "192.168.31.251"
    kitchen_port: Optional[int] = 9100
    kitchen_enabled: Optional[bool] = True
    cashier_ip: Optional[str] = "192.168.31.252"
    cashier_port: Optional[int] = 9100
    cashier_enabled: Optional[bool] = True
    auto_kitchen: Optional[bool] = True
    auto_cashier: Optional[bool] = True

@router.get("/status")
def api_get_printer_status():
    """Kiểm tra thời gian thực trạng thái kết nối socket port 9100 của cả 2 máy in."""
    return get_printers_status()

@router.get("/config")
def api_get_printer_config():
    """Lấy thông số cấu hình IP, Port của hệ thống máy in."""
    return get_printer_config()

@router.post("/config")
def api_save_printer_config(payload: PrinterConfigPayload):
    """Cập nhật địa chỉ IP và Port cho Máy in Bếp và Máy in Thu ngân."""
    cfg = payload.model_dump(exclude_unset=True)
    save_printer_config(cfg)
    return {"status": "SUCCESS", "message": "Đã lưu cấu hình máy in thành công!", "config": get_printer_config()}

@router.post("/test/kitchen")
def api_test_kitchen():
    """In phiếu kiểm tra Máy in Bếp (192.168.31.251:9100) có còi hú beeper."""
    ok, msg = test_kitchen_printer()
    if not ok:
        raise HTTPException(status_code=500, detail=f"Không thể in tới Máy in Bếp: {msg}")
    return {"status": "SUCCESS", "message": "Đã gửi lệnh in test thành công tới Máy in Bếp (192.168.31.251)!"}

@router.post("/test/cashier")
def api_test_cashier():
    """In phiếu kiểm tra Máy in Thu ngân (192.168.31.252:9100) theo chuẩn 2 dòng."""
    ok, msg = test_cashier_printer()
    if not ok:
        raise HTTPException(status_code=500, detail=f"Không thể in tới Máy in Thu ngân: {msg}")
    return {"status": "SUCCESS", "message": "Đã gửi lệnh in test thành công tới Máy in Thu ngân (192.168.31.252)!"}

@router.post("/table/{table_id}/print-bill")
async def api_print_table_bill(table_id: int, background_tasks: BackgroundTasks):
    """
    Thu ngân bấm 'In Hóa Đơn Tạm Tính' trên màn hình POS:
    - Bóc tách toàn bộ món của bàn hiện tại.
    - Định dạng dòng 1 Tên món, dòng 2 SL x Đơn giá = Thành tiền.
    - Đẩy lệnh in tức thì xuống Máy in Thu ngân 192.168.31.252:9100.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    table = cursor.fetchone()
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Bàn không tồn tại")

    cursor.execute("""
        SELECT * FROM orders 
        WHERE table_id = ? AND payment_status = 'UNPAID'
        ORDER BY round_number ASC
    """, (table_id,))
    orders = [dict(o) for o in cursor.fetchall()]

    all_items = []
    total_discount = 0

    for order in orders:
        cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC", (order["id"],))
        items = [dict(it) for it in cursor.fetchall()]
        all_items.extend(items)
        total_discount += order.get("discount", 0)

    conn.close()

    if not all_items:
        raise HTTPException(status_code=400, detail="Bàn chưa có món nào để in hóa đơn")

    totals_info = {
        "title": "HÓA ĐƠN TẠM TÍNH",
        "cashier_name": "Thu Ngân PiPo",
        "discount": total_discount,
        "vat": 0
    }

    # Bắn in trong background để phản hồi UI mượt mà
    background_tasks.add_task(print_cashier_receipt, dict(table), all_items, totals_info)

    return {
        "status": "SUCCESS",
        "message": f"Đã gửi lệnh in hóa đơn bàn {table['name']} xuống Máy in Thu ngân (192.168.31.252)!",
        "items_count": len(all_items)
    }
