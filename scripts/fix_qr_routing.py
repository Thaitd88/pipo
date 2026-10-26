# -*- coding: utf-8 -*-
"""
Sửa lỗi điều hướng QR cho bàn Sảnh 2:
Loại trừ bàn Sảnh 2 (Cạnh Sân Pickleball) khỏi việc bị nhận nhầm thành Sân Pickleball.
Chỉ có duy nhất 4 bàn Sân Pickle (PK-01 -> PK-04 hoặc khu 'Sân Pickle') mới vào thẳng Menu Sân Pickle.
Các bàn Sảnh 2, Sảnh 1, Hồ Bơi đều vào thẳng Menu Nhà Hàng.
"""
import sys

# 1. Sửa app/main.py
with open("app/main.py", "r", encoding="utf-8") as f:
    main_code = f.read()

main_code_lf = main_code.replace("\r\n", "\n")

old_branch_routing = """    if "cafe" in area_str or "sáng" in area_str or code_str.startswith("CF") or "cafe" in name_str:
        table_dict["branch_type"] = "CAFE"
    elif "pickle" in area_str or code_str.startswith("PK") or "pickle" in name_str:
        table_dict["branch_type"] = "PICKLE"
    else:
        table_dict["branch_type"] = "RESTAURANT" """

new_branch_routing = """    # Sảnh 2, Sảnh 1, Hồ bơi là các khu nhà hàng chính
    if "sảnh 2" in area_str or code_str.startswith("S2") or code_str.startswith("S1") or code_str.startswith("HB"):
        table_dict["branch_type"] = "RESTAURANT"
    elif code_str.startswith("PK") or area_str.strip() == "sân pickle" or (area_str.startswith("sân pickle") and "sảnh" not in area_str):
        table_dict["branch_type"] = "PICKLE"
    elif "cafe" in area_str or "sáng" in area_str or code_str.startswith("CF") or "cafe" in name_str:
        table_dict["branch_type"] = "CAFE"
    else:
        table_dict["branch_type"] = "RESTAURANT" """

# Fallback matching with more flexible whitespace
pattern_main = r'if "cafe" in area_str[\s\S]*?table_dict\["branch_type"\] = "RESTAURANT"'
import re
if re.search(pattern_main, main_code_lf):
    main_code_lf = re.sub(pattern_main, new_branch_routing.strip(), main_code_lf, count=1)
    with open("app/main.py", "w", encoding="utf-8") as f:
        f.write(main_code_lf)
    print("[+] Da cap nhat dieu huong branch_type trong app/main.py")
else:
    print("[-] Khong tim thay pattern trong app/main.py")

# 2. Sửa app/templates/customer.html
with open("app/templates/customer.html", "r", encoding="utf-8") as f:
    cust_code = f.read()

cust_code_lf = cust_code.replace("\r\n", "\n")

# Sửa hàm nhận diện isPickleTable ở cả 2 chỗ trong customer.html
old_is_pickle = 'const isPickleTable = (TABLE_INFO.branchType === "PICKLE" || (TABLE_INFO.area || "").trim() === "Sân Pickle" || (TABLE_INFO.code || "").toUpperCase().startsWith("PK"));'

new_is_pickle = '''const isSanh2OrDining = (TABLE_INFO.code || "").toUpperCase().startsWith("S2") || 
                              (TABLE_INFO.code || "").toUpperCase().startsWith("S1") || 
                              (TABLE_INFO.code || "").toUpperCase().startsWith("HB") || 
                              (TABLE_INFO.name || "").toLowerCase().includes("sảnh") || 
                              (TABLE_INFO.name || "").toLowerCase().includes("hồ bơi");
      const isPickleTable = !isSanh2OrDining && (
        (TABLE_INFO.code || "").toUpperCase().startsWith("PK") || 
        (TABLE_INFO.area || "").trim().toLowerCase() === "sân pickle" || 
        (TABLE_INFO.branchType === "PICKLE" && !(TABLE_INFO.area || "").toLowerCase().includes("sảnh"))
      );'''

if old_is_pickle in cust_code_lf:
    cust_code_lf = cust_code_lf.replace(old_is_pickle, new_is_pickle)
    with open("app/templates/customer.html", "w", encoding="utf-8") as f:
        f.write(cust_code_lf)
    print("[+] Da cap nhat nhan dien isPickleTable trong app/templates/customer.html")
else:
    print("[-] Khong tim thay old_is_pickle trong app/templates/customer.html")

print("[*] Hoan tat fix QR routing!")
