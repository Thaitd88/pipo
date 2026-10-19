"""
Dịch Vụ Đa Ngôn Ngữ PiPo Garden (Auto-Translation Service)
Hỗ trợ 5 ngôn ngữ chính:
  - vi: Tiếng Việt (Ngôn ngữ gốc)
  - en: English (Tiếng Anh)
  - zh: 中文 (Tiếng Trung giản thể - zh-CN)
  - ko: 한국어 (Tiếng Hàn)
  - ru: Русский (Tiếng Nga)
"""

import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

# Bản đồ mã ngôn ngữ chuẩn của Google Translate
GOOGLE_LANG_MAP = {
    "en": "en",
    "zh": "zh-CN",
    "ko": "ko",
    "ru": "ru"
}

# Từ điển ẩm thực dự phòng chuyên sâu cho PiPo Garden (Offline Fallback Dictionary)
OFFLINE_FOOD_DICT = {
    "Cá Mú 2 Món": {
        "en": "Grouper Prepared Two Ways (Sashimi & Hotpot/Steamed)",
        "zh": "石斑鱼两吃 (清蒸/刺身与鱼汤)",
        "ko": "다금바리(그루퍼) 2코스 요리 (회 & 전골/찜)",
        "ru": "Морской окунь (групер) двумя способами (сашими и суп/на пару)"
    },
    "Cá Sòng nướng": {
        "en": "Chili Salt Grilled Scad Fish",
        "zh": "炭烤竹荚鱼",
        "ko": "숯불 전갱이 생선구이",
        "ru": "Ставрида на гриле с чили"
    },
    "Bia Hơi Hà Nội": {
        "en": "Hanoi Fresh Draft Beer",
        "zh": "河内特色生啤酒 (扎啤)",
        "ko": "하노이 생맥주 (비아호이)",
        "ru": "Ханойское разливное свежее пиво (Bia Hoi)"
    },
    "Bò Xuyên Tiêu": {
        "en": "Phu Quoc Stir-fried Beef with Green Peppercorns",
        "zh": "富国岛青花椒炒牛肉",
        "ko": "푸꾸옥 통후추 소고기 볶음",
        "ru": "Говядина вок с зеленым перцем Фукуок"
    },
    "Sườn Cây Nướng Sốt BBQ PiPo": {
        "en": "Grilled Pork Ribs with PiPo BBQ Sauce",
        "zh": "PiPo特制烧烤酱烤排骨",
        "ko": "PiPo BBQ 소스 등갈비 구이",
        "ru": "Свиные ребрышки гриль под соусом BBQ PiPo"
    },
    "Gà Nướng Mắc Khén Tây Bắc": {
        "en": "Northwest Mac Khen Grilled Free-range Chicken",
        "zh": "西北花椒烤土鸡",
        "ko": "북서부 막켄 산초 숯불 닭구이",
        "ru": "Курица на гриле с диким перцем Мак Кхен"
    },
    "Mực Trứng Nướng Sa Tế": {
        "en": "Grilled Egg Squid with Satay Chili",
        "zh": "沙爹酱烤富贵墨鱼",
        "ko": "사테 칠리 구운 알오징어",
        "ru": "Кальмары с икрой на гриле в соусе сатай"
    },
    "Lẩu Thái Hải Sản Tomyum Sân Vườn": {
        "en": "Garden Tom Yum Seafood Hotpot",
        "zh": "花园冬阴功海鲜火锅",
        "ko": "가든 똠얌 해물 샤브샤브 전골",
        "ru": "Садовый острый суп Том Ям с морепродуктами"
    },
    "Lẩu Bò Nhúng Mẻ Tây Nam Bộ": {
        "en": "Southwest Fermented Broth Beef Hotpot",
        "zh": "西南风味发酵酸汤牛肉火锅",
        "ko": "남서부 발효 쌀 육수 소고기 전골",
        "ru": "Мясное фондю из говядины по-юго-западному"
    },
    "Gỏi Cuốn Tôm Thịt PiPo Garden": {
        "en": "PiPo Garden Fresh Spring Rolls with Shrimp & Pork",
        "zh": "PiPo花园鲜虾猪肉春卷",
        "ko": "PiPo 가든 새우 돼지고기 월남쌈",
        "ru": "Свежие спринг-роллы с креветками и свининой"
    },
    "Khoai Tây Chiên Lắc Phô Mai": {
        "en": "Crispy French Fries Shaken with Cheese",
        "zh": "黄金芝士摇摇薯条",
        "ko": "치즈 시즈닝 감자튀김",
        "ru": "Картофель фри с сырной посыпкой"
    },
    "Salad Cá Hồi Xông Khói Sốt Chanh Leo": {
        "en": "Smoked Salmon Salad with Passion Fruit Dressing",
        "zh": "烟熏三文鱼百香果沙拉",
        "ko": "훈제 연어 패션후르츠 드레싱 샐러드",
        "ru": "Салат с копченым лососем и соусом из маракуйи"
    },
    "Trà Đào Cam Sả PiPo Special": {
        "en": "PiPo Special Peach Orange Lemongrass Tea",
        "zh": "PiPo招牌蜜桃香橙柠檬草茶",
        "ko": "PiPo 스페셜 복숭아 오렌지 레몬그라스 티",
        "ru": "Фирменный чай с персиком, апельсином и лемонграссом"
    },
    "Trà Mãng Cầu Xiêm Nhiệt Đới": {
        "en": "Tropical Soursop Iced Tea",
        "zh": "热带刺果番荔枝冰茶",
        "ko": "트로피컬 사워서프 과일 아이스티",
        "ru": "Тропический чай со сметанным яблоком (гуанабана)"
    },
    "Nước Ép Dưa Hấu Bạc Hà": {
        "en": "Fresh Watermelon Mint Juice",
        "zh": "鲜榨薄荷西瓜汁",
        "ko": "신선한 수박 민트 생과일 주스",
        "ru": "Свежевыжатый арбузный сок с мятой"
    },
    "Bia Thủ Công Hoegaarden Rosee (Chai)": {
        "en": "Hoegaarden Rosee Craft Wheat Beer (Bottle)",
        "zh": "福佳白玫瑰精酿啤酒 (瓶装)",
        "ko": "호가든 로제 수제 밀맥주 (병)",
        "ru": "Крафтовое пиво Hoegaarden Rosee (бутылка)"
    },
    "Bia Corona Extra (Ướp Lạnh Kèm Chanh)": {
        "en": "Chilled Corona Extra Beer with Fresh Lime",
        "zh": "科罗娜特级啤酒 (冰镇配青柠)",
        "ko": "시원한 코로나 엑스트라 맥주 (라임 제공)",
        "ru": "Ледяное пиво Corona Extra с лаймом"
    },
    # 2 Nhóm Thực Đơn Chính
    "Menu Nhà Hàng": {
        "en": "Restaurant Menu",
        "zh": "餐厅菜单",
        "ko": "레스토랑 메뉴",
        "ru": "Меню ресторана"
    },
    "Menu Cafe / Ăn Sáng": {
        "en": "Cafe & Breakfast Menu",
        "zh": "咖啡与早餐菜单",
        "ko": "카페 & 조식 메뉴",
        "ru": "Меню кафе и завтраков"
    },
    "Menu cafe/ăn sáng": {
        "en": "Cafe & Breakfast Menu",
        "zh": "咖啡与早餐菜单",
        "ko": "카페 & 조식 메뉴",
        "ru": "Меню кафе и завтраков"
    },
    # 36 Món Thực Đơn Nhà Hàng (danh_sach_menu_nha_hang_anh_WEB.xlsx)
    "Gỏi khoai môn hải sản": {
        "en": "Crispy Taro Seafood Salad",
        "zh": "香芋海鲜沙拉",
        "ko": "타로 해산물 샐러드",
        "ru": "Хрустящий салат с таро и морепродуктами"
    },
    "Khoai tây chiên": {
        "en": "Crispy French Fries",
        "zh": "香脆炸薯条",
        "ko": "바삭한 감자튀김",
        "ru": "Хрустящий картофель фри"
    },
    "Đậu hũ tẩm hành": {
        "en": "Fried Tofu with Scallion Sauce",
        "zh": "葱油香炸豆腐",
        "ko": "파소스 두부튀김",
        "ru": "Жареный тофу с зеленым луком"
    },
    "Gỏi xoài tôm khô": {
        "en": "Green Mango Salad with Dried Shrimp",
        "zh": "虾米青木瓜芒果沙拉",
        "ko": "건새우 그린망고 샐러드",
        "ru": "Салат из зеленого манго с сушеными креветками"
    },
    "Rau muống xào tỏi": {
        "en": "Stir-fried Morning Glory with Garlic",
        "zh": "蒜蓉炒空心菜",
        "ko": "마늘 모닝글로리(공심채) 볶음",
        "ru": "Водяной шпинат (утреннее сияние), обжаренный с чесноком"
    },
    "Cải thìa sốt dầu hào": {
        "en": "Bok Choy in Oyster Sauce",
        "zh": "蚝油扒上海青",
        "ko": "굴소스 청경채 볶음",
        "ru": "Бок-чой под устричным соусом"
    },
    "Bò xuyên tiêu": {
        "en": "Sichuan Peppercorn Beef",
        "zh": "川味黑椒牛肉",
        "ko": "사천식 통후추 소고기 볶음",
        "ru": "Говядина с сычуаньским перцем"
    },
    "Đậu hũ chiên giòn": {
        "en": "Crispy Fried Golden Tofu",
        "zh": "金黄香脆炸豆腐",
        "ko": "바삭한 두부튀김",
        "ru": "Хрустящий жареный тофу"
    },
    "Gà hấp mắm nhĩ": {
        "en": "Steamed Free-range Chicken with Anchovy Fish Sauce",
        "zh": "特级鱼露蒸土鸡",
        "ko": "프리미엄 피쉬소스 찜닭",
        "ru": "Курица на пару с анчоусным рыбным соусом"
    },
    "Gà nướng muối ớt": {
        "en": "Chili Salt Grilled Chicken",
        "zh": "椒盐炭烤土鸡",
        "ko": "칠리 솔트 숯불 닭구이",
        "ru": "Курица на гриле с солью и чили"
    },
    "Gà chiên mắm": {
        "en": "Crispy Fried Chicken with Fish Sauce Glaze",
        "zh": "鱼露香炸土鸡",
        "ko": "느억맘 피쉬소스 치킨",
        "ru": "Жареная курица в глазури из рыбного соуса"
    },
    "Gà hấp hành": {
        "en": "Steamed Chicken with Scallions",
        "zh": "葱香清蒸土鸡",
        "ko": "대파 찜닭",
        "ru": "Курица на пару с зеленым луком"
    },
    "Lẩu gà lá giang": {
        "en": "Chicken Hotpot with Sour Giang Leaves",
        "zh": "酸叶土鸡火锅",
        "ko": "라장(새콤한 잎) 닭고기 전골",
        "ru": "Куриный хот-пот с кислыми листьями Зянг"
    },
    "Gà tiềm thuốc bắc": {
        "en": "Braised Chicken with Traditional Herbs",
        "zh": "药膳滋补炖土鸡",
        "ko": "한방 약재 보양 닭백숙",
        "ru": "Тушеная курица с целебными травами"
    },
    "Vịt quay thảo mộc": {
        "en": "Herbal Roasted Duck",
        "zh": "秘制香草烤鸭",
        "ko": "허브 로스트 오리구이",
        "ru": "Утка, запеченная с ароматными травами"
    },
    "Chân gà nướng": {
        "en": "Grilled Spiced Chicken Feet",
        "zh": "炭烤香辣凤爪",
        "ko": "숯불 닭발 구이",
        "ru": "Куриные лапки на гриле со специями"
    },
    "Heo nướng giả cầy (riềng mẻ)": {
        "en": "Grilled Pork with Galangal & Fermented Rice",
        "zh": "南姜酒酿炭烤猪肉",
        "ko": "갈랑갈 발효 쌀 양념 돼지고기 구이",
        "ru": "Свинина на гриле с галангалом и ферментированным рисом"
    },
    "Nầm nướng sa tế": {
        "en": "Satay Grilled Pork Udder",
        "zh": "沙爹炭烤猪乳房肉",
        "ko": "사테 소스 돼지 특수부위 구이",
        "ru": "Свинина на гриле в остром соусе сатай"
    },
    "Nầm nướng chao": {
        "en": "Grilled Pork Udder with Fermented Tofu Sauce",
        "zh": "腐乳炭烤猪乳房肉",
        "ko": "발효 두부소스 돼지 구이",
        "ru": "Свинина на гриле с соусом из ферментированного тофу"
    },
    "Hàu nướng phô mai": {
        "en": "Grilled Oyster with Melted Cheese",
        "zh": "芝士焗生蚝",
        "ko": "치즈 구이 굴",
        "ru": "Устрица, запеченная под сыром"
    },
    "Hàu nướng mỡ hành": {
        "en": "Grilled Oyster with Scallion Oil & Peanuts",
        "zh": "葱油花生烤生蚝",
        "ko": "파기름 땅콩 굴구이",
        "ru": "Устрица на гриле с зеленым луком и арахисом"
    },
    "Nghêu hấp sả": {
        "en": "Steamed Clams with Lemongrass",
        "zh": "香茅清蒸蛤蜊",
        "ko": "레몬그라스 조개찜",
        "ru": "Моллюски на пару с лемонграссом"
    },
    "Nghêu hấp Thái": {
        "en": "Thai-style Spicy & Sour Steamed Clams",
        "zh": "泰式酸辣蒸蛤蜊",
        "ko": "태국식 매콤새콤 조개찜",
        "ru": "Моллюски на пару по-тайски в кисло-остром бульоне"
    },
    "Tôm sốt bơ tỏi": {
        "en": "Prawns in Garlic Butter Sauce",
        "zh": "蒜香黄油大虾",
        "ko": "갈릭 버터 새우",
        "ru": "Креветки в чесночно-сливочном соусе"
    },
    "Tôm hấp": {
        "en": "Fresh Steamed Prawns",
        "zh": "清蒸鲜虾",
        "ko": "신선한 새우찜",
        "ru": "Свежие креветки на пару"
    },
    "Tôm nướng muối ớt": {
        "en": "Chili Salt Grilled Prawns",
        "zh": "椒盐炭烤大虾",
        "ko": "칠리 솔트 새우구이",
        "ru": "Креветки на гриле с солью и чили"
    },
    "Ốc hương sốt trứng muối": {
        "en": "Sweet Sea Snails in Salted Egg Yolk Sauce",
        "zh": "咸蛋黄炒花螺",
        "ko": "솔티드 에그(염란) 소라 볶음",
        "ru": "Морские улитки в соусе из соленого желтка"
    },
    "Ốc hương hấp sả": {
        "en": "Steamed Sweet Sea Snails with Lemongrass",
        "zh": "香茅清蒸花螺",
        "ko": "레몬그라스 소라찜",
        "ru": "Морские улитки на пару с лемонграссом"
    },
    "Ốc hương cháy tỏi": {
        "en": "Stir-fried Sweet Sea Snails with Crispy Garlic",
        "zh": "避风塘蒜香炒花螺",
        "ko": "갈릭 플레이크 소라 볶음",
        "ru": "Морские улитки, обжаренные с хрустящим чесноком"
    },
    "Bạch tuộc xào cay": {
        "en": "Spicy Stir-fried Octopus",
        "zh": "香辣爆炒章鱼",
        "ko": "매콤한 문어/주꾸미 볶음",
        "ru": "Осьминог, обжаренный в остром соусе"
    },
    "Bạch tuộc nướng muối ớt": {
        "en": "Chili Salt Grilled Octopus",
        "zh": "椒盐炭烤章鱼",
        "ko": "칠리 솔트 문어 숯불구이",
        "ru": "Осьминог на гриле с солью и чили"
    },
    "Bạch tuộc hấp hành": {
        "en": "Steamed Octopus with Ginger & Scallions",
        "zh": "葱姜清蒸章鱼",
        "ko": "대파 생강 문어숙회",
        "ru": "Осьминог на пару с зеленым луком и имбирем"
    },
    "Cơm chiên hải sản": {
        "en": "Seafood Fried Rice",
        "zh": "海鲜炒饭",
        "ko": "해물 볶음밥",
        "ru": "Жареный рис с морепродуктами"
    },
    "Cơm chiên bò": {
        "en": "Beef Fried Rice",
        "zh": "牛肉炒饭",
        "ko": "소고기 볶음밥",
        "ru": "Жареный рис с говядиной"
    },
    "Mì xào hải sản": {
        "en": "Stir-fried Noodles with Seafood",
        "zh": "海鲜炒面",
        "ko": "해물 야끼소바(볶음면)",
        "ru": "Жареная лапша с морепродуктами"
    },
    "Mì xào bò": {
        "en": "Stir-fried Noodles with Beef",
        "zh": "牛肉炒面",
        "ko": "소고기 볶음면",
        "ru": "Жареная лапша с говядиной"
    },
    "Gà hấp mắm nhĩ + Lòng mề xào": {
        "en": "Steamed Free-range Chicken with Fish Sauce + Sautéed Giblets",
        "zh": "特级鱼露蒸土鸡 + 爆炒鸡杂",
        "ko": "프리미엄 피쉬소스 찜닭 + 닭똥집 볶음",
        "ru": "Курица на пару с рыбным соусом + потроха"
    },
    "Gà nướng muối ớt + Lòng mề xào": {
        "en": "Chili Salt Grilled Chicken + Sautéed Giblets",
        "zh": "椒盐炭烤土鸡 + 爆炒鸡杂",
        "ko": "칠리 솔트 숯불 닭구이 + 닭똥집 볶음",
        "ru": "Курица на гриле с солью и чили + потроха"
    },
    "Gà chiên mắm + Lòng mề xào": {
        "en": "Crispy Chicken in Fish Sauce + Sautéed Giblets",
        "zh": "鱼露香炸土鸡 + 爆炒鸡杂",
        "ko": "느억맘 치킨 + 닭똥집 볶음",
        "ru": "Жареная курица в рыбном соусе + потроха"
    },
    "Gà hấp hành + Lòng mề xào": {
        "en": "Steamed Chicken with Scallions + Sautéed Giblets",
        "zh": "葱香清蒸土鸡 + 爆炒鸡杂",
        "ko": "대파 찜닭 + 닭똥집 볶음",
        "ru": "Курица на пару с луком + потроха"
    },
    "Gà nướng tây bắc + Lòng mề xào": {
        "en": "Northwest Mac Khen Grilled Chicken + Sautéed Giblets",
        "zh": "西北花椒烤土鸡 + 爆炒鸡杂",
        "ko": "북서부 막켄 산초 닭구이 + 닭똥집 볶음",
        "ru": "Курица на гриле с диким перцем Мак Кхен + потроха"
    },
    "Lẩu gà thuốc bắc": {
        "en": "Herbal Chicken Hotpot",
        "zh": "药膳滋补土鸡火锅",
        "ko": "한방 보양 닭고기 전골",
        "ru": "Куриный хот-пот с целебными травами"
    },
    "Cánh gà chiên mắm": {
        "en": "Crispy Chicken Wings with Fish Sauce",
        "zh": "鱼露炸鸡翅",
        "ko": "피쉬소스 치킨 윙 튀김",
        "ru": "Куриные крылышки в рыбном соусе"
    },
    "Cánh gà nướng muối ớt": {
        "en": "Chili Salt Grilled Chicken Wings",
        "zh": "椒盐炭烤鸡翅",
        "ko": "칠리 솔트 숯불 닭날개 구이",
        "ru": "Куриные крылышки на гриле с чили и солью"
    },
    "Cánh gà nướng tây bắc": {
        "en": "Northwest Spiced Grilled Chicken Wings",
        "zh": "西北风味烤鸡翅",
        "ko": "북서부 허브 산초 닭날개 구이",
        "ru": "Куриные крылышки на гриле по-северо-западному"
    },
    "Khoai môn chiên nước mắm": {
        "en": "Crispy Taro with Savory Fish Sauce",
        "zh": "鱼露香炸芋头",
        "ko": "피쉬소스 바삭 타로 튀김",
        "ru": "Хрустящий таро в рыбном соусе"
    },
    "Heo nướng giềng mẻ": {
        "en": "Grilled Pork with Galangal & Fermented Rice",
        "zh": "南姜酒酿炭烤猪肉",
        "ko": "갈랑갈 발효 쌀 양념 돼지구이",
        "ru": "Свинина на гриле с галангалом и ферментированным рисом"
    },
    "Ốc hương sốt trứng muối - bánh mì": {
        "en": "Sweet Snails in Salted Egg Sauce with Baguette",
        "zh": "咸蛋黄酱炒香螺 配法棍",
        "ko": "솔티드 에그 소스 골뱅이 구이 (바게트 포함)",
        "ru": "Улитки в соусе из соленого желтка с багетом"
    },
    "Ốc móng tay cháy tỏi": {
        "en": "Stir-fried Razor Clams with Crispy Garlic",
        "zh": "金蒜炒竹蛏",
        "ko": "바삭한 마늘 맛조개 볶음",
        "ru": "Морские черенки, обжаренные с чесноком"
    },
    "Ốc móng tay nướng mỡ hành": {
        "en": "Grilled Razor Clams with Scallion Oil & Peanuts",
        "zh": "葱油烤竹蛏",
        "ko": "파기름 맛조개 구이",
        "ru": "Морские черенки на гриле с луковым маслом"
    },
    "Ốc móng tay xào rau muống": {
        "en": "Stir-fried Razor Clams with Morning Glory",
        "zh": "空心菜炒竹蛏",
        "ko": "모닝글로리(공심채) 맛조개 볶음",
        "ru": "Морские черенки с водяным шпинатом"
    },
    "Bạch tuộc hấp hành gừng": {
        "en": "Steamed Octopus with Ginger & Scallions",
        "zh": "姜葱清蒸八爪鱼",
        "ko": "생강 대파 문어 숙회",
        "ru": "Осьминог на пару с имбирем и зеленым луком"
    },
    "Cơm chiên ghẹ": {
        "en": "Crab Meat Fried Rice",
        "zh": "鲜蟹肉黄金炒饭",
        "ko": "신선한 게살 볶음밥",
        "ru": "Жареный рис с мясом краба"
    },
    # 28 Vị chế biến món ăn PiPo Garden (Preparation Styles / Flavors)
    "Nướng muối ớt": { "en": "Chili Salt BBQ", "zh": "椒盐炭烤", "ko": "칠리 솔트 숯불구이", "ru": "На гриле с солью и чили" },
    "Chiên mắm": { "en": "Crispy Fish Sauce Glaze", "zh": "金牌鱼露脆炸", "ko": "단짠 피시소스 튀김", "ru": "В карамельном рыбном соусе" },
    "Hấp mắm nhĩ": { "en": "Steamed with Premium Fish Sauce", "zh": "原汁鱼露清蒸", "ko": "피시소스 찜", "ru": "На пару с рыбным соусом" },
    "Hấp hành": { "en": "Steamed with Fresh Scallions", "zh": "鲜葱清蒸", "ko": "대파 찜", "ru": "На пару со свежим луком" },
    "Hấp hành gừng": { "en": "Steamed with Ginger & Scallions", "zh": "葱姜清蒸", "ko": "생강 대파 찜", "ru": "На пару с имбирем и луком" },
    "Nướng Tây Bắc": { "en": "Northwest Pepper Herb BBQ", "zh": "西北野胡椒炭烤", "ko": "서북 허브 숯불구이", "ru": "С северо-западными травами" },
    "Lẩu thuốc bắc": { "en": "Herbal Medicine Hotpot", "zh": "秘制滋补药膳锅", "ko": "한방 약선 전골", "ru": "Травяной целебный суп" },
    "Nướng riềng mẻ": { "en": "Galangal & Fermented Rice BBQ", "zh": "南姜香糟炭烤", "ko": "생강 발효 숯불구이", "ru": "На гриле с галангалом и рисом" },
    "Sốt BBQ": { "en": "Garden BBQ Sauce", "zh": "特色烤肉BBQ酱", "ko": "가든 BBQ 소스", "ru": "Фирменный соус BBQ" },
    "Sốt BBQ cay ngọt": { "en": "Sweet & Spicy BBQ Sauce", "zh": "秘制甜辣BBQ酱", "ko": "스위트 스파이시 BBQ", "ru": "Сладко-острый соус BBQ" },
    "Sốt BBQ cay nhẹ": { "en": "Mild Spicy BBQ Sauce", "zh": "温和微辣BBQ酱", "ko": "마일드 스파이시 BBQ", "ru": "Мягкий соус BBQ" },
    "Sốt tiêu đen": { "en": "Black Pepper Sauce", "zh": "秘制黑椒浓汁", "ko": "블랙페퍼 소스", "ru": "С соусом из черного перца" },
    "Ướp mật ong thảo mộc": { "en": "Wild Honey & Herbs", "zh": "野生蜂蜜香草", "ko": "야생꿀 & 허브 양념", "ru": "С диким медом и травами" },
    "Phô mai tan chảy": { "en": "Melted Mozzarella Cheese", "zh": "浓郁拉丝芝士", "ko": "치즈 토핑", "ru": "С расплавленным сыром" },
    "Mỡ hành tóp mỡ": { "en": "Scallion Oil & Crispy Pork Rind", "zh": "葱油香脆猪油渣", "ko": "대파 기름 & 돼지껍데기", "ru": "Луковое масло со шкварками" },
    "Trứng cút sốt cay BBQ": { "en": "Quail Egg & Spicy BBQ", "zh": "鹌鹑蛋甜辣酱", "ko": "메추리알 매콤 BBQ", "ru": "Перепелиное яйцо с острым BBQ" },
    "Sốt bơ tỏi": { "en": "Garlic Butter Glaze", "zh": "蒜香黄油浓汁", "ko": "갈릭 버터 소스", "ru": "В чесночно-сливочном соусе" },
    "Muối ớt Tây Bắc": { "en": "Northwest Salt & Pepper", "zh": "西北特色椒盐", "ko": "북서부 허브 소금", "ru": "Северо-западная соль с чили" },
    "Cháy tỏi": { "en": "Crispy Garlic Tossed", "zh": "金蒜香炒", "ko": "바삭한 마늘 볶음", "ru": "С хрустящим чесноком" },
    "Sốt trứng muối (kèm bánh mì)": { "en": "Salted Egg Lava Sauce (+ Baguette)", "zh": "金沙咸蛋黄酱 (配法棍)", "ko": "솔티드 에그 소스 (+ 바게트)", "ru": "В соусе из соленого желтка (+ багет)" },
    "Hấp sả": { "en": "Steamed with Lemongrass", "zh": "清香香茅蒸", "ko": "레몬그라스 찜", "ru": "На пару с лемонграссом" },
    "Hấp Thái": { "en": "Thai Spicy Lemongrass Steamed", "zh": "泰式冬阴酸辣蒸", "ko": "태국식 매콤 똠얌 찜", "ru": "По-тайски с лемонграссом" },
    "Hấp nước dừa / sả": { "en": "Steamed with Coconut & Lemongrass", "zh": "椰汁香茅原味蒸", "ko": "코코넛 워터 & 레몬그라스 찜", "ru": "На пару в кокосовом молоке с лемонграссом" },
    "Nướng mỡ hành": { "en": "Grilled with Scallion Oil & Peanuts", "zh": "葱油花生炭烤", "ko": "파기름 & 땅콩 숯불구이", "ru": "На гриле с зеленым луком и арахисом" },
    "Xào rau muống": { "en": "Stir-Fried with Morning Glory", "zh": "蒜香空心菜炒", "ko": "모닝글로리(공심채) 볶음", "ru": "С водяным шпинатом" },
    "Xào cay": { "en": "Spicy Sautéed", "zh": "川香香辣炒", "ko": "매콤 양념 볶음", "ru": "В остром соусе" },
    "Xào tỏi": { "en": "Stir-Fried with Garlic", "zh": "金蒜清炒", "ko": "마늘 볶음", "ru": "Обжаренный с чесноком" },
    "Luộc": { "en": "Boiled / Poached", "zh": "原汁白灼", "ko": "데침 / 숙회", "ru": "Отварной" },
    "Sốt dầu hào": { "en": "Oyster Sauce Glazed", "zh": "蚝油生抽鲜炒", "ko": "굴소스 볶음", "ru": "В устричном соусе" },
    "Chiên giòn": { "en": "Golden Crispy", "zh": "香脆酥炸", "ko": "황금 바삭 튀김", "ru": "Хрустящий жареный" },
    "Tẩm hành": { "en": "Tossed with Scallion Oil", "zh": "传统葱油浸香", "ko": "고소한 파기름 양념", "ru": "С зеленым луком в масле" },
    "Bò": { "en": "Tender Beef", "zh": "鲜嫩牛肉", "ko": "소고기", "ru": "С говядиной" },
    "Ghẹ": { "en": "Fresh Flower Crab", "zh": "鲜甜花蟹肉", "ko": "꽃게살", "ru": "С мясом краба" },
    "Hải sản": { "en": "Mixed Seafood", "zh": "极品海鲜", "ko": "모듬 해산물", "ru": "С морепродуктами" }
}

def translate_single_text(text: str, target_lang: str) -> str:
    """Dịch một đoạn văn bản từ Tiếng Việt sang ngôn ngữ đích với nhiều tầng dự phòng bền vững."""
    if not text or not text.strip():
        return ""
    
    clean_text = text.strip()
    
    # Tầng 1: Kiểm tra trong từ điển ẩm thực offline chuyên sâu trước
    if clean_text in OFFLINE_FOOD_DICT and target_lang in OFFLINE_FOOD_DICT[clean_text]:
        return OFFLINE_FOOD_DICT[clean_text][target_lang]
    
    # Kiểm tra case-insensitive trong từ điển offline
    for k, v in OFFLINE_FOOD_DICT.items():
        if k.lower() == clean_text.lower() and target_lang in v:
            return v[target_lang]
            
    tl = GOOGLE_LANG_MAP.get(target_lang, target_lang)
    q = urllib.parse.quote(clean_text)
    
    # Tầng 2: Google Dict Chrome Extension API (Không bị 429, cực nhanh & chuẩn xác)
    try:
        url = f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=vi&tl={tl}&q={q}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], str) and data[0].strip():
                return data[0].strip()
            elif isinstance(data, str) and data.strip():
                return data.strip()
    except Exception:
        pass

    # Tầng 3: MyMemory Translation API dự phòng
    try:
        mymemory_tl = "zh-CN" if target_lang == "zh" else target_lang
        url = f"https://api.mymemory.translated.net/get?q={q}&langpair=vi|{mymemory_tl}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
            trans_res = (data.get("responseData") or {}).get("translatedText")
            if trans_res and trans_res.strip() and not trans_res.startswith("MYMEMORY WARNING"):
                return trans_res.strip()
    except Exception:
        pass

    # Tầng 4: Google GTX API
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=vi&tl={tl}&dt=t&q={q}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
            result = "".join(seg[0] for seg in data[0] if seg and seg[0])
            if result and result.strip():
                return result.strip()
    except Exception:
        pass

    # Dự phòng cuối cùng: trả về văn bản gốc
    return clean_text

def translate_dish(name: str, description: str = "") -> Dict[str, Dict[str, str]]:
    """
    Dịch tự động song song Tên món và Mô tả từ Tiếng Việt sang:
    en (English), zh (中文), ko (한국어), ru (Русский).
    Trả về dict chuẩn:
    {
        "en": {"name": "...", "description": "..."},
        "zh": {"name": "...", "description": "..."},
        "ko": {"name": "...", "description": "..."},
        "ru": {"name": "...", "description": "..."}
    }
    """
    results: Dict[str, Dict[str, str]] = {
        "en": {"name": "", "description": ""},
        "zh": {"name": "", "description": ""},
        "ko": {"name": "", "description": ""},
        "ru": {"name": "", "description": ""}
    }
    
    tasks = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        for lang in ["en", "zh", "ko", "ru"]:
            if name:
                tasks[(lang, "name")] = executor.submit(translate_single_text, name, lang)
            if description:
                tasks[(lang, "description")] = executor.submit(translate_single_text, description, lang)
                
        for (lang, field), fut in tasks.items():
            try:
                results[lang][field] = fut.result()
            except Exception:
                results[lang][field] = name if field == "name" else description
                
    return results

def translate_category_name(name: str) -> Dict[str, str]:
    """Dịch tên danh mục sang 4 ngôn ngữ."""
    results = {}
    tasks = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        for lang in ["en", "zh", "ko", "ru"]:
            tasks[lang] = executor.submit(translate_single_text, name, lang)
        for lang, fut in tasks.items():
            try:
                results[lang] = fut.result()
            except Exception:
                results[lang] = name
    return results
