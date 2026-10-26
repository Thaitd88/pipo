# -*- coding: utf-8 -*-
with open("app/database.py", "r", encoding="utf-8") as f:
    code = f.read()

code_lf = code.replace("\r\n", "\n")

old_func_pattern = r'def seed_translations_if_missing\(conn=None\):[\s\S]*?def seed_historical_revenue'

new_func = '''def seed_translations_if_missing(conn=None):
    """Tự động kiểm tra và bổ sung bản dịch 4 ngôn ngữ (en, zh, ko, ru) cho categories và menu_items (Không giữ khóa CSDL khi dịch)."""
    try:
        from .services.translator import translate_dish, translate_category_name
    except Exception as e:
        print("[PiPo Multi-Lang] Chua the import translator:", e)
        return

    try:
        read_conn = get_db()
        cursor = read_conn.cursor()
        
        # 1. Categories
        cursor.execute("SELECT id, name, translations_json FROM categories")
        cat_updates = []
        for cat in cursor.fetchall():
            trans_str = cat["translations_json"]
            needs_trans = False
            if not trans_str or trans_str in ("{}", '""', "null"):
                needs_trans = True
            else:
                try:
                    parsed = json.loads(trans_str)
                    if not isinstance(parsed, dict) or "en" not in parsed:
                        needs_trans = True
                except Exception:
                    needs_trans = True
            if needs_trans:
                cat_updates.append((cat["id"], cat["name"]))

        # 2. Menu Items
        cursor.execute("SELECT id, name, description, translations_json FROM menu_items")
        item_updates = []
        for item in cursor.fetchall():
            trans_str = item["translations_json"]
            needs_trans = False
            if not trans_str or trans_str in ("{}", '""', "null"):
                needs_trans = True
            else:
                try:
                    parsed = json.loads(trans_str)
                    if not isinstance(parsed, dict) or "en" not in parsed:
                        needs_trans = True
                except Exception:
                    needs_trans = True
            if needs_trans:
                item_updates.append((item["id"], item["name"], item["description"] or ""))

        read_conn.close()

        if not cat_updates and not item_updates:
            return

        # Dịch in-memory hoàn toàn KHÔNG giữ khóa CSDL
        cat_payloads = []
        for cid, cname in cat_updates:
            trans = translate_category_name(cname)
            cat_payloads.append((json.dumps(trans, ensure_ascii=False), cid))

        item_payloads = []
        for iid, iname, idesc in item_updates:
            trans = translate_dish(iname, idesc)
            item_payloads.append((json.dumps(trans, ensure_ascii=False), iid))

        # Ghi vào CSDL cực nhanh
        write_conn = get_db()
        w_cur = write_conn.cursor()
        for trans_json, cid in cat_payloads:
            w_cur.execute("UPDATE categories SET translations_json = ? WHERE id = ?", (trans_json, cid))
        for trans_json, iid in item_payloads:
            w_cur.execute("UPDATE menu_items SET translations_json = ? WHERE id = ?", (trans_json, iid))
        write_conn.commit()
        write_conn.close()
    except Exception as err:
        print("[PiPo Multi-Lang] Loi seed translations:", err)

def seed_historical_revenue'''

import re
if re.search(old_func_pattern, code_lf):
    code_lf = re.sub(old_func_pattern, new_func, code_lf, count=1)
    with open("app/database.py", "w", encoding="utf-8") as f:
        f.write(code_lf)
    print("[+] Da sua seed_translations_if_missing khong khoa DB!")
else:
    print("[-] Khong tim thay pattern trong database.py")
