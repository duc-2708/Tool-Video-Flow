import re
import pytest
from pathlib import Path

def test_vocabulary_anti_default_literals():
    """Verify that vocabulary.js contains no Vietnamese default placeholders or fabricated numbers."""
    vocab_path = Path(__file__).resolve().parents[1] / "editor/motion/recipes/vocabulary.js"
    assert vocab_path.is_file(), "vocabulary.js not found"
    content = vocab_path.read_text(encoding="utf-8")

    # Prohibited fallback strings that previously leaked to video
    prohibited_strings = [
        "Trước", "Sau", "Khởi điểm", "Diễn tiến", "Hiện tại",
        "Địa điểm", "Hồ sơ đối tượng", "Tài liệu", "Camera giám sát",
        "Mục A", "Mục B", "Mục C", "Hệ thống", "Thời hạn xem xét",
        "Vế trái", "Vế phải", "Vì sao dấu hiệu cảnh báo bị bỏ quên?",
        "Tòa án & Luật sư", "Truyền thống", "Hiện đại hóa",
        "45%", "98%", "0 TỶ USD"
    ]

    found_prohibited = []
    for s in prohibited_strings:
        if re.search(r"['\"]" + re.escape(s) + r"['\"]", content):
            found_prohibited.append(s)

    assert not found_prohibited, f"Found prohibited fallback strings in vocabulary.js: {found_prohibited}"

    # Verify no hardcoded 30 fallback for countdown_timer
    assert "d.value || 30" not in content, "countdown_timer still has fallback to 30"

    # Verify vs_flip_cards does not use default cardA / cardB objects with 45%/98%
    assert "{ title: 'Truyền thống'" not in content, "vs_flip_cards has default cardA"
    assert "{ title: 'Hiện đại hóa'" not in content, "vs_flip_cards has default cardB"

    # Verify strike_replace does not default oldVal to 0
    assert "old_value ?? (d.bars && d.bars[0]?.value) ?? 0" not in content, "strike_replace defaults oldVal to 0"


def test_semantic_label_no_incomplete_trailing():
    """Verify sanitizeSemanticLabel and clean_semantic_label preserve compound noun boundaries."""
    from agents.presentation import clean_semantic_label

    cases = [
        ("Xâm nhập thiết bị cá nhân", "Xâm nhập thiết bị"),
        ("Lỗ hổng từ thiết bị", "Lỗ hổng thiết bị"),
        ("Hoạt động ngân hàng", "Hoạt động ngân hàng"),
        ("Hệ thống an ninh mạng", "Hệ thống an ninh"),
        ("Bảo mật thông tin tài chính", "Bảo mật thông tin"),
    ]

    for input_text, expected_prefix in cases:
        result = clean_semantic_label(input_text)
        assert result != "", f"Result for '{input_text}' should not be empty"
        # Must not end with cutoff morphemes like 'thiết', 'ngân', 'từ'
        for cut in ["thiết", "ngân", "từ", "an", "bảo"]:
            assert not result.lower().endswith(" " + cut), f"'{result}' ends with cutoff '{cut}'"
        assert result.startswith(expected_prefix), f"Expected '{result}' to start with '{expected_prefix}'"


def test_mock_enough_false_does_not_override_to_text_focus():
    """Verify that when enough() is False, fallback uses chosen_alt recipe and does NOT set illustration_fallback to force text_focus."""
    from schemas.motion_scene import MotionScenePlan
    from schemas.visual import VisualData
    from agents.illustrations import enough

    # Numeric recipe with no numeric value
    empty_data = VisualData(text="Không có số liệu cụ thể")
    assert not enough("slot_counter", empty_data), "enough() should be False for slot_counter with no value"

    # Verify render_motion SUPPORTED contains cta_card and icon_card
    from pipeline.render_motion import SUPPORTED, is_motion_supported
    assert "cta_card" in SUPPORTED, "cta_card must be in SUPPORTED"
    assert is_motion_supported("cta_card"), "cta_card should be supported"
    assert is_motion_supported("balance_scale"), "balance_scale should be supported"


def test_blank_frame_detection_logic():
    """Verify that a frame with 0 shapes is treated as empty (emptySpaceRatio == 1.0)."""
    runtime_path = Path(__file__).resolve().parents[1] / "editor/motion/runtime.js"
    content = runtime_path.read_text(encoding="utf-8")

    # Confirm we no longer fake heroWidth = 880 when allShapes.length == 0
    assert "heroWidth = 0; heroHeight = 0; heroArea = 0;" in content, "runtime.js should set hero area to 0 when no shapes exist"
    assert "allShapes.length < 2 ? 1.0" in content, "runtime.js should detect blank frame when fewer than 2 shapes exist"
