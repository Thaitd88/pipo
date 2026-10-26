"""
app/menu_syncer.py
Tự động đồng bộ Menu, Danh mục, NVL (Kho), Vị chế biến (options_json) và Công thức (BOM) được cập nhật từ file Excel.
Chạy an toàn và tự động khi khởi động server (lifespan) trên cả Cloud lẫn Local.
"""

import sqlite3

CATEGORIES = [
  {
    "id": 1,
    "name": "Khai Vị",
    "icon": "🥗",
    "display_order": 1
  },
  {
    "id": 2,
    "name": "Gà - Vịt",
    "icon": "🍗",
    "display_order": 2
  },
  {
    "id": 3,
    "name": "Heo - Bò",
    "icon": "🥩",
    "display_order": 3
  },
  {
    "id": 4,
    "name": "Hải Sản",
    "icon": "🦐",
    "display_order": 4
  },
  {
    "id": 5,
    "name": "Cơm - Mì",
    "icon": "🍚",
    "display_order": 5
  },
  {
    "id": 6,
    "name": "Đồ Uống",
    "icon": "🍹",
    "display_order": 6
  },
  {
    "id": 7,
    "name": "Hot BBQ",
    "icon": "🔥",
    "display_order": 7
  },
  {
    "id": 8,
    "name": "Dịch Vụ Sân Pickleball",
    "icon": "🎾",
    "display_order": 8
  },
  {
    "id": 9,
    "name": "Best Seller",
    "icon": "⭐",
    "display_order": 9
  },
  {
    "id": 10,
    "name": "Súp - Cháo",
    "icon": "🍲",
    "display_order": 10
  },
  {
    "id": 11,
    "name": "Món Lẩu",
    "icon": "🥘",
    "display_order": 11
  }
]

MENU_ITEMS = [
  {
    "id": 139,
    "category_id": 4,
    "name": "Gỏi khoai môn hải sản",
    "price": 99000,
    "station": "COLD_KITCHEN",
    "image_url": "/static/dishes/goi_khoai_mon_hai_san.jpg?v=1792746424",
    "description": "Khai vị • Đĩa/Phần • Định lượng: Khoai 300g, Mực 60g, Tôm 60g, Sốt 30g",
    "is_available": 0,
    "calories": 440,
    "portion": "Khoai môn 300g, hải sản 120g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 140,
    "category_id": 1,
    "name": "Khoai tây",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/khoai_tay_chien.jpg",
    "description": "Khai vị khoai tây chiên giòn thơm",
    "is_available": 1,
    "calories": 480,
    "portion": "Đĩa 300g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên\", \"Xốc bơ sữa\"]}]"
  },
  {
    "id": 142,
    "category_id": 1,
    "name": "Gỏi xoài khô mực",
    "price": 99000,
    "station": "COLD_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Gỏi xoài xanh chua ngọt trộn khô mực nướng xé sợi",
    "is_available": 1,
    "calories": 282,
    "portion": "Đĩa 350g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 143,
    "category_id": 1,
    "name": "Rau muống",
    "price": 59000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/rau_muong_xao_toi.jpg",
    "description": "Rau muống xanh giòn xào tỏi thơm lừng",
    "is_available": 1,
    "calories": 92,
    "portion": "Đĩa 400g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Xào tỏi\", \"Luộc\"]}]"
  },
  {
    "id": 144,
    "category_id": 1,
    "name": "Cải thìa",
    "price": 59000,
    "station": "COLD_KITCHEN",
    "image_url": "/static/dishes/cai_thia_sot_dau_hao.jpg",
    "description": "Cải thìa Đà Lạt sốt dầu hào tỏi thơm béo",
    "is_available": 1,
    "calories": 68,
    "portion": "Đĩa 400g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt dầu hào\", \"Xào tỏi\", \"Luộc\"]}]"
  },
  {
    "id": 145,
    "category_id": 3,
    "name": "Bò sốt tiêu đen",
    "price": 279000,
    "station": "COLD_KITCHEN",
    "image_url": "/static/dishes/bo_xuyen_tieu.jpg",
    "description": "Bò mềm quyện sốt tiêu đen Phú Quốc đặc sản",
    "is_available": 1,
    "calories": 380,
    "portion": "Gói chuẩn bị sẵn 250g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 146,
    "category_id": 1,
    "name": "Đậu hũ",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/dau_hu_chien_gion.jpg",
    "description": "Đậu hũ non chiên giòn rụm, tẩm hành hoặc sả ớt",
    "is_available": 1,
    "calories": 340,
    "portion": "Đĩa 4 bìa",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên giòn\", \"Tẩm hành\", \"Chiên sả ớt\"]}]"
  },
  {
    "id": 147,
    "category_id": 1,
    "name": "Khoai môn",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/khoai_mon_chien_nuoc_mam.jpg",
    "description": "Khoai môn chiên nước mắm đậm đà bùi thơm",
    "is_available": 1,
    "calories": 392,
    "portion": "Đĩa 350g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên nước mắm\", \"Chiên giòn\"]}]"
  },
  {
    "id": 148,
    "category_id": 2,
    "name": "Gà đen nguyên con",
    "price": 399000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/ga_en_nguyen_con.jpg",
    "description": "Gà đen thả vườn da giòn thịt ngọt bổ dưỡng",
    "is_available": 1,
    "calories": 2056,
    "portion": "Gà 1 con (1.3kg)",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Hấp mắm nhĩ\", \"Chiên mắm\", \"Nướng muối ớt\"]}]"
  },
  {
    "id": 150,
    "category_id": 2,
    "name": "Gà ta nguyên con",
    "price": 350000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/ga_nuong_muoi_ot_long_me_xao.jpg",
    "description": "Gà ta thả vườn Phú Quốc thịt chắc ngọt thơm ngon",
    "is_available": 1,
    "calories": 2147,
    "portion": "Gà 1 con (1.3kg) + cháo/lòng mề",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Luộc kèm cháo\", \"Hấp hành\", \"Hấp mắm nhĩ\", \"Chiên mắm\", \"Nấu chanh ớt\", \"Nướng muối ớt\"]}]"
  },
  {
    "id": 157,
    "category_id": 2,
    "name": "Cánh gà",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/canh_ga_nuong_muoi_ot.jpg",
    "description": "Cánh gà tươi giòn rụm đậm đà hương vị",
    "is_available": 1,
    "calories": 860,
    "portion": "Dĩa 3 cái (400g)",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên nước mắm\", \"Nướng muối ớt\"]}]"
  },
  {
    "id": 159,
    "category_id": 2,
    "name": "Vịt quay thảo mộc",
    "price": 250000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/vit_quay_thao_moc.jpg?v=1792746424",
    "description": "Gà - Vịt • Nửa con • Định lượng: Vịt nửa con (~900g - 1kg)",
    "is_available": 1,
    "calories": 2660,
    "portion": "Vịt 1/2 con (900g)",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 160,
    "category_id": 2,
    "name": "Chân gà",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/chan_ga_nuong.jpg",
    "description": "Chân gà mạ cháy tỏi, chiên mắm hoặc nướng muối ớt",
    "is_available": 1,
    "calories": 752,
    "portion": "Dĩa 5 cặp",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Cháy tỏi\", \"Chiên mắm\", \"Nướng muối ớt\"]}]"
  },
  {
    "id": 161,
    "category_id": 3,
    "name": "Ba chỉ heo",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/heo_nuong_gieng_me.jpg",
    "description": "Ba chỉ heo nướng riềng mẻ hoặc chiên mắm giòn rụm",
    "is_available": 1,
    "calories": 1015,
    "portion": "Dĩa 350g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng riềng mẻ\", \"Chiên giòn\", \"Chiên nước mắm\", \"Nướng muối ớt\"]}]"
  },
  {
    "id": 162,
    "category_id": 4,
    "name": "Hàu nướng phô mai / mỡ hành",
    "price": 25000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/hau_nuong_pho_mai.jpg",
    "description": "Hàu sữa đại dương nướng phô mai béo ngậy",
    "is_available": 1,
    "calories": 65,
    "portion": "Con lớn",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng phô mai\", \"Nướng mỡ hành\"]}]"
  },
  {
    "id": 163,
    "category_id": 4,
    "name": "Hàu nướng mỡ hành",
    "price": 20000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/hau_nuong_mo_hanh.jpg?v=1792746424",
    "description": "Hàu • Con • Định lượng: Hàu tươi 1 con, Mỡ hành",
    "is_available": 1,
    "calories": 65,
    "portion": "Hàu sữa 1 con",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 164,
    "category_id": 4,
    "name": "Nghêu",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/ngheu_hap_sa.jpg",
    "description": "Nghêu lụa hấp sả hoặc hấp Thái ngọt cay thanh mát",
    "is_available": 1,
    "calories": 168,
    "portion": "Tô 500g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Hấp Thái\", \"Hấp sả\", \"Xào lá quế\"]}]"
  },
  {
    "id": 167,
    "category_id": 4,
    "name": "Tôm sú",
    "price": 179000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/tom_hap.jpg",
    "description": "Tôm sú tươi sống Phú Quốc thịt chắc ngọt đậm đà",
    "is_available": 1,
    "calories": 255,
    "portion": "Đĩa 250g (6-8 con)",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Cháy tỏi\", \"Rang muối HK\", \"Nướng muối ớt\", \"Hấp nước dừa / sả\", \"Sốt bơ tỏi\", \"Chiên xù\"]}]"
  },
  {
    "id": 169,
    "category_id": 4,
    "name": "Ốc hương",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/oc_huong_sot_trung_muoi_banh_mi.jpg?v=1792746424",
    "description": "Ốc hương tươi sống Phú Quốc giòn ngọt đậm đà, tùy chọn xào sốt trứng muối béo ngậy kèm bánh mì, cháy tỏi thơm lừng hoặc hấp sả thanh ngọt.",
    "is_available": 1,
    "calories": 320,
    "portion": "Ốc hương 250g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt trứng muối (kèm bánh mì)\", \"Cháy tỏi\", \"Hấp sả\"]}]"
  },
  {
    "id": 172,
    "category_id": 4,
    "name": "Ốc móng tay",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/oc_mong_tay_chay_toi.jpg?v=1792746424",
    "description": "Ốc móng tay tươi dày thịt giòn ngọt, tùy chọn cháy tỏi thơm nức, nướng mỡ hành đậu phộng hoặc xào rau muống giòn ngon.",
    "is_available": 1,
    "calories": 312,
    "portion": "Ốc móng tay 300g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Cháy tỏi\", \"Nướng mỡ hành\", \"Xào rau muống\"]}]"
  },
  {
    "id": 176,
    "category_id": 4,
    "name": "Bạch tuộc",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/bach_tuoc_nuong_muoi_ot.jpg?v=1792746424",
    "description": "Bạch tuộc tươi giòn sần sật, tùy chọn nướng muối ớt than hoa cay giòn, xào cay đậm vị hoặc hấp hành gừng thơm lừng.",
    "is_available": 1,
    "calories": 344,
    "portion": "Bạch tuộc 300g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng muối ớt\", \"Xào cay\", \"Hấp hành gừng\"]}]"
  },
  {
    "id": 180,
    "category_id": 5,
    "name": "Cơm chiên",
    "price": 119000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/com_chien_ghe.jpg",
    "description": "Cơm chiên hạt vàng ươm tơi xốp kèm hải sản/cá mặn",
    "is_available": 1,
    "calories": 574,
    "portion": "Đĩa lớn 250g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Hải sản\", \"Bò\", \"Úp trứng\"]}]"
  },
  {
    "id": 181,
    "category_id": 5,
    "name": "Mì xào",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/mi_xao_hai_san.jpg",
    "description": "Mì trứng xào hải sản hoặc xào bò đậm đà",
    "is_available": 1,
    "calories": 646,
    "portion": "Đĩa lớn 2 vắt",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Xào hải sản\", \"Xào bò\"]}]"
  },
  {
    "id": 183,
    "category_id": 6,
    "name": "Nước suối",
    "price": 10000,
    "station": "BAR",
    "image_url": "/static/dishes/nuoc_suoi.jpg?v=1792746424",
    "description": "Đồ uống • Chai • Nước khoáng tinh khiết • Định lượng: Chai 500ml",
    "is_available": 1,
    "calories": 0,
    "portion": "1 chai (500ml)",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]"
  },
  {
    "id": 184,
    "category_id": 6,
    "name": "Coca Cola",
    "price": 15000,
    "station": "BAR",
    "image_url": "/static/dishes/coca_cola.jpg?v=1792746424",
    "description": "Đồ uống • Lon • Nước ngọt có ga • Định lượng: Lon 320ml",
    "is_available": 1,
    "calories": 139,
    "portion": "1 lon (320ml)",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]"
  },
  {
    "id": 185,
    "category_id": 6,
    "name": "Pepsi",
    "price": 15000,
    "station": "BAR",
    "image_url": "/static/dishes/pepsi.jpg?v=1792746424",
    "description": "Đồ uống • Lon • Nước ngọt có ga • Định lượng: Lon 320ml",
    "is_available": 1,
    "calories": 145,
    "portion": "1 lon (320ml)",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]"
  },
  {
    "id": 186,
    "category_id": 6,
    "name": "Aquarius",
    "price": 15000,
    "station": "BAR",
    "image_url": "/static/dishes/aquarius.jpg?v=1792746424",
    "description": "Đồ uống • Lon • Nước thể thao • Định lượng: Lon 320ml",
    "is_available": 1,
    "calories": 86,
    "portion": "1 chai (390ml)",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]"
  },
  {
    "id": 187,
    "category_id": 6,
    "name": "Revive",
    "price": 15000,
    "station": "BAR",
    "image_url": "/static/dishes/revive.jpg?v=1792746424",
    "description": "Đồ uống • Chai • Nước bù khoáng • Định lượng: Chai 500ml",
    "is_available": 1,
    "calories": 95,
    "portion": "1 chai (500ml)",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]"
  },
  {
    "id": 188,
    "category_id": 6,
    "name": "Bia Bivina",
    "price": 16000,
    "station": "BAR",
    "image_url": "/static/dishes/bia_bivina.jpg?v=1792746424",
    "description": "Đồ uống • Lon • Bia lon • Định lượng: Lon 330ml",
    "is_available": 1,
    "calories": 142,
    "portion": "1 lon (330ml)",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]"
  },
  {
    "id": 189,
    "category_id": 6,
    "name": "Bia Sài Gòn",
    "price": 22000,
    "station": "BAR",
    "image_url": "/static/dishes/bia_sai_gon.jpg?v=1792746424",
    "description": "Đồ uống • Lon • Bia lon • Định lượng: chai 330ml",
    "is_available": 1,
    "calories": 145,
    "portion": "1 lon (330ml)",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]"
  },
  {
    "id": 190,
    "category_id": 6,
    "name": "Bia Heineken",
    "price": 25000,
    "station": "BAR",
    "image_url": "/static/dishes/bia_heineken.jpg?v=1792746424",
    "description": "Đồ uống • Lon • Bia Heineken Sleek/Mini 250ml • Định lượng: Lon 250ml",
    "is_available": 1,
    "calories": 105,
    "portion": "1 lon (250ml)",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]"
  },
  {
    "id": 197,
    "category_id": 4,
    "name": "Cá Mú 2 Món",
    "price": 800000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Cá mú sống chế biến 2 món hấp Hồng Kông & nấu lẩu",
    "is_available": 1,
    "calories": 0,
    "portion": "Con 2.0kg",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Hấp Hồng Kông\", \"Nấu lẩu\", \"Chiên xù\", \"nấu cháo\", \"sashimi\"]}]"
  },
  {
    "id": 198,
    "category_id": 4,
    "name": "Cá Sòng nướng",
    "price": 75000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/casongnuong_06516bf4.webp?v=1792746424",
    "description": "Cá sòng 400gram + rau sống",
    "is_available": 1,
    "calories": 0,
    "portion": "Con 400gram",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 199,
    "category_id": 6,
    "name": "Bia Hơi Hà Nội",
    "price": 80000,
    "station": "BAR",
    "image_url": "/static/dishes/biahoihn1l_c4483f52.webp?v=1792746424",
    "description": "",
    "is_available": 1,
    "calories": 0,
    "portion": "1L",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]"
  },
  {
    "id": 201,
    "category_id": 3,
    "name": "Sườn heo",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/suon_heo_nuong_muoi_ot.jpg",
    "description": "Sườn heo que nướng than hoa đậm đà thơm phức",
    "is_available": 1,
    "calories": 1160,
    "portion": "Dĩa 400g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt chua ngọt\", \"Nướng muối ớt\", \"BBQ\", \"Chiên mắm\"]}]"
  },
  {
    "id": 205,
    "category_id": 1,
    "name": "Trứng gà luộc",
    "price": 10000,
    "station": "HOT_KITCHEN",
    "image_url": "",
    "description": "Trứng gà ta luộc thơm ngon, giàu protein bổ sung năng lượng nhanh chóng cho người chơi thể thao tại sân Pickleball.",
    "is_available": 1,
    "calories": 0,
    "portion": "1 quả",
    "main_menu_type": "PICKLE",
    "options_json": "[]"
  },
  {
    "id": 206,
    "category_id": 1,
    "name": "Ngô luộc - Coming Soon",
    "price": 0,
    "station": "HOT_KITCHEN",
    "image_url": "",
    "description": "Bắp ngô ngọt luộc nóng hổi, thơm bùi tự nhiên (Món sắp ra mắt - Coming Soon).",
    "is_available": 0,
    "calories": 0,
    "portion": "1 bắp",
    "main_menu_type": "PICKLE",
    "options_json": "[]"
  },
  {
    "id": 301,
    "category_id": 8,
    "name": "Vé Social Chiều (16h-22h kèm nước)",
    "price": 60000,
    "station": "BAR",
    "image_url": "/static/logo.png",
    "description": "Suất chơi Pickleball Social khung giờ vàng (16h - 22h). Đã bao gồm 01 chai nước uống giải khát mát lạnh.",
    "is_available": 1,
    "calories": 0,
    "portion": "1 lượt chơi + 1 nước",
    "main_menu_type": "PICKLE",
    "options_json": "[]"
  },
  {
    "id": 302,
    "category_id": 8,
    "name": "Vé Social Sáng (06h-16h)",
    "price": 30000,
    "station": "BAR",
    "image_url": "/static/logo.png",
    "description": "Suất chơi Pickleball Social khung giờ sáng và trưa (06h - 16h). Thể thao năng động đầu ngày.",
    "is_available": 1,
    "calories": 0,
    "portion": "1 lượt chơi sáng",
    "main_menu_type": "PICKLE",
    "options_json": "[]"
  },
  {
    "id": 303,
    "category_id": 8,
    "name": "Thuê Vợt Pickleball",
    "price": 50000,
    "station": "BAR",
    "image_url": "/static/logo.png",
    "description": "Thuê vợt carbon thi đấu cao cấp siêu nhẹ, êm tay, tặng kèm bóng tập trong suốt buổi chơi.",
    "is_available": 1,
    "calories": 0,
    "portion": "1 cây / lượt",
    "main_menu_type": "PICKLE",
    "options_json": "[]"
  },
  {
    "id": 304,
    "category_id": 8,
    "name": "Thuê Sân Theo Giờ (200k/giờ, tặng 2 nước)",
    "price": 200000,
    "station": "BAR",
    "image_url": "/static/logo.png",
    "description": "Bao trọn 01 sân thi đấu tiêu chuẩn có mái che thoáng mát, tặng kèm 02 chai nước suối giải khát.",
    "is_available": 1,
    "calories": 0,
    "portion": "1 giờ / sân (kèm 2 nước)",
    "main_menu_type": "PICKLE",
    "options_json": "[]"
  },
  {
    "id": 305,
    "category_id": 8,
    "name": "Gói Social Tháng (Mọi Khung Giờ)",
    "price": 1200000,
    "station": "BAR",
    "image_url": "/static/logo.png",
    "description": "Thẻ hội viên Social tháng không giới hạn khung giờ, chơi thỏa thích bất kỳ lúc nào trong ngày (06h - 22h).",
    "is_available": 1,
    "calories": 0,
    "portion": "30 ngày không giới hạn giờ",
    "main_menu_type": "PICKLE",
    "options_json": "[]"
  },
  {
    "id": 306,
    "category_id": 8,
    "name": "Gói Social Tháng (Chỉ Buổi Sáng)",
    "price": 600000,
    "station": "BAR",
    "image_url": "/static/logo.png",
    "description": "Thẻ hội viên Social tháng khung giờ sáng (06h - 16h) dành cho người yêu thích rèn luyện thể lực đầu ngày.",
    "is_available": 1,
    "calories": 0,
    "portion": "30 ngày (06h - 16h)",
    "main_menu_type": "PICKLE",
    "options_json": "[]"
  },
  {
    "id": 307,
    "category_id": 8,
    "name": "Gói Social Năm (Cá Nhân)",
    "price": 5000000,
    "station": "BAR",
    "image_url": "/static/logo.png",
    "description": "Thẻ hội viên VIP cá nhân 1 năm (365 ngày). Chơi không giới hạn giờ, ưu tiên xếp sân và quyền lợi CLB.",
    "is_available": 1,
    "calories": 0,
    "portion": "365 ngày cá nhân",
    "main_menu_type": "PICKLE",
    "options_json": "[]"
  },
  {
    "id": 308,
    "category_id": 8,
    "name": "Đặt Sân Cố Định Tháng (Đàm Phán)",
    "price": 0,
    "station": "BAR",
    "image_url": "/static/logo.png",
    "description": "Đặt cố định sân và khung giờ theo tháng (ví dụ 18h-20h T2-T4-T6). Giá thỏa thuận linh hoạt.",
    "is_available": 1,
    "calories": 0,
    "portion": "Theo giá thỏa thuận",
    "main_menu_type": "PICKLE",
    "options_json": "[]"
  },
  {
    "id": 309,
    "category_id": 4,
    "name": "Gỏi cá",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "",
    "description": "",
    "is_available": 1,
    "calories": 0,
    "portion": "1 phần",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Trích\", \"Giỏi\"]}]"
  },
  {
    "id": 310,
    "category_id": 4,
    "name": "Mực ống",
    "price": 180000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Mực ống tươi giòn ngọt chế biến đa dạng",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 300g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên nước mắm\", \"Nướng muối ớt\", \"Hấp hành gừng\", \"Xào chua ngọt\"]}]"
  },
  {
    "id": 311,
    "category_id": 1,
    "name": "Cải Thìa Đông Cô Sốt Bào Ngư",
    "price": 200000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "",
    "is_available": 1,
    "calories": 0,
    "portion": "Dĩa 5 con bào ngư",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 312,
    "category_id": 1,
    "name": "Cà tím",
    "price": 69000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Cà tím chiên nước mắm thơm giòn đậm vị",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 350g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên nước mắm\"]}]"
  },
  {
    "id": 313,
    "category_id": 3,
    "name": "Bò lúc lắc",
    "price": 180000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Bò thăn lúc lắc mềm ngon kèm khoai tây chiên",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 250g bò",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Kèm khoai tây chiên\"]}]"
  },
  {
    "id": 314,
    "category_id": 3,
    "name": "Sườn bò",
    "price": 220000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Bò nướng tảng than hoa thơm lừng mọng nước",
    "is_available": 1,
    "calories": 0,
    "portion": "Phần 300g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng Sốt BBQ\", \"Nướng sốt mắm nhĩ\"]}]"
  },
  {
    "id": 315,
    "category_id": 3,
    "name": "Bò cháy tỏi",
    "price": 180000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Bò thăn mềm xào tỏi phi giòn rụm",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 250g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 316,
    "category_id": 3,
    "name": "Bò xào rau muống",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Bò xào rau muống đồng giòn ngọt đậm đà",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 200g bò + rau",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 317,
    "category_id": 2,
    "name": "Đùi gà",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Đùi gà nướng sốt mật ong thơm ngọt mọng nước",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 2 đùi lớn",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt mật ong\", \"Sốt mắm tỏi\", \"Nướng BBQ\"]}]"
  },
  {
    "id": 318,
    "category_id": 9,
    "name": "Heo Massage",
    "price": 279000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Thịt heo tẩm ướp đặc biệt nướng thơm giòn",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 300g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 319,
    "category_id": 3,
    "name": "Má heo",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Má heo giòn ngậy xào cháy tỏi thơm lừng",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 250g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Cháy tỏi\"]}]"
  },
  {
    "id": 320,
    "category_id": 4,
    "name": "Ốc Hương",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Sò huyết tươi xào sốt trứng muối béo ngậy",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 350g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt trứng muối\", \"Rang muối\", \"Cháy tỏi\", \"Hấp sả\", \"Sốt XO\"]}]"
  },
  {
    "id": 321,
    "category_id": 4,
    "name": "Cá chim biển",
    "price": 250000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Cá chim biển tươi nướng muối ớt thơm giòn",
    "is_available": 1,
    "calories": 0,
    "portion": "Con 800g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng muối ớt\", \"Hấp Hồng Kông\", \"nấu lẩu\"]}]"
  },
  {
    "id": 322,
    "category_id": 10,
    "name": "Súp",
    "price": 89000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Súp hải sản thanh ngọt thơm ngon",
    "is_available": 1,
    "calories": 0,
    "portion": "Tô vừa",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Súp hải sản\", \"Súp bào ngư\"]}]"
  },
  {
    "id": 323,
    "category_id": 10,
    "name": "Cháo",
    "price": 89000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Cháo nóng hổi nấu sánh mịn thơm ngon",
    "is_available": 1,
    "calories": 0,
    "portion": "Tô lớn",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Cháo hải sản\", \"Cháo bò băm\", \"Cháo bào ngư\"]}]"
  },
  {
    "id": 324,
    "category_id": 10,
    "name": "Súp Cua TomYum",
    "price": 129000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Súp TomYum cua cay nồng chuẩn vị Thái",
    "is_available": 1,
    "calories": 0,
    "portion": "Tô lớn",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 325,
    "category_id": 11,
    "name": "Lẩu Thái Hải Sản",
    "price": 299000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Lẩu Thái hải sản chua cay thơm đậm đà",
    "is_available": 1,
    "calories": 0,
    "portion": "Nồi lẩu (3-4 người)",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 326,
    "category_id": 11,
    "name": "Lẩu Gà Chanh Ớt",
    "price": 299000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Lẩu gà chanh ớt xiêm xanh cay thơm nức",
    "is_available": 1,
    "calories": 0,
    "portion": "Nồi lẩu",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 327,
    "category_id": 11,
    "name": "Lẩu Cá Chim / Cá Mú",
    "price": 299000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Lẩu cá tươi nấu ngọt thanh hoặc nấu Thái chua cay",
    "is_available": 1,
    "calories": 0,
    "portion": "Nồi lẩu 1 con",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nấu ngọt\", \"Nấu Thái\"]}]"
  },
  {
    "id": 328,
    "category_id": 9,
    "name": "Tôm khô rang muối hạt",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "",
    "is_available": 1,
    "calories": 0,
    "portion": "Dĩa 100g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 329,
    "category_id": 9,
    "name": "Khô Mực Núp Lùm",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "",
    "is_available": 1,
    "calories": 0,
    "portion": "Dĩa 100g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 330,
    "category_id": 9,
    "name": "Chả giò hải sản",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "",
    "is_available": 1,
    "calories": 0,
    "portion": "Dĩa 4 cuộn",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 331,
    "category_id": 9,
    "name": "Miến xào hải sản X.O",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "",
    "is_available": 1,
    "calories": 0,
    "portion": "Dĩa 80g miến khô, hải sản",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 332,
    "category_id": 9,
    "name": "Cơm Chiên Tôm X.O",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "",
    "is_available": 1,
    "calories": 0,
    "portion": "Dĩa 150 cơm, tôm tươi",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]"
  },
  {
    "id": 333,
    "category_id": 7,
    "name": "Sườn bò",
    "price": 220000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Bò nướng tảng than hoa thơm lừng mọng nước",
    "is_available": 1,
    "calories": 0,
    "portion": "Phần 300g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng Sốt BBQ\", \"Nướng sốt mắm nhĩ\"]}]"
  },
  {
    "id": 334,
    "category_id": 7,
    "name": "Gà đen nguyên con",
    "price": 399000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/ga_en_nguyen_con.jpg",
    "description": "Gà đen thả vườn da giòn thịt ngọt bổ dưỡng",
    "is_available": 1,
    "calories": 0,
    "portion": "Gà 1 con (1.3kg)",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Hấp mắm nhĩ\", \"Chiên mắm\", \"Nướng muối ớt\"]}]"
  },
  {
    "id": 335,
    "category_id": 7,
    "name": "Gà ta nguyên con",
    "price": 350000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/ga_nuong_muoi_ot_long_me_xao.jpg",
    "description": "Gà ta thả vườn Phú Quốc thịt chắc ngọt thơm ngon",
    "is_available": 1,
    "calories": 0,
    "portion": "Gà 1 con (1.3kg) + cháo/lòng mề",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Luộc kèm cháo\", \"Hấp hành\", \"Hấp mắm nhĩ\", \"Chiên mắm\", \"Nấu chanh ớt\", \"Nướng muối ớt\"]}]"
  },
  {
    "id": 336,
    "category_id": 7,
    "name": "Cánh gà",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/canh_ga_nuong_muoi_ot.jpg",
    "description": "Cánh gà tươi giòn rụm đậm đà hương vị",
    "is_available": 1,
    "calories": 0,
    "portion": "Dĩa 3 cái (400g)",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên nước mắm\", \"Nướng muối ớt\"]}]"
  },
  {
    "id": 337,
    "category_id": 7,
    "name": "Chân gà",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/chan_ga_nuong.jpg",
    "description": "Chân gà mạ cháy tỏi, chiên mắm hoặc nướng muối ớt",
    "is_available": 1,
    "calories": 0,
    "portion": "Dĩa 5 cặp",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Cháy tỏi\", \"Chiên mắm\", \"Nướng muối ớt\"]}]"
  },
  {
    "id": 338,
    "category_id": 7,
    "name": "Đùi gà",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Đùi gà nướng sốt mật ong thơm ngọt mọng nước",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 2 đùi lớn",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt mật ong\", \"Sốt mắm tỏi\", \"Nướng BBQ\"]}]"
  },
  {
    "id": 339,
    "category_id": 7,
    "name": "Sườn heo",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/suon_heo_nuong_muoi_ot.jpg",
    "description": "Sườn heo que nướng than hoa đậm đà thơm phức",
    "is_available": 1,
    "calories": 0,
    "portion": "Dĩa 400g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt chua ngọt\", \"Nướng muối ớt\", \"BBQ\", \"Chiên mắm\"]}]"
  },
  {
    "id": 340,
    "category_id": 7,
    "name": "Ba chỉ heo",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/heo_nuong_gieng_me.jpg",
    "description": "Ba chỉ heo nướng riềng mẻ hoặc chiên mắm giòn rụm",
    "is_available": 1,
    "calories": 0,
    "portion": "Dĩa 350g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng riềng mẻ\", \"Chiên giòn\", \"Chiên nước mắm\", \"Nướng muối ớt\"]}]"
  },
  {
    "id": 341,
    "category_id": 7,
    "name": "Tôm sú",
    "price": 179000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/tom_hap.jpg",
    "description": "Tôm sú tươi sống Phú Quốc thịt chắc ngọt đậm đà",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 250g (6-8 con)",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Cháy tỏi\", \"Rang muối HK\", \"Nướng muối ớt\", \"Hấp nước dừa / sả\", \"Sốt bơ tỏi\", \"Chiên xù\"]}]"
  },
  {
    "id": 342,
    "category_id": 7,
    "name": "Mực ống",
    "price": 180000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Mực ống tươi giòn ngọt chế biến đa dạng",
    "is_available": 1,
    "calories": 0,
    "portion": "Đĩa 300g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên nước mắm\", \"Nướng muối ớt\", \"Hấp hành gừng\", \"Xào chua ngọt\"]}]"
  },
  {
    "id": 343,
    "category_id": 7,
    "name": "Cá chim biển",
    "price": 250000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/logo.png",
    "description": "Cá chim biển tươi nướng muối ớt thơm giòn",
    "is_available": 1,
    "calories": 0,
    "portion": "Con 800g",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng muối ớt\", \"Hấp Hồng Kông\", \"nấu lẩu\"]}]"
  },
  {
    "id": 344,
    "category_id": 7,
    "name": "Hàu nướng phô mai / mỡ hành",
    "price": 25000,
    "station": "HOT_KITCHEN",
    "image_url": "/static/dishes/hau_nuong_pho_mai.jpg",
    "description": "Hàu sữa đại dương nướng phô mai béo ngậy",
    "is_available": 1,
    "calories": 0,
    "portion": "Con lớn",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng phô mai\", \"Nướng mỡ hành\"]}]"
  }
]

INVENTORY_ITEMS = [
  {
    "id": 1,
    "code": "NVL01",
    "name": "Tôm Sú / Tôm Thẻ Tươi Phú Quốc",
    "unit": "kg",
    "stock_quantity": 34.64,
    "min_stock": 8.0,
    "cost_price": 220000,
    "supplier": "Vựa Hải Sản Hàm Ninh"
  },
  {
    "id": 2,
    "code": "NVL02",
    "name": "Ốc Hương Tươi Sống",
    "unit": "kg",
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "cost_price": 250000,
    "supplier": "Vựa Hải Sản Hàm Ninh"
  },
  {
    "id": 3,
    "code": "NVL03",
    "name": "Bạch Tuộc Tươi Phú Quốc",
    "unit": "kg",
    "stock_quantity": 28.0,
    "min_stock": 6.0,
    "cost_price": 160000,
    "supplier": "Hải Sản Đảo Ngọc"
  },
  {
    "id": 4,
    "code": "NVL04",
    "name": "Hàu Sữa Tươi Đại Dương",
    "unit": "con",
    "stock_quantity": 200.0,
    "min_stock": 40.0,
    "cost_price": 7000,
    "supplier": "Hải Sản Đảo Ngọc"
  },
  {
    "id": 5,
    "code": "NVL05",
    "name": "Nghêu Lụa Tươi Sống",
    "unit": "kg",
    "stock_quantity": 30.0,
    "min_stock": 6.0,
    "cost_price": 65000,
    "supplier": "Vựa Hải Sản Hàm Ninh"
  },
  {
    "id": 6,
    "code": "NVL06",
    "name": "Tôm Khô Phú Quốc Loại 1",
    "unit": "kg",
    "stock_quantity": 8.0,
    "min_stock": 2.0,
    "cost_price": 450000,
    "supplier": "Đặc Sản Dương Đông"
  },
  {
    "id": 7,
    "code": "NVL07",
    "name": "Gà Ta Thả Vườn Làm Sạch",
    "unit": "kg",
    "stock_quantity": 45.0,
    "min_stock": 10.0,
    "cost_price": 82000,
    "supplier": "Trang Trại Gà Đồi Phú Quốc"
  },
  {
    "id": 8,
    "code": "NVL08",
    "name": "Chân Gà Tươi Chọn Lọc",
    "unit": "kg",
    "stock_quantity": 18.0,
    "min_stock": 4.0,
    "cost_price": 80000,
    "supplier": "CP Foods Vietnam"
  },
  {
    "id": 9,
    "code": "NVL09",
    "name": "Vịt Tươi Nguyên Con",
    "unit": "kg",
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "cost_price": 78000,
    "supplier": "Trang Trại Gia Cầm Sạch"
  },
  {
    "id": 10,
    "code": "NVL10",
    "name": "Thịt Bò Thăn Mềm Tươi",
    "unit": "kg",
    "stock_quantity": 22.0,
    "min_stock": 5.0,
    "cost_price": 260000,
    "supplier": "Thực Phẩm Bò Tơ"
  },
  {
    "id": 11,
    "code": "NVL11",
    "name": "Thịt Chân Giò / Ba Chỉ Heo",
    "unit": "kg",
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "cost_price": 125000,
    "supplier": "CP Foods Vietnam"
  },
  {
    "id": 12,
    "code": "NVL12",
    "name": "Nầm Heo Tươi Chọn Lọc",
    "unit": "kg",
    "stock_quantity": 18.0,
    "min_stock": 4.0,
    "cost_price": 145000,
    "supplier": "CP Foods Vietnam"
  },
  {
    "id": 13,
    "code": "NVL13",
    "name": "Khoai Môn Cao Sản",
    "unit": "kg",
    "stock_quantity": 18.199999999999996,
    "min_stock": 5.0,
    "cost_price": 35000,
    "supplier": "Nông Sản Miền Tây"
  },
  {
    "id": 14,
    "code": "NVL14",
    "name": "Khoai Tây Cọng Đông Lạnh",
    "unit": "kg",
    "stock_quantity": 32.300000000000026,
    "min_stock": 8.0,
    "cost_price": 52000,
    "supplier": "Lutosa Imports"
  },
  {
    "id": 15,
    "code": "NVL15",
    "name": "Đậu Hũ Non / Đậu Hũ Trắng",
    "unit": "bìa",
    "stock_quantity": 120.0,
    "min_stock": 25.0,
    "cost_price": 4000,
    "supplier": "Làng Đậu Truyền Thống"
  },
  {
    "id": 16,
    "code": "NVL16",
    "name": "Xoài Xanh Keo Giòn",
    "unit": "kg",
    "stock_quantity": 20.0,
    "min_stock": 5.0,
    "cost_price": 28000,
    "supplier": "Nông Sản Miền Tây"
  },
  {
    "id": 17,
    "code": "NVL17",
    "name": "Rau Muống Tươi Nhặt Sẵn",
    "unit": "kg",
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "cost_price": 20000,
    "supplier": "Vườn Rau Sạch PiPo"
  },
  {
    "id": 18,
    "code": "NVL18",
    "name": "Cải Thìa Đà Lạt",
    "unit": "kg",
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "cost_price": 25000,
    "supplier": "Nông Trại Đà Lạt"
  },
  {
    "id": 20,
    "code": "NVL20",
    "name": "Gạo Thơm ST25 (Nấu Cơm)",
    "unit": "kg",
    "stock_quantity": 50.0,
    "min_stock": 10.0,
    "cost_price": 32000,
    "supplier": "Đại Lý Gạo Sóc Trăng"
  },
  {
    "id": 21,
    "code": "NVL21",
    "name": "Mì Vàng Tươi / Mì Trứng",
    "unit": "vắt",
    "stock_quantity": 150.0,
    "min_stock": 30.0,
    "cost_price": 5000,
    "supplier": "Lò Mì Tươi Gia Truyền"
  },
  {
    "id": 23,
    "code": "NVL23",
    "name": "Trứng Muối & Trứng Gà Tươi",
    "unit": "quả",
    "stock_quantity": 180.0,
    "min_stock": 30.0,
    "cost_price": 4500,
    "supplier": "CP Foods Vietnam"
  },
  {
    "id": 27,
    "code": "NVL27",
    "name": "Trà Lài & Trà Olong Thượng Hạng",
    "unit": "kg",
    "stock_quantity": 10.0,
    "min_stock": 2.0,
    "cost_price": 180000,
    "supplier": "Trà Bảo Lộc"
  },
  {
    "id": 28,
    "code": "NVL28",
    "name": "Đào Ngâm & Mãng Cầu Xiêm Tươi",
    "unit": "kg",
    "stock_quantity": 20.0,
    "min_stock": 4.0,
    "cost_price": 65000,
    "supplier": "Thực Phẩm Pha Chế"
  },
  {
    "id": 29,
    "code": "NVL29",
    "name": "Dưa Hấu & Trái Cây Tươi",
    "unit": "kg",
    "stock_quantity": 35.0,
    "min_stock": 8.0,
    "cost_price": 22000,
    "supplier": "Nông Sản Miền Tây"
  },
  {
    "id": 31,
    "code": "NVL100",
    "name": "Mực Ống Tươi Phú Quốc",
    "unit": "kg",
    "stock_quantity": 24.64,
    "min_stock": 2.0,
    "cost_price": 180000,
    "supplier": "Vựa Hải Sản Hàm Ninh"
  },
  {
    "id": 32,
    "code": "NVL31",
    "name": "Ốc Móng Tay Tươi Sống",
    "unit": "kg",
    "stock_quantity": 30.0,
    "min_stock": 6.0,
    "cost_price": 110000,
    "supplier": "Vựa Hải Sản Hàm Ninh"
  },
  {
    "id": 33,
    "code": "NVL32",
    "name": "Cánh Gà Tươi Chọn Lọc",
    "unit": "kg",
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "cost_price": 85000,
    "supplier": "CP Foods Vietnam"
  },
  {
    "id": 34,
    "code": "NVL33",
    "name": "Thịt Ghẹ Tươi Bóc Sẵn Phú Quốc",
    "unit": "kg",
    "stock_quantity": 15.0,
    "min_stock": 3.0,
    "cost_price": 290000,
    "supplier": "Hải Sản Đảo Ngọc"
  },
  {
    "id": 38,
    "code": "NVL37",
    "name": "Gói Bò Xuyên Tiêu Chuẩn Bị Sẵn",
    "unit": "gói",
    "stock_quantity": 30.0,
    "min_stock": 6.0,
    "cost_price": 85000,
    "supplier": "Thực Phẩm Chế Biến Sẵn"
  },
  {
    "id": 41,
    "code": "NVL40",
    "name": "Gà Đen H'Mông Thả Vườn",
    "unit": "kg",
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "cost_price": 140000,
    "supplier": "Trang Trại Gà Đồi"
  },
  {
    "id": 42,
    "code": "NVL41",
    "name": "Nước Suối Tinh Khiết Chai 500ml",
    "unit": "chai",
    "stock_quantity": 105.0,
    "min_stock": 24.0,
    "cost_price": 4000,
    "supplier": "Đại Lý Nước Giải Khát"
  },
  {
    "id": 43,
    "code": "NVL42",
    "name": "Nước Ngọt Coca Cola Lon 320ml",
    "unit": "lon",
    "stock_quantity": 120.0,
    "min_stock": 24.0,
    "cost_price": 6800,
    "supplier": "Đại Lý Nước Giải Khát"
  },
  {
    "id": 44,
    "code": "NVL43",
    "name": "Nước Ngọt Pepsi Lon 320ml",
    "unit": "lon",
    "stock_quantity": 120.0,
    "min_stock": 24.0,
    "cost_price": 6800,
    "supplier": "Đại Lý Nước Giải Khát"
  },
  {
    "id": 45,
    "code": "NVL44",
    "name": "Nước Thể Thao Aquarius Lon 320ml",
    "unit": "lon",
    "stock_quantity": 80.0,
    "min_stock": 15.0,
    "cost_price": 6800,
    "supplier": "Đại Lý Nước Giải Khát"
  },
  {
    "id": 46,
    "code": "NVL45",
    "name": "Nước Bù Khoáng Revive Chai 500ml",
    "unit": "chai",
    "stock_quantity": 78.0,
    "min_stock": 15.0,
    "cost_price": 6800,
    "supplier": "Đại Lý Nước Giải Khát"
  },
  {
    "id": 47,
    "code": "NVL46",
    "name": "Bia Bivina Đặc Sản Đảo Lon 330ml",
    "unit": "lon",
    "stock_quantity": 150.0,
    "min_stock": 30.0,
    "cost_price": 8000,
    "supplier": "Nhà Phân Phối Bia Phú Quốc"
  },
  {
    "id": 48,
    "code": "NVL47",
    "name": "Bia Sài Gòn Special/Lager Lon 330ml",
    "unit": "lon",
    "stock_quantity": 150.0,
    "min_stock": 30.0,
    "cost_price": 11000,
    "supplier": "Nhà Phân Phối Bia Sabeco"
  },
  {
    "id": 49,
    "code": "NVL48",
    "name": "Bia Heineken Sleek Lon 250ml",
    "unit": "lon",
    "stock_quantity": 120.0,
    "min_stock": 24.0,
    "cost_price": 13500,
    "supplier": "Nhà Phân Phối Bia Heineken"
  },
  {
    "id": 50,
    "code": "NVL50",
    "name": "Nguyên liệu Cà tím",
    "unit": "đĩa",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 12000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 51,
    "code": "NVL51",
    "name": "Nguyên liệu Sườn bò",
    "unit": "phần",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 70000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 52,
    "code": "NVL52",
    "name": "Nguyên liệu Đùi gà",
    "unit": "đĩa",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 32000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 53,
    "code": "NVL53",
    "name": "Nguyên liệu Heo Massage",
    "unit": "đĩa",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 130000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 54,
    "code": "NVL54",
    "name": "Nguyên liệu Má heo",
    "unit": "đĩa",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 45000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 55,
    "code": "NVL55",
    "name": "Nguyên liệu Sườn heo",
    "unit": "dĩa",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 50000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 56,
    "code": "NVL56",
    "name": "Nguyên liệu Ốc Hương",
    "unit": "đĩa",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 50000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 57,
    "code": "NVL57",
    "name": "Nguyên liệu Cá Mú 2 Món",
    "unit": "con",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 280000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 58,
    "code": "NVL58",
    "name": "Nguyên liệu Cá chim biển",
    "unit": "con",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 80000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 59,
    "code": "NVL59",
    "name": "Nguyên liệu Hàu nướng phô mai / mỡ hành",
    "unit": "con",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 7000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 60,
    "code": "NVL60",
    "name": "Nguyên liệu Súp",
    "unit": "phần",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 25000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 61,
    "code": "NVL61",
    "name": "Nguyên liệu Súp Cua TomYum",
    "unit": "phần",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 40000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 62,
    "code": "NVL62",
    "name": "Nguyên liệu Lẩu Thái Hải Sản",
    "unit": "phần",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 90000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 63,
    "code": "NVL63",
    "name": "Nguyên liệu Lẩu Cá Chim / Cá Mú",
    "unit": "con",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 95000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 64,
    "code": "NVL64",
    "name": "Nguyên liệu Tôm khô rang muối hạt",
    "unit": "dĩa",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 55000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 65,
    "code": "NVL65",
    "name": "Nguyên liệu Khô Mực Núp Lùm",
    "unit": "dĩa",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 50000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 66,
    "code": "NVL66",
    "name": "Nguyên liệu Cơm Chiên Tôm X.O",
    "unit": "dĩa",
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "cost_price": 55000,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  }
]

RECIPE_BOM = [
  {
    "id": 111,
    "menu_item_id": 37,
    "ingredient_id": 27,
    "quantity": 0.015
  },
  {
    "id": 112,
    "menu_item_id": 37,
    "ingredient_id": 28,
    "quantity": 0.12
  },
  {
    "id": 114,
    "menu_item_id": 38,
    "ingredient_id": 27,
    "quantity": 0.015
  },
  {
    "id": 115,
    "menu_item_id": 38,
    "ingredient_id": 28,
    "quantity": 0.15
  },
  {
    "id": 117,
    "menu_item_id": 39,
    "ingredient_id": 29,
    "quantity": 0.45
  },
  {
    "id": 568,
    "menu_item_id": 139,
    "ingredient_id": 13,
    "quantity": 0.3
  },
  {
    "id": 569,
    "menu_item_id": 139,
    "ingredient_id": 31,
    "quantity": 0.06
  },
  {
    "id": 570,
    "menu_item_id": 139,
    "ingredient_id": 1,
    "quantity": 0.06
  },
  {
    "id": 571,
    "menu_item_id": 140,
    "ingredient_id": 14,
    "quantity": 0.3
  },
  {
    "id": 572,
    "menu_item_id": 142,
    "ingredient_id": 6,
    "quantity": 0.04
  },
  {
    "id": 573,
    "menu_item_id": 142,
    "ingredient_id": 16,
    "quantity": 0.3
  },
  {
    "id": 574,
    "menu_item_id": 143,
    "ingredient_id": 17,
    "quantity": 0.401
  },
  {
    "id": 576,
    "menu_item_id": 145,
    "ingredient_id": 38,
    "quantity": 1.0
  },
  {
    "id": 577,
    "menu_item_id": 146,
    "ingredient_id": 15,
    "quantity": 4.0
  },
  {
    "id": 578,
    "menu_item_id": 147,
    "ingredient_id": 13,
    "quantity": 0.35
  },
  {
    "id": 579,
    "menu_item_id": 148,
    "ingredient_id": 41,
    "quantity": 1.301
  },
  {
    "id": 580,
    "menu_item_id": 150,
    "ingredient_id": 7,
    "quantity": 1.301
  },
  {
    "id": 581,
    "menu_item_id": 157,
    "ingredient_id": 33,
    "quantity": 0.4
  },
  {
    "id": 582,
    "menu_item_id": 159,
    "ingredient_id": 9,
    "quantity": 0.95
  },
  {
    "id": 583,
    "menu_item_id": 160,
    "ingredient_id": 8,
    "quantity": 0.35
  },
  {
    "id": 584,
    "menu_item_id": 161,
    "ingredient_id": 11,
    "quantity": 0.35
  },
  {
    "id": 585,
    "menu_item_id": 162,
    "ingredient_id": 4,
    "quantity": 1.0
  },
  {
    "id": 586,
    "menu_item_id": 163,
    "ingredient_id": 4,
    "quantity": 1.0
  },
  {
    "id": 587,
    "menu_item_id": 164,
    "ingredient_id": 5,
    "quantity": 0.35
  },
  {
    "id": 588,
    "menu_item_id": 167,
    "ingredient_id": 1,
    "quantity": 0.3
  },
  {
    "id": 589,
    "menu_item_id": 169,
    "ingredient_id": 23,
    "quantity": 2.0
  },
  {
    "id": 590,
    "menu_item_id": 169,
    "ingredient_id": 2,
    "quantity": 0.2
  },
  {
    "id": 591,
    "menu_item_id": 172,
    "ingredient_id": 32,
    "quantity": 0.4
  },
  {
    "id": 592,
    "menu_item_id": 176,
    "ingredient_id": 3,
    "quantity": 0.4
  },
  {
    "id": 593,
    "menu_item_id": 180,
    "ingredient_id": 20,
    "quantity": 0.25
  },
  {
    "id": 594,
    "menu_item_id": 180,
    "ingredient_id": 34,
    "quantity": 0.07
  },
  {
    "id": 595,
    "menu_item_id": 180,
    "ingredient_id": 23,
    "quantity": 1.0
  },
  {
    "id": 597,
    "menu_item_id": 183,
    "ingredient_id": 42,
    "quantity": 1.0
  },
  {
    "id": 598,
    "menu_item_id": 184,
    "ingredient_id": 43,
    "quantity": 1.0
  },
  {
    "id": 599,
    "menu_item_id": 185,
    "ingredient_id": 44,
    "quantity": 1.0
  },
  {
    "id": 600,
    "menu_item_id": 186,
    "ingredient_id": 45,
    "quantity": 1.0
  },
  {
    "id": 601,
    "menu_item_id": 187,
    "ingredient_id": 46,
    "quantity": 1.0
  },
  {
    "id": 602,
    "menu_item_id": 188,
    "ingredient_id": 47,
    "quantity": 1.0
  },
  {
    "id": 603,
    "menu_item_id": 189,
    "ingredient_id": 48,
    "quantity": 1.0
  },
  {
    "id": 604,
    "menu_item_id": 190,
    "ingredient_id": 49,
    "quantity": 1.0
  },
  {
    "id": 605,
    "menu_item_id": 200,
    "ingredient_id": 10,
    "quantity": 0.35
  },
  {
    "id": 606,
    "menu_item_id": 201,
    "ingredient_id": 11,
    "quantity": 0.4
  },
  {
    "id": 607,
    "menu_item_id": 202,
    "ingredient_id": 10,
    "quantity": 0.25
  },
  {
    "id": 608,
    "menu_item_id": 203,
    "ingredient_id": 11,
    "quantity": 0.15
  },
  {
    "id": 633,
    "menu_item_id": 144,
    "ingredient_id": 18,
    "quantity": 0.4
  },
  {
    "id": 634,
    "menu_item_id": 181,
    "ingredient_id": 21,
    "quantity": 2.0
  },
  {
    "id": 635,
    "menu_item_id": 181,
    "ingredient_id": 1,
    "quantity": 0.05
  },
  {
    "id": 636,
    "menu_item_id": 181,
    "ingredient_id": 31,
    "quantity": 0.05
  },
  {
    "id": 637,
    "menu_item_id": 311,
    "ingredient_id": 18,
    "quantity": 1.0
  },
  {
    "id": 638,
    "menu_item_id": 312,
    "ingredient_id": 50,
    "quantity": 1.0
  },
  {
    "id": 639,
    "menu_item_id": 313,
    "ingredient_id": 10,
    "quantity": 1.0
  },
  {
    "id": 640,
    "menu_item_id": 314,
    "ingredient_id": 51,
    "quantity": 1.0
  },
  {
    "id": 641,
    "menu_item_id": 315,
    "ingredient_id": 10,
    "quantity": 1.0
  },
  {
    "id": 642,
    "menu_item_id": 316,
    "ingredient_id": 10,
    "quantity": 1.0
  },
  {
    "id": 643,
    "menu_item_id": 317,
    "ingredient_id": 52,
    "quantity": 1.0
  },
  {
    "id": 644,
    "menu_item_id": 318,
    "ingredient_id": 53,
    "quantity": 1.0
  },
  {
    "id": 645,
    "menu_item_id": 319,
    "ingredient_id": 54,
    "quantity": 1.0
  },
  {
    "id": 646,
    "menu_item_id": 320,
    "ingredient_id": 56,
    "quantity": 1.0
  },
  {
    "id": 647,
    "menu_item_id": 310,
    "ingredient_id": 31,
    "quantity": 1.0
  },
  {
    "id": 648,
    "menu_item_id": 197,
    "ingredient_id": 57,
    "quantity": 1.0
  },
  {
    "id": 649,
    "menu_item_id": 321,
    "ingredient_id": 58,
    "quantity": 1.0
  },
  {
    "id": 650,
    "menu_item_id": 322,
    "ingredient_id": 60,
    "quantity": 1.0
  },
  {
    "id": 651,
    "menu_item_id": 323,
    "ingredient_id": 20,
    "quantity": 1.0
  },
  {
    "id": 652,
    "menu_item_id": 324,
    "ingredient_id": 61,
    "quantity": 1.0
  },
  {
    "id": 653,
    "menu_item_id": 325,
    "ingredient_id": 62,
    "quantity": 1.0
  },
  {
    "id": 654,
    "menu_item_id": 326,
    "ingredient_id": 7,
    "quantity": 1.0
  },
  {
    "id": 655,
    "menu_item_id": 327,
    "ingredient_id": 63,
    "quantity": 1.0
  },
  {
    "id": 656,
    "menu_item_id": 328,
    "ingredient_id": 64,
    "quantity": 1.0
  },
  {
    "id": 657,
    "menu_item_id": 329,
    "ingredient_id": 65,
    "quantity": 1.0
  },
  {
    "id": 658,
    "menu_item_id": 330,
    "ingredient_id": 62,
    "quantity": 1.0
  },
  {
    "id": 659,
    "menu_item_id": 331,
    "ingredient_id": 62,
    "quantity": 1.0
  },
  {
    "id": 660,
    "menu_item_id": 332,
    "ingredient_id": 66,
    "quantity": 1.0
  },
  {
    "id": 661,
    "menu_item_id": 333,
    "ingredient_id": 51,
    "quantity": 1.0
  },
  {
    "id": 662,
    "menu_item_id": 334,
    "ingredient_id": 41,
    "quantity": 1.301
  },
  {
    "id": 663,
    "menu_item_id": 335,
    "ingredient_id": 7,
    "quantity": 1.301
  },
  {
    "id": 664,
    "menu_item_id": 336,
    "ingredient_id": 33,
    "quantity": 0.4
  },
  {
    "id": 665,
    "menu_item_id": 337,
    "ingredient_id": 8,
    "quantity": 0.35
  },
  {
    "id": 666,
    "menu_item_id": 338,
    "ingredient_id": 52,
    "quantity": 1.0
  },
  {
    "id": 667,
    "menu_item_id": 339,
    "ingredient_id": 11,
    "quantity": 0.4
  },
  {
    "id": 668,
    "menu_item_id": 340,
    "ingredient_id": 11,
    "quantity": 0.35
  },
  {
    "id": 669,
    "menu_item_id": 341,
    "ingredient_id": 1,
    "quantity": 0.3
  },
  {
    "id": 670,
    "menu_item_id": 342,
    "ingredient_id": 31,
    "quantity": 1.0
  },
  {
    "id": 671,
    "menu_item_id": 343,
    "ingredient_id": 58,
    "quantity": 1.0
  },
  {
    "id": 672,
    "menu_item_id": 344,
    "ingredient_id": 4,
    "quantity": 1.0
  }
]

def ensure_updated_menu(conn: sqlite3.Connection):
    cur = conn.cursor()
    
    # 1. Đồng bộ Danh mục
    for c in CATEGORIES:
        cur.execute("SELECT id FROM categories WHERE id = ? OR name = ?", (c["id"], c["name"]))
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE categories 
                SET name = ?, icon = ?, display_order = ?
                WHERE id = ?
            """, (c["name"], c["icon"], c["display_order"], row[0]))
        else:
            cur.execute("""
                INSERT INTO categories (id, name, icon, display_order)
                VALUES (?, ?, ?, ?)
            """, (c["id"], c["name"], c["icon"], c["display_order"]))

    # 2. Đồng bộ NVL (inventory_items)
    for iv in INVENTORY_ITEMS:
        cur.execute("SELECT id FROM inventory_items WHERE code = ? OR name = ?", (iv["code"], iv["name"]))
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE inventory_items
                SET code = ?, name = ?, unit = ?, cost_price = ?, supplier = ?
                WHERE id = ?
            """, (iv["code"], iv["name"], iv["unit"], iv["cost_price"], iv["supplier"], row[0]))
        else:
            cur.execute("""
                INSERT INTO inventory_items (id, code, name, unit, stock_quantity, min_stock, cost_price, supplier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (iv["id"], iv["code"], iv["name"], iv["unit"], iv["stock_quantity"], iv["min_stock"], iv["cost_price"], iv["supplier"]))

    # 3. Đồng bộ Món ăn & Vị chế biến (menu_items)
    for it in MENU_ITEMS:
        cur.execute("SELECT id FROM menu_items WHERE id = ? OR (name = ? AND category_id = ?)", (it["id"], it["name"], it["category_id"]))
        row = cur.fetchone()
        opt_json = it.get("options_json") or "[]"
        if row:
            cur.execute("""
                UPDATE menu_items
                SET category_id = ?, name = ?, price = ?, station = ?, 
                    image_url = ?, description = ?, is_available = ?, calories = ?, portion = ?, 
                    main_menu_type = ?, options_json = ?
                WHERE id = ?
            """, (it["category_id"], it["name"], it["price"], it["station"],
                  it["image_url"], it["description"], it["is_available"], it["calories"], it["portion"],
                  it["main_menu_type"], opt_json, row[0]))
        else:
            cur.execute("""
                INSERT INTO menu_items (id, category_id, name, price, station, image_url, description, is_available, calories, portion, main_menu_type, options_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (it["id"], it["category_id"], it["name"], it["price"], it["station"],
                  it["image_url"], it["description"], it["is_available"], it["calories"], it["portion"],
                  it["main_menu_type"], opt_json))

    # 4. Đồng bộ Định mức NVL (recipe_bom)
    for b in RECIPE_BOM:
        cur.execute("SELECT id FROM recipe_bom WHERE menu_item_id = ? AND ingredient_id = ?", (b["menu_item_id"], b["ingredient_id"]))
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE recipe_bom
                SET quantity = ?
                WHERE id = ?
            """, (b["quantity"], row[0]))
        else:
            cur.execute("""
                INSERT INTO recipe_bom (menu_item_id, ingredient_id, quantity)
                VALUES (?, ?, ?)
            """, (b["menu_item_id"], b["ingredient_id"], b["quantity"]))

    conn.commit()
    print("[PiPo Garden] Menu, Vị chế biến, NVL và BOM đã được đồng bộ chuẩn xác từ Excel vào DB!")
