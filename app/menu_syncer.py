"""
app/menu_syncer.py
Tự động đồng bộ Menu, Danh mục, NVL (Kho), Vị chế biến (options_json) và Công thức (BOM).
Chạy an toàn khi khởi động máy chủ: Tự động CLEAR toàn bộ món cũ trên Host và nạp lại chuẩn xác từ file Excel!
"""

import sqlite3

CATEGORIES = [
  {
    "id": 7,
    "name": "Hot BBQ",
    "icon": "🔥",
    "display_order": 1
  },
  {
    "id": 9,
    "name": "Best Seller",
    "icon": "⭐",
    "display_order": 2
  },
  {
    "id": 1,
    "name": "Khai Vị",
    "icon": "🥗",
    "display_order": 3
  },
  {
    "id": 2,
    "name": "Gà - Vịt",
    "icon": "🍗",
    "display_order": 4
  },
  {
    "id": 3,
    "name": "Heo - Bò",
    "icon": "🥩",
    "display_order": 5
  },
  {
    "id": 4,
    "name": "Hải Sản",
    "icon": "🦐",
    "display_order": 6
  },
  {
    "id": 5,
    "name": "Cơm - Mì",
    "icon": "🍚",
    "display_order": 7
  },
  {
    "id": 10,
    "name": "Súp - Cháo",
    "icon": "🍲",
    "display_order": 8
  },
  {
    "id": 11,
    "name": "Món Lẩu",
    "icon": "🥘",
    "display_order": 9
  },
  {
    "id": 6,
    "name": "Đồ Uống",
    "icon": "🍹",
    "display_order": 10
  },
  {
    "id": 8,
    "name": "Dịch Vụ Sân Pickleball",
    "icon": "🎾",
    "display_order": 11
  }
]
MENU_ITEMS = [
  {
    "id": 140,
    "category_id": 1,
    "name": "Khoai tây",
    "portion": "Đĩa 300g",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên\", \"Xốc bơ sữa\"]}]",
    "image_url": "/static/dishes/khoai_tay_chien.jpg",
    "description": "Khai vị khoai tây chiên giòn thơm",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 142,
    "category_id": 1,
    "name": "Gỏi xoài khô mực",
    "portion": "Đĩa 350g",
    "price": 99000,
    "station": "COLD_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Gỏi xoài xanh chua ngọt trộn khô mực nướng xé sợi",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 143,
    "category_id": 1,
    "name": "Rau muống",
    "portion": "Đĩa 400g",
    "price": 59000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Xào tỏi\", \"Luộc\"]}]",
    "image_url": "/static/dishes/rau_muong_xao_toi.jpg",
    "description": "Rau muống xanh giòn xào tỏi thơm lừng",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 144,
    "category_id": 1,
    "name": "Cải thìa",
    "portion": "Đĩa 400g",
    "price": 59000,
    "station": "COLD_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt dầu hào\", \"Xào tỏi\", \"Luộc\"]}]",
    "image_url": "/static/dishes/cai_thia_sot_dau_hao.jpg",
    "description": "Cải thìa Đà Lạt sốt dầu hào tỏi thơm béo",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 146,
    "category_id": 1,
    "name": "Đậu hũ",
    "portion": "Đĩa 4 bìa",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên giòn\", \"Tẩm hành\", \"Chiên sả ớt\"]}]",
    "image_url": "/static/dishes/dau_hu_chien_gion.jpg",
    "description": "Đậu hũ non chiên giòn rụm, tẩm hành hoặc sả ớt",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 147,
    "category_id": 1,
    "name": "Khoai môn",
    "portion": "Đĩa 350g",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên nước mắm\", \"Chiên giòn\"]}]",
    "image_url": "/static/dishes/khoai_mon_chien_nuoc_mam.jpg",
    "description": "Khoai môn chiên nước mắm đậm đà bùi thơm",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 205,
    "category_id": 1,
    "name": "Trứng gà luộc",
    "portion": "1 quả",
    "price": 10000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "PICKLE",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Trứng gà ta luộc thơm ngon, giàu protein bổ sung năng lượng nhanh chóng cho người chơi thể thao tại sân Pickleball.",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 206,
    "category_id": 1,
    "name": "Ngô luộc - Coming Soon",
    "portion": "1 bắp",
    "price": 0,
    "station": "HOT_KITCHEN",
    "main_menu_type": "PICKLE",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Bắp ngô ngọt luộc nóng hổi, thơm bùi tự nhiên (Món sắp ra mắt - Coming Soon).",
    "is_available": 0,
    "calories": 0
  },
  {
    "id": 311,
    "category_id": 1,
    "name": "Cải Thìa Đông Cô Sốt Bào Ngư",
    "portion": "Dĩa 5 con bào ngư",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Cải Thìa Đông Cô Sốt Bào Ngư tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 312,
    "category_id": 1,
    "name": "Cà tím",
    "portion": "Đĩa 350g",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên nước mắm\", \"Nướng mỡ hành\"]}]",
    "image_url": "/static/logo.png",
    "description": "Cà tím chiên nước mắm thơm giòn đậm vị",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 345,
    "category_id": 1,
    "name": "Khô Mực Núp Lùm",
    "portion": "Dĩa 100g",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Khô Mực Núp Lùm tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 346,
    "category_id": 1,
    "name": "Chả giò hải sản",
    "portion": "Dĩa 4 cuộn",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Chả giò hải sản tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 148,
    "category_id": 2,
    "name": "Gà đen nguyên con",
    "portion": "Gà 1 con (1.3kg)",
    "price": 399000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Hấp mắm nhĩ\", \"Chiên mắm\", \"Nướng muối ớt\", \"Luộc + cháo\"]}]",
    "image_url": "/static/dishes/ga_en_nguyen_con.jpg",
    "description": "Gà đen thả vườn da giòn thịt ngọt bổ dưỡng",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 150,
    "category_id": 2,
    "name": "Gà ta nguyên con",
    "portion": "Gà 1 con (1.3kg) + cháo/lòng mề",
    "price": 350000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Luộc + cháo\", \"Hấp hành\", \"Hấp mắm nhĩ\", \"Chiên mắm\", \"Nấu chanh ớt\", \"Nướng muối ớt\"]}]",
    "image_url": "/static/dishes/ga_nuong_muoi_ot_long_me_xao.jpg",
    "description": "Gà ta thả vườn Phú Quốc thịt chắc ngọt thơm ngon",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 157,
    "category_id": 2,
    "name": "Cánh gà",
    "portion": "Dĩa 3 cái (400g)",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên nước mắm\", \"Nướng muối ớt\"]}]",
    "image_url": "/static/dishes/canh_ga_nuong_muoi_ot.jpg",
    "description": "Cánh gà tươi giòn rụm đậm đà hương vị",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 159,
    "category_id": 2,
    "name": "Vịt quay thảo mộc",
    "portion": "Vịt 1/2 con (900g)",
    "price": 250000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/dishes/vit_quay_thao_moc.jpg",
    "description": "Gà - Vịt • Nửa con • Định lượng: Vịt nửa con (~900g - 1kg)",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 160,
    "category_id": 2,
    "name": "Chân gà",
    "portion": "Dĩa 5 cặp",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Cháy tỏi\", \"Chiên mắm\", \"Nướng muối ớt\"]}]",
    "image_url": "/static/dishes/chan_ga_nuong.jpg",
    "description": "Chân gà mạ cháy tỏi, chiên mắm hoặc nướng muối ớt",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 317,
    "category_id": 2,
    "name": "Đùi gà",
    "portion": "Đĩa 2 đùi lớn",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt mật ong\", \"Sốt mắm tỏi\", \"Nướng BBQ\"]}]",
    "image_url": "/static/logo.png",
    "description": "Đùi gà nướng sốt mật ong thơm ngọt mọng nước",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 145,
    "category_id": 3,
    "name": "Bò",
    "portion": "Gói chuẩn bị sẵn 250g",
    "price": 279000,
    "station": "COLD_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt tiêu đen\", \"Cháy Tỏi\", \"Lúc lắc + khoai chiên\"]}]",
    "image_url": "/static/dishes/bo_xuyen_tieu.jpg",
    "description": "Bò mềm quyện sốt tiêu đen Phú Quốc đặc sản",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 161,
    "category_id": 3,
    "name": "Ba chỉ heo",
    "portion": "Dĩa 350g",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng riềng mẻ\", \"Chiên giòn\", \"Chiên nước mắm\", \"Nướng muối ớt\"]}]",
    "image_url": "/static/dishes/heo_nuong_gieng_me.jpg",
    "description": "Ba chỉ heo nướng riềng mẻ hoặc chiên mắm giòn rụm",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 201,
    "category_id": 3,
    "name": "Sườn heo",
    "portion": "Dĩa 400g",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt chua ngọt\", \"Nướng muối ớt\", \"BBQ\", \"Chiên mắm\"]}]",
    "image_url": "/static/dishes/suon_heo_nuong_muoi_ot.jpg",
    "description": "Sườn heo que nướng than hoa đậm đà thơm phức",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 314,
    "category_id": 3,
    "name": "Sườn bò",
    "portion": "Phần 300g",
    "price": 220000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng Sốt BBQ\", \"Nướng sốt mắm nhĩ\"]}]",
    "image_url": "/static/logo.png",
    "description": "Bò nướng tảng than hoa thơm lừng mọng nước",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 319,
    "category_id": 3,
    "name": "Má heo",
    "portion": "Đĩa 250g",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Cháy tỏi\"]}]",
    "image_url": "/static/logo.png",
    "description": "Má heo giòn ngậy xào cháy tỏi thơm lừng",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 347,
    "category_id": 3,
    "name": "Heo Massage",
    "portion": "Đĩa 300g",
    "price": 180000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Thịt heo tẩm ướp đặc biệt nướng thơm giòn",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 162,
    "category_id": 4,
    "name": "Hàu nướng",
    "portion": "Con lớn",
    "price": 25000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Phô mai\", \"Mỡ hành\"]}]",
    "image_url": "/static/dishes/hau_nuong_pho_mai.jpg",
    "description": "Hàu sữa đại dương nướng phô mai béo ngậy",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 164,
    "category_id": 4,
    "name": "Nghêu",
    "portion": "Tô 500g",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Hấp Thái\", \"Hấp sả\", \"Xào lá quế\"]}]",
    "image_url": "/static/dishes/ngheu_hap_sa.jpg",
    "description": "Nghêu lụa hấp sả hoặc hấp Thái ngọt cay thanh mát",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 167,
    "category_id": 4,
    "name": "Tôm sú",
    "portion": "Đĩa 250g (6-8 con)",
    "price": 179000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Cháy tỏi\", \"Rang muối HK\", \"Nướng muối ớt\", \"Hấp nước dừa / sả\", \"Sốt bơ tỏi\", \"Chiên xù\"]}]",
    "image_url": "/static/dishes/tom_hap.jpg",
    "description": "Tôm sú tươi sống Phú Quốc thịt chắc ngọt đậm đà",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 169,
    "category_id": 4,
    "name": "Ốc hương",
    "portion": "Ốc hương 250g",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt trứng muối (kèm bánh mì)\", \"Cháy tỏi\", \"Hấp sả\"]}]",
    "image_url": "/static/dishes/oc_huong_sot_trung_muoi_banh_mi.jpg",
    "description": "Ốc hương tươi sống Phú Quốc giòn ngọt đậm đà, tùy chọn xào sốt trứng muối béo ngậy kèm bánh mì, cháy tỏi thơm lừng hoặc hấp sả thanh ngọt.",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 172,
    "category_id": 4,
    "name": "Ốc móng tay",
    "portion": "Ốc móng tay 300g",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Cháy tỏi\", \"Nướng mỡ hành\", \"Xào rau muống\"]}]",
    "image_url": "/static/dishes/oc_mong_tay_chay_toi.jpg",
    "description": "Ốc móng tay tươi dày thịt giòn ngọt, tùy chọn cháy tỏi thơm nức, nướng mỡ hành đậu phộng hoặc xào rau muống giòn ngon.",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 176,
    "category_id": 4,
    "name": "Bạch tuộc",
    "portion": "Bạch tuộc 300g",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng muối ớt\", \"Xào cay\", \"Hấp hành gừng\"]}]",
    "image_url": "/static/dishes/bach_tuoc_nuong_muoi_ot.jpg",
    "description": "Bạch tuộc tươi giòn sần sật, tùy chọn nướng muối ớt than hoa cay giòn, xào cay đậm vị hoặc hấp hành gừng thơm lừng.",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 197,
    "category_id": 4,
    "name": "Cá Mú 2 Món",
    "portion": "Con 2.0kg",
    "price": 800000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Hấp Hồng Kông\", \"Nấu lẩu\", \"Chiên xù\", \"nấu cháo\", \"sashimi\"]}]",
    "image_url": "/static/logo.png",
    "description": "Cá mú sống chế biến 2 món hấp Hồng Kông & nấu lẩu",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 198,
    "category_id": 4,
    "name": "Cá Sòng nướng",
    "portion": "Con 400gram",
    "price": 75000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/dishes/casongnuong_06516bf4.webp",
    "description": "Cá sòng 400gram + rau sống",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 309,
    "category_id": 4,
    "name": "Gỏi cá",
    "portion": "1 phần",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Trích\"]}]",
    "image_url": "/static/logo.png",
    "description": "Gỏi cá tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 310,
    "category_id": 4,
    "name": "Mực ống",
    "portion": "Đĩa 300g",
    "price": 180000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chiên nước mắm\", \"Nướng muối ớt\", \"Hấp hành gừng\", \"Xào chua ngọt\"]}]",
    "image_url": "/static/logo.png",
    "description": "Mực ống tươi giòn ngọt chế biến đa dạng",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 320,
    "category_id": 4,
    "name": "Ốc Hương",
    "portion": "Đĩa 350g",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt trứng muối\", \"Rang muối\", \"Cháy tỏi\", \"Hấp sả\", \"Sốt XO\"]}]",
    "image_url": "/static/logo.png",
    "description": "Sò huyết tươi xào sốt trứng muối béo ngậy",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 321,
    "category_id": 4,
    "name": "Cá chim biển",
    "portion": "Con 800g",
    "price": 250000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Nướng muối ớt\", \"Hấp Hồng Kông\", \"nấu lẩu\"]}]",
    "image_url": "/static/logo.png",
    "description": "Cá chim biển tươi nướng muối ớt thơm giòn",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 180,
    "category_id": 5,
    "name": "Cơm chiên",
    "portion": "Đĩa lớn 250g",
    "price": 119000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Hải sản\", \"Bò\", \"Úp trứng\"]}]",
    "image_url": "/static/dishes/com_chien_ghe.jpg",
    "description": "Cơm chiên hạt vàng ươm tơi xốp kèm hải sản/cá mặn",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 181,
    "category_id": 5,
    "name": "Mì xào",
    "portion": "Đĩa lớn 2 vắt",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Xào hải sản\", \"Xào bò\"]}]",
    "image_url": "/static/dishes/mi_xao_hai_san.jpg",
    "description": "Mì trứng xào hải sản hoặc xào bò đậm đà",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 348,
    "category_id": 5,
    "name": "Miến xào hải sản X.O",
    "portion": "Dĩa 80g miến khô, hải sản",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Miến xào hải sản X.O tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 349,
    "category_id": 5,
    "name": "Cơm Chiên Tôm X.O",
    "portion": "Dĩa 150 cơm, tôm tươi",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Cơm Chiên Tôm X.O tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 183,
    "category_id": 6,
    "name": "Nước suối",
    "portion": "1 chai (500ml)",
    "price": 10000,
    "station": "BAR",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]",
    "image_url": "/static/dishes/nuoc_suoi.jpg",
    "description": "Đồ uống • Chai • Nước khoáng tinh khiết • Định lượng: Chai 500ml",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 184,
    "category_id": 6,
    "name": "Coca Cola",
    "portion": "1 lon (320ml)",
    "price": 15000,
    "station": "BAR",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]",
    "image_url": "/static/dishes/coca_cola.jpg",
    "description": "Đồ uống • Lon • Nước ngọt có ga • Định lượng: Lon 320ml",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 185,
    "category_id": 6,
    "name": "Pepsi",
    "portion": "1 lon (320ml)",
    "price": 15000,
    "station": "BAR",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]",
    "image_url": "/static/dishes/pepsi.jpg",
    "description": "Đồ uống • Lon • Nước ngọt có ga • Định lượng: Lon 320ml",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 186,
    "category_id": 6,
    "name": "Aquarius",
    "portion": "1 chai (390ml)",
    "price": 15000,
    "station": "BAR",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]",
    "image_url": "/static/dishes/aquarius.jpg",
    "description": "Đồ uống • Lon • Nước thể thao • Định lượng: Lon 320ml",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 187,
    "category_id": 6,
    "name": "Revive",
    "portion": "1 chai (500ml)",
    "price": 15000,
    "station": "BAR",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]",
    "image_url": "/static/dishes/revive.jpg",
    "description": "Đồ uống • Chai • Nước bù khoáng • Định lượng: Chai 500ml",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 188,
    "category_id": 6,
    "name": "Bia Bivina",
    "portion": "1 lon (330ml)",
    "price": 16000,
    "station": "BAR",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]",
    "image_url": "/static/dishes/bia_bivina.jpg",
    "description": "Đồ uống • Lon • Bia lon • Định lượng: Lon 330ml",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 189,
    "category_id": 6,
    "name": "Bia Sài Gòn",
    "portion": "1 lon (330ml)",
    "price": 22000,
    "station": "BAR",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]",
    "image_url": "/static/dishes/bia_sai_gon.jpg",
    "description": "Đồ uống • Lon • Bia lon • Định lượng: chai 330ml",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 190,
    "category_id": 6,
    "name": "Bia Heineken",
    "portion": "1 lon (250ml)",
    "price": 25000,
    "station": "BAR",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]",
    "image_url": "/static/dishes/bia_heineken.jpg",
    "description": "Đồ uống • Lon • Bia Heineken Sleek/Mini 250ml • Định lượng: Lon 250ml",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 199,
    "category_id": 6,
    "name": "Bia Hơi Hà Nội",
    "portion": "1L",
    "price": 80000,
    "station": "BAR",
    "main_menu_type": "RESTAURANT,PICKLE",
    "options_json": "[]",
    "image_url": "/static/dishes/biahoihn1l_c4483f52.webp",
    "description": "Bia Hơi Hà Nội tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 333,
    "category_id": 7,
    "name": "Sườn bò nướng",
    "portion": "Phần 300g",
    "price": 220000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt BBQ\", \"Sốt mắm nhĩ\"]}]",
    "image_url": "/static/logo.png",
    "description": "Bò nướng tảng than hoa thơm lừng mọng nước",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 334,
    "category_id": 7,
    "name": "Gà đen nướng",
    "portion": "Gà 1 con (1.3kg)",
    "price": 399000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt BBQ\", \"Sốt mắm nhĩ\", \"Muối ớt\"]}]",
    "image_url": "/static/dishes/ga_en_nguyen_con.jpg",
    "description": "Gà đen thả vườn da giòn thịt ngọt bổ dưỡng",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 335,
    "category_id": 7,
    "name": "Gà ta nướng",
    "portion": "Gà 1 con (1.3kg) + cháo/lòng mề",
    "price": 350000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt BBQ\", \"Sốt mắm nhĩ\", \"Muối ớt\"]}]",
    "image_url": "/static/dishes/ga_nuong_muoi_ot_long_me_xao.jpg",
    "description": "Gà ta thả vườn Phú Quốc thịt chắc ngọt thơm ngon",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 336,
    "category_id": 7,
    "name": "Cánh gà nướng",
    "portion": "Dĩa 3 cái (400g)",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt BBQ\", \"Sốt mắm nhĩ\", \"Muối ớt\"]}]",
    "image_url": "/static/dishes/canh_ga_nuong_muoi_ot.jpg",
    "description": "Cánh gà tươi giòn rụm đậm đà hương vị",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 337,
    "category_id": 7,
    "name": "Chân gà nướng",
    "portion": "Dĩa 5 cặp",
    "price": 79000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt BBQ\", \"Sốt mắm nhĩ\", \"Muối ớt\"]}]",
    "image_url": "/static/dishes/chan_ga_nuong.jpg",
    "description": "Chân gà mạ cháy tỏi, chiên mắm hoặc nướng muối ớt",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 338,
    "category_id": 7,
    "name": "Đùi gà nướng",
    "portion": "Đĩa 2 đùi lớn",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt BBQ\", \"Sốt mắm nhĩ\", \"Muối ớt\"]}]",
    "image_url": "/static/logo.png",
    "description": "Đùi gà nướng sốt mật ong thơm ngọt mọng nước",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 339,
    "category_id": 7,
    "name": "Sườn heo nướng",
    "portion": "Dĩa 400g",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt BBQ\", \"Sốt mắm nhĩ\", \"Muối ớt\"]}]",
    "image_url": "/static/dishes/suon_heo_nuong_muoi_ot.jpg",
    "description": "Sườn heo que nướng than hoa đậm đà thơm phức",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 340,
    "category_id": 7,
    "name": "Ba chỉ heo nướng",
    "portion": "Dĩa 350g",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt BBQ\", \"Sốt mắm nhĩ\", \"Muối ớt\", \"Riềng mẻ\"]}]",
    "image_url": "/static/dishes/heo_nuong_gieng_me.jpg",
    "description": "Ba chỉ heo nướng riềng mẻ hoặc chiên mắm giòn rụm",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 341,
    "category_id": 7,
    "name": "Tôm sú nướng",
    "portion": "Đĩa 250g (6-8 con)",
    "price": 179000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt BBQ\", \"Sốt mắm nhĩ\", \"Muối ớt\"]}]",
    "image_url": "/static/dishes/tom_hap.jpg",
    "description": "Tôm sú tươi sống Phú Quốc thịt chắc ngọt đậm đà",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 342,
    "category_id": 7,
    "name": "Mực ống nướng",
    "portion": "Đĩa 300g",
    "price": 180000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt BBQ\", \"Sốt mắm nhĩ\", \"Muối ớt\"]}]",
    "image_url": "/static/logo.png",
    "description": "Mực ống tươi giòn ngọt chế biến đa dạng",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 343,
    "category_id": 7,
    "name": "Cá chim biển nướng",
    "portion": "Con 800g",
    "price": 250000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Sốt BBQ\", \"Sốt mắm nhĩ\", \"Muối ớt\"]}]",
    "image_url": "/static/logo.png",
    "description": "Cá chim biển tươi nướng muối ớt thơm giòn",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 344,
    "category_id": 7,
    "name": "Hàu nướng",
    "portion": "Con lớn",
    "price": 25000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Phô mai\", \"Mỡ hành\"]}]",
    "image_url": "/static/dishes/hau_nuong_pho_mai.jpg",
    "description": "Hàu sữa đại dương nướng phô mai béo ngậy",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 301,
    "category_id": 8,
    "name": "Vé Social Chiều (16h-22h kèm nước)",
    "portion": "1 lượt chơi + 1 nước",
    "price": 60000,
    "station": "BAR",
    "main_menu_type": "PICKLE",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Suất chơi Pickleball Social khung giờ vàng (16h - 22h). Đã bao gồm 01 chai nước uống giải khát mát lạnh.",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 302,
    "category_id": 8,
    "name": "Vé Social Sáng (06h-16h)",
    "portion": "1 lượt chơi sáng",
    "price": 30000,
    "station": "BAR",
    "main_menu_type": "PICKLE",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Suất chơi Pickleball Social khung giờ sáng và trưa (06h - 16h). Thể thao năng động đầu ngày.",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 303,
    "category_id": 8,
    "name": "Thuê Vợt Pickleball",
    "portion": "1 cây / lượt",
    "price": 50000,
    "station": "BAR",
    "main_menu_type": "PICKLE",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Thuê vợt carbon thi đấu cao cấp siêu nhẹ, êm tay, tặng kèm bóng tập trong suốt buổi chơi.",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 304,
    "category_id": 8,
    "name": "Thuê Sân Theo Giờ (200k/giờ, tặng 2 nước)",
    "portion": "1 giờ / sân (kèm 2 nước)",
    "price": 200000,
    "station": "BAR",
    "main_menu_type": "PICKLE",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Bao trọn 01 sân thi đấu tiêu chuẩn có mái che thoáng mát, tặng kèm 02 chai nước suối giải khát.",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 305,
    "category_id": 8,
    "name": "Gói Social Tháng (Mọi Khung Giờ)",
    "portion": "30 ngày không giới hạn giờ",
    "price": 1200000,
    "station": "BAR",
    "main_menu_type": "PICKLE",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Thẻ hội viên Social tháng không giới hạn khung giờ, chơi thỏa thích bất kỳ lúc nào trong ngày (06h - 22h).",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 306,
    "category_id": 8,
    "name": "Gói Social Tháng (Chỉ Buổi Sáng)",
    "portion": "30 ngày (06h - 16h)",
    "price": 600000,
    "station": "BAR",
    "main_menu_type": "PICKLE",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Thẻ hội viên Social tháng khung giờ sáng (06h - 16h) dành cho người yêu thích rèn luyện thể lực đầu ngày.",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 307,
    "category_id": 8,
    "name": "Gói Social Năm (Cá Nhân)",
    "portion": "365 ngày cá nhân",
    "price": 5000000,
    "station": "BAR",
    "main_menu_type": "PICKLE",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Thẻ hội viên VIP cá nhân 1 năm (365 ngày). Chơi không giới hạn giờ, ưu tiên xếp sân và quyền lợi CLB.",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 308,
    "category_id": 8,
    "name": "Đặt Sân Cố Định Tháng (Đàm Phán)",
    "portion": "Theo giá thỏa thuận",
    "price": 0,
    "station": "BAR",
    "main_menu_type": "PICKLE",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Đặt cố định sân và khung giờ theo tháng (ví dụ 18h-20h T2-T4-T6). Giá thỏa thuận linh hoạt.",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 318,
    "category_id": 9,
    "name": "Heo Massage",
    "portion": "Đĩa 300g",
    "price": 180000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Thịt heo tẩm ướp đặc biệt nướng thơm giòn",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 328,
    "category_id": 9,
    "name": "Tôm khô rang muối hạt",
    "portion": "Dĩa 100g",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Tôm khô rang muối hạt tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 329,
    "category_id": 9,
    "name": "Khô Mực Núp Lùm",
    "portion": "Dĩa 100g",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Khô Mực Núp Lùm tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 330,
    "category_id": 9,
    "name": "Chả giò hải sản",
    "portion": "Dĩa 4 cuộn",
    "price": 99000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Chả giò hải sản tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 331,
    "category_id": 9,
    "name": "Miến xào hải sản X.O",
    "portion": "Dĩa 80g miến khô, hải sản",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Miến xào hải sản X.O tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 332,
    "category_id": 9,
    "name": "Cơm Chiên Tôm X.O",
    "portion": "Dĩa 150 cơm, tôm tươi",
    "price": 150000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Cơm Chiên Tôm X.O tại PiPo Garden Phú Quốc",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 322,
    "category_id": 10,
    "name": "Súp",
    "portion": "Tô vừa",
    "price": 89000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Súp hải sản\", \"Súp bào ngư\"]}]",
    "image_url": "/static/logo.png",
    "description": "Súp hải sản thanh ngọt thơm ngon",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 323,
    "category_id": 10,
    "name": "Cháo",
    "portion": "Tô lớn",
    "price": 89000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"hải sản\", \"bò băm\", \"bào ngư\", \"Ngheu\"]}]",
    "image_url": "/static/logo.png",
    "description": "Cháo nóng hổi nấu sánh mịn thơm ngon",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 324,
    "category_id": 10,
    "name": "Súp Cua TomYum",
    "portion": "Tô lớn",
    "price": 129000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Súp TomYum cua cay nồng chuẩn vị Thái",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 325,
    "category_id": 11,
    "name": "Lẩu Thái Hải Sản",
    "portion": "Nồi lẩu (3-4 người)",
    "price": 350000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Lẩu Thái hải sản chua cay thơm đậm đà",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 326,
    "category_id": 11,
    "name": "Lẩu Gà Chanh Ớt",
    "portion": "Nồi lẩu",
    "price": 350000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[]",
    "image_url": "/static/logo.png",
    "description": "Lẩu gà chanh ớt xiêm xanh cay thơm nức",
    "is_available": 1,
    "calories": 0
  },
  {
    "id": 327,
    "category_id": 11,
    "name": "Lẩu Cá - đặt trước",
    "portion": "Nồi lẩu 1 con",
    "price": 400000,
    "station": "HOT_KITCHEN",
    "main_menu_type": "RESTAURANT",
    "options_json": "[{\"name\": \"Chọn vị chế biến\", \"options\": [\"Chim biển\", \"bớp\", \"Mú\"]}]",
    "image_url": "/static/logo.png",
    "description": "Lẩu cá tươi nấu ngọt thanh hoặc nấu Thái chua cay",
    "is_available": 1,
    "calories": 0
  }
]

INVENTORY_ITEMS = [
  {
    "id": 1,
    "code": "NVL01",
    "name": "Tôm Sú / Tôm Thẻ Tươi Phú Quốc",
    "unit": "kg",
    "cost_price": 220000,
    "stock_quantity": 34.64,
    "min_stock": 8.0,
    "supplier": "Vựa Hải Sản Hàm Ninh"
  },
  {
    "id": 2,
    "code": "NVL02",
    "name": "Ốc Hương Tươi Sống",
    "unit": "kg",
    "cost_price": 250000,
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "supplier": "Vựa Hải Sản Hàm Ninh"
  },
  {
    "id": 3,
    "code": "NVL03",
    "name": "Bạch Tuộc Tươi Phú Quốc",
    "unit": "kg",
    "cost_price": 160000,
    "stock_quantity": 28.0,
    "min_stock": 6.0,
    "supplier": "Hải Sản Đảo Ngọc"
  },
  {
    "id": 4,
    "code": "NVL04",
    "name": "Hàu Sữa Tươi Đại Dương",
    "unit": "con",
    "cost_price": 7000,
    "stock_quantity": 200.0,
    "min_stock": 40.0,
    "supplier": "Hải Sản Đảo Ngọc"
  },
  {
    "id": 5,
    "code": "NVL05",
    "name": "Nghêu Lụa Tươi Sống",
    "unit": "kg",
    "cost_price": 65000,
    "stock_quantity": 30.0,
    "min_stock": 6.0,
    "supplier": "Vựa Hải Sản Hàm Ninh"
  },
  {
    "id": 6,
    "code": "NVL06",
    "name": "Tôm Khô Phú Quốc Loại 1",
    "unit": "kg",
    "cost_price": 450000,
    "stock_quantity": 8.0,
    "min_stock": 2.0,
    "supplier": "Đặc Sản Dương Đông"
  },
  {
    "id": 7,
    "code": "NVL07",
    "name": "Gà Ta Thả Vườn Làm Sạch",
    "unit": "kg",
    "cost_price": 82000,
    "stock_quantity": 45.0,
    "min_stock": 10.0,
    "supplier": "Trang Trại Gà Đồi Phú Quốc"
  },
  {
    "id": 8,
    "code": "NVL08",
    "name": "Chân Gà Tươi Chọn Lọc",
    "unit": "kg",
    "cost_price": 80000,
    "stock_quantity": 18.0,
    "min_stock": 4.0,
    "supplier": "CP Foods Vietnam"
  },
  {
    "id": 9,
    "code": "NVL09",
    "name": "Vịt Tươi Nguyên Con",
    "unit": "kg",
    "cost_price": 78000,
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "supplier": "Trang Trại Gia Cầm Sạch"
  },
  {
    "id": 10,
    "code": "NVL10",
    "name": "Thịt Bò Thăn Mềm Tươi",
    "unit": "kg",
    "cost_price": 260000,
    "stock_quantity": 22.0,
    "min_stock": 5.0,
    "supplier": "Thực Phẩm Bò Tơ"
  },
  {
    "id": 11,
    "code": "NVL11",
    "name": "Thịt Chân Giò / Ba Chỉ Heo",
    "unit": "kg",
    "cost_price": 125000,
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "supplier": "CP Foods Vietnam"
  },
  {
    "id": 12,
    "code": "NVL12",
    "name": "Nầm Heo Tươi Chọn Lọc",
    "unit": "kg",
    "cost_price": 145000,
    "stock_quantity": 18.0,
    "min_stock": 4.0,
    "supplier": "CP Foods Vietnam"
  },
  {
    "id": 13,
    "code": "NVL13",
    "name": "Khoai Môn Cao Sản",
    "unit": "kg",
    "cost_price": 35000,
    "stock_quantity": 18.2,
    "min_stock": 5.0,
    "supplier": "Nông Sản Miền Tây"
  },
  {
    "id": 14,
    "code": "NVL14",
    "name": "Khoai Tây Cọng Đông Lạnh",
    "unit": "kg",
    "cost_price": 52000,
    "stock_quantity": 32.30000000000003,
    "min_stock": 8.0,
    "supplier": "Lutosa Imports"
  },
  {
    "id": 15,
    "code": "NVL15",
    "name": "Đậu Hũ Non / Đậu Hũ Trắng",
    "unit": "bìa",
    "cost_price": 4000,
    "stock_quantity": 120.0,
    "min_stock": 25.0,
    "supplier": "Làng Đậu Truyền Thống"
  },
  {
    "id": 16,
    "code": "NVL16",
    "name": "Xoài Xanh Keo Giòn",
    "unit": "kg",
    "cost_price": 28000,
    "stock_quantity": 20.0,
    "min_stock": 5.0,
    "supplier": "Nông Sản Miền Tây"
  },
  {
    "id": 17,
    "code": "NVL17",
    "name": "Rau Muống Tươi Nhặt Sẵn",
    "unit": "kg",
    "cost_price": 20000,
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "supplier": "Vườn Rau Sạch PiPo"
  },
  {
    "id": 18,
    "code": "NVL18",
    "name": "Cải Thìa Đà Lạt",
    "unit": "kg",
    "cost_price": 25000,
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "supplier": "Nông Trại Đà Lạt"
  },
  {
    "id": 20,
    "code": "NVL20",
    "name": "Gạo Thơm ST25 (Nấu Cơm)",
    "unit": "kg",
    "cost_price": 32000,
    "stock_quantity": 50.0,
    "min_stock": 10.0,
    "supplier": "Đại Lý Gạo Sóc Trăng"
  },
  {
    "id": 21,
    "code": "NVL21",
    "name": "Mì Vàng Tươi / Mì Trứng",
    "unit": "vắt",
    "cost_price": 5000,
    "stock_quantity": 150.0,
    "min_stock": 30.0,
    "supplier": "Lò Mì Tươi Gia Truyền"
  },
  {
    "id": 23,
    "code": "NVL23",
    "name": "Trứng Muối & Trứng Gà Tươi",
    "unit": "quả",
    "cost_price": 4500,
    "stock_quantity": 180.0,
    "min_stock": 30.0,
    "supplier": "CP Foods Vietnam"
  },
  {
    "id": 27,
    "code": "NVL27",
    "name": "Trà Lài & Trà Olong Thượng Hạng",
    "unit": "kg",
    "cost_price": 180000,
    "stock_quantity": 10.0,
    "min_stock": 2.0,
    "supplier": "Trà Bảo Lộc"
  },
  {
    "id": 28,
    "code": "NVL28",
    "name": "Đào Ngâm & Mãng Cầu Xiêm Tươi",
    "unit": "kg",
    "cost_price": 65000,
    "stock_quantity": 20.0,
    "min_stock": 4.0,
    "supplier": "Thực Phẩm Pha Chế"
  },
  {
    "id": 29,
    "code": "NVL29",
    "name": "Dưa Hấu & Trái Cây Tươi",
    "unit": "kg",
    "cost_price": 22000,
    "stock_quantity": 35.0,
    "min_stock": 8.0,
    "supplier": "Nông Sản Miền Tây"
  },
  {
    "id": 31,
    "code": "NVL100",
    "name": "Mực Ống Tươi Phú Quốc",
    "unit": "kg",
    "cost_price": 180000,
    "stock_quantity": 24.64,
    "min_stock": 2.0,
    "supplier": "Vựa Hải Sản Hàm Ninh"
  },
  {
    "id": 32,
    "code": "NVL31",
    "name": "Ốc Móng Tay Tươi Sống",
    "unit": "kg",
    "cost_price": 110000,
    "stock_quantity": 30.0,
    "min_stock": 6.0,
    "supplier": "Vựa Hải Sản Hàm Ninh"
  },
  {
    "id": 33,
    "code": "NVL32",
    "name": "Cánh Gà Tươi Chọn Lọc",
    "unit": "kg",
    "cost_price": 85000,
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "supplier": "CP Foods Vietnam"
  },
  {
    "id": 34,
    "code": "NVL33",
    "name": "Thịt Ghẹ Tươi Bóc Sẵn Phú Quốc",
    "unit": "kg",
    "cost_price": 290000,
    "stock_quantity": 15.0,
    "min_stock": 3.0,
    "supplier": "Hải Sản Đảo Ngọc"
  },
  {
    "id": 38,
    "code": "NVL37",
    "name": "Gói Bò Xuyên Tiêu Chuẩn Bị Sẵn",
    "unit": "gói",
    "cost_price": 85000,
    "stock_quantity": 30.0,
    "min_stock": 6.0,
    "supplier": "Thực Phẩm Chế Biến Sẵn"
  },
  {
    "id": 41,
    "code": "NVL40",
    "name": "Gà Đen H'Mông Thả Vườn",
    "unit": "kg",
    "cost_price": 140000,
    "stock_quantity": 25.0,
    "min_stock": 5.0,
    "supplier": "Trang Trại Gà Đồi"
  },
  {
    "id": 42,
    "code": "NVL41",
    "name": "Nước Suối Tinh Khiết Chai 500ml",
    "unit": "chai",
    "cost_price": 4000,
    "stock_quantity": 105.0,
    "min_stock": 24.0,
    "supplier": "Đại Lý Nước Giải Khát"
  },
  {
    "id": 43,
    "code": "NVL42",
    "name": "Nước Ngọt Coca Cola Lon 320ml",
    "unit": "lon",
    "cost_price": 6800,
    "stock_quantity": 120.0,
    "min_stock": 24.0,
    "supplier": "Đại Lý Nước Giải Khát"
  },
  {
    "id": 44,
    "code": "NVL43",
    "name": "Nước Ngọt Pepsi Lon 320ml",
    "unit": "lon",
    "cost_price": 6800,
    "stock_quantity": 120.0,
    "min_stock": 24.0,
    "supplier": "Đại Lý Nước Giải Khát"
  },
  {
    "id": 45,
    "code": "NVL44",
    "name": "Nước Thể Thao Aquarius Lon 320ml",
    "unit": "lon",
    "cost_price": 6800,
    "stock_quantity": 80.0,
    "min_stock": 15.0,
    "supplier": "Đại Lý Nước Giải Khát"
  },
  {
    "id": 46,
    "code": "NVL45",
    "name": "Nước Bù Khoáng Revive Chai 500ml",
    "unit": "chai",
    "cost_price": 6800,
    "stock_quantity": 78.0,
    "min_stock": 15.0,
    "supplier": "Đại Lý Nước Giải Khát"
  },
  {
    "id": 47,
    "code": "NVL46",
    "name": "Bia Bivina Đặc Sản Đảo Lon 330ml",
    "unit": "lon",
    "cost_price": 8000,
    "stock_quantity": 150.0,
    "min_stock": 30.0,
    "supplier": "Nhà Phân Phối Bia Phú Quốc"
  },
  {
    "id": 48,
    "code": "NVL47",
    "name": "Bia Sài Gòn Special/Lager Lon 330ml",
    "unit": "lon",
    "cost_price": 11000,
    "stock_quantity": 150.0,
    "min_stock": 30.0,
    "supplier": "Nhà Phân Phối Bia Sabeco"
  },
  {
    "id": 49,
    "code": "NVL48",
    "name": "Bia Heineken Sleek Lon 250ml",
    "unit": "lon",
    "cost_price": 13500,
    "stock_quantity": 120.0,
    "min_stock": 24.0,
    "supplier": "Nhà Phân Phối Bia Heineken"
  },
  {
    "id": 50,
    "code": "NVL50",
    "name": "Nguyên liệu Cà tím",
    "unit": "đĩa",
    "cost_price": 12000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 51,
    "code": "NVL51",
    "name": "Nguyên liệu Sườn bò",
    "unit": "phần",
    "cost_price": 70000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 52,
    "code": "NVL52",
    "name": "Nguyên liệu Đùi gà",
    "unit": "đĩa",
    "cost_price": 32000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 53,
    "code": "NVL53",
    "name": "Nguyên liệu Heo Massage",
    "unit": "đĩa",
    "cost_price": 130000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 54,
    "code": "NVL54",
    "name": "Nguyên liệu Má heo",
    "unit": "đĩa",
    "cost_price": 45000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 55,
    "code": "NVL55",
    "name": "Nguyên liệu Sườn heo",
    "unit": "dĩa",
    "cost_price": 50000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 56,
    "code": "NVL56",
    "name": "Nguyên liệu Ốc Hương",
    "unit": "đĩa",
    "cost_price": 50000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 57,
    "code": "NVL57",
    "name": "Nguyên liệu Cá Mú 2 Món",
    "unit": "con",
    "cost_price": 280000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 58,
    "code": "NVL58",
    "name": "Nguyên liệu Cá chim biển",
    "unit": "con",
    "cost_price": 80000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 59,
    "code": "NVL59",
    "name": "Nguyên liệu Hàu nướng phô mai / mỡ hành",
    "unit": "con",
    "cost_price": 7000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 60,
    "code": "NVL60",
    "name": "Nguyên liệu Súp",
    "unit": "phần",
    "cost_price": 25000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 61,
    "code": "NVL61",
    "name": "Nguyên liệu Súp Cua TomYum",
    "unit": "phần",
    "cost_price": 40000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 62,
    "code": "NVL62",
    "name": "Nguyên liệu Lẩu Thái Hải Sản",
    "unit": "phần",
    "cost_price": 90000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 63,
    "code": "NVL63",
    "name": "Nguyên liệu Lẩu Cá Chim / Cá Mú",
    "unit": "con",
    "cost_price": 95000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 64,
    "code": "NVL64",
    "name": "Nguyên liệu Tôm khô rang muối hạt",
    "unit": "dĩa",
    "cost_price": 55000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 65,
    "code": "NVL65",
    "name": "Nguyên liệu Khô Mực Núp Lùm",
    "unit": "dĩa",
    "cost_price": 50000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  },
  {
    "id": 66,
    "code": "NVL66",
    "name": "Nguyên liệu Cơm Chiên Tôm X.O",
    "unit": "dĩa",
    "cost_price": 55000,
    "stock_quantity": 50.0,
    "min_stock": 5.0,
    "supplier": "Nhà cung cấp tươi Phú Quốc"
  }
]

RECIPE_BOM = [
  {
    "id": 673,
    "menu_item_id": 140,
    "ingredient_id": 14,
    "quantity": 0.3
  },
  {
    "id": 674,
    "menu_item_id": 142,
    "ingredient_id": 6,
    "quantity": 0.04
  },
  {
    "id": 675,
    "menu_item_id": 142,
    "ingredient_id": 16,
    "quantity": 0.3
  },
  {
    "id": 676,
    "menu_item_id": 143,
    "ingredient_id": 17,
    "quantity": 0.401
  },
  {
    "id": 677,
    "menu_item_id": 144,
    "ingredient_id": 18,
    "quantity": 0.4
  },
  {
    "id": 678,
    "menu_item_id": 146,
    "ingredient_id": 15,
    "quantity": 4.0
  },
  {
    "id": 679,
    "menu_item_id": 147,
    "ingredient_id": 13,
    "quantity": 0.35
  },
  {
    "id": 680,
    "menu_item_id": 311,
    "ingredient_id": 18,
    "quantity": 1.0
  },
  {
    "id": 681,
    "menu_item_id": 312,
    "ingredient_id": 50,
    "quantity": 1.0
  },
  {
    "id": 682,
    "menu_item_id": 345,
    "ingredient_id": 65,
    "quantity": 1.0
  },
  {
    "id": 683,
    "menu_item_id": 346,
    "ingredient_id": 62,
    "quantity": 1.0
  },
  {
    "id": 684,
    "menu_item_id": 148,
    "ingredient_id": 41,
    "quantity": 1.301
  },
  {
    "id": 685,
    "menu_item_id": 150,
    "ingredient_id": 7,
    "quantity": 1.301
  },
  {
    "id": 686,
    "menu_item_id": 157,
    "ingredient_id": 33,
    "quantity": 0.4
  },
  {
    "id": 687,
    "menu_item_id": 159,
    "ingredient_id": 9,
    "quantity": 0.95
  },
  {
    "id": 688,
    "menu_item_id": 160,
    "ingredient_id": 8,
    "quantity": 0.35
  },
  {
    "id": 689,
    "menu_item_id": 317,
    "ingredient_id": 52,
    "quantity": 1.0
  },
  {
    "id": 690,
    "menu_item_id": 145,
    "ingredient_id": 38,
    "quantity": 1.0
  },
  {
    "id": 691,
    "menu_item_id": 161,
    "ingredient_id": 11,
    "quantity": 0.35
  },
  {
    "id": 692,
    "menu_item_id": 201,
    "ingredient_id": 11,
    "quantity": 0.4
  },
  {
    "id": 693,
    "menu_item_id": 314,
    "ingredient_id": 51,
    "quantity": 1.0
  },
  {
    "id": 694,
    "menu_item_id": 319,
    "ingredient_id": 54,
    "quantity": 1.0
  },
  {
    "id": 695,
    "menu_item_id": 347,
    "ingredient_id": 53,
    "quantity": 1.0
  },
  {
    "id": 696,
    "menu_item_id": 162,
    "ingredient_id": 4,
    "quantity": 1.0
  },
  {
    "id": 697,
    "menu_item_id": 164,
    "ingredient_id": 5,
    "quantity": 0.35
  },
  {
    "id": 698,
    "menu_item_id": 167,
    "ingredient_id": 1,
    "quantity": 0.3
  },
  {
    "id": 699,
    "menu_item_id": 169,
    "ingredient_id": 2,
    "quantity": 0.2
  },
  {
    "id": 700,
    "menu_item_id": 169,
    "ingredient_id": 23,
    "quantity": 2.0
  },
  {
    "id": 701,
    "menu_item_id": 172,
    "ingredient_id": 32,
    "quantity": 0.4
  },
  {
    "id": 702,
    "menu_item_id": 176,
    "ingredient_id": 3,
    "quantity": 0.4
  },
  {
    "id": 703,
    "menu_item_id": 197,
    "ingredient_id": 57,
    "quantity": 1.0
  },
  {
    "id": 704,
    "menu_item_id": 310,
    "ingredient_id": 31,
    "quantity": 1.0
  },
  {
    "id": 705,
    "menu_item_id": 320,
    "ingredient_id": 56,
    "quantity": 1.0
  },
  {
    "id": 706,
    "menu_item_id": 321,
    "ingredient_id": 58,
    "quantity": 1.0
  },
  {
    "id": 707,
    "menu_item_id": 180,
    "ingredient_id": 20,
    "quantity": 0.25
  },
  {
    "id": 708,
    "menu_item_id": 180,
    "ingredient_id": 23,
    "quantity": 1.0
  },
  {
    "id": 709,
    "menu_item_id": 180,
    "ingredient_id": 34,
    "quantity": 0.07
  },
  {
    "id": 710,
    "menu_item_id": 181,
    "ingredient_id": 1,
    "quantity": 0.05
  },
  {
    "id": 711,
    "menu_item_id": 181,
    "ingredient_id": 21,
    "quantity": 2.0
  },
  {
    "id": 712,
    "menu_item_id": 181,
    "ingredient_id": 31,
    "quantity": 0.05
  },
  {
    "id": 713,
    "menu_item_id": 348,
    "ingredient_id": 62,
    "quantity": 1.0
  },
  {
    "id": 714,
    "menu_item_id": 349,
    "ingredient_id": 66,
    "quantity": 1.0
  },
  {
    "id": 715,
    "menu_item_id": 183,
    "ingredient_id": 42,
    "quantity": 1.0
  },
  {
    "id": 716,
    "menu_item_id": 184,
    "ingredient_id": 43,
    "quantity": 1.0
  },
  {
    "id": 717,
    "menu_item_id": 185,
    "ingredient_id": 44,
    "quantity": 1.0
  },
  {
    "id": 718,
    "menu_item_id": 186,
    "ingredient_id": 45,
    "quantity": 1.0
  },
  {
    "id": 719,
    "menu_item_id": 187,
    "ingredient_id": 46,
    "quantity": 1.0
  },
  {
    "id": 720,
    "menu_item_id": 188,
    "ingredient_id": 47,
    "quantity": 1.0
  },
  {
    "id": 721,
    "menu_item_id": 189,
    "ingredient_id": 48,
    "quantity": 1.0
  },
  {
    "id": 722,
    "menu_item_id": 190,
    "ingredient_id": 49,
    "quantity": 1.0
  },
  {
    "id": 723,
    "menu_item_id": 333,
    "ingredient_id": 51,
    "quantity": 1.0
  },
  {
    "id": 724,
    "menu_item_id": 334,
    "ingredient_id": 41,
    "quantity": 1.301
  },
  {
    "id": 725,
    "menu_item_id": 335,
    "ingredient_id": 7,
    "quantity": 1.301
  },
  {
    "id": 726,
    "menu_item_id": 336,
    "ingredient_id": 33,
    "quantity": 0.4
  },
  {
    "id": 727,
    "menu_item_id": 337,
    "ingredient_id": 8,
    "quantity": 0.35
  },
  {
    "id": 728,
    "menu_item_id": 338,
    "ingredient_id": 52,
    "quantity": 1.0
  },
  {
    "id": 729,
    "menu_item_id": 339,
    "ingredient_id": 11,
    "quantity": 0.4
  },
  {
    "id": 730,
    "menu_item_id": 340,
    "ingredient_id": 11,
    "quantity": 0.35
  },
  {
    "id": 731,
    "menu_item_id": 341,
    "ingredient_id": 1,
    "quantity": 0.3
  },
  {
    "id": 732,
    "menu_item_id": 342,
    "ingredient_id": 31,
    "quantity": 1.0
  },
  {
    "id": 733,
    "menu_item_id": 343,
    "ingredient_id": 58,
    "quantity": 1.0
  },
  {
    "id": 734,
    "menu_item_id": 344,
    "ingredient_id": 4,
    "quantity": 1.0
  },
  {
    "id": 735,
    "menu_item_id": 318,
    "ingredient_id": 53,
    "quantity": 1.0
  },
  {
    "id": 736,
    "menu_item_id": 328,
    "ingredient_id": 64,
    "quantity": 1.0
  },
  {
    "id": 737,
    "menu_item_id": 329,
    "ingredient_id": 65,
    "quantity": 1.0
  },
  {
    "id": 738,
    "menu_item_id": 330,
    "ingredient_id": 62,
    "quantity": 1.0
  },
  {
    "id": 739,
    "menu_item_id": 331,
    "ingredient_id": 62,
    "quantity": 1.0
  },
  {
    "id": 740,
    "menu_item_id": 332,
    "ingredient_id": 66,
    "quantity": 1.0
  },
  {
    "id": 741,
    "menu_item_id": 322,
    "ingredient_id": 60,
    "quantity": 1.0
  },
  {
    "id": 742,
    "menu_item_id": 323,
    "ingredient_id": 20,
    "quantity": 1.0
  },
  {
    "id": 743,
    "menu_item_id": 324,
    "ingredient_id": 61,
    "quantity": 1.0
  },
  {
    "id": 744,
    "menu_item_id": 325,
    "ingredient_id": 62,
    "quantity": 1.0
  },
  {
    "id": 745,
    "menu_item_id": 326,
    "ingredient_id": 7,
    "quantity": 1.0
  },
  {
    "id": 746,
    "menu_item_id": 327,
    "ingredient_id": 63,
    "quantity": 1.0
  }
]

def ensure_updated_menu(conn: sqlite3.Connection):
    cur = conn.cursor()

    # 1. Cập nhật Danh mục
    for c in CATEGORIES:
        cur.execute("SELECT id FROM categories WHERE id = ?", (c["id"],))
        if cur.fetchone():
            cur.execute("""
                UPDATE categories 
                SET name = ?, icon = ?, display_order = ?
                WHERE id = ?
            """, (c["name"], c["icon"], c["display_order"], c["id"]))
        else:
            cur.execute("""
                INSERT INTO categories (id, name, icon, display_order)
                VALUES (?, ?, ?, ?)
            """, (c["id"], c["name"], c["icon"], c["display_order"]))

    # 2. Cập nhật Nguyên Vật Liệu Kho
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

    # 3. CLEAR SẠCH MÓN CŨ TRÊN HOST VÀ NẠP LẠI TOÀN BỘ MENU CHUẨN XÁC
    cur.execute("DELETE FROM menu_items")
    cur.execute("DELETE FROM recipe_bom")

    for it in MENU_ITEMS:
        cur.execute("""
            INSERT INTO menu_items (id, category_id, name, price, station, image_url, description, is_available, calories, portion, main_menu_type, options_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (it["id"], it["category_id"], it["name"], it["price"], it["station"],
              it["image_url"], it["description"], it["is_available"], it["calories"], it["portion"],
              it["main_menu_type"], it["options_json"]))

    # 4. Nạp lại Định mức Recipe BOM
    for b in RECIPE_BOM:
        cur.execute("""
            INSERT INTO recipe_bom (menu_item_id, ingredient_id, quantity)
            VALUES (?, ?, ?)
        """, (b["menu_item_id"], b["ingredient_id"], b["quantity"]))

    conn.commit()
    try:
        print(f"[PiPo Garden] Da CLEAR va nap moi thanh cong {len(MENU_ITEMS)} mon an chuan xac tu Excel vao CSDL!")
    except Exception:
        pass
