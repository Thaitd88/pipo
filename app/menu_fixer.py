"""
app/menu_fixer.py
Chuẩn hóa Menu, Vị chế biến, Định lượng BOM, Dịch Vụ Sân Pickleball và Bản dịch 4 ngôn ngữ (EN, ZH, KO, RU)
cho 48 món ăn và 8 danh mục của PiPo Garden Restaurant.
Được tự động kích hoạt mỗi khi server khởi động trên cả Cloud Host (pipogarden.com)
lẫn máy Local Thu ngân.
"""

import json
import sqlite3
import os

TRANSLATIONS_DICT = {
    # 1. KHAI VỊ & ĂN NHẸ
    139: {
        "en": {"name": "Crispy Taro Seafood Salad", "description": "Crispy shredded taro topped with fresh seafood, herbs, and sweet-sour dressing."},
        "zh": {"name": "香芋海鲜沙拉", "description": "酥脆香芋丝搭配鲜甜海鲜、香草与特调酸甜酱汁。"},
        "ko": {"name": "바삭 타로 해산물 샐러드", "description": "바삭한 토란채 튀김과 신선한 해산물, 새콤달콤한 특제 드레싱이 어우러진 샐러드."},
        "ru": {"name": "Хрустящий салат с таро и морепродуктами", "description": "Хрустящий жареный таро со свежими морепродуктами, зеленью и кисло-сладким соусом."}
    },
    140: {
        "en": {"name": "Crispy French Fries", "description": "Golden crispy potato fries served with chili sauce or mayo."},
        "zh": {"name": "香脆黄金炸薯条", "description": "外酥里嫩的金黄薯条，搭配番茄酱或甜辣酱。"},
        "ko": {"name": "바삭한 감자튀김", "description": "바삭하고 고소하게 튀겨낸 황금빛 감자튀김."},
        "ru": {"name": "Хрустящий картофель фри", "description": "Золотистый хрустящий картофель фри с соусом на выбор."}
    },
    142: {
        "en": {"name": "Green Mango Salad with Dried Shrimp", "description": "Tangy green mango salad tossed with premium dried shrimp and roasted peanuts."},
        "zh": {"name": "青芒果干虾沙拉", "description": "酸爽青芒果丝伴富国岛特级虾干与香脆花生。"},
        "ko": {"name": "건새우 그린망고 샐러드", "description": "새콤한 그린망고와 푸꾸옥 특산 건새우, 볶은 땅콩의 상큼한 조화."},
        "ru": {"name": "Салат из зеленого манго с сушеными креветками", "description": "Пикантный салат из свежего зеленого манго с сушеными креветками и арахисом."}
    },
    143: {
        "en": {"name": "Water Spinach / Morning Glory", "description": "Fresh water spinach wok-fried with fragrant garlic or gently boiled."},
        "zh": {"name": "时令空心菜 (蒜蓉炒 / 白灼)", "description": "鲜嫩空心菜，蒜蓉大火快炒或清爽白灼。"},
        "ko": {"name": "모닝글로리 (공심채 볶음 / 데침)", "description": "아삭한 모닝글로리(공심채) 마늘 볶음 또는 깔끔한 데침 요리."},
        "ru": {"name": "Водный шпинат (Морнинг глори)", "description": "Свежий водный шпинат, обжаренный с чесноком в воке или отварной."}
    },
    144: {
        "en": {"name": "Baby Bok Choy in Oyster Sauce / Boiled", "description": "Tender bok choy drizzled with rich oyster sauce or lightly boiled."},
        "zh": {"name": "鲜嫩上海青 (蚝油 / 白灼)", "description": "翠绿爽脆的上海青，配浓郁蚝油汁或白灼清甜。"},
        "ko": {"name": "청경채 요리 (굴소스 볶음 / 데침)", "description": "신선한 청경채 굴소스 볶음 hoặc 깔끔한 데침 채소 요리."},
        "ru": {"name": "Бок-чой (под устричным соусом / отварной)", "description": "Нежная капуста бок-чой под устричным соусом или на пару."}
    },
    146: {
        "en": {"name": "Golden Crispy Tofu", "description": "Crispy fried tofu squares served plain or dipped in scallion oil."},
        "zh": {"name": "外酥里嫩鲜豆腐 (酥炸 / 葱油)", "description": "外皮金黄酥脆、内里如布丁般滑嫩的豆腐，配葱油。"},
        "ko": {"name": "바삭 두부 튀김 (크리스피 / 파기름 양념)", "description": "겉은 바삭하고 속은 부드러운 수제 두부 튀김."},
        "ru": {"name": "Хрустящий золотистый тофу", "description": "Жареный тофу с хрустящей корочкой, с зеленым луком или соусом."}
    },
    147: {
        "en": {"name": "Crispy Taro with Savory Fish Sauce", "description": "Golden crispy taro chips glazed in savory caramelized fish sauce or deep fried."},
        "zh": {"name": "浓香鱼露炸香芋 (酥炸 / 鱼露酱)", "description": "香酥芋头条裹上特调咸甜鱼露浓汁，浓香可口。"},
        "ko": {"name": "피쉬소스 바삭 타로 튀김", "description": "바삭하게 튀겨 달콤짭조름한 특제 피쉬소스에 버무린 타로 튀김."},
        "ru": {"name": "Хрустящий таро в рыбном соусе", "description": "Хрустящие брусочки таро в карамелизированном рыбном соусе."}
    },
    205: {
        "en": {"name": "Boiled Chicken Egg", "description": "Freshly boiled organic chicken egg."},
        "zh": {"name": "水煮土鸡蛋", "description": "营养健康水煮新鲜土鸡蛋。"},
        "ko": {"name": "삶은 계란", "description": "고소하고 영양 가득한 신선한 삶은 달걀."},
        "ru": {"name": "Вареное яйцо", "description": "Свежее вареное куриное яйцо."}
    },
    206: {
        "en": {"name": "Boiled Sweet Corn (Coming Soon)", "description": "Naturally sweet boiled golden corn."},
        "zh": {"name": "香甜水煮玉米 (即将推出)", "description": "金黄香甜的新鲜水煮玉米棒。"},
        "ko": {"name": "삶은 옥수수 (출시 예정)", "description": "달콤하고 톡톡 터지는 신선한 삶은 옥수수."},
        "ru": {"name": "Вареная сладкая кукуруза (Скоро)", "description": "Сочная сладкая отварная кукуруза."}
    },

    # 2. GÀ - VỊT
    148: {
        "en": {"name": "Whole H'Mong Black Chicken (Choose Style)", "description": "Whole free-range H'Mong black chicken: Salt-chili grilled, fish sauce glazed, herbal hotpot, or steamed."},
        "zh": {"name": "整只赫蒙黑骨土鸡 (做法任选)", "description": "珍贵整只黑鸡：炭烤椒盐、浓香鱼露、药膳滋补火锅或原味清蒸。"},
        "ko": {"name": "통 흑계 요리 (조리 방식 선택)", "description": "영양 가득 통 흑계(검은 닭): 숯불 칠리소금구이, 피쉬소스 튀김, 한방 백숙, 생선액젓 찜 선택."},
        "ru": {"name": "Целая черная курица Хмонг (на выбор)", "description": "Целая черная курица: на гриле с чили и солью, в рыбном соусе, в травяном бульоне или на пару."}
    },
    150: {
        "en": {"name": "Whole Free-Range Farm Chicken + Giblets", "description": "Whole Vietnamese garden chicken with sautéed giblets: Chili salt grilled, fish sauce glazed, onion steamed, or herbal hotpot."},
        "zh": {"name": "整只走地土鸡 + 爆炒鸡杂", "description": "整只优质土鸡配鸡杂：炭烤椒盐、鱼露油炸、葱香清蒸、药膳火锅。"},
        "ko": {"name": "토종 통닭 요리 + 닭똥집 볶음", "description": "육질이 쫄깃한 토종 통닭과 닭모래집: 숯불 칠리소금구이, 피쉬소스 튀김, 파 찜, 한방 백숙."},
        "ru": {"name": "Целая домашняя курица с потрошками", "description": "Домашняя курица на гриле с солью и чили, в рыбном соусе, на пару с луком или в бульоне."}
    },
    157: {
        "en": {"name": "Crispy Chicken Wings (Choose Flavor)", "description": "Crispy chicken wings: Chili salt grilled, fish sauce glazed, or Northwest mountain spices."},
        "zh": {"name": "香脆烤鸡翅 (可选风味)", "description": "外脆内嫩鸡翅：炭烤椒盐、金牌鱼露、西北特色香料烤。"},
        "ko": {"name": "바삭 치킨 윙 (맛 선택)", "description": "겉바속촉 닭날개 구이: 칠리소금 숯불구이, 피쉬소스 글레이즈, 북서부 특제 향신료 구이."},
        "ru": {"name": "Куриные крылышки (вкус на выбор)", "description": "Хрустящие крылышки: на гриле с солью и чили, в рыбном соусе или с горными травами."}
    },
    159: {
        "en": {"name": "Herbal Roasted Duck (Half)", "description": "Half tender duck roasted with traditional herbs and crispy golden skin."},
        "zh": {"name": "秘制香草脆皮烤鸭 (半只)", "description": "精选半只肥鸭，配以秘制草本慢火慢烤，皮脆肉嫩多汁。"},
        "ko": {"name": "허브 로스트 오리구이 (반 마리)", "description": "엄선된 허브로 마리네이드하여 겉은 바삭하고 속은 촉촉한 오리구이."},
        "ru": {"name": "Утка, запеченная с травами (половина)", "description": "Половина утки с хрустящей корочкой, запеченная с ароматными травами."}
    },
    160: {
        "en": {"name": "Grilled Spiced Chicken Feet (5 Pairs)", "description": "Tender chicken feet grilled with fragrant spices and sweet-spicy dip."},
        "zh": {"name": "炭烤风味凤爪 (5对)", "description": "炭火慢烤香脆鸡爪，搭配青柠辣椒沾酱，越嚼越香。"},
        "ko": {"name": "숯불 닭발 구이 (5쌍)", "description": "불향 가득 바삭쫄깃하게 구워낸 별미 숯불 닭발 구이."},
        "ru": {"name": "Куриные лапки на гриле (5 пар)", "description": "Пряные куриные лапки на гриле с острым соусом."}
    },

    # 3. HEO - BÒ
    145: {
        "en": {"name": "Sichuan Peppercorn Beef", "description": "Tender beef slices wok-tossed with aromatic cracked peppercorns and herbs."},
        "zh": {"name": "川味黑椒牛肉", "description": "鲜嫩牛肉块爆炒香浓黑胡椒与彩椒，香气扑鼻。"},
        "ko": {"name": "사천식 통후추 소고기 볶음", "description": "알싸한 통후추와 신선한 야채로 볶아낸 부드러운 소고기 요리."},
        "ru": {"name": "Говядина с сычуаньским перцем", "description": "Нежная говядина, обжаренная с дробленым ароматным перцем."}
    },
    161: {
        "en": {"name": "Grilled Pork Belly (Choose Flavor)", "description": "Marinated pork belly grilled over charcoal: Galangal fermented rice or chili salt."},
        "zh": {"name": "秘制炭烤五花肉 (选风味)", "description": "精选五花肉：南姜酒酿炭烤或特调香辣椒盐烤。"},
        "ko": {"name": "숯불 삼겹살 구이 (양념 선택)", "description": "두툼한 삼겹살을 숯불에 구워낸 요리: 갈랑갈 발효 양념 또는 칠리소금구이."},
        "ru": {"name": "Свиная грудинка на гриле", "description": "Маринованная свиная грудинка на углях с галангалом или солью и чили."}
    },
    201: {
        "en": {"name": "Grilled Pork Ribs (Choose Flavor)", "description": "Tender pork ribs grilled over charcoal: Chili salt or savory fish sauce."},
        "zh": {"name": "炭烤秘制猪排 (选风味)", "description": "肉厚汁多的猪肋排：香辣椒盐烤或鲜香鱼露炸。"},
        "ko": {"name": "돼지 등갈비 구이 (맛 선택)", "description": "육즙 가득한 돼지갈비 구이: 매콤 칠리소금구이 또는 감칠맛 피쉬소스 구이."},
        "ru": {"name": "Свиные ребрышки на гриле (на выбор)", "description": "Нежные свиные ребрышки на углях с чили и солью или в рыбном соусе."}
    },

    # 4. HẢI SẢN
    162: {
        "en": {"name": "Grilled Sea Oyster with Melted Cheese", "description": "Fresh sea oyster grilled and topped with rich, melted mozzarella cheese."},
        "zh": {"name": "芝士焗海生蚝 (1只)", "description": "新鲜饱满大生蚝，覆盖浓香融化芝士奶酪炭烤。"},
        "ko": {"name": "치즈 굴 구이 (1개)", "description": "신선한 대왕 굴 위에 고소한 모짜렐라 치즈를 듬뿍 올려 구운 요리."},
        "ru": {"name": "Запеченная устрица под сыром", "description": "Свежая морская устрица, запеченная с расплавленным сыром моцарелла."}
    },
    163: {
        "en": {"name": "Grilled Sea Oyster with Scallion Oil & Peanuts", "description": "Fresh sea oyster grilled with fragrant scallion oil, crunchy peanuts, and fried shallots."},
        "zh": {"name": "葱油炭烤海生蚝 (1只)", "description": "新鲜生蚝配喷香葱油、碎花生与酥香葱酥。"},
        "ko": {"name": "파기름 땅콩 굴 구이 (1개)", "description": "고소한 파기름과 바삭한 땅콩, 튀긴 샬롯을 얹어 구운 베트남 전통 굴구이."},
        "ru": {"name": "Устрица на гриле с зеленым луком и арахисом", "description": "Устрица на гриле с ароматным луковым маслом и хрустящим арахисом."}
    },
    164: {
        "en": {"name": "Steamed Clams (Lemongrass or Thai Tom Yum)", "description": "Fresh clams steamed with fragrant lemongrass or spicy sweet-sour Thai broth."},
        "zh": {"name": "鲜甜白蛤 (香茅清蒸 / 泰式酸辣)", "description": "肉质细嫩的白蛤：香茅清蒸鲜甜，或浓郁泰式冬阴酸辣汤煮。"},
        "ko": {"name": "조개 찜 (레몬글라스 찜 / 매콤 똠얌 탕)", "description": "해산물의 시원한 국물 맛: 향긋한 레몬글라스 찜 또는 칼칼한 태국식 똠얌 스타일."},
        "ru": {"name": "Вонголе на пару (с лемонграссом или по-тайски)", "description": "Свежие ракушки вонголе на пару с лемонграссом или в кисло-остром тайском бульоне."}
    },
    167: {
        "en": {"name": "Phu Quoc Tiger Prawns (Choose Style)", "description": "Fresh tiger prawns: Coconut water/lemongrass steamed, chili salt grilled, garlic butter, or crispy panko."},
        "zh": {"name": "富国岛特级黑虎虾 (做法任选)", "description": "鲜活大黑虎虾：椰汁香茅蒸、炭烤椒盐、浓香蒜蓉黄油或香酥黄金炸。"},
        "ko": {"name": "푸꾸옥 블랙타이거 새우 (조리 방식 선택)", "description": "탱글탱글한 왕새우: 코코넛워터 레몬글라스 찜, 칠리소금 숯불구이, 갈릭버터 볶음, 바삭 튀김."},
        "ru": {"name": "Тигровые креветки Фукуок (на выбор)", "description": "Тигровые креветки: на пару в кокосовой воде, на гриле с чили, в чесночном масле или в сухарях."}
    },
    169: {
        "en": {"name": "Sweet Snails (Choose Flavor)", "description": "Fresh sweet snails: Salted egg yolk sauce with warm bread, garlic wok-tossed, or lemongrass steamed."},
        "zh": {"name": "富国岛鲜香螺 (口味任选)", "description": "肥美海香螺：黄金咸蛋黄酱配热面包、爆炒金蒜、清香香茅蒸。"},
        "ko": {"name": "향고둥 / 골뱅이 요리 (맛 선택)", "description": "쫄깃한 특산 고둥: 바게트와 함께 즐기는 솔티드 에그 소스, 마늘 볶음, 레몬글라스 찜."},
        "ru": {"name": "Морские улитки (вкус на выбор)", "description": "Морские улитки: в соусе из соленого желтка с багетом, с чесноком или на пару с лемонграссом."}
    },
    172: {
        "en": {"name": "Razor Clams (Choose Flavor)", "description": "Fresh razor clams: Garlic wok-tossed, grilled with scallion oil, or wok-fried with water spinach."},
        "zh": {"name": "鲜活竹蛏 (做法任选)", "description": "鲜甜大竹蛏：蒜香大火炒、葱油花生烤或脆嫩空心菜同炒。"},
        "ko": {"name": "맛조개 요리 (조리 방식 선택)", "description": "신선한 맛조개: 갈릭 볶음, 파기름 숯불구이, 모닝글로리 볶음."},
        "ru": {"name": "Морские черенки (на выбор)", "description": "Морские черенки (ножи): с жареным чесноком, на гриле с луковым маслом или с водяным шпинатом."}
    },
    176: {
        "en": {"name": "Phu Quoc Baby Octopus (Choose Style)", "description": "Fresh tender octopus: Chili salt grilled, spicy wok-sautéed, or ginger-scallion steamed."},
        "zh": {"name": "富国特产鲜小章鱼 (做法任选)", "description": "爽脆小章鱼：炭烤椒盐、火辣爆炒、姜葱清蒸。"},
        "ko": {"name": "푸꾸옥 주꾸미 / 낙지 요리 (선택)", "description": "쫄깃하고 부드러운 낙지/주꾸미: 칠리소금 숯불구이, 매콤 볶음, 생강파 찜."},
        "ru": {"name": "Молодой осьминог Фукуок (на выбор)", "description": "Нежный осьминог: на гриле с чили и солью, в остром соусе или на пару с имбирем."}
    },
    197: {
        "en": {"name": "Live Grouper 2-Way Feast (2kg)", "description": "Whole live ocean grouper prepared in two styles: Fresh sashimi and hotpot, or steamed with soy sauce."},
        "zh": {"name": "生猛活石斑鱼两吃大餐 (约2公斤)", "description": "整条鲜活石斑鱼双重美味：鲜甜刺身 + 浓香酸汤火锅，或港式葱姜清蒸。"},
        "ko": {"name": "활 다금바리(그루퍼) 2코스 요리 (2kg)", "description": "살아있는 2kg 대형 그루퍼 요리: 신선한 생선회(사시미) & 얼큰한 매운탕/전골 또는 중화풍 찜."},
        "ru": {"name": "Живой морской окунь групер в 2 подачах (2 кг)", "description": "Свежевыловленный групер: сашими и наваристый суп-хотпот или на пару в соевом соусе."}
    },
    198: {
        "en": {"name": "Charcoal Grilled Scad Fish (400g)", "description": "Fresh ocean scad grilled whole over charcoal with chili salt, served with rice paper and fresh herbs."},
        "zh": {"name": "炭烤鲜竹荚鱼 (400克)", "description": "整条深海竹荚鱼炭火慢烤，鱼皮焦香鱼肉鲜嫩，搭配米纸蔬菜卷。"},
        "ko": {"name": "숯불 전갱이 통 생선구이 (400g)", "description": "숯불에 통째로 노릇하게 구워낸 전갱이 생선구이, 라이스페이퍼 쌈 제공."},
        "ru": {"name": "Ставрида на углях с солью и чили (400 г)", "description": "Целая океаническая ставрида на углях со специями, подается с рисовой бумагой и зеленью."}
    },

    # 5. CƠM - MÌ (CHỌN VỊ BÒ / HẢI SẢN / GHẸ)
    180: {
        "en": {
            "name": "Signature Fried Rice (Choose: Crab / Seafood / Beef)",
            "description": "Fragrant ST25 jasmine rice fried with golden eggs and your choice of fresh crab meat, ocean seafood, or tender beef."
        },
        "zh": {
            "name": "招牌黄金炒饭 (可选: 鲜蟹肉 / 海鲜 / 牛肉)",
            "description": "精选ST25香米配土鸡蛋金黄翻炒，可选鲜拆蟹肉、海鲜大虾或鲜嫩牛肉。"
        },
        "ko": {
            "name": "시그니처 볶음밥 (선택: 게살 / 해물 / 소고기)",
            "description": "고슬고슬한 ST25 쌀밥과 계란에 신선한 게살, 해산물 또는 소고기를 듬뿍 넣은 볶음밥."
        },
        "ru": {
            "name": "Фирменный жареный рис (на выбор: с крабом / морепродуктами / говядиной)",
            "description": "Ароматный жареный рис с яйцом и топпингом на выбор: мясо краба, морепродукты или говядина."
        }
    },
    181: {
        "en": {
            "name": "Stir-fried Noodles (Choose: Seafood / Beef)",
            "description": "Wok-tossed egg noodles with crisp vegetables and your choice of fresh ocean seafood or tender beef slices."
        },
        "zh": {
            "name": "特色炒面 (可选: 海鲜 / 牛肉)",
            "description": "大火快炒香韧鸡蛋面，搭配时令蔬菜与鲜美海鲜或滑嫩牛肉。"
        },
        "ko": {
            "name": "특선 볶음면 (선택: 해물 / 소고기)",
            "description": "쫄깃한 에그 누들과 아삭한 야채에 신선한 해산물 또는 소고기를 센 불에 볶아낸 요리."
        },
        "ru": {
            "name": "Жареная лапша (на выбор: с морепродуктами / говядиной)",
            "description": "Яичная лапша вок со свежими овощами и топпингом на выбор: морепродукты или нежная говядина."
        }
    },

    # 6. ĐỒ UỐNG & BIA
    183: {
        "en": {"name": "Aquafina Mineral Water (500ml)", "description": "Pure bottled mineral water served chilled."},
        "zh": {"name": "纯净矿泉水 (500ml 瓶装)", "description": "冰镇清凉天然矿泉水。"},
        "ko": {"name": "생수 (500ml)", "description": "시원하고 깨끗한 생수."},
        "ru": {"name": "Минеральная вода (500 мл)", "description": "Чистая бутилированная вода."}
    },
    184: {
        "en": {"name": "Coca Cola (320ml)", "description": "Classic carbonated soft drink served chilled."},
        "zh": {"name": "可口可乐 (320ml 听装)", "description": "经典冰镇可口可乐汽水。"},
        "ko": {"name": "코카콜라 (320ml)", "description": "시원한 오리지널 코카콜라 캔."},
        "ru": {"name": "Кока-Кола (320 мл)", "description": "Классическая газировка со льдом."}
    },
    185: {
        "en": {"name": "Pepsi (320ml)", "description": "Crisp refreshing cola served chilled."},
        "zh": {"name": "百事可乐 (320ml 听装)", "description": "清爽冰镇百事可乐汽水。"},
        "ko": {"name": "펩시 콜라 (320ml)", "description": "시원하고 청량한 펩시 콜라 캔."},
        "ru": {"name": "Пепси (320 мл)", "description": "Освежающая пепси-кола со льдом."}
    },
    186: {
        "en": {"name": "Aquarius Electrolyte Drink (390ml)", "description": "Hydrating electrolyte isotonic drink."},
        "zh": {"name": "水动乐电解质水 (390ml 瓶装)", "description": "运动补充电解质微量元素。"},
        "ko": {"name": "아쿠아리스 이온음료 (390ml)", "description": "운동 후 수분과 전해질을 빠르게 충전해주는 이온음료."},
        "ru": {"name": "Изотоник Aquarius (390 мл)", "description": "Освежающий изотонический напиток для восстановления сил."}
    },
    187: {
        "en": {"name": "Revive Isotonic Drink (500ml)", "description": "Sparkling hydration drink rich in vitamins."},
        "zh": {"name": "活力补充水 Revive (500ml 瓶装)", "description": "解渴提神、补充水分与维生素的微气泡饮料。"},
        "ko": {"name": "리바이브 이온음료 (500ml)", "description": "갈증 해소와 비타민 공급에 탁월한 탄산 이온음료."},
        "ru": {"name": "Напиток Revive (500 мл)", "description": "Витаминный изотонический газированный напиток."}
    },
    188: {
        "en": {"name": "Bivina Beer (330ml Can)", "description": "Crisp island specialty lager brewed for Phu Quoc."},
        "zh": {"name": "Bivina 海岛特产啤酒 (330ml 听装)", "description": "富国岛风味特产啤酒，冰爽清冽。"},
        "ko": {"name": "비비나 맥주 (330ml)", "description": "푸꾸옥 섬 특산 시원한 로컬 라거 캔맥주."},
        "ru": {"name": "Пиво Бивина (330 мл)", "description": "Островное освежающее светлое пиво Фукуока."}
    },
    189: {
        "en": {"name": "Saigon Special / Lager (330ml)", "description": "Famous Vietnamese golden malt lager."},
        "zh": {"name": "西贡特酿金牌啤酒 (330ml 听装)", "description": "越南经典特酿啤酒，麦芽浓郁回味甘醇。"},
        "ko": {"name": "사이공 스페셜 맥주 (330ml)", "description": "베트남의 대표적인 진하고 깊은 풍미의 프리미엄 맥주."},
        "ru": {"name": "Пиво Сайгон Спешл (330 мл)", "description": "Классический вьетнамский светлый лагер."}
    },
    190: {
        "en": {"name": "Heineken Silver Sleek (250ml)", "description": "Smooth, easy-drinking premium European lager."},
        "zh": {"name": "喜力星银特酿啤酒 (250ml 听装)", "description": "国际高端喜力星银，口感极致顺滑清爽。"},
        "ko": {"name": "하이네켄 실버 캔맥주 (250ml)", "description": "부드러운 목넘김과 깔끔한 피니시의 프리미엄 하이네켄 실버."},
        "ru": {"name": "Пиво Хайнекен Сильвер (250 мл)", "description": "Освежающее премиальное пиво Heineken Silver."}
    },
    199: {
        "en": {"name": "Hanoi Fresh Draft Beer (1 Litre Jug)", "description": "Iconic traditional Hanoi fresh draft beer served cold."},
        "zh": {"name": "河内传统生鲜啤酒 (扎装 1公升)", "description": "越南著名河内传统鲜生啤酒，泡沫绵密麦香浓厚。"},
        "ko": {"name": "하노이 비아호이 생맥주 (1리터 저그)", "description": "하노이 전통 방식의 신선하고 부드러운 생맥주 1L."},
        "ru": {"name": "Ханойское свежее разливное пиво Bia Hoi (1 л)", "description": "Знаменитое свежее разливное пиво по ханойскому рецепту в кувшине 1 л."}
    },

    # 7. HOT BBQ
    200: {
        "en": {"name": "Grilled US Beef Ribs (Choose Sauce)", "description": "Tender marbled US beef ribs grilled with your choice of Black Pepper Sauce or BBQ Sauce."},
        "zh": {"name": "炭烤美式牛肋条 (选酱汁)", "description": "大理石花纹美式牛肋条炭火慢烤：黑椒酱汁或浓郁BBQ酱汁。"},
        "ko": {"name": "미국산 소갈비살 숯불구이 (소스 선택)", "description": "육즙 가득 마블링 소갈비살 숯불구이: 블랙페퍼 소스 또는 정통 BBQ 소스."},
        "ru": {"name": "Говяжьи ребрышки на гриле (соус на выбор)", "description": "Мраморные говяжьи ребрышки на углях с соусом барбекю или черным перцем."}
    },
    202: {
        "en": {"name": "Grilled US Beef Rib Steak (Coming Soon)", "description": "Thick-cut juicy beef rib steak glazed in savory BBQ sauce and grilled over charcoal."},
        "zh": {"name": "炭烤厚切美式牛排肋 (即将推出)", "description": "厚切鲜嫩牛肋大排裹上特调BBQ酱料炭烤，肉香浓郁。"},
        "ko": {"name": "미국산 통소갈비 숯불구이 (출시 예정)", "description": "두툼한 소갈비 스테이크에 BBQ 소스를 발라 숯불에 구워낸 프리미엄 요리."},
        "ru": {"name": "Стейк из говяжьих ребрышек на гриле (Скоро)", "description": "Сочный толстый говяжий стейк на ребрышках с соусом барбекю на углях."}
    },
    203: {
        "en": {"name": "PiPo Garden Mixed BBQ Skewers (4 Large Skewers)", "description": "Assorted skewers of spiced meats and fresh vegetables grilled over outdoor charcoal."},
        "zh": {"name": "PiPo花园特色综合烤串 (4大串)", "description": "精选鲜肉与时令蔬菜搭配秘制香料炭火炙烤。"},
        "ko": {"name": "피포 가든 모듬 꼬치구이 (4꼬치)", "description": "신선한 육류와 채소를 특제 양념에 재워 숯불에 구운 모듬 꼬치."},
        "ru": {"name": "Ассорти шашлычков PiPo Garden (4 шпажки)", "description": "Большие шпажки с маринованным мясом и овощами на углях."}
    },

    # 8. DỊCH VỤ SÂN PICKLEBALL
    301: {
        "en": {"name": "Social Pickleball Ticket (16:00-22:00 + Drink)", "description": "Evening session social pickleball pass including 1 chilled bottled beverage."},
        "zh": {"name": "匹克球下午/晚场畅打票 (16:00-22:00 含饮品)", "description": "黄金时段匹克球体验票，免费附赠1瓶冰镇饮料。"},
        "ko": {"name": "피클볼 소셜 오후/야간권 (16:00-22:00 + 음료 1병)", "description": "오후 및 야간 소셜 피클볼 이용권 (시원한 음료 1병 무료 제공)."},
        "ru": {"name": "Билет на вечерний пиклбол (16:00-22:00 + напиток)", "description": "Вечерняя сессия игры в пиклбол, включая 1 прохладительный напиток."}
    },
    302: {
        "en": {"name": "Morning Social Pickleball Ticket (06:00-16:00)", "description": "Morning social pickleball play pass (without included drink)."},
        "zh": {"name": "匹克球早场畅打票 (06:00-16:00)", "description": "早间匹克球单次畅打体验（不含饮品）。"},
        "ko": {"name": "피클볼 소셜 오전권 (06:00-16:00)", "description": "오전 시간대 피클볼 소셜 이용권 (음료 미포함)."},
        "ru": {"name": "Билет на утренний пиклбол (06:00-16:00)", "description": "Утренний сеанс пиклбола (без напитка)."}
    },
    303: {
        "en": {"name": "Pickleball Paddle Rental", "description": "High-grade carbon fiber pickleball paddle rental per session."},
        "zh": {"name": "匹克球碳纤维球拍租借", "description": "专业级超轻碳纤维匹克球拍单次租借。"},
        "ko": {"name": "피클볼 고급 라켓 대여", "description": "경기용 카본 피클볼 라켓 1회 대여 서비스."},
        "ru": {"name": "Аренда ракетки для пиклбола", "description": "Аренда профессиональной карбоновой ракетки на 1 сессию."}
    },
    304: {
        "en": {"name": "Hourly Court Rental (1 Hour)", "description": "Covered professional resort pickleball court rental per hour."},
        "zh": {"name": "匹克球包场每小时 (1小时)", "description": "标准防滑避震遮阳匹克球场时租服务。"},
        "ko": {"name": "피클볼 코트 시간당 대여 (1시간)", "description": "리조트 표준 규격 지붕형 피클볼 코트 1시간 대관."},
        "ru": {"name": "Аренда корта почасово (1 час)", "description": "Аренда профессионального крытого корта для пиклбола на 1 час."}
    },
    305: {
        "en": {"name": "Monthly Social Pass (All Hours Unlimited)", "description": "30-day all-hours unlimited access to social pickleball sessions."},
        "zh": {"name": "全时段匹克球月卡会员 (30天不限时)", "description": "30天全时段自由畅打，随时上场尽情挥拍。"},
        "ko": {"name": "올타임 피클볼 월회원권 (30일 무제한)", "description": "시간 제한 없이 한 달 동안 자유롭게 이용 가능한 소셜 월회원권."},
        "ru": {"name": "Безлимитный абонемент на месяц (все часы)", "description": "Абонемент на 30 дней без ограничений по времени."}
    },
    306: {
        "en": {"name": "Morning-Only Monthly Social Pass", "description": "30-day morning session (06:00-16:00) social pickleball pass."},
        "zh": {"name": "早场匹克球月卡会员 (06:00-16:00)", "description": "30天早间时段专属优惠月卡，健康晨练首选。"},
        "ko": {"name": "모닝 피클볼 월회원권 (06:00-16:00)", "description": "매일 오전 시간대(06시~16시) 전용 알뜰 월회원권."},
        "ru": {"name": "Утренний абонемент на месяц (06:00-16:00)", "description": "Абонемент на 30 дней на утренние часы с 06:00 до 16:00."}
    },
    307: {
        "en": {"name": "Annual Individual VIP Social Pass", "description": "365-day individual VIP pass with unlimited year-round pickleball access."},
        "zh": {"name": "个人尊享匹克球年度VIP会员 (365天)", "description": "全年365天无限制畅打VIP会员资格，享专属球友礼遇。"},
        "ko": {"name": "개인 연간 VIP 회원권 (365일)", "description": "365일 1년 내내 언제든 즐기는 개인 연간 최고급 VIP 멤버십."},
        "ru": {"name": "Годовой VIP абонемент (365 дней)", "description": "Индивидуальный годовой VIP абонемент на 365 дней без ограничений."}
    },
    308: {
        "en": {"name": "Fixed Monthly Court Booking (Custom Rate)", "description": "Dedicated recurring monthly time slot booking at negotiated rate."},
        "zh": {"name": "固定时段包场月订 (协议价)", "description": "企业或俱乐部专属固定每周时段包场，价格协商定制。"},
        "ko": {"name": "고정 시간 코트 월대관 (협의 가격)", "description": "지정 요일/시간대 전용 코트 고정 월대관 (맞춤 협의가)."},
        "ru": {"name": "Фиксированная бронь корта на месяц (договорная цена)", "description": "Фиксированное бронирование корта на месяц по договорной цене."}
    }
}

CATEGORY_TRANSLATIONS = {
    1: {"en": "Appetizers & Starters", "zh": "精选开胃前菜", "ko": "에피타이저 (전채요리)", "ru": "Аппетитные закуски"},
    2: {"en": "Poultry (Chicken & Duck)", "zh": "特色家禽 (土鸡/烤鸭)", "ko": "닭 & 오리 특선 요리", "ru": "Блюда из птицы (курица, утка)"},
    3: {"en": "Pork & Beef Specialties", "zh": "经典猪肉 & 牛肉", "ko": "돼지고기 & 소고기 요리", "ru": "Мясные блюда (свинина, говядина)"},
    4: {"en": "Fresh Seafood", "zh": "鲜美海鲜特撰", "ko": "신선한 해산물 요리", "ru": "Свежие морепродукты"},
    5: {"en": "Rice & Noodles", "zh": "主食精选 (黄金炒饭/炒面)", "ko": "식사류 (볶음밥 & 볶음면)", "ru": "Рис и жареная лапша"},
    6: {"en": "Beverages & Drinks", "zh": "冷饮果汁 & 啤酒", "ko": "시원한 음료 & 맥주", "ru": "Прохладительные напитки и пиво"},
    7: {"en": "Garden Hot BBQ", "zh": "炭火热烤 (花园BBQ)", "ko": "가든 숯불 핫 BBQ", "ru": "Горячее барбекю в саду"},
    8: {"en": "Pickleball Court Services", "zh": "匹克球球场服务", "ko": "피클볼 코트 서비스", "ru": "Услуги корта пиклбол"}
}

PICKLEBALL_SERVICES = [
    {
        "id": 301,
        "name": "Vé Social Chiều (16h-22h kèm nước)",
        "price": 60000,
        "portion": "1 lượt chơi + 1 nước",
        "description": "Suất chơi Pickleball Social khung giờ vàng (16h - 22h). Đã bao gồm 01 chai nước uống giải khát mát lạnh.",
        "category_id": 8,
        "main_menu_type": "PICKLE",
        "station": "BAR"
    },
    {
        "id": 302,
        "name": "Vé Social Sáng (06h-16h)",
        "price": 30000,
        "portion": "1 lượt chơi sáng",
        "description": "Suất chơi Pickleball Social khung giờ sáng và trưa (06h - 16h). Thể thao năng động đầu ngày.",
        "category_id": 8,
        "main_menu_type": "PICKLE",
        "station": "BAR"
    },
    {
        "id": 303,
        "name": "Thuê Vợt Pickleball",
        "price": 50000,
        "portion": "1 cây / lượt",
        "description": "Thuê vợt carbon thi đấu cao cấp siêu nhẹ, êm tay, tặng kèm bóng tập trong suốt buổi chơi.",
        "category_id": 8,
        "main_menu_type": "PICKLE",
        "station": "BAR"
    },
    {
        "id": 304,
        "name": "Thuê Sân Theo Giờ",
        "price": 200000,
        "portion": "1 giờ / sân",
        "description": "Bao trọn 01 sân thi đấu tiêu chuẩn có mái che thoáng mát, mặt sân cao su giảm chấn chuẩn quốc tế.",
        "category_id": 8,
        "main_menu_type": "PICKLE",
        "station": "BAR"
    },
    {
        "id": 305,
        "name": "Gói Social Tháng (Mọi Khung Giờ)",
        "price": 1200000,
        "portion": "30 ngày không giới hạn giờ",
        "description": "Thẻ hội viên Social tháng không giới hạn khung giờ, chơi thỏa thích bất kỳ lúc nào trong ngày (06h - 22h).",
        "category_id": 8,
        "main_menu_type": "PICKLE",
        "station": "BAR"
    },
    {
        "id": 306,
        "name": "Gói Social Tháng (Chỉ Buổi Sáng)",
        "price": 600000,
        "portion": "30 ngày (06h - 16h)",
        "description": "Thẻ hội viên Social tháng khung giờ sáng (06h - 16h) dành cho người yêu thích rèn luyện thể lực đầu ngày.",
        "category_id": 8,
        "main_menu_type": "PICKLE",
        "station": "BAR"
    },
    {
        "id": 307,
        "name": "Gói Social Năm (Cá Nhân)",
        "price": 5000000,
        "portion": "365 ngày cá nhân",
        "description": "Thẻ hội viên VIP cá nhân 1 năm (365 ngày). Chơi không giới hạn giờ, ưu tiên xếp sân và quyền lợi CLB.",
        "category_id": 8,
        "main_menu_type": "PICKLE",
        "station": "BAR"
    },
    {
        "id": 308,
        "name": "Đặt Sân Cố Định Tháng (Đàm Phán)",
        "price": 0,
        "portion": "Theo giá thỏa thuận",
        "description": "Đặt cố định sân và khung giờ theo tháng (ví dụ 18h-20h T2-T4-T6). Giá thỏa thuận linh hoạt.",
        "category_id": 8,
        "main_menu_type": "PICKLE",
        "station": "BAR"
    }
]

def apply_menu_bom_and_translations_fix(conn=None):
    """
    Áp dụng toàn bộ chuẩn hóa menu, định lượng, BOM, dịch vụ sân Pickleball và dịch đa ngôn ngữ.
    Hoàn toàn idempotent (chạy nhiều lần an toàn tuyệt đối).
    """
    should_close = False
    if conn is None:
        from .database import get_db
        conn = get_db()
        should_close = True

    cursor = conn.cursor()

    try:
        # 1. Sửa BOM Cải Thìa (ID 144): Đổi từ Bia Heineken sang Cải Thìa Đà Lạt (NVL18: 0.4 kg)
        cursor.execute("DELETE FROM recipe_bom WHERE menu_item_id = 144")
        cursor.execute("INSERT INTO recipe_bom (menu_item_id, ingredient_id, quantity) VALUES (144, 18, 0.4)")

        # 2. Sửa BOM Mì Xào (ID 181): NVL21 Mì vàng (2 vắt), NVL01 Tôm sú (0.05kg), NVL31 Mực ống (0.05kg)
        cursor.execute("DELETE FROM recipe_bom WHERE menu_item_id = 181")
        cursor.execute("""
            INSERT INTO recipe_bom (menu_item_id, ingredient_id, quantity)
            VALUES (181, 21, 2.0), (181, 1, 0.05), (181, 31, 0.05)
        """)

        # 3. Cập nhật portion trong menu_items
        cursor.execute("UPDATE menu_items SET portion = 'Mì 2 vắt, Bò hoặc Hải sản 100g' WHERE id = 181")
        cursor.execute("UPDATE menu_items SET portion = 'Cơm 250g, Ghẹ / Hải sản / Bò 80-100g' WHERE id = 180")

        # 4. Đảm bảo Danh mục 8: Dịch Vụ Sân Pickleball
        cursor.execute("""
            INSERT INTO categories (id, name, icon, display_order, is_active, translations_json)
            VALUES (8, 'Dịch Vụ Sân Pickleball', '🎾', 8, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                icon = excluded.icon,
                display_order = excluded.display_order,
                is_active = excluded.is_active,
                translations_json = excluded.translations_json
        """, (json.dumps(CATEGORY_TRANSLATIONS[8], ensure_ascii=False),))

        # 5. Đảm bảo các món Dịch vụ Sân Pickleball (IDs 301 - 308)
        for svc in PICKLEBALL_SERVICES:
            trans_json = json.dumps(TRANSLATIONS_DICT.get(svc["id"], {}), ensure_ascii=False)
            cursor.execute("""
                INSERT INTO menu_items (
                    id, category_id, name, price, portion, description,
                    image_url, station, options_json, translations_json,
                    is_available, out_of_ingredients, main_menu_type
                ) VALUES (?, ?, ?, ?, ?, ?, '/static/logo.png', ?, '[]', ?, 1, 0, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    price = excluded.price,
                    portion = excluded.portion,
                    description = excluded.description,
                    category_id = excluded.category_id,
                    main_menu_type = excluded.main_menu_type,
                    station = excluded.station,
                    translations_json = excluded.translations_json,
                    is_available = 1
            """, (
                svc["id"], svc["category_id"], svc["name"], svc["price"],
                svc["portion"], svc["description"], svc["station"], trans_json, svc["main_menu_type"]
            ))

        # 6. Đảm bảo cấu hình đồ uống đi kèm vé Social (mặc định 183: Nước suối)
        cursor.execute("""
            INSERT OR IGNORE INTO system_settings (key, value)
            VALUES ('pickle_social_included_drink_id', '183')
        """)

        # 7. Cập nhật bản dịch chuẩn 4 thứ tiếng cho tất cả món ăn
        for dish_id, trans in TRANSLATIONS_DICT.items():
            cursor.execute("UPDATE menu_items SET translations_json = ? WHERE id = ?", (
                json.dumps(trans, ensure_ascii=False), dish_id
            ))

        # 8. Cập nhật bản dịch 4 thứ tiếng cho tất cả danh mục
        for cat_id, trans in CATEGORY_TRANSLATIONS.items():
            cursor.execute("UPDATE categories SET translations_json = ? WHERE id = ?", (
                json.dumps(trans, ensure_ascii=False), cat_id
            ))

        conn.commit()
        print("[PiPo Menu Fixer] Da dong bo thanh cong Menu, Dinh luong, BOM, Dich vu San Pickleball va Ban dich 4 ngon ngu!")
    except Exception as e:
        print("[PiPo Menu Fixer] Loi khi dong bo menu:", e)
    finally:
        if should_close:
            conn.close()

if __name__ == "__main__":
    apply_menu_bom_and_translations_fix()
