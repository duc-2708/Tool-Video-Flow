import pytest
from pathlib import Path
from editor.motion.scheduler import (
    schedule_shots_no_repeat,
    extract_shot_brief_and_data,
    enough_for_shot,
    NUMERIC_RECIPES,
    AVAILABLE_SHOT_RECIPES,
)

def test_number_recipes_no_calendar_dates():
    # Calendar dates should NOT trigger number recipes
    brief_oct = extract_shot_brief_and_data(
        "Lỗ hổng PHP nghiêm trọng",
        "Tháng 10 năm 2026, lỗ hổng PHP nghiêm trọng công bố",
        spoken_text="Tháng 10 năm 2026, lỗ hổng PHP nghiêm trọng"
    )
    assert not brief_oct["has_number"], "Calendar date 'Tháng 10 năm 2026' must not set has_number=True"
    assert brief_oct["value"] is None
    assert brief_oct["intent"] != "number"

def test_shot_number_strict_from_spoken_text():
    # Shot with number in spoken text gets has_number=True and value=84
    brief_num = extract_shot_brief_and_data(
        "Lãnh đạo tăng ngân sách",
        "PwC báo cáo 84% lãnh đạo dự kiến tăng ngân sách",
        spoken_text="PwC báo cáo 84% lãnh đạo dự kiến tăng ngân sách"
    )
    assert brief_num["has_number"], "Spoken text with 84% must trigger has_number=True"
    assert brief_num["value"] == 84.0
    assert brief_num["unit"] == "%"
    assert brief_num["intent"] == "number"

    # Subsequent shot without number in spoken text must NOT inherit scene number
    brief_no_num = extract_shot_brief_and_data(
        "Chiến lược bảo mật",
        "PwC báo cáo 84% lãnh đạo dự kiến tăng ngân sách an ninh mạng. Chiến lược bảo mật được điều chỉnh thích ứng rủi ro.",
        spoken_text="Chiến lược bảo mật được điều chỉnh thích ứng rủi ro mới"
    )
    assert not brief_no_num["has_number"], "Shot without spoken number must not inherit scene number"
    assert brief_no_num["value"] is None
    assert brief_no_num["intent"] != "number"
    assert not enough_for_shot("slot_counter", brief_no_num)
    assert not enough_for_shot("odometer", brief_no_num)
    assert not enough_for_shot("gauge_needle", brief_no_num)

def test_scheduler_strict_max_freq_and_min_dist():
    # 20 dummy shots across diverse cybersecurity topics
    mock_shots = [
        {"card_text": f"Mục tiêu bảo mật số {i+1}", "narration": f"Chi tiết bước bảo mật số {i+1}", "duration": 3.0}
        for i in range(20)
    ]
    # Add one number shot at index 15
    mock_shots[15]["narration"] = "Khảo sát cho thấy 84% tổ chức đã tăng cường phòng thủ"
    mock_shots[15]["card_text"] = "84% tổ chức tăng phòng thủ"

    scheduled, _ = schedule_shots_no_repeat(
        mock_shots,
        min_distinct=10,
        min_dist=4,
        max_freq=2
    )
    assert len(scheduled) == 20

    from collections import Counter
    counts = Counter(s["recipe"] for s in scheduled)
    for recipe, count in counts.items():
        assert count <= 2, f"Recipe {recipe} used {count} > 2 times!"

    # Verify min distance >= 4
    for i in range(len(scheduled)):
        current_r = scheduled[i]["recipe"]
        for j in range(max(0, i - 3), i):
            assert scheduled[j]["recipe"] != current_r, f"Recipe {current_r} repeated within distance {i - j} < 4 at indices {j} and {i}!"

def test_label_not_severed_at_compound_boundary():
    # Ensure 5-6 word phrases are kept intact and not cut into broken fragments
    brief1 = extract_shot_brief_and_data(
        "Khóa cửa lỗi thiết kế",
        "Lỗ hổng phần mềm giống như khóa cửa lỗi thiết kế",
        spoken_text="giống như khóa cửa lỗi thiết kế"
    )
    assert brief1["label"] == "Khóa cửa lỗi thiết kế"

    brief2 = extract_shot_brief_and_data(
        "Lỗ hổng PHP nghiêm trọng",
        "Tháng 10 năm 2026, lỗ hổng PHP nghiêm trọng công bố",
        spoken_text="lỗ hổng PHP nghiêm trọng"
    )
    assert brief2["label"] == "Lỗ hổng PHP nghiêm trọng"

    brief3 = extract_shot_brief_and_data(
        "Hàng triệu nỗ lực khai thác",
        "Ghi nhận hàng triệu nỗ lực khai thác lỗ hổng",
        spoken_text="hàng triệu nỗ lực khai thác"
    )
    assert brief3["label"] == "Hàng triệu nỗ lực khai thác"

def test_vocabulary_card_dimensions():
    vocab_path = Path(__file__).resolve().parent.parent / "editor" / "motion" / "recipes" / "vocabulary.js"
    assert vocab_path.is_file()
    content = vocab_path.read_text(encoding="utf-8")
    
    # Check that no cardW is below 880
    import re
    card_w_matches = re.findall(r"const (?:cardW|boxW)\s*=\s*(\d+);", content)
    assert card_w_matches, "Should find cardW or boxW definitions"
    for w in card_w_matches:
        assert int(w) >= 880, f"Hero card width {w}px < 880px violation!"

    # Check that cardH is >= 680
    card_h_matches = re.findall(r"const (?:cardH|boxH)\s*=\s*(\d+);", content)
    assert card_h_matches, "Should find cardH or boxH definitions"
    for h in card_h_matches:
        assert int(h) >= 680, f"Hero card height {h}px < 680px violation!"

def test_no_empty_ghost_card_circles_in_recipes():
    recipes_js = Path(__file__).resolve().parent.parent / "editor" / "motion" / "engine" / "recipes.js"
    content = recipes_js.read_text(encoding="utf-8")
    # Verify renderTextFocus no longer draws the 2 blurry ghost circles
    assert "r: 60" not in content, "Found blurry circle r=60 in recipes.js"
    assert "r: 42" not in content, "Found blurry circle r=42 in recipes.js"
