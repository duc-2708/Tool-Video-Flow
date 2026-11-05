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

