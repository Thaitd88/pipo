# ESC/POS byte generator and 80mm Formatter (T80W / Xprinter / Epson standard) for PiPo Garden
import re
import unicodedata
import json
from datetime import datetime
from .timezone_utils import now_vn_str

# Khổ in nhiệt 80mm chuẩn (T80W / Xprinter XP-C300H / Epson TM-T82)
# Font A (12x24 dots): 48 ký tự / dòng (576 dots / 72mm printable width)
LINE_WIDTH_80MM = 48

_VN_ACCENTS = u'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
_VN_NO_ACCENTS = u'AAAAEEEIIOOOOUUYaaaaeeeiioooouuyAaDdIiUuOoUuAaAaAaAaAaAaAaAaAaAaAaAaEeEeEeEeEeEeEeEeIiIiOoOoOoOoOoOoOoOoOoOoOoOoUuUuUuUuUuUuUuYyYyYyYy'
_VN_TRANS_TABLE = str.maketrans(_VN_ACCENTS, _VN_NO_ACCENTS)

def remove_vietnamese_accents(input_str: str) -> str:
    """Chuyển đổi tiếng Việt có dấu sang không dấu để tương thích 100% với firmware máy in nhiệt T80W."""
    if not input_str:
        return ""
    return str(input_str).translate(_VN_TRANS_TABLE)

def format_currency_vnd(amount: int) -> str:
    """Định dạng tiền tệ theo chuẩn VNĐ (VD: 165000 -> 165.000 d)"""
    return f"{int(amount):,.0f}".replace(",", ".") + " d"

def crc16_ccitt(data: str) -> str:
    """Thuật toán CRC-16/CCITT-FALSE chuẩn theo quy định quốc tế EMVCo và Napas 247."""
    crc = 0xFFFF
    for byte in data.encode("ascii"):
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"

def clean_vietqr_message(msg: str) -> str:
    """Chuẩn hóa nội dung chuyển khoản theo chuẩn VietQR (chỉ chữ, số, khoảng trắng, tối đa 25 ký tự)."""
    import re
    msg = remove_vietnamese_accents(str(msg or ""))
    msg = re.sub(r'[^a-zA-Z0-9 ]', ' ', msg)
    msg = re.sub(r'\s+', ' ', msg).strip()
    return msg[:25]

def generate_vietqr_emvco(bank_bin: str = "970422", account_no: str = "075624456", amount: int = 0, message: str = "") -> str:
    """Tạo chuỗi chuẩn Napas247 VietQR EMVCo để mọi ứng dụng ngân hàng quét thanh toán tự động."""
    aid = "A000000727"
    sub_00 = f"00{len(aid):02d}{aid}"
    sub_01_val = f"00{len(bank_bin):02d}{bank_bin}01{len(account_no):02d}{account_no}"
    sub_01 = f"01{len(sub_01_val):02d}{sub_01_val}"
    sub_02 = "0208QRIBFTTA"
    tag_38_val = f"{sub_00}{sub_01}{sub_02}"
    tag_38 = f"38{len(tag_38_val):02d}{tag_38_val}"

    payload = "000201"
    payload += "010212" if amount > 0 else "010211"
    payload += tag_38
    payload += "5303704" # Currency VND
    if amount > 0:
        amt_str = str(int(amount))
        payload += f"54{len(amt_str):02d}{amt_str}"
    payload += "5802VN"
    clean_msg = clean_vietqr_message(message)
    if clean_msg:
        sub_08 = f"08{len(clean_msg):02d}{clean_msg}"
        payload += f"62{len(sub_08):02d}{sub_08}"
    payload += "6304"
    crc = crc16_ccitt(payload)
    return payload + crc


def get_item_portion_from_db(item_id: int) -> str:
    """Truy vấn định lượng NVL chính của món từ CSDL nếu dict order_item chưa có."""
    if not item_id:
        return ""
    try:
        from .database import get_db
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT portion FROM menu_items WHERE id = ?", (item_id,))
        row = c.fetchone()
        conn.close()
        if row and row["portion"]:
            return str(row["portion"]).strip()
    except Exception:
        pass
    return ""


def extract_item_details(name: str, portion: str = "", modifiers = None, note: str = "") -> tuple[str, str, str, str]:
    """
    Trích xuất tên gốc, vị chế biến (flavor), định lượng NVL (portion) và ghi chú thực sự (clean_note).
    Trả về: (base_name, chosen_flavor, resolved_portion, clean_note)
    Quy chuẩn hiển thị tiết kiệm giấy in:
      - Bill tính tiền: Tên món (vị chế biến) chung 1 dòng: 'Gà ta nguyên con (Hấp hành)'
      - Bill bếp / bar: Dòng 1: 'Tên món (vị chế biến) x <SL>'
                        Dòng 2: '  * Dinh luong: <NVL chính>'
    """
    clean_name = str(name or "").strip()
    clean_port = str(portion or "").strip()
    clean_note = str(note or "").strip()

    # 1. Trích xuất modifier/vị chế biến
    mod_values = []
    if isinstance(modifiers, str) and modifiers.strip():
        try:
            parsed = json.loads(modifiers)
            if isinstance(parsed, list):
                modifiers = parsed
        except Exception:
            pass

    if modifiers and isinstance(modifiers, list):
        for m in modifiers:
            if isinstance(m, dict):
                v = str(m.get("value") or "").strip()
                if not v:
                    raw_n = str(m.get("name") or "").strip()
                    if raw_n.lower() not in ("chọn vị chế biến", "chon vi che bien", "vị", "vi"):
                        v = raw_n
                if v and v.lower() not in ("chọn vị chế biến", "chon vi che bien"):
                    mod_values.append(v)
            elif isinstance(m, str) and m.strip():
                mod_values.append(m.strip())

    chosen_flavor = " - ".join(mod_values) if mod_values else ""

    # 2. Xử lý trường hợp tên món đã có sẵn ngoặc [VỊ...] hoặc (...)
    m = re.search(r"\s*[\(\[]([^\)\]]+)[\)\]]\s*$", clean_name)
    if m:
        extracted = m.group(1).strip()
        clean_ext = re.sub(r"^(vị|vi)\s*:\s*", "", extracted, flags=re.IGNORECASE).strip()
        if clean_ext.lower().startswith("vị ") or clean_ext.lower().startswith("vi "):
            clean_ext = clean_ext[3:].strip()
        clean_name = re.sub(r"\s*[\(\[]([^\)\]]+)[\)\]]\s*$", "", clean_name).strip()
        if not chosen_flavor and clean_ext:
            chosen_flavor = clean_ext

    # 3. Định lượng chuẩn theo vị cho các món xào / chiên
    lower_name = clean_name.lower()
    lower_flavor = chosen_flavor.lower()
    if any(k in lower_name for k in ("mì xào", "mi xao", "mỳ xào", "my xao")):
        if "bò" in lower_flavor or "bo" in lower_flavor:
            clean_port = "Mì 2 vắt, thịt bò 100g, rau cải"
        elif "hải sản" in lower_flavor or "hai san" in lower_flavor:
            clean_port = "Mì 2 vắt, tôm mực 100g, rau cải"
    elif any(k in lower_name for k in ("cơm chiên", "com chien")):
        if "bò" in lower_flavor or "bo" in lower_flavor:
            clean_port = "Cơm 250g, thịt bò 100g, trứng"
        elif "hải sản" in lower_flavor or "hai san" in lower_flavor:
            clean_port = "Cơm 250g, tôm mực 100g, trứng"
        elif "ghẹ" in lower_flavor or "ghe" in lower_flavor:
            clean_port = "Cơm 250g, thịt ghẹ 80g, trứng"

    # 4. Làm sạch ghi chú nếu ghi chú chỉ lặp lại vị hoặc tên món
    if clean_note:
        if chosen_flavor and (clean_note.lower() == chosen_flavor.lower() or f"({clean_note.lower()})" == chosen_flavor.lower()):
            clean_note = ""
        elif clean_note.lower() in clean_name.lower():
            clean_note = ""

    return clean_name, chosen_flavor, clean_port, clean_note


def resolve_item_name_and_portion(name: str, portion: str, modifiers: list) -> tuple[str, str, str]:
    """Hàm tương thích ngược với code cũ."""
    base_name, flavor, clean_port, _ = extract_item_details(name, portion, modifiers, "")
    display_name = f"{base_name} ({flavor})" if flavor else base_name
    return display_name, clean_port, flavor


def format_kitchen_ticket_text(order_info: dict, items: list, station: str = "HOT_KITCHEN") -> str:
    """
    Tạo văn bản phiếu in bếp khổ 80mm (48 ký tự) cho màn hình monitor và log:
    - BÀN TO RÕ RÀNG
    - Đợt gọi, giờ gọi
    - Số lượng món đóng ngoặc vuông nổi bật
    """
    station_names = {
        "HOT_KITCHEN": "PHIEU BEP NONG (NUONG / LAU / XAO)",
                "BAR": "PHIEU QUAY BAR (PHA CHE / BIA)",
        "ALL": "PHIEU TONG BEP DIEU PHOI"
    }
    st_title = station_names.get(station, "PHIEU CHE BIEN")

    now_str = order_info.get("created_at") or now_vn_str("%H:%M:%S - %d/%m/%Y")
    table_name = order_info.get("table_name", "BAN ?")
    area_name = order_info.get("area", "Khu San Vuon")
    order_id = order_info.get("id", 0)
    round_no = order_info.get("round_number", 1)
    customer_note = order_info.get("customer_note", "")

    w = LINE_WIDTH_80MM
    div_double = "=" * w
    div_single = "-" * w

    lines = []
    lines.append("PIPO GARDEN".center(w))
    lines.append(f"*** {st_title} ***".center(w))
    lines.append(div_double)
    lines.append(f" BAN: {table_name.upper()} ({area_name})")
    lines.append(f" Don so: #{order_id} | Dot goi: {round_no}")
    lines.append(f" Gio goi: {now_str}")
    lines.append(div_single)
    lines.append(" MON CHE BIEN & SO LUONG")
    lines.append(div_single)

    for it in items:
        if it.get("status") == "CANCELLED":
            continue
        qty = it.get("quantity", 1)
        name = it.get("item_name") or it.get("name", "")
        note = it.get("note", "")
        modifiers = it.get("modifiers", [])
        portion = it.get("portion") or ""

        # Lấy định lượng NVL từ DB nếu chưa có
        if not portion and (it.get("item_id") or it.get("id")):
            portion = get_item_portion_from_db(it.get("item_id") or it.get("id"))

        base_name, flavor, resolved_portion, clean_note = extract_item_details(name, portion, modifiers, note)

        # Dòng 1: Tên món (vị chế biến) x <SL>
        if flavor:
            lines.append(f" {base_name.upper()} ({flavor.upper()}) x {qty}")
        else:
            lines.append(f" {base_name.upper()} x {qty}")

        # Dòng 2: Định lượng NVL chính (1 hàng ngắn gọn bên dưới)
        if resolved_portion:
            lines.append(f"   * Dinh luong: {resolved_portion}")

        # Ghi chú chế biến riêng nếu có (khác vị)
        if clean_note:
            lines.append(f"   * Ghi chu: {clean_note}")

        lines.append(div_single)

    if customer_note:
        lines.append(f" LUU Y CUA BAN: {customer_note}")
        lines.append(div_double)

    lines.append("*** VUI LONG LAM MON NGAY ***".center(w))
    lines.append("PiPo Garden Kitchen System".center(w))
    lines.append("")

    return remove_vietnamese_accents("\n".join(lines))

def format_receipt_ticket_text(table_info: dict, items: list, totals_info: dict = None) -> str:
    """
    Tạo văn bản hóa đơn thanh toán / tạm tính khổ 80mm (48 ký tự) cho máy in T80W:
    - Thương hiệu chuẩn: PiPo Garden - Restaurant, Cafe, Pool Bar (Không Resort)
    - Dòng 1: Tên món
    - Dòng 2:   SL x Đơn giá                       Thành tiền
    """
    if totals_info is None:
        totals_info = {}

    w = LINE_WIDTH_80MM
    div_double = "=" * w
    div_single = "-" * w

    now_str = totals_info.get("created_at") or table_info.get("created_at") or now_vn_str("%H:%M - %d/%m/%Y")
    table_name = table_info.get("name", "BAN ?")
    area_name = table_info.get("area", "Khu San Vuon")
    cashier_name = totals_info.get("cashier_name", "Thu Ngan")
    invoice_title = totals_info.get("title", "HOA DON TAM TINH")

    lines = []
    lines.append("PIPO GARDEN".center(w))
    lines.append("Restaurant, Cafe, Pool Bar".center(w))
    lines.append("Sonasea, Bai Truong, Phu Quoc".center(w))
    lines.append("Hotline: 0838.993.316".center(w))
    lines.append(div_double)
    lines.append(f"*** {invoice_title} ***".center(w))
    lines.append(div_double)
    lines.append(f" Ban: {table_name.upper()} ({area_name})")
    lines.append(f" Gio in: {now_str}")
    lines.append(f" Thu ngan: {cashier_name}")
    lines.append(div_single)
    lines.append(" TEN MON")
    lines.append("   SL x DON GIA                       THANH TIEN")
    lines.append(div_single)

    subtotal = 0
    idx = 1
    has_active_items = False
    for it in items:
        if it.get("status") == "CANCELLED":
            continue

        has_active_items = True
        name = it.get("item_name") or it.get("name", "")
        qty = int(it.get("quantity", 1))
        price = int(it.get("unit_price") or it.get("price", 0))
        total_price = int(it.get("total_price", qty * price))
        subtotal += total_price

        modifiers = it.get("modifiers")
        note = it.get("note", "")
        portion = it.get("portion", "")

        base_name, flavor, _, clean_note = extract_item_details(name, portion, modifiers, note)
        display_name = f"{base_name} ({flavor})" if flavor else base_name

        # Dòng 1: Tên món kèm vị chế biến trên cùng hàng để tiết kiệm giấy in
        lines.append(f" {idx}. {display_name}")

        # Dòng 2: SL x Đơn giá = Thành tiền (căn chỉnh đúng 48 ký tự)
        left_col = f"    {qty} x {price:,.0f}".replace(",", ".")
        right_col = f"{total_price:,.0f}".replace(",", ".") + " d"
        spacing = w - len(left_col) - len(right_col)
        if spacing < 1:
            spacing = 1
        lines.append(f"{left_col}{' ' * spacing}{right_col}")

        # Ghi chú nếu có và khác vị
        if clean_note:
            lines.append(f"       >>> {clean_note}")

        idx += 1

    if not has_active_items:
        lines.append("   (Phieu thu phi dich vu / phu thu san)")

    discount = int(totals_info.get("discount", 0))
    service_fee = int(totals_info.get("service_fee", 0))
    vat = int(totals_info.get("vat", 0))
    grand_total = max(0, subtotal - discount + service_fee + vat)

    lines.append(div_single)

    # Tổng tiền món
    lbl_sub = " Tong tien mon:"
    val_sub = format_currency_vnd(subtotal)
    sp_sub = w - len(lbl_sub) - len(val_sub)
    lines.append(f"{lbl_sub}{' ' * max(1, sp_sub)}{val_sub}")

    if discount > 0:
        disc_reason = totals_info.get("discount_reason")
        disc_pct = totals_info.get("discount_percent")
        if disc_pct:
            lbl_disc = f" Giam gia ({disc_pct}% - {remove_vietnamese_accents(disc_reason)}):" if disc_reason else f" Giam gia ({disc_pct}%):"
        else:
            lbl_disc = f" Giam gia ({remove_vietnamese_accents(disc_reason)}):" if disc_reason else " Giam gia:"
        val_disc = f"-{format_currency_vnd(discount)}"
        sp_disc = w - len(lbl_disc) - len(val_disc)
        lines.append(f"{lbl_disc}{' ' * max(1, sp_disc)}{val_disc}")

    if service_fee > 0:
        lbl_fee = " Phi phuc vu:"
        val_fee = f"+{format_currency_vnd(service_fee)}"
        sp_fee = w - len(lbl_fee) - len(val_fee)
        lines.append(f"{lbl_fee}{' ' * max(1, sp_fee)}{val_fee}")

    pay_method = (totals_info.get("payment_method") or "CASH").upper()
    if pay_method in ("TRANSFER", "VIETQR"):
        lines.append(" Hinh thuc TT: Chuyen khoan (VietQR)")
    elif pay_method == "INTERNAL" or totals_info.get("bill_target") == "ADMIN":
        adm_name = remove_vietnamese_accents(str(totals_info.get("billed_admin_name") or ""))
        lines.append(" Hinh thuc TT: Tinh tien noi bo")
        if adm_name:
            lines.append(f" Nguoi chiu / Ghi chu: {adm_name}")
    else:
        lines.append(" Hinh thuc TT: Tien mat")

    if vat > 0:
        lbl_vat = " Thue VAT (8%):"
        val_vat = format_currency_vnd(vat)
        sp_vat = w - len(lbl_vat) - len(val_vat)
        lines.append(f"{lbl_vat}{' ' * max(1, sp_vat)}{val_vat}")

    lines.append(div_double)

    lbl_tot = " TONG CONG:"
    val_tot = format_currency_vnd(grand_total)
    sp_tot = w - len(lbl_tot) - len(val_tot)
    lines.append(f"{lbl_tot}{' ' * max(1, sp_tot)}{val_tot}")

    lines.append(div_double)

    # Khung VietQR MB Bank
    table_code = remove_vietnamese_accents(str(table_info.get("table_code") or table_info.get("name", "01"))).upper()
    if table_code.startswith("BAN "):
        table_code = table_code.replace("BAN ", "")
    clean_table_code = re.sub(r'[^a-zA-Z0-9]', '', table_code) or "01"
    transfer_note = f"TT PiPo Ban {clean_table_code}"

    lines.append("QUET MA VIETQR THANH TOAN".center(w))
    lines.append("Ngan hang: MB Bank (Quan Doi) - STK: 075624456".center(w))
    lines.append("Chu TK: PIPO GARDEN".center(w))
    lines.append(f"ND: {transfer_note}".center(w))
    lines.append(div_double)
    lines.append("Cam on Quy khach & Hen gap lai!".center(w))
    lines.append("Wifi: PiPo Garden | Pass: 88888888".center(w))
    lines.append("Website: www.PiPoGarden.com".center(w))
    lines.append("")

    return remove_vietnamese_accents("\n".join(lines))

def build_escpos_kitchen_bytes(order_info: dict, items: list, station: str = "HOT_KITCHEN", beep: bool = True) -> bytes:
    """
    Biên dịch phiếu in Bếp (KOT) thành luồng lệnh ESC/POS nhị phân chuẩn cho T80W:
    - Bật còi hú cảnh báo bếp (3 tiếng BEEP)
    - Tên BÀN được phóng to gấp đôi (Double Size) để đầu bếp nhìn rõ từ xa
    - Số lượng món in to và đậm
    - Tự động Feed 4 dòng và cắt giấy một phần (Partial Cut)
    """
    ESC = b'\x1b'
    GS = b'\x1d'

    station_names = {
        "HOT_KITCHEN": "PHIEU BEP NONG (NUONG / LAU / XAO)",
                "BAR": "PHIEU QUAY BAR (PHA CHE / BIA)",
        "ALL": "PHIEU TONG BEP DIEU PHOI"
    }
    st_title = station_names.get(station, "PHIEU CHE BIEN")

    now_str = order_info.get("created_at") or now_vn_str("%H:%M:%S - %d/%m/%Y")
    table_name = remove_vietnamese_accents(str(order_info.get("table_name", "BAN ?"))).upper()
    area_name = remove_vietnamese_accents(str(order_info.get("area", "Khu San Vuon")))
    order_id = order_info.get("id", 0)
    round_no = order_info.get("round_number", 1)
    customer_note = remove_vietnamese_accents(str(order_info.get("customer_note", "")))

    w = LINE_WIDTH_80MM
    div_double = ("=" * w + "\n").encode("ascii")
    div_single = ("-" * w + "\n").encode("ascii")

    buf = bytearray()
    buf.extend(ESC + b'@') # Initialize

    # Lệnh hú còi đa năng cho T80W / Xprinter
    if beep:
        buf.extend(ESC + b'B\x03\x02') # Xprinter buzzer command (3 beeps, interval 2)
        buf.extend(b'\x07\x07\x07')     # ASCII BEL
        buf.extend(ESC + b'p\x00\x19\xfa') # Pulse cash drawer / buzzer pin

    # Header căn giữa
    buf.extend(ESC + b'a\x01') # Center
    buf.extend(ESC + b'E\x01') # Bold
    buf.extend(b'PIPO GARDEN\n')
    buf.extend(GS + b'!\x01')  # Double height
    buf.extend(f"*** {st_title} ***\n".encode("ascii"))
    buf.extend(GS + b'!\x00')  # Normal size
    buf.extend(ESC + b'E\x00') # Bold off
    buf.extend(div_double)

    # Thông tin bàn căn trái - Tên bàn in to gấp đôi cho Bếp dễ nhìn
    buf.extend(ESC + b'a\x00') # Left
    buf.extend(ESC + b'E\x01')
    buf.extend(GS + b'!\x11')  # Double width & height
    buf.extend(f"BAN: {table_name}\n".encode("ascii"))
    buf.extend(GS + b'!\x00')  # Normal size
    buf.extend(ESC + b'E\x00')
    buf.extend(f"Khu vuc: {area_name} | Don so: #{order_id} | Dot goi: {round_no}\n".encode("ascii"))
    buf.extend(f"Gio goi: {now_str}\n".encode("ascii"))
    buf.extend(div_single)

    buf.extend(ESC + b'E\x01')
    buf.extend(b' MON CHE BIEN & SO LUONG\n')
    buf.extend(ESC + b'E\x00')
    buf.extend(div_single)

    for it in items:
        if it.get("status") == "CANCELLED":
            continue
        qty = it.get("quantity", 1)
        raw_name = it.get("item_name") or it.get("name", "")
        note = it.get("note", "")
        modifiers = it.get("modifiers", [])
        raw_portion = it.get("portion") or ""

        # Fallback lấy định lượng món từ DB nếu chưa có trong dict
        if not raw_portion and (it.get("item_id") or it.get("id")):
            raw_portion = get_item_portion_from_db(it.get("item_id") or it.get("id"))

        base_name, flavor, resolved_portion, clean_note = extract_item_details(raw_name, raw_portion, modifiers, note)
        name_ascii = remove_vietnamese_accents(base_name).upper()
        flavor_ascii = remove_vietnamese_accents(flavor).upper() if flavor else ""
        portion_ascii = remove_vietnamese_accents(resolved_portion)
        note_ascii = remove_vietnamese_accents(clean_note)

        # Dòng 1: Tên món (vị chế biến) x <SL> in đậm
        if flavor_ascii:
            item_line = f" {name_ascii} ({flavor_ascii}) x {qty}\n"
        else:
            item_line = f" {name_ascii} x {qty}\n"

        buf.extend(ESC + b'E\x01') # Bold on
        buf.extend(item_line.encode("ascii"))
        buf.extend(ESC + b'E\x00') # Bold off

        # Dòng 2: Định lượng NVL chính (1 hàng ngắn gọn bên dưới)
        if portion_ascii:
            buf.extend(f"   * Dinh luong: {portion_ascii}\n".encode("ascii"))

        # Ghi chú chế biến riêng
        if note_ascii:
            buf.extend(f"   * Ghi chu: {note_ascii}\n".encode("ascii"))

        buf.extend(div_single)

    if customer_note:
        buf.extend(ESC + b'E\x01')
        buf.extend(f"LUU Y CUA BAN: {customer_note}\n".encode("ascii"))
        buf.extend(ESC + b'E\x00')
        buf.extend(div_double)

    # Footer
    buf.extend(ESC + b'a\x01') # Center
    buf.extend(ESC + b'E\x01')
    buf.extend(b'*** VUI LONG LAM MON NGAY ***\n')
    buf.extend(ESC + b'E\x00')
    buf.extend(b'PiPo Garden Kitchen System\n')
    buf.extend(b'\n\n\n\n')
    buf.extend(GS + b'V\x42\x00') # Feed & Partial cut

    return bytes(buf)

def build_escpos_receipt_bytes(table_info: dict, items: list, totals_info: dict = None) -> bytes:
    """
    Biên dịch hóa đơn thanh toán / tạm tính thành mã ESC/POS nhị phân chuẩn 80mm (T80W):
    - Thương hiệu PiPo Garden (Double size, Center)
    - Dòng 1: Tên món
    - Dòng 2: SL x Đơn giá                       Thành tiền
    - Tổng cộng to, rõ ràng
    - Feed 4 dòng & cắt giấy tự động
    """
    if totals_info is None:
        totals_info = {}

    ESC = b'\x1b'
    GS = b'\x1d'

    w = LINE_WIDTH_80MM
    div_double = ("=" * w + "\n").encode("ascii")
    div_single = ("-" * w + "\n").encode("ascii")

    now_str = totals_info.get("created_at") or table_info.get("created_at") or now_vn_str("%H:%M - %d/%m/%Y")
    table_name = remove_vietnamese_accents(str(table_info.get("name", "BAN ?"))).upper()
    area_name = remove_vietnamese_accents(str(table_info.get("area", "Khu San Vuon")))
    cashier_name = remove_vietnamese_accents(str(totals_info.get("cashier_name", "Thu Ngan")))
    invoice_title = remove_vietnamese_accents(str(totals_info.get("title", "HOA DON TAM TINH"))).upper()

    buf = bytearray()
    buf.extend(ESC + b'@') # Initialize

    # Header căn giữa
    buf.extend(ESC + b'a\x01') # Center
    buf.extend(ESC + b'E\x01') # Bold
    buf.extend(GS + b'!\x11')  # Double width & height
    buf.extend(b'PIPO GARDEN\n')
    buf.extend(GS + b'!\x00')  # Normal size
    buf.extend(b'Restaurant, Cafe, Pool Bar\n')
    buf.extend(b'Sonasea, Bai Truong, Phu Quoc\n')
    buf.extend(b'Hotline: 0838.993.316\n')
    buf.extend(ESC + b'E\x00') # Bold off
    buf.extend(div_double)

    # Tiêu đề hóa đơn
    buf.extend(ESC + b'E\x01')
    buf.extend(GS + b'!\x01')  # Double height
    buf.extend(f"*** {invoice_title} ***\n".encode("ascii"))
    buf.extend(GS + b'!\x00')
    buf.extend(ESC + b'E\x00')
    buf.extend(div_double)

    # Thông tin bàn căn trái
    buf.extend(ESC + b'a\x00') # Left
    buf.extend(ESC + b'E\x01')
    buf.extend(f" Ban: {table_name} ({area_name})\n".encode("ascii"))
    buf.extend(ESC + b'E\x00')
    buf.extend(f" Gio in: {now_str}\n".encode("ascii"))
    buf.extend(f" Thu ngan: {cashier_name}\n".encode("ascii"))
    buf.extend(div_single)

    buf.extend(ESC + b'E\x01')
    buf.extend(b' TEN MON\n')
    buf.extend(b'   SL x DON GIA                       THANH TIEN\n')
    buf.extend(ESC + b'E\x00')
    buf.extend(div_single)

    subtotal = 0
    idx = 1
    has_active_items = False
    for it in items:
        if it.get("status") == "CANCELLED":
            continue

        has_active_items = True
        name = remove_vietnamese_accents(it.get("item_name") or it.get("name", ""))
        qty = int(it.get("quantity", 1))
        price = int(it.get("unit_price") or it.get("price", 0))
        total_price = int(it.get("total_price", qty * price))
        subtotal += total_price

        raw_name = it.get("item_name") or it.get("name", "")
        modifiers = it.get("modifiers")
        note = it.get("note", "")
        portion = it.get("portion", "")

        base_name, flavor, _, clean_note = extract_item_details(raw_name, portion, modifiers, note)
        display_name = f"{base_name} ({flavor})" if flavor else base_name
        name_ascii = remove_vietnamese_accents(display_name)

        # Dòng 1: Tên món kèm vị chế biến trên cùng hàng để tiết kiệm giấy in
        buf.extend(f" {idx}. {name_ascii}\n".encode("ascii"))

        # Dòng 2: SL x Đơn giá = Thành tiền (căn chỉnh đúng 48 ký tự)
        left_col = f"    {qty} x {price:,.0f}".replace(",", ".")
        right_col = f"{total_price:,.0f}".replace(",", ".") + " d"
        spacing = w - len(left_col) - len(right_col)
        if spacing < 1:
            spacing = 1
        line_2 = f"{left_col}{' ' * spacing}{right_col}\n"
        buf.extend(line_2.encode("ascii"))

        # Ghi chú nếu có và khác vị
        if clean_note:
            note_ascii = remove_vietnamese_accents(clean_note)
            buf.extend(f"       >>> {note_ascii}\n".encode("ascii"))

        idx += 1

    if not has_active_items:
        buf.extend(b'   (Phieu thu phi dich vu / phu thu san)\n')

    discount = int(totals_info.get("discount", 0))
    service_fee = int(totals_info.get("service_fee", 0))
    vat = int(totals_info.get("vat", 0))
    grand_total = max(0, subtotal - discount + service_fee + vat)

    buf.extend(div_single)

    # Tổng tiền món
    lbl_sub = " Tong tien mon:"
    val_sub = format_currency_vnd(subtotal)
    sp_sub = w - len(lbl_sub) - len(val_sub)
    buf.extend(f"{lbl_sub}{' ' * max(1, sp_sub)}{val_sub}\n".encode("ascii"))

    if discount > 0:
        disc_reason = totals_info.get("discount_reason")
        disc_pct = totals_info.get("discount_percent")
        if disc_pct:
            lbl_disc = f" Giam gia ({disc_pct}% - {remove_vietnamese_accents(disc_reason)}):" if disc_reason else f" Giam gia ({disc_pct}%):"
        else:
            lbl_disc = f" Giam gia ({remove_vietnamese_accents(disc_reason)}):" if disc_reason else " Giam gia:"
        val_disc = f"-{format_currency_vnd(discount)}"
        sp_disc = w - len(lbl_disc) - len(val_disc)
        buf.extend(f"{lbl_disc}{' ' * max(1, sp_disc)}{val_disc}\n".encode("ascii"))

    if service_fee > 0:
        lbl_fee = " Phi phuc vu:"
        val_fee = f"+{format_currency_vnd(service_fee)}"
        sp_fee = w - len(lbl_fee) - len(val_fee)
        buf.extend(f"{lbl_fee}{' ' * max(1, sp_fee)}{val_fee}\n".encode("ascii"))

    pay_method = (totals_info.get("payment_method") or "CASH").upper()
    if pay_method in ("TRANSFER", "VIETQR"):
        buf.extend(b" Hinh thuc TT: Chuyen khoan (VietQR)\n")
    elif pay_method == "INTERNAL" or totals_info.get("bill_target") == "ADMIN":
        adm_name = remove_vietnamese_accents(str(totals_info.get("billed_admin_name") or ""))
        buf.extend(b" Hinh thuc TT: Tinh tien noi bo\n")
        if adm_name:
            buf.extend(f" Nguoi chiu / Ghi chu: {adm_name}\n".encode("ascii"))
    else:
        buf.extend(b" Hinh thuc TT: Tien mat\n")

    if vat > 0:
        lbl_vat = " Thue VAT (8%):"
        val_vat = format_currency_vnd(vat)
        sp_vat = w - len(lbl_vat) - len(val_vat)
        buf.extend(f"{lbl_vat}{' ' * max(1, sp_vat)}{val_vat}\n".encode("ascii"))

    buf.extend(div_double)

    # TỔNG CỘNG in to và đậm
    lbl_tot = " TONG CONG:"
    val_tot = format_currency_vnd(grand_total)
    sp_tot = w - len(lbl_tot) - len(val_tot)
    buf.extend(ESC + b'E\x01')
    buf.extend(GS + b'!\x01') # Double height
    buf.extend(f"{lbl_tot}{' ' * max(1, sp_tot)}{val_tot}\n".encode("ascii"))
    buf.extend(GS + b'!\x00')
    buf.extend(ESC + b'E\x00')

    buf.extend(div_double)

    # VietQR MB Bank 075624456 Block
    table_code = remove_vietnamese_accents(str(table_info.get("table_code") or table_info.get("name", "01"))).upper()
    if table_code.startswith("BAN "):
        table_code = table_code.replace("BAN ", "")
    clean_table_code = re.sub(r'[^a-zA-Z0-9]', '', table_code) or "01"
    transfer_note = f"TT PiPo Ban {clean_table_code}"

    # Tạo chuỗi EMVCo chuẩn Napas247 cho mọi App ngân hàng
    qr_emvco = generate_vietqr_emvco("970422", "075624456", grand_total, transfer_note)
    qr_data = qr_emvco.encode("ascii")

    buf.extend(ESC + b'a\x01') # Center
    buf.extend(ESC + b'E\x01')
    buf.extend(b'QUET MA VIETQR THANH TOAN\n')
    buf.extend(ESC + b'E\x00')
    buf.extend(b'Ngan hang: MB Bank (Quan Doi) - STK: 075624456\n')
    buf.extend(b'Chu TK: PIPO GARDEN\n')
    buf.extend(f"ND: {transfer_note}\n\n".encode("ascii"))

    # Lệnh in mã QR chuẩn ESC/POS Model 2 trên T80W
    buf.extend(GS + b'(k\x04\x00\x31\x41\x32\x00') # Model 2
    buf.extend(GS + b'(k\x03\x00\x31\x43\x06')     # Module size 6 dots
    buf.extend(GS + b'(k\x03\x00\x31\x45\x31')     # Error correction M
    data_len = len(qr_data) + 3
    buf.extend(GS + b'(k' + bytes([data_len % 256, data_len // 256]) + b'\x31\x50\x30' + qr_data) # Store
    buf.extend(GS + b'(k\x03\x00\x31\x51\x30')     # Print QR

    buf.extend(b'\n')
    buf.extend(div_double)

    # Footer
    buf.extend(ESC + b'a\x01') # Center
    buf.extend(b'Cam on Quy khach & Hen gap lai!\n')
    buf.extend(b'Wifi: PiPo Garden | Pass: 88888888\n')
    buf.extend(b'Website: www.PiPoGarden.com\n')
    buf.extend(b'\n\n\n\n')
    buf.extend(GS + b'V\x42\x00') # Feed & Partial cut

    return bytes(buf)

def build_escpos_bytes(ticket_text: str, beep: bool = True) -> bytes:
    """Hàm tương thích cũ cho các module truyền chuỗi văn bản tự do."""
    ESC = b'\x1b'
    GS = b'\x1d'
    payload = bytearray()
    payload.extend(ESC + b'@')
    if beep:
        payload.extend(ESC + b'B\x03\x02')
        payload.extend(b'\x07\x07\x07')
    payload.extend(ESC + b'a\x00')
    clean_text = remove_vietnamese_accents(ticket_text)
    payload.extend(clean_text.encode('ascii', errors='replace'))
    payload.extend(b'\n\n\n\n' + GS + b'V\x42\x00')
    return bytes(payload)
