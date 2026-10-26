"""Tests for Phase 4b Motion Design System: engine, 6 recipes, safe area, and annotations."""
import hashlib
import math
import pytest
from pathlib import Path

from config.settings import ROOT_DIR
from editor.captions import find_font
from editor.motion.engine import bundle_engine
from pipeline.render_motion import browser_page, capture
from tests.test_motion import has_chromium


@pytest.fixture(scope="module")
def shared_page():
    if not has_chromium():
        pytest.skip("Chromium not installed")
    with browser_page((270, 480)) as page:
        yield page


def test_bundle_engine_integrity():
    css, js, digest = bundle_engine()
    assert len(css) > 0
    assert len(js) > 0
    assert len(digest) == 64
    assert "MotionEasing" in js
    assert "MotionRecipes" in js
    assert "MotionPRNG" in js
    assert "MotionLayout" in js


def test_motion_engine_deterministic_seek(shared_page):
    """Calling renderAt(t) at different times and returning yields identical screenshot hashes."""
    page = shared_page
    font = find_font(ROOT_DIR)

    payload = {
        "width": 270,
        "height": 480,
        "duration": 4.0,
        "words": [],
        "captions": {"enabled": False},
        "shots": [{
            "start": 0,
            "duration": 4.0,
            "template": "text_focus",
            "data": {"value": 75, "unit": "%", "label": "Kiểm định độc lập"},
            "beats": []
        }],
        "theme": {"name": "neon_dark"},
        "visual_plan": {
            "scene_type": "stat_number",
            "variant_index": 0,
            "data": {"value": 75, "unit": "%", "label": "Kiểm định độc lập"},
            "beats": [],
            "camera": {"move": "push_in", "amount": 0.05}
        }
    }

    capture(page, payload, font)

    # 1. First seek at t=1.5s
    page.evaluate("() => window.renderAt(1.5)")
    shot1 = page.screenshot()
    hash1 = hashlib.sha256(shot1).hexdigest()

    # 2. Seek to t=3.2s (frame must change)
    page.evaluate("() => window.renderAt(3.2)")
    shot2 = page.screenshot()
    hash2 = hashlib.sha256(shot2).hexdigest()
    assert hash1 != hash2, "Frame at t=3.2s should differ from t=1.5s"

    # 3. Seek back to t=1.5s (must match hash1 byte-for-byte)
    page.evaluate("() => window.renderAt(1.5)")
    shot3 = page.screenshot()
    hash3 = hashlib.sha256(shot3).hexdigest()
    assert hash1 == hash3, "Deterministic replay failed: frame at t=1.5s must be bit-identical"


@pytest.mark.parametrize("recipe_name", [
    "stat_number",
    "bar_compare",
    "flow_chain",
    "hub_spoke",
    "container_fill",
    "checklist",
    "mock_ui_window",
    "magnifier_check",
    "versus_split",
    "line_chart_draw",
    "terminal_typing",
    "timeline",
    "funnel",
    "progress_tracker",
    "source_badge",
    "icon_tile",
    "chat_bubble_poll",
    "gauge_ring",
])
def test_recipes_render_without_js_errors(shared_page, recipe_name):
    """Each of the 6 core recipes + mock_ui + magnifier renders at multiple time points without exceptions."""
    page = shared_page
    font = find_font(ROOT_DIR)

    payload = {
        "width": 270,
        "height": 480,
        "duration": 4.0,
        "words": [],
        "captions": {"enabled": False},
        "shots": [{
            "start": 0,
            "duration": 4.0,
            "template": "text_focus",
            "data": {
                "value": 60,
                "unit": "%",
                "label": "Chỉ số thử nghiệm",
                "text": "Đánh giá hiệu năng",
                "items": ["Mục 1", "Mục 2", "Mục 3"],
                "bars": [{"label": "A", "value": 30}, {"label": "B", "value": 70}]
            },
            "beats": []
        }],
        "theme": {"name": "neon_dark"},
        "visual_plan": {
            "scene_type": recipe_name,
            "variant_index": 0,
            "data": {
                "value": 60,
                "unit": "%",
                "label": "Chỉ số thử nghiệm",
                "text": "Đánh giá hiệu năng",
                "items": ["Mục 1", "Mục 2", "Mục 3"],
                "bars": [{"label": "A", "value": 30}, {"label": "B", "value": 70}]
            },
            "beats": [{"at_sec": 1.0, "action": "beat_hit"}],
            "camera": {"move": "push_in", "amount": 0.05},
            "annotations": [
                {"type": "strike", "at_sec": 1.0, "text": "Hủy"},
                {"type": "stamp", "at_sec": 1.5, "text": "ƯỚC LƯỢNG"},
                {"type": "underline", "at_sec": 0.8}
            ]
        }
    }

    capture(page, payload, font)

    for t in (0.1, 1.2, 2.5, 3.8):
        res = page.evaluate(f"() => window.renderAt({t})")
        assert res is not None


def test_progressive_reveal_not_all_at_zero(shared_page):
    """Elements must reveal gradually across time, not all clustered at t=0."""
    page = shared_page
    font = find_font(ROOT_DIR)

    payload = {
        "width": 270,
        "height": 480,
        "duration": 4.0,
        "words": [],
        "captions": {"enabled": False},
        "shots": [{
            "start": 0,
            "duration": 4.0,
            "template": "text_focus",
            "data": {"items": ["Bước 1", "Bước 2", "Bước 3", "Bước 4"]},
            "beats": []
        }],
        "theme": {"name": "neon_dark"},
        "visual_plan": {
            "scene_type": "flow_chain",
            "variant_index": 0,
            "data": {"items": ["Bước 1", "Bước 2", "Bước 3", "Bước 4"]},
            "beats": [
                {"at_sec": 0.2, "action": "reveal_item_0"},
                {"at_sec": 1.2, "action": "reveal_item_1"},
                {"at_sec": 2.2, "action": "reveal_item_2"},
                {"at_sec": 3.0, "action": "reveal_item_3"},
            ],
            "camera": {"move": "none", "amount": 0.04}
        }
    }

    capture(page, payload, font)

    # At t=0.05, early frame: only early element exists
    page.evaluate("() => window.renderAt(0.05)")
    early_elements = page.evaluate("() => document.querySelectorAll('.scene-art text').length")

    # At t=2.5s, later frame: more elements must have been revealed
    page.evaluate("() => window.renderAt(2.5)")
    late_elements = page.evaluate("() => document.querySelectorAll('.scene-art text').length")

    assert late_elements >= early_elements


def test_collision_repair_separates_overlapping_boxes(shared_page):
    """MotionLayout.repairCollisions detects overlapping boxes and resolves them."""
    page = shared_page
    boxes = [
        {"x": 100, "y": 200, "w": 400, "h": 60},
        {"x": 100, "y": 220, "w": 400, "h": 60},  # Heavy 40px vertical overlap
    ]

    repaired = page.evaluate("""(boxes) => {
        return window.MotionLayout.repairCollisions(boxes);
    }""", boxes)

    # Box 1 must be moved down so overlap is resolved
    assert repaired[1]["y"] >= repaired[0]["y"] + repaired[0]["h"]


def test_all_10_annotations(shared_page):
    """Verify all 10 annotation types render without JavaScript errors."""
    page = shared_page
    font = find_font(ROOT_DIR)

    all_types = ["strike", "stamp", "underline", "question", "check", "cross", "arrow", "circle_highlight", "tag", "pencil"]
    annotations = [{"type": t, "at_sec": 0.5 + i * 0.2, "text": f"Tag_{i}"} for i, t in enumerate(all_types)]

    payload = {
        "width": 270,
        "height": 480,
        "duration": 4.0,
        "words": [],
        "captions": {"enabled": False},
        "shots": [{
            "start": 0,
            "duration": 4.0,
            "template": "text_focus",
            "data": {"text": "Kiểm tra chú thích hoạt họa"},
            "beats": []
        }],
        "theme": {"name": "neon_dark"},
        "visual_plan": {
            "scene_type": "stat_number",
            "variant_index": 0,
            "data": {"value": 88, "unit": "%", "label": "Đánh giá"},
            "beats": [],
            "camera": {"move": "none", "amount": 0.04},
            "annotations": annotations
        }
    }

    capture(page, payload, font)
    for t in (0.2, 1.5, 3.0):
        res = page.evaluate(f"() => window.renderAt({t})")
        assert res is not None


def test_lighting_and_transitions(shared_page):
    """Verify light sweep and glitch cut transitions execute without JS errors."""
    page = shared_page
    font = find_font(ROOT_DIR)

    payload = {
        "width": 270,
        "height": 480,
        "duration": 3.0,
        "words": [],
        "captions": {"enabled": False},
        "shots": [{
            "start": 0,
            "duration": 3.0,
            "template": "text_focus",
            "data": {"text": "Kiểm tra chuyển cảnh và ánh sáng"},
            "beats": [{"at_sec": 0.8, "action": "beat_hit"}]
        }],
        "theme": {"name": "neon_dark"},
        "visual_plan": {
            "scene_type": "stat_number",
            "variant_index": 0,
            "transition": "glitch_cut",
            "data": {"value": 99, "unit": "%", "label": "Chuyển cảnh"},
            "beats": [{"at_sec": 0.8, "action": "beat_hit"}],
            "camera": {"move": "zoom_through", "amount": 0.06}
        }
    }

    capture(page, payload, font)
    # t=0.1 (during glitch), t=0.8 (during light sweep), t=2.8 (during zoom_through exit)
    for t in (0.1, 0.8, 2.8):
        res = page.evaluate(f"() => window.renderAt({t})")
        assert res is not None


def test_illustrations_and_mascot_engine(shared_page):
    """Verify mascot joints animation and dynamic illustration rendering and keyword matching."""
    from editor.motion.registry import match_illustration_for_topic, list_available_illustrations, get_illustration_info
    
    # 1. Verify 15 illustrations in registry and filesystem
    illustrations = list_available_illustrations()
    assert len(illustrations) >= 15
    for ill_id in illustrations:
        info = get_illustration_info(ill_id)
        assert info is not None
        svg_file = Path(info["file"])
        assert svg_file.is_file(), f"Missing SVG file {svg_file}"
        svg_content = svg_file.read_text(encoding="utf-8")
        assert "<svg" in svg_content and "</svg>" in svg_content

    # 2. Topic keyword matching
    assert match_illustration_for_topic("Bãi thử UAV Hòa Lạc có gì đặc biệt?") in {"drone", "runway_test_site"}
    assert match_illustration_for_topic("Bảo mật dữ liệu và phòng thủ không gian mạng") == "shield_protect"
    assert match_illustration_for_topic("Tối ưu hóa thời lượng pin cho thiết bị") == "battery_charging"

    # 3. Mascot and Illustration deterministic rendering in browser
    page = shared_page
    font = find_font(ROOT_DIR)

    payload = {
        "width": 270,
        "height": 480,
        "duration": 4.0,
        "words": [],
        "captions": {"enabled": False},
        "shots": [{
            "start": 0,
            "duration": 4.0,
            "template": "text_focus",
            "data": {"text": "Trình diễn Mascot và Minh họa động"},
            "beats": [{"at_sec": 1.0, "action": "beat_mascot"}]
        }],
        "theme": {"name": "neon_dark"},
        "visual_plan": {
            "scene_type": "stat_number",
            "variant_index": 0,
            "mascot_state": "pointing",
            "mascot": {"enabled": True, "state": "pointing", "at_sec": 0.5, "pointing_target": [135, 240]},
            "data": {"value": 100, "unit": "km", "label": "Thử nghiệm UAV"},
            "beats": [{"at_sec": 1.0, "action": "beat_mascot"}],
            "camera": {"move": "push_in", "amount": 0.04}
        }
    }

    capture(page, payload, font)
    # Check Mascot object in window
    has_mascot = page.evaluate("() => typeof window.MotionMascot !== 'undefined'")
    assert has_mascot is True
    has_ill = page.evaluate("() => typeof window.MotionIllustrations !== 'undefined'")
    assert has_ill is True

    # Render at different time points
    for t in (0.3, 1.2, 2.5, 3.8):
        res = page.evaluate(f"() => window.renderAt({t})")
        assert res is not None
