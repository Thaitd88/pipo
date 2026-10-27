import sys
import os

sys.path.insert(0, os.path.abspath("."))
from app.escpos import build_escpos_kitchen_bytes, build_escpos_receipt_bytes
from scripts.verify_before_edit import sample_items, table_info, order_info, totals_info

k_bytes = build_escpos_kitchen_bytes(order_info, sample_items, station="HOT_KITCHEN", beep=True)
r_bytes = build_escpos_receipt_bytes(table_info, sample_items, totals_info=totals_info)

print(f"Kitchen bytes len: {len(k_bytes)}")
print(f"Receipt bytes len: {len(r_bytes)}")
assert b"GA TA NGUYEN CON (HAP HANH) x 1" in k_bytes
assert b"BIA HOI HA NOI x 10" in k_bytes
assert b"1. Ga ta nguyen con (Hap hanh)" in r_bytes
print("ESC/POS Byte checks passed 100%!")
