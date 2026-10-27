# -*- coding: utf-8 -*-
"""
Bảng từ điển song ngữ Việt - Anh (ENG - VN) chuẩn ẩm thực cho Menu PiPo Garden Phú Quốc
Phục vụ in ấn thực đơn bản cứng A4 và hiển thị thực đơn song ngữ trên hệ thống.
"""

import json

TRANSLATIONS = {
    # 1. Hot BBQ Sân Vườn
    333: {"en": "Grilled Beef Ribs", "portion_en": "300g portion"},
    334: {"en": "Grilled Black Chicken", "portion_en": "Whole 1.3kg chicken"},
    335: {"en": "Grilled Free-Range Chicken", "portion_en": "Whole 1.3kg + congee & giblets"},
    336: {"en": "Grilled Chicken Wings", "portion_en": "Plate of 3 wings (400g)"},
    337: {"en": "Grilled Chicken Feet", "portion_en": "Plate of 5 pairs"},
    338: {"en": "Grilled Chicken Drumsticks", "portion_en": "Plate of 2 large drumsticks"},
    339: {"en": "Grilled Pork Ribs", "portion_en": "400g plate"},
    340: {"en": "Grilled Pork Belly", "portion_en": "350g plate"},
    341: {"en": "Grilled Black Tiger Prawns", "portion_en": "250g plate (6-8 prawns)"},
    342: {"en": "Grilled Calamari (Squid)", "portion_en": "300g plate"},
    343: {"en": "Grilled Sea Pomfret", "portion_en": "Whole 800g fish"},
    344: {"en": "Grilled Fresh Oysters", "portion_en": "Large fresh oyster"},

    # 2. Best Seller
    328: {"en": "Roasted Dried Shrimp with Sea Salt", "portion_en": "100g plate"},
    329: {"en": "Crispy Shredded Dried Squid 'Nup Lum'", "portion_en": "100g plate"},
    330: {"en": "Crispy Seafood Spring Rolls", "portion_en": "4 rolls"},
    331: {"en": "Stir-Fried Glass Noodles with Seafood in X.O Sauce", "portion_en": "Plate with seafood"},
    332: {"en": "Signature Shrimp Fried Rice in X.O Sauce", "portion_en": "Plate with fresh prawns"},

    # 3. Khai Vị
    140: {"en": "Crispy French Fries", "portion_en": "300g plate"},
    142: {"en": "Green Mango Salad with Dried Squid", "portion_en": "350g plate"},
    143: {"en": "Stir-Fried Morning Glory (Water Spinach)", "portion_en": "400g plate"},
    144: {"en": "Braised / Stir-Fried Bok Choy", "portion_en": "400g plate"},
    146: {"en": "Fresh Tofu Special", "portion_en": "4 pieces plate"},
    147: {"en": "Crispy Taro Fries", "portion_en": "350g plate"},
    205: {"en": "Boiled Chicken Egg", "portion_en": "1 piece"},
    311: {"en": "Braised Bok Choy & Shiitake in Abalone Sauce", "portion_en": "Plate with 5 abalones"},
    312: {"en": "Grilled / Fried Eggplant", "portion_en": "350g plate"},
    345: {"en": "Crispy Shredded Dried Squid", "portion_en": "100g plate"},
    346: {"en": "Seafood Spring Rolls", "portion_en": "4 rolls"},

    # 4. Gà - Vịt
    148: {"en": "Whole Herbal Black Chicken", "portion_en": "Whole 1.3kg chicken"},
    150: {"en": "Whole Free-Range Garden Chicken", "portion_en": "Whole 1.3kg + congee & giblets"},
    157: {"en": "Savory Chicken Wings", "portion_en": "3 pieces (400g)"},
    159: {"en": "Herbal Roasted Duck", "portion_en": "Half duck (900g)"},
    160: {"en": "Crispy Chicken Feet", "portion_en": "5 pairs plate"},
    317: {"en": "Chicken Drumsticks", "portion_en": "2 large drumsticks"},

    # 5. Heo - Bò
    145: {"en": "Tender Beef Slices", "portion_en": "250g prepped pack"},
    161: {"en": "Pork Belly Slices", "portion_en": "350g plate"},
    201: {"en": "Pork Ribs Special", "portion_en": "400g plate"},
    314: {"en": "Prime Beef Short Ribs", "portion_en": "300g portion"},

    # 6. Hải Sản
    162: {"en": "Grilled Fresh Oysters", "portion_en": "Large fresh oyster"},
    164: {"en": "Steamed Fresh Clams", "portion_en": "500g bowl"},
    167: {"en": "Black Tiger Prawns", "portion_en": "250g plate (6-8 prawns)"},
    169: {"en": "Spotted Babylon Snails (Oc Huong)", "portion_en": "250g plate"},
    172: {"en": "Fresh Razor Clams", "portion_en": "300g plate"},
    176: {"en": "Fresh Octopus", "portion_en": "300g plate"},
    197: {"en": "Live Grouper Prepared 2 Ways", "portion_en": "Whole 2.0kg fish"},
    198: {"en": "Grilled Phu Quoc Mackerel", "portion_en": "Whole 400g fish"},
    309: {"en": "Phu Quoc Raw Herring Salad (Goi Ca)", "portion_en": "1 portion"},
    310: {"en": "Fresh Calamari (Squid)", "portion_en": "300g plate"},
    320: {"en": "Spotted Babylon Snails Special", "portion_en": "350g plate"},
    321: {"en": "Fresh Sea Pomfret", "portion_en": "Whole 800g fish"},

    # 7. Cơm - Mì
    180: {"en": "Special Fried Rice", "portion_en": "Large 250g plate"},
    181: {"en": "Stir-Fried Egg Noodles", "portion_en": "Large 2 cakes plate"},
    348: {"en": "Stir-Fried Glass Noodles with Seafood in X.O Sauce", "portion_en": "Glass noodles with seafood"},
    349: {"en": "Signature Shrimp Fried Rice in X.O Sauce", "portion_en": "Fried rice with fresh shrimp"},

    # 8. Súp - Cháo
    322: {"en": "Hot Gourmet Soup", "portion_en": "Medium bowl"},
    323: {"en": "Nutritious Rice Congee / Porridge", "portion_en": "Large bowl"},
    324: {"en": "Tom Yum Crab Soup", "portion_en": "Large bowl"},

    # 9. Món Lẩu
    325: {"en": "Thai Spicy Seafood Hotpot", "portion_en": "Hotpot set (3-4 pax)"},
    326: {"en": "Chicken Hotpot with Chili & Lime", "portion_en": "Hotpot set (3-4 pax)"},
    327: {"en": "Whole Fish Sour Hotpot (Pre-order)", "portion_en": "Whole fish hotpot"},

    # 10. Đồ Uống
    183: {"en": "Bottled Mineral Water", "portion_en": "500ml bottle"},
    184: {"en": "Coca-Cola Can", "portion_en": "320ml can"},
    185: {"en": "Pepsi Can", "portion_en": "320ml can"},
    186: {"en": "Aquarius Isotonic Drink", "portion_en": "390ml bottle"},
    187: {"en": "Revive Electrolyte Drink", "portion_en": "500ml bottle"},
    188: {"en": "Bivina Phu Quoc Beer", "portion_en": "330ml can"},
    189: {"en": "Saigon Special Beer", "portion_en": "330ml can"},
    190: {"en": "Heineken Beer", "portion_en": "250ml slim can"},
    199: {"en": "Hanoi Fresh Draught Beer (1L Pitcher)", "portion_en": "1 Liter Pitcher"},

    # 11. Pickleball
    301: {"en": "Afternoon Social Session (4PM-10PM + Drink)", "portion_en": "1 play session + 1 drink"},
    302: {"en": "Morning Social Session (6AM-4PM)", "portion_en": "1 morning session"},
    303: {"en": "Pickleball Paddle Rental", "portion_en": "1 paddle / session"},
    304: {"en": "Hourly Court Rental (+2 Drinks Included)", "portion_en": "1 hour / court"},
    305: {"en": "Monthly Unlimited Pass (All Hours)", "portion_en": "30 days unlimited access"},
    306: {"en": "Monthly Morning Pass (6AM-4PM)", "portion_en": "30 days morning slot"},
    307: {"en": "Annual VIP Individual Membership", "portion_en": "365 days VIP access"},
    308: {"en": "Fixed Monthly Slot Reservation", "portion_en": "Custom negotiated rate"}
}

OPTION_TRANS = {
    "Chiên": "Fried",
    "Xốc bơ sữa": "Butter Milk",
    "Xào tỏi": "Garlic Stir-fry",
    "Luộc": "Boiled",
    "Sốt dầu hào": "Oyster Sauce",
    "Sốt tiêu đen": "Black Pepper Sauce",
    "Cháy Tỏi": "Garlic Butter",
    "Cháy tỏi": "Garlic Butter",
    "Lúc lắc + khoai chiên": "Shaking Beef + Fries",
    "Chiên giòn": "Crispy Fried",
    "Tẩm hành": "Scallion Oil",
    "Chiên sả ớt": "Lemongrass & Chili",
    "Chiên nước mắm": "Fish Sauce Glaze",
    "Chiên mắm": "Fish Sauce Glaze",
    "Hấp mắm nhĩ": "Fish Sauce Steamed",
    "Nướng muối ớt": "Grilled Chili Salt",
    "Luộc + cháo": "Boiled + Congee",
    "Hấp hành": "Steamed Scallion",
    "Nấu chanh ớt": "Chili & Lime Broth",
    "Sốt mật ong": "Honey Glazed",
    "Sốt mắm tỏi": "Garlic Fish Sauce",
    "Nướng BBQ": "BBQ Grilled",
    "Nướng riềng mẻ": "Galangal & Fermented Rice",
    "Sốt chua ngọt": "Sweet & Sour",
    "BBQ": "BBQ Sauce",
    "Nướng Sốt BBQ": "BBQ Sauce",
    "Nướng sốt mắm nhĩ": "Fish Sauce Glaze",
    "Phô mai": "Melted Cheese",
    "Mỡ hành": "Scallion Oil & Peanuts",
    "Hấp Thái": "Spicy Thai Style",
    "Hấp sả": "Steamed with Lemongrass",
    "Xào lá quế": "Basil Stir-fry",
    "Rang muối HK": "Hong Kong Salt Bake",
    "Hấp nước dừa / sả": "Coconut Water & Lemongrass",
    "Sốt bơ tỏi": "Garlic Butter",
    "Chiên xù": "Crispy Breaded",
    "Sốt trứng muối (kèm bánh mì)": "Salted Egg Lava (w/ bread)",
    "Sốt trứng muối": "Salted Egg Sauce",
    "Nướng mỡ hành": "Scallion Oil",
    "Xào rau muống": "Morning Glory Stir-fry",
    "Xào cay": "Spicy Stir-fry",
    "Hấp hành gừng": "Ginger & Scallion Steamed",
    "Hấp Hồng Kông": "Hong Kong Steamed",
    "Nấu lẩu": "Hotpot Broth",
    "nấu lẩu": "Hotpot Broth",
    "nấu cháo": "Congee Broth",
    "sashimi": "Sashimi",
    "Trích": "Herring",
    "Xào chua ngọt": "Sweet & Sour",
    "Rang muối": "Salt Roasted",
    "Sốt XO": "XO Sauce",
    "Hải sản": "Seafood",
    "Bò": "Beef",
    "Úp trứng": "Sunny Egg",
    "Xào hải sản": "Seafood",
    "Xào bò": "Beef",
    "Sốt BBQ": "BBQ Sauce",
    "Sốt mắm nhĩ": "Fish Sauce Glaze",
    "Muối ớt": "Chili Salt",
    "Riềng mẻ": "Galangal & Rice",
    "Súp hải sản": "Seafood Soup",
    "Súp bào ngư": "Abalone Soup",
    "hải sản": "Seafood",
    "bò băm": "Minced Beef",
    "bào ngư": "Abalone",
    "Ngheu": "Clams",
    "Chim biển": "Sea Pomfret",
    "bớp": "Cobia",
    "Mú": "Grouper"
}


def enrich_menu_item(it: dict) -> dict:
    """Bổ sung các trường song ngữ: name_en, portion_en, options_bilingual, image_url chuẩn."""
    item_id = it.get("id") or it.get("item_id")
    
    # 1. Tên tiếng Anh & Định lượng tiếng Anh
    t_info = TRANSLATIONS.get(item_id, {})
    if not t_info and it.get("translations_json"):
        try:
            t_info = json.loads(it["translations_json"])
        except Exception:
            t_info = {}
            
    it["name_en"] = t_info.get("en") or t_info.get("name_en") or ""
    it["portion_en"] = t_info.get("portion_en") or ""

    # 2. Xử lý options / vị chế biến
    if it.get("options_json"):
        try:
            it["options"] = json.loads(it["options_json"])
        except Exception:
            it["options"] = []
    elif "options" not in it:
        it["options"] = []

    if it.get("options") and isinstance(it["options"], list) and len(it["options"]) > 0:
        opt_group = it["options"][0]
        if isinstance(opt_group, dict) and "options" in opt_group:
            opts = opt_group["options"]
            bilingual_opts = []
            for opt in opts:
                en_opt = OPTION_TRANS.get(opt, "")
                if en_opt:
                    bilingual_opts.append(f"{opt} / {en_opt}")
                else:
                    bilingual_opts.append(opt)
            it["options_bilingual"] = bilingual_opts
        else:
            it["options_bilingual"] = []
    else:
        it["options_bilingual"] = []

    # 3. Chuẩn hóa ảnh tuyệt đối https://pipogarden.com/... để in ấn luôn load được
    img = it.get("image_url") or ""
    if img.startswith("/static/"):
        it["image_url"] = "https://pipogarden.com" + img
    elif not img:
        it["image_url"] = "https://pipogarden.com/static/logo.png"

    return it
