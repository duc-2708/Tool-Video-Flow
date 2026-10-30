"""Test suite for Recipe Diversity, Transitions, Persistent Anchors, Depth and Factual Formatting."""
import pytest
from editor.format_number import parse_display_number, NumberKind
from editor.motion.scheduler import (
    schedule_shots_no_repeat,
    AVAILABLE_SHOT_RECIPES,
    build_shot_factual_data,
    validate_recipe_fit,
    TRANSITION_TYPES,
)


def test_format_number_currency_vs_count_units():
    """A1: format_number does not default to VND without currency keywords."""
    p_count1 = parse_display_number("Ashley Paul Griffith đối mặt với 202 tội danh lạm dụng trẻ em")
    assert p_count1 is not None
    assert p_count1.value == 202
    assert p_count1.currency == ""
    assert p_count1.unit_display == ""
    assert p_count1.kind == NumberKind.COUNT

    p_count2 = parse_display_number("hơn 200 cáo buộc tại tòa")
    assert p_count2 is not None
    assert p_count2.value == 200
    assert p_count2.currency == ""

    p_money = parse_display_number("đầu tư 5 tỷ đồng vào dự án công nghệ")
    assert p_money is not None
    assert p_money.value == 5.0
    assert p_money.full_numeric_value == 5_000_000_000
    assert p_money.kind == NumberKind.MONEY
    assert p_money.currency == "VND"

    p_percent = parse_display_number("tỷ lệ hoàn thành đạt 85%")
    assert p_percent is not None
    assert p_percent.value == 85
    assert p_percent.kind == NumberKind.PERCENT

    p_time = parse_display_number("thời hạn điều tra kéo dài 3 tháng")
    assert p_time is not None
    assert p_time.value == 3
    assert p_time.kind == NumberKind.TIME


def test_12_new_recipes_available():
    """A3: All 12 newly added recipes exist in AVAILABLE_SHOT_RECIPES."""
    expected_12 = [
        "before_after_split", "timeline_milestones", "map_location_pin",
        "profile_dossier", "document_page_flip", "camera_surveillance_scan",
        "evidence_board", "network_graph", "countdown_timer",
        "courtroom_balance", "code_terminal_window", "quote_dialog_card"
    ]
    for r in expected_12:
        assert r in AVAILABLE_SHOT_RECIPES, f"Recipe {r} missing from AVAILABLE_SHOT_RECIPES"


def test_schedule_shots_diversity_and_anti_repetition():
    """A2 & A3: Scheduler achieves >= 10 distinct recipes, max_freq <= 2, min_dist >= 4."""
    # Create 14 simulated shots covering a 60s news story
    sentences = [
        "Ashley Paul Griffith đối mặt với hơn 200 cáo buộc tại New South Wales",
        "Tòa án tại Brisbane quyết định hoãn phiên xét xử sau các phiên tranh tụng căng thẳng",
        "Hồ sơ vụ án ghi nhận các hành vi phạm tội kéo dài suốt nhiều năm",
        "Các cơ quan điều tra mở rộng việc quét dữ liệu và giám sát",
        "Bảng chứng cứ liên kết nhiều nạn nhân trên toàn nước Úc",
        "Mạng lưới liên kết giữa các trung tâm chăm sóc trẻ em được rà soát",
        "Thời hạn tạm giam bị cáo được gia hạn thêm 10 ngày đếm ngược",
        "Hệ thống cơ sở dữ liệu xác minh các tài liệu số",
        "Một nhân chứng khẳng định rằng hành vi này không thể dung thứ",
        "Trước đây các dấu hiệu bị bỏ qua, nay cơ quan chức năng vào cuộc gắt gao",
        "Cán cân pháp lý đang nghiêng về phía bảo vệ nạn nhân",
        "Chuỗi các mốc thời gian từ 2007 đến nay được vạch rõ",
        "Tổng hợp các điểm then chốt cần ghi nhớ trong vụ án",
        "Phiên tòa tiếp theo sẽ mở lại sau khi hoàn tất thủ tục",
    ]

    shots_data = [
        {"narration": sent, "text": sent, "duration": 4.5, "shot_id": i + 1}
        for i, sent in enumerate(sentences)
    ]

    scheduled, notes = schedule_shots_no_repeat(
        shots_data,
        min_distinct=10,
        min_dist=4,
        max_freq=2
    )

    assert len(scheduled) == len(shots_data)
    recipes = [s["recipe"] for s in scheduled]
    distinct_recipes = set(recipes)

    # 1. Video has >= 10 distinct recipes
    assert len(distinct_recipes) >= 10, f"Expected >= 10 distinct recipes, got {len(distinct_recipes)}: {distinct_recipes}"

    # 2. Max frequency per recipe <= 2
    from collections import Counter
    counts = Counter(recipes)
    for r, count in counts.items():
        assert count <= 2, f"Recipe {r} appeared {count} times (max allowed 2)"

    # 3. Min distance check (no repeat in 4 consecutive shots)
    for i in range(len(recipes)):
        for j in range(i + 1, min(len(recipes), i + 4)):
            assert recipes[i] != recipes[j], f"Recipe {recipes[i]} repeated at index {i} and {j} (distance {j - i} < 4)"

    # 4. recipe_fit metadata present and grounded
    for sh in scheduled:
        assert "recipe_fit" in sh
        assert "recipe" in sh["recipe_fit"]
        assert "reason" in sh["recipe_fit"]
        assert len(sh["recipe_fit"]["reason"]) > 10


def test_transitions_and_persistent_anchors():
    """B1 & B2: Transitions from 5 styles without consecutive repeats, persistent anchor present."""
    shots_data = [
        {"narration": f"Câu chuyện thứ {i+1} với diễn biến mới", "text": f"Nội dung {i+1}", "duration": 4.0}
        for i in range(8)
    ]
    scheduled, _ = schedule_shots_no_repeat(shots_data, min_distinct=6, min_dist=2, max_freq=2)

    transitions = [s["transition"] for s in scheduled]
    # Check that all transitions are valid
    for t in transitions:
        assert t in TRANSITION_TYPES, f"Unknown transition type: {t}"

    # No two consecutive shots have identical transition
    for i in range(len(transitions) - 1):
        assert transitions[i] != transitions[i + 1], f"Duplicate consecutive transition {transitions[i]} at index {i}"

    # Persistent anchor present on all shots
    for sh in scheduled:
        assert "anchor" in sh
        assert "anchor_element" in sh["anchor"]
        assert "metaphor_name" in sh["anchor"]


def test_no_forbidden_ungrounded_labels_manufactured():
    """A2: Labels forbidden from manufactured ungrounded generation."""
    brief_info = {
        "label": "Tội danh",
        "has_number": False,
        "value": None,
        "unit": "",
        "number_text": "",
        "intent": "legal",
    }
    raw_text = "Ashley Paul Griffith đối mặt với các cáo buộc lạm dụng"
    data = build_shot_factual_data("balance_scale", brief_info, raw_text, raw_text)

    # Validate that data does not contain manufactured labels
    forbidden = ["BẢO VỆ", "ĐANG KHÓA CHẶT", "MAX", "DẤU HIỆU BẮT", "Dấu hiệu bỏ qua"]
    for forb in forbidden:
        for val in data.values():
            if isinstance(val, str):
                assert forb.lower() not in val.lower()
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        assert forb.lower() not in item.lower()
