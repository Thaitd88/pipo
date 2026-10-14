# ESC/POS byte generator and Kitchen Order Ticket (KOT) formatter for PiPo Garden
import unicodedata
from datetime import datetime

def remove_vietnamese_accents(input_str: str) -> str:
    """Chuyển đổi tiếng Việt có dấu sang không dấu để tương thích 100% với mọi dòng máy in nhiệt cổ điển."""
    s1 = u'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
    s0 = u'AAAAEEEIIOOOOUUYaaaaeeeiioooouuyAaDdIiUuOoUuAaAaAaAaAaAaAaAaAaAaAaAaEeEeEeEeEeEeEeEeIiIiOoOoOoOoOoOoOoOoOoOoOoOoUuUuUuUuUuUuUuYyYyYyYy'
    s = ''
    for c in input_str:
        if c in s1:
            s += s0[s1.index(c)]
        else:
            s += c
    return s

def format_kitchen_ticket_text(order_info: dict, items: list, station: str = "HOT_KITCHEN") -> str:
    """Tạo văn bản phiếu in bếp 80mm rõ ràng, trực quan."""
    station_names = {
        "HOT_KITCHEN": "PHIẾU BẾP NÓNG (NƯỚNG/LẨU/XÀO)",
        "COLD_KITCHEN": "PHIẾU BẾP LẠNH (KHAI VỊ/GỎI)",
        "BAR": "PHIẾU QUẦY BAR (PHA CHẾ/BIA)",
        "ALL": "PHIẾU TỔNG BẾP ĐIỀU PHỐI"
    }
    st_title = station_names.get(station, "PHIẾU CHẾ BIẾN")

    now_str = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
    table_name = order_info.get("table_name", "BÀN ?")
    area_name = order_info.get("area", "Khu Vườn")
    order_id = order_info.get("id", 0)
    round_no = order_info.get("round_number", 1)
    customer_note = order_info.get("customer_note", "")

    width = 42
    div_double = "=" * width
    div_single = "-" * width

    lines = []
    lines.append("        NHÀ HÀNG PIPO GARDEN")
    lines.append(f"      *** {st_title} ***")
    lines.append(div_double)
    lines.append(f" BÀN: {table_name.upper()} ({area_name})")
    lines.append(f" Đơn số: #{order_id} | Đợt gọi món: {round_no}")
    lines.append(f" Giờ gọi: {now_str}")
    lines.append(div_single)
    lines.append(" SL  TÊN MÓN                       STT")
    lines.append(div_single)

    idx = 1
    for it in items:
        qty = it.get("quantity", 1)
        name = it.get("item_name", "")
        note = it.get("note", "")
        modifiers = it.get("modifiers", [])

        # Dòng tên món với số lượng nổi bật
        lines.append(f"[{qty}]  {name}")
        
        # In modifiers nếu có (Độ cay, Size, Mức đường đá)
        if modifiers:
            if isinstance(modifiers, list):
                mod_str = ", ".join([f"{m.get('name')}: {m.get('value')}" for m in modifiers if isinstance(m, dict)])
                if mod_str:
                    lines.append(f"     * Tùy chọn: {mod_str}")
        
        # Ghi chú riêng của món
        if note:
            lines.append(f"     >>> GHI CHÚ: {note}")

        lines.append(div_single)
        idx += 1

    if customer_note:
        lines.append(f"LƯU Ý CỦA BÀN: {customer_note}")
        lines.append(div_single)

    lines.append("     *** VUI LÒNG LÀM MÓN NGAY ***")
    lines.append("          PiPo Garden System")
    lines.append("")

    return "\n".join(lines)

def build_escpos_bytes(ticket_text: str, beep: bool = True) -> bytes:
    """
    Biên dịch văn bản phiếu in thành chuỗi byte mã ESC/POS chuẩn công nghiệp
    tương thích Xprinter (XP-C300H), Sunmi, Epson, Bixolon.
    """
    # ESC/POS Commands
    ESC = b'\x1b'
    GS = b'\x1d'
    
    cmd_init = ESC + b'@'                    # Initialize printer
    cmd_center = ESC + b'a\x01'              # Align center
    cmd_left = ESC + b'a\x00'                # Align left
    cmd_bold_on = ESC + b'E\x01'             # Bold on
    cmd_bold_off = ESC + b'E\x00'            # Bold off
    cmd_double_size = GS + b'!\x11'          # Double width & height
    cmd_normal_size = GS + b'!\x00'          # Normal size
    cmd_cut = b'\n\n\n\n' + GS + b'V\x41\x00'# Feed and partial cut
    
    # Lệnh hú còi cho máy in bếp chuyên dụng (Xprinter XP-C300H beeper: 3 beeps)
    cmd_beep = ESC + b'B\x03\x02' if beep else b''

    # Chuyển text sang tiếng Việt không dấu để in trên mọi phần cứng nhiệt
    clean_text = remove_vietnamese_accents(ticket_text)
    
    # Ghép dữ liệu byte
    payload = bytearray()
    payload.extend(cmd_init)
    if beep:
        payload.extend(cmd_beep)
        
    payload.extend(cmd_left)
    payload.extend(clean_text.encode('ascii', errors='replace'))
    payload.extend(cmd_cut)
    
    return bytes(payload)
