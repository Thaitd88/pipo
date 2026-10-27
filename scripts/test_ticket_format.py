import sys
import re
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def extract_item_details(name: str, portion: str = "", modifiers = None, note: str = "") -> tuple[str, str, str, str]:
    clean_name = str(name or "").strip()
    clean_port = str(portion or "").strip()
    clean_note = str(note or "").strip()

    # 1. Parse modifiers
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

    # 2. Check if name already has bracketed/parenthesized flavor e.g. [HẤP HÀNH] or (Hấp hành)
    m = re.search(r"\s*[\(\[]([^\)\]]+)[\)\]]\s*$", clean_name)
    if m:
        extracted = m.group(1).strip()
        clean_ext = re.sub(r"^(vị|vi)\s*:\s*", "", extracted, flags=re.IGNORECASE).strip()
        if clean_ext.lower().startswith("vị ") or clean_ext.lower().startswith("vi "):
            clean_ext = clean_ext[3:].strip()
        clean_name = re.sub(r"\s*[\(\[]([^\)\]]+)[\)\]]\s*$", "", clean_name).strip()
        if not chosen_flavor and clean_ext:
            chosen_flavor = clean_ext

    # 3. Special dish rules (Mì xào, Cơm chiên)
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

    # 4. Clean note if note is just repeating flavor or name
    if clean_note:
        if chosen_flavor and (clean_note.lower() == chosen_flavor.lower() or f"({clean_note.lower()})" == chosen_flavor.lower()):
            clean_note = ""
        elif clean_note.lower() in clean_name.lower():
            clean_note = ""

    return clean_name, chosen_flavor, clean_port, clean_note

if __name__ == "__main__":
    test_cases = [
        ("Gà ta nguyên con", "Ga 1 con (1.3kg)", [{"name": "Chọn vị chế biến", "value": "Hấp hành"}], "Hấp hành"),
        ("Gà ta nguyên con [HẤP HÀNH]", "Ga 1 con (1.3kg)", [], ""),
        ("Gà ta nguyên con (Hấp hành)", "Ga 1 con (1.3kg)", [{"name": "Chọn vị chế biến", "value": "Hấp hành"}], ""),
        ("Mì xào", "", [{"value": "Bò"}], "ít cay"),
        ("Bia hơi Hà Nội", "", [], ""),
        ("Khoai tây", "Đĩa 300g", '[{"name": "Chọn vị chế biến", "value": "Chiên"}]', "")
    ]

    for name, port, mods, note in test_cases:
        bname, flav, p, n = extract_item_details(name, port, mods, note)
        full_name = f"{bname} ({flav})" if flav else bname
        print(f"INPUT: name='{name}', mods={mods}, note='{note}'")
        print(f"  -> Bill: {full_name}")
        print(f"  -> Kitchen Line 1: {full_name.upper()} x 1")
        if p:
            print(f"  -> Kitchen Line 2:   * Dinh luong: {p}")
        if n:
            print(f"  -> Kitchen Line 3:   * Ghi chu: {n}")
        print("-" * 50)
