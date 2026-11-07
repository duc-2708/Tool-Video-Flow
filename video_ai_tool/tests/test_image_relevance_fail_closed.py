"""Regression tests for fail-closed image relevance across 4+ different topics.

Verifies:
1. Fail-closed: missing or empty metadata -> False.
2. Person images (Trump, Musk, etc.) rejected unless person appears verbatim in narration.
3. Stock generic tech (chip AI, robot, laptop, keyboard) rejected unless scene is genuinely AI/chip/robot.
4. Correct topical images kept across diverse domains (underground pipeline, endoscopy surgery, tree planting, AI/chip).
"""
import pytest
from pipeline.slide_image_resolver import check_image_relevance, extract_scene_entities


def test_topic_1_underground_pipeline():
    """Topic: Underground pipeline and civil excavation."""
    text = "Thi công đường ống ngầm đô thị dưới tầng đất phức tạp đòi hỏi kỹ thuật cao."
    headline = "Đường ống ngầm đô thị"

    # Relevant image with metadata -> KEEP
    meta_good = {
        "title": "City underground pipeline excavation and installation trench",
        "tags": ["pipeline", "underground", "infrastructure"],
        "description": "Workers installing concrete water pipes below street level.",
    }
    assert check_image_relevance(text, image_metadata=meta_good, headline=headline) is True

    # Bad image: Trump -> REJECT
    meta_trump = {
        "title": "Donald Trump holding press conference at White House",
        "tags": ["donald trump", "politician", "president"],
    }
    assert check_image_relevance(text, image_metadata=meta_trump, headline=headline) is False

    # Bad image: Musk -> REJECT
    meta_musk = {
        "title": "Elon Musk speaking on stage at tech conference",
        "tags": ["elon musk", "celebrity", "portrait"],
    }
    assert check_image_relevance(text, image_metadata=meta_musk, headline=headline) is False

    # Bad image: AI chip -> REJECT
    meta_chip = {
        "title": "AI microchip processor semiconductor hardware on circuit board",
        "tags": ["ai", "chip", "semiconductor", "technology background"],
    }
    assert check_image_relevance(text, image_metadata=meta_chip, headline=headline) is False

    # Bad image: Factory robot -> REJECT
    meta_robot = {
        "title": "Industrial robotic arm automated factory manufacturing line",
        "tags": ["robot", "robotics", "automation"],
    }
    assert check_image_relevance(text, image_metadata=meta_robot, headline=headline) is False

    # Missing metadata -> REJECT (Fail-closed)
    assert check_image_relevance(text, image_metadata=None, headline=headline) is False
    assert check_image_relevance(text, image_metadata={}, headline=headline) is False
    assert check_image_relevance(text, image_metadata="", headline=headline) is False


def test_topic_2_laparoscopic_surgery():
    """Topic: Medical surgery and endoscopy."""
    text = "Bác sĩ tiến hành phẫu thuật nội soi điều trị sỏi thận bằng thiết bị chuyên dụng."
    headline = "Phẫu thuật nội soi"

    # Relevant image -> KEEP
    meta_good = {
        "title": "Surgeon performing laparoscopic surgery with endoscopy camera in clinic",
        "tags": ["endoscopy", "laparoscopy", "surgery", "medical"],
        "description": "Operating room setup for minimally invasive endoscopic procedure.",
    }
    assert check_image_relevance(text, image_metadata=meta_good, headline=headline) is True

    # Bad image: Trump -> REJECT
    meta_trump = {
        "title": "Trump addressing supporters at rally",
        "tags": ["trump", "politician"],
    }
    assert check_image_relevance(text, image_metadata=meta_trump, headline=headline) is False

    # Bad image: AI chip -> REJECT
    meta_chip = {
        "title": "Glowing futuristic AI chip semiconductor motherboard",
        "tags": ["chip", "microchip", "ai"],
    }
    assert check_image_relevance(text, image_metadata=meta_chip, headline=headline) is False

    # Bad image: Industrial robot -> REJECT
    meta_robot = {
        "title": "Factory welding robot arm assembly",
        "tags": ["robot", "industrial"],
    }
    assert check_image_relevance(text, image_metadata=meta_robot, headline=headline) is False

    # Missing metadata -> REJECT
    assert check_image_relevance(text, image_metadata=None, headline=headline) is False
    assert check_image_relevance(text, image_metadata={"title": ""}, headline=headline) is False


def test_topic_3_soil_tree_planting():
    """Topic: Urban agriculture and tree planting."""
    text = "Nông dân đào đất và trồng cây xanh phủ đồi trọc nhằm bảo vệ môi trường sinh thái."
    headline = "Đào đất trồng cây"

    # Relevant image -> KEEP
    meta_good = {
        "title": "Volunteers planting trees in rich fertile soil reforestation project",
        "tags": ["tree planting", "trees", "soil", "agriculture"],
        "description": "Young tree seedling planted in ground earth.",
    }
    assert check_image_relevance(text, image_metadata=meta_good, headline=headline) is True

    # Bad image: Musk -> REJECT
    meta_musk = {
        "title": "Elon Musk keynote speech portrait",
        "tags": ["elon musk", "speaker", "celebrity"],
    }
    assert check_image_relevance(text, image_metadata=meta_musk, headline=headline) is False

    # Bad image: AI chip -> REJECT
    meta_chip = {
        "title": "Semiconductor microchip CPU on circuit board",
        "tags": ["microchip", "circuit board", "technology background"],
    }
    assert check_image_relevance(text, image_metadata=meta_chip, headline=headline) is False

    # Bad image: Factory robot -> REJECT
    meta_robot = {
        "title": "Industrial robotic welding arm in Gigafactory",
        "tags": ["robot", "automation"],
    }
    assert check_image_relevance(text, image_metadata=meta_robot, headline=headline) is False

    # Missing metadata -> REJECT
    assert check_image_relevance(text, image_metadata=None, headline=headline) is False


def test_topic_4_semiconductor_ai_chip():
    """Topic: Semiconductor and AI microchip manufacturing."""
    text = "Nghiên cứu sản xuất vi mạch bán dẫn và chip AI phục vụ trung tâm dữ liệu thế hệ mới."
    headline = "Sản xuất chip AI"

    # Relevant image: wafer -> KEEP
    meta_wafer = {
        "title": "Cleanroom engineer holding silicon semiconductor wafer in fab",
        "tags": ["semiconductor", "wafer", "microchip"],
    }
    assert check_image_relevance(text, image_metadata=meta_wafer, headline=headline) is True

    # Relevant image: AI chip (valid because topic IS genuinely AI/chip!) -> KEEP
    meta_ai_chip = {
        "title": "AI microchip quantum neural processor hardware accelerator",
        "tags": ["ai chip", "microchip", "processor"],
    }
    assert check_image_relevance(text, image_metadata=meta_ai_chip, headline=headline) is True

    # Bad image: Trump -> REJECT
    meta_trump = {
        "title": "Donald Trump speaking in Oval Office",
        "tags": ["donald trump", "president"],
    }
    assert check_image_relevance(text, image_metadata=meta_trump, headline=headline) is False

    # Bad image: Endoscopy surgery -> REJECT (irrelevant to semiconductor)
    meta_surgery = {
        "title": "Laparoscopic endoscopy surgery in operating room",
        "tags": ["surgery", "endoscopy"],
    }
    assert check_image_relevance(text, image_metadata=meta_surgery, headline=headline) is False

    # Missing metadata -> REJECT
    assert check_image_relevance(text, image_metadata=None, headline=headline) is False


def test_person_in_narration_exception():
    """Person image is allowed ONLY if the exact person name appears verbatim in slide narration."""
    # Narration mentions Elon Musk specifically
    text_musk = "Elon Musk phát biểu về chiến lược phát triển mô hình trí tuệ nhân tạo."
    meta_musk = {
        "title": "Elon Musk keynote conference speech",
        "tags": ["elon musk", "speaker", "portrait"],
    }
    # Musk is in narration -> allowed
    assert check_image_relevance(text_musk, image_metadata=meta_musk) is True

    # Trump is NOT in narration -> rejected
    meta_trump = {
        "title": "Donald Trump press briefing",
        "tags": ["donald trump", "politician"],
    }
    assert check_image_relevance(text_musk, image_metadata=meta_trump) is False


def test_bullet_similarity_anti_duplication():
    """Requirement 5: Bullets must not overlap >= 70% with headline."""
    from editor.motion.light_glass_slots import text_similarity, create_heuristic_slide_script

    h1 = "Xử lý kỹ thuật ngầm"
    b_dup = "Xử lý kỹ thuật ngầm đô thị"
    assert text_similarity(b_dup, h1) >= 0.70

    sentences = [
        {"id": 1, "text": "Xử lý kỹ thuật địa chất phức tạp.", "start": 0.0, "end": 5.0, "duration": 5.0},
        {"id": 2, "text": "Áp dụng công nghệ tường vây hiện đại.", "start": 5.0, "end": 10.0, "duration": 5.0},
        {"id": 3, "text": "Việt Nam từng bước tự chủ hạ tầng.", "start": 10.0, "end": 15.0, "duration": 5.0},
    ]
    ss = create_heuristic_slide_script(sentences, total_duration=15.0)
    for s in ss.slides:
        if s.layout == "kit_list":
            title = s.slots.get("title", "")
            items = s.slots.get("items", [])
            for it in items:
                assert text_similarity(it, title) < 0.70


def test_prohibited_kickers_and_cut_off_headlines():
    """Requirement 5 & 6: Prohibited template kickers and cut-off headlines."""
    from schemas.slide_script import extract_clean_headline, is_incomplete_phrase

    # "Cách kỹ sư Việt" alone is an incomplete phrase -> must keep complete clause or sentence
    sent1 = "Cách kỹ sư Việt làm chủ công nghệ thi công dưới lòng đô thị"
    hl1 = extract_clean_headline(sent1)
    assert not is_incomplete_phrase(hl1)
    assert "làm chủ công nghệ" in hl1.lower() or hl1 == sent1

    # Question phrase
    sent2 = "Làm thế nào để Việt Nam tự chủ hạ tầng hoàn toàn?"
    hl2 = extract_clean_headline(sent2)
    assert not is_incomplete_phrase(hl2)
    assert hl2 != "Làm thế nào"


def test_kit_stat_grounding_and_context():
    """Requirement 7: kit_stat requires {value, unit, measurement_target} and contextual checks for 410 km / 4 km."""
    from editor.motion.light_glass_slots import extract_grounded_stat

    # 1. 1541 km
    res_1541 = extract_grounded_stat("Đường sắt tốc độ cao Bắc - Nam dài 1.541 km.")
    assert res_1541 is not None
    v, u, target = res_1541
    assert "1.541" in v or "1541" in v
    assert u.lower() == "km"
    assert "toàn tuyến" in target.lower()

    # 2. 410 km with segment context
    res_410_good = extract_grounded_stat("Đoạn ưu tiên Hà Nội - Vinh có chiều dài khoảng 410 km.")
    assert res_410_good is not None
    v, u, target = res_410_good
    assert "410" in v
    assert "đoạn ưu tiên" in target.lower() or "hà nội - vinh" in target.lower()

    # 3. 410 km missing segment context -> None
    res_410_bad = extract_grounded_stat("Tổng chiều dài tuyến lên tới 410 km.")
    assert res_410_bad is None

    # 4. 4 km with underground metro context
    res_4_good = extract_grounded_stat("Đoạn hầm ngầm metro dài 4 km qua trung tâm.")
    assert res_4_good is not None
    v, u, target = res_4_good
    assert "4" in v
    assert "hầm ngầm" in target.lower() or "đoạn" in target.lower()

    # 5. Missing measurement object -> None
    res_no_obj = extract_grounded_stat("Con số đạt được là 850.")
    assert res_no_obj is None


def test_regression_singapore_tunnel_rejects_medical_diagram_patent_book():
    """Requirement 2: Sơ đồ giải phẫu, trang sách, thiết bị y tế, patent phải bị LOẠI cho cảnh hầm/Singapore; ảnh công trường hầm/TBM thật phải được GIỮ."""
    from pipeline.slide_image_resolver import check_image_relevance, is_document_or_schematic_image
    from PIL import Image, ImageDraw

    text = "Sự cố sụt lún Singapore và bài học kinh nghiệm về địa kỹ thuật, kiểm soát lún và máy đào TBM."
    headline = "Sự cố sụt lún Singapore"

    # 1. Ảnh sơ đồ giải phẫu (anatomy / eye / skull) -> BỊ LOẠI
    meta_anatomy = {
        "title": "Human cranial nerve and eye anatomy cross section diagram",
        "tags": ["anatomy", "diagram", "medical", "eye", "failure"],
        "description": "Schematic diagram of cranial cavity and eye structure.",
    }
    assert check_image_relevance(text, image_metadata=meta_anatomy, headline=headline) is False

    # 2. Trang sách / bài báo y tế hoặc tài liệu (textbook page / document) -> BỊ LOẠI
    meta_book_page = {
        "title": "Textbook page document analysis of structural standard system failure",
        "tags": ["page", "document", "pdf", "textbook", "paper", "standard"],
        "description": "Scanned document page discussing structural engineering theories.",
    }
    assert check_image_relevance(text, image_metadata=meta_book_page, headline=headline) is False

    # 3. Minh họa thiết bị y tế (medical device / healthcare) -> BỊ LOẠI
    meta_medical_device = {
        "title": "Medical equipment and clinical monitor standard system",
        "tags": ["medical", "clinical", "standard", "system", "equipment"],
    }
    assert check_image_relevance(text, image_metadata=meta_medical_device, headline=headline) is False

    # 4. Bằng sáng chế (patent schematic) -> BỊ LOẠI
    meta_patent = {
        "title": "Patent schematic drawing for underground rotary excavation device",
        "tags": ["patent", "schematic", "drawing", "illustration"],
    }
    assert check_image_relevance(text, image_metadata=meta_patent, headline=headline) is False

    # 5. Ảnh công trường hầm / TBM thật -> ĐƯỢC GIỮ
    meta_real_tunnel = {
        "title": "Singapore Nicoll Highway metro tunnel TBM excavation site",
        "tags": ["singapore", "tbm", "tunnel", "metro", "excavation"],
        "caption": "Civil engineering construction site with massive tunnel boring machine in Singapore metro tunnel.",
    }
    assert check_image_relevance(text, image_metadata=meta_real_tunnel, headline=headline) is True

    # 6. Kiểm tra hàm đo pixel cục bộ is_document_or_schematic_image
    # Ảnh trắng > 60% với nét vẽ/chữ đen (mô phỏng trang sách / sơ đồ) -> BỊ LOẠI
    white_doc = Image.new("RGB", (400, 400), (250, 250, 250))
    draw = ImageDraw.Draw(white_doc)
    for y in range(20, 380, 15):
        draw.line([(20, y), (380, y)], fill=(10, 10, 10), width=2)
    is_doc, reason = is_document_or_schematic_image(white_doc)
    assert is_doc is True
    assert "Tài liệu/sơ đồ/trang sách" in reason

    # Ảnh chụp công trường (nền tối / phong phú màu sắc, không phải nền trắng >= 60%) -> ĐƯỢC GIỮ
    real_photo_mock = Image.new("RGB", (400, 400), (50, 60, 75))
    is_doc_photo, _ = is_document_or_schematic_image(real_photo_mock)
    assert is_doc_photo is False


def test_regression_topic_ai_chip_non_overfit():
    """Requirement 2: Thêm chủ đề AI/chip chứng minh không overfit."""
    from pipeline.slide_image_resolver import check_image_relevance

    text = "Sản xuất vi mạch bán dẫn và chip AI thế hệ mới tại các nhà máy fab hiện đại."
    headline = "Vi mạch bán dẫn và chip AI"

    # Ảnh thật: fab wafer -> GIỮ
    meta_fab = {
        "title": "Cleanroom engineer inspecting silicon semiconductor wafer in manufacturing fab",
        "tags": ["semiconductor", "wafer", "microchip", "fab"],
        "caption": "High-tech cleanroom semiconductor wafer production line.",
    }
    assert check_image_relevance(text, image_metadata=meta_fab, headline=headline) is True

    # Ảnh sai: Sơ đồ y khoa / thiết bị y tế -> LOẠI
    meta_medical = {
        "title": "Medical device clinical monitor equipment standard system",
        "tags": ["medical", "clinical", "system", "standard"],
    }
    assert check_image_relevance(text, image_metadata=meta_medical, headline=headline) is False

    # Ảnh sai: Bằng sáng chế trang sách -> LOẠI
    meta_patent_doc = {
        "title": "Patent document schematic page on integrated circuit wiring",
        "tags": ["patent", "document", "schematic", "page"],
    }
    assert check_image_relevance(text, image_metadata=meta_patent_doc, headline=headline) is False


def test_regression_topic_finance_macroeconomics_non_overfit():
    """Requirement 2: Thêm chủ đề tài chính / kinh tế vĩ mô chứng minh không overfit."""
    from pipeline.slide_image_resolver import check_image_relevance

    text = "Ngân hàng trung ương điều chỉnh chính sách lãi suất nhằm kiểm soát lạm phát và ổn định tài chính."
    headline = "Lãi suất và lạm phát"

    # Ảnh thật: sàn giao dịch / ngân hàng trung ương -> GIỮ
    meta_finance = {
        "title": "Central bank headquarters and financial market trading exchange",
        "tags": ["central bank", "financial", "interest rate", "trading", "finance"],
        "caption": "Wall street financial trading floor monitoring central bank interest rate decisions.",
    }
    assert check_image_relevance(text, image_metadata=meta_finance, headline=headline) is True

    # Ảnh sai: Robot nhà máy chung chung -> LOẠI
    meta_robot = {
        "title": "Industrial robotic welding arm in car assembly factory",
        "tags": ["robot", "robotics", "automation"],
    }
    assert check_image_relevance(text, image_metadata=meta_robot, headline=headline) is False

    # Ảnh sai: Sơ đồ giải phẫu mắt / y khoa -> LOẠI
    meta_eye = {
        "title": "Human eye anatomy and retina clinical diagram",
        "tags": ["anatomy", "eye", "diagram", "medical"],
    }
    assert check_image_relevance(text, image_metadata=meta_eye, headline=headline) is False


def test_cv_detect_faces_local():
    """Requirement 1: Kiểm tra phát hiện khuôn mặt bằng YuNet DNN không API."""
    from pipeline.slide_image_resolver import detect_faces
    from PIL import Image

    # Ảnh trơn không có người
    blank_im = Image.new("RGB", (320, 320), (40, 50, 60))
    face_count, faces = detect_faces(blank_im)
    assert face_count == 0
    assert len(faces) == 0


def test_cv_detect_text_slide_document_local():
    """Requirement 1: Kiểm tra phát hiện ảnh slide/bảng/tài liệu bằng MSER & brightness không API."""
    from pipeline.slide_image_resolver import detect_text_slide_document
    from PIL import Image, ImageDraw

    # Tạo ảnh giả lập slide tài liệu với nền sáng >= 45% và nhiều khối chữ nhỏ
    slide_im = Image.new("RGB", (600, 600), (240, 240, 245))
    draw = ImageDraw.Draw(slide_im)
    # Vẽ các dòng kẻ và khối chữ nhỏ dạng bảng số liệu / slide presentation
    for y in range(40, 560, 25):
        for x in range(30, 550, 40):
            draw.rectangle([x, y, x + 25, y + 14], fill=(20, 25, 30))

    is_text_heavy, boxes_count, reason = detect_text_slide_document(slide_im)
    assert is_text_heavy is True
    assert boxes_count >= 60
    assert "bright_bg=" in reason or "dense_mser_boxes=" in reason

    # Ảnh chụp tự nhiên không phải slide (nền tối, không có cụm chữ dày đặc)
    photo_im = Image.new("RGB", (400, 400), (30, 40, 50))
    is_text_heavy_photo, _, _ = detect_text_slide_document(photo_im)
    assert is_text_heavy_photo is False


def test_cv_detect_large_text_or_watermark():
    """Requirement 2b: Kiểm tra phát hiện ảnh có chữ lớn / watermark / poster banner bằng local CV."""
    from pipeline.slide_image_resolver import detect_large_text_or_watermark
    from PIL import Image, ImageDraw

    # 1. Ảnh giả lập có chữ lớn dạng poster (như "KISS THE GROUND") trên nền đất
    poster_im = Image.new("RGB", (800, 800), (60, 45, 30))
    draw = ImageDraw.Draw(poster_im)
    # Vẽ chữ lớn chiếm dải ngang rộng ở trung tâm
    for x in range(120, 680, 28):
        draw.rectangle([x, 360, x + 18, 440], fill=(255, 255, 255))
        draw.line([x, 400, x + 18, 400], fill=(255, 255, 255), width=4)

    has_large_txt, reason = detect_large_text_or_watermark(poster_im)
    assert has_large_txt is True
    assert "chữ lớn" in reason or "watermark" in reason or "cạnh chữ" in reason

    # 2. Ảnh công trường sạch chữ (texture đồng nhất không có chữ lớn)
    clean_im = Image.new("RGB", (800, 800), (45, 55, 65))
    has_large_clean, _ = detect_large_text_or_watermark(clean_im)
    assert has_large_clean is False


def test_generic_stock_stopwords_rejected():
    """Requirement 2a: Pixabay chỉ được dùng nếu tags/title khớp thực thể đặc trưng; loại trừ từ chung."""
    from pipeline.slide_image_resolver import check_image_relevance

    text = "Kỹ sư cân bằng áp lực đất để ổn định địa tầng khi thi công."
    headline = "Cân bằng áp lực"

    # Ảnh stock chỉ khớp từ chung: "earth", "ground", "world" -> LOẠI
    meta_generic_earth = {
        "title": "Planet Earth glowing golden world globe from space",
        "tags": ["earth", "ground", "world", "concept", "abstract"],
    }
    assert check_image_relevance(text, image_metadata=meta_generic_earth, headline=headline) is False

    meta_kiss_ground = {
        "title": "KISS the GROUND dry cracked soil agriculture texture",
        "tags": ["ground", "soil", "earth", "nature"],
    }
    assert check_image_relevance(text, image_metadata=meta_kiss_ground, headline=headline) is False

    # Ảnh khớp thực thể đặc trưng: "địa tầng", "áp lực", "strata" -> GIỮ
    meta_strata = {
        "title": "Geotechnical excavation soil strata pressure monitoring",
        "tags": ["soil mechanics", "strata", "geotechnical", "pressure"],
        "caption": "Civil engineering ground pressure balance monitoring during tunneling.",
    }
    assert check_image_relevance(text, image_metadata=meta_strata, headline=headline) is True


def test_chart_data_mixed_units_rejected_vs_valid():
    """Requirement 1: 1 biểu đồ = 1 mệnh đề. Dữ liệu trộn đơn vị -> KHÔNG ra biểu đồ."""
    from schemas.fact_number import FactNumber, select_chart_for_facts

    # 1. Dữ liệu trộn đơn vị và khác câu nguồn (USD, %, số sự cố, CAGR) -> KHÔNG ra kit_chart_bar
    mixed_facts = [
        FactNumber(
            label="Thiệt hại sự cố",
            value=83.2,
            unit="tỷ USD",
            source_sentence="Thiệt hại tại Mỹ qua 669.000 sự cố tiêu tốn 83,2 tỷ USD.",
        ),
        FactNumber(
            label="Vốn tư nhân",
            value=82.0,
            unit="%",
            source_sentence="Tổng mức đầu tư các dự án lớn, vốn tư nhân chiếm hơn 82%.",
        ),
        FactNumber(
            label="Tốc độ tăng trưởng",
            value=12.88,
            unit="%",
            source_sentence="Thị trường robot đạt tốc độ CAGR 12.88% trong giai đoạn tới.",
        ),
    ]
    res_mixed = select_chart_for_facts(mixed_facts)
    # Không được sinh kit_chart_bar hoặc chart nhiều cột trộn các câu
    assert res_mixed is not None
    assert res_mixed.get("layout") in ("kit_stat", None)
    assert res_mixed.get("layout") != "kit_chart_bar"

    # 2. Dữ liệu đúng: Cùng một câu mệnh đề, cùng đơn vị %, có nhãn cụ thể -> ra biểu đồ có nhãn
    valid_facts = [
        FactNumber(
            label="Đô thị lớn",
            value=65.0,
            unit="%",
            source_sentence="Cơ cấu hạ tầng phân bổ gồm 65% ở đô thị lớn và 35% tại khu vực vệ tinh.",
        ),
        FactNumber(
            label="Khu vực vệ tinh",
            value=35.0,
            unit="%",
            source_sentence="Cơ cấu hạ tầng phân bổ gồm 65% ở đô thị lớn và 35% tại khu vực vệ tinh.",
        ),
    ]
    res_valid = select_chart_for_facts(valid_facts)
    assert res_valid is not None
    assert res_valid.get("layout") in ("kit_chart_donut", "kit_chart_bar")
    assert len(res_valid.get("series", [])) == 2
    assert res_valid.get("series")[0]["label"] == "Đô thị lớn"


def test_metaphor_and_dangling_headline_regression():
    """Requirement 4: Kiểm tra loại bỏ ví von và sửa tiêu đề lửng/cụt."""
    from editor.motion.light_glass_slots import contains_metaphor, _sanitize_metaphor
    from schemas.slide_script import extract_clean_headline

    # 1. Test trực tiếp lên chính chuỗi ví von bác sĩ phẫu thuật
    s_metaphor = "Thi công ngầm giống như bác sĩ phẫu thuật nội soi qua vết rạch nhỏ."
    assert contains_metaphor(s_metaphor) is True
    sanitized = _sanitize_metaphor(s_metaphor)
    assert contains_metaphor(sanitized) is False
    assert "bác sĩ" not in sanitized.lower()

    s_metaphor_short = "Thi công ngầm giống như bác sĩ phẫu"
    assert contains_metaphor(s_metaphor_short) is True
    sanitized_short = _sanitize_metaphor(s_metaphor_short)
    assert contains_metaphor(sanitized_short) is False

    # 2. Test câu số 83,2 tỷ USD không bị cắt cụt ở dấu phẩy decimal
    s_num = "Hạ tầng ngầm bị chôn lấp từng tiêu tốn 83,2 tỷ USD tại Mỹ qua gần 669.000 sự cố, với gần 90 phần trăm xảy ra ở khu vực đô thị."
    h_num = extract_clean_headline(s_num)
    assert "tiêu tốn 83" not in h_num or "83,2" in h_num
    assert not h_num.endswith(" 83")
    assert "83,2 tỷ USD" in h_num

    # 3. Test tiêu đề bắt đầu bằng từ chỉ thị lửng được viết lại thành chủ ngữ cụ thể
    s_dem = "Con số này cho thấy sai sót kỹ thuật gây ra cái giá quá đắt."
    h_dem = extract_clean_headline(s_dem)
    assert not h_dem.lower().startswith("con số này")
    assert "sai sót kỹ thuật" in h_dem.lower()



