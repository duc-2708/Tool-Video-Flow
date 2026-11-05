"""Regression tests for Web Pipeline Slide Planner, Kit v2 pacing, and grounding audits."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from config.settings import get_settings
from editor.motion.light_glass_slots import create_heuristic_slide_script
from schemas.slide_script import SlideScript, SlideItem
from tools.audit_style import audit_light_glass_project
from validation.grounding import extract_numbers, normalize_number, numbers_match


def test_normalized_number_mismatch_detected():
    """Verify that 704 does not match 'tám trăm tấn' (800) and grounding comparison flags it."""
    n1 = normalize_number("704")
    spoken_nums = extract_numbers("Máy đào hầm nặng khoảng tám trăm tấn chuẩn bị khoan.")
    assert n1 is not None
    assert len(spoken_nums) > 0
    assert spoken_nums[0].effective_value == 800
    matched = any(numbers_match(n1, sn) for sn in spoken_nums)
    assert not matched, "704 must not match 800 ('tám trăm tấn')"


def test_audit_fails_on_number_mismatch(tmp_path: Path):
    """Audit must fail when screen number doesn't match spoken narration number."""
    brief_data = {
        "topic": "Công nghệ hầm đô thị",
        "facts": [
            {"id": 1, "claim": "Máy đào TBM nặng tám trăm tấn.", "evidence_quote": "tám trăm tấn", "source_name": "Báo Xây Dựng", "source_url": "https://baoxaydung.vn", "published_at": "2026-05-10"}
        ]
    }
    (tmp_path / "brief.json").write_text(json.dumps(brief_data, ensure_ascii=False), encoding="utf-8")

    slides = [
        {
            "id": "slide_1",
            "layout": "kit_title",
            "slots": {"title": "CÔNG NGHỆ MỚI", "subtitle": "Máy đào ngầm"},
            "narration": "Công nghệ máy đào ngầm.",
            "duration": 5.0,
            "t_start": 0.0,
            "t_end": 5.0,
        },
        {
            "id": "slide_2",
            "layout": "kit_stat",
            "slots": {"value": 704, "unit": "tấn", "label": "Khối lượng TBM"},
            # Narration says "tám trăm tấn" (800) which mismatches 704
            "narration": "Máy đào hầm nặng khoảng tám trăm tấn chuẩn bị vận hành.",
            "duration": 5.0,
            "t_start": 5.0,
            "t_end": 10.0,
        },
        {
            "id": "slide_3",
            "layout": "kit_outro",
            "slots": {"channel_name": "Kênh Kỹ Thuật", "source": "baoxaydung.vn"},
            "narration": "Cảm ơn bạn đã xem tin.",
            "duration": 5.0,
            "t_start": 10.0,
            "t_end": 15.0,
        }
    ]
    ss = {"topic": "Công nghệ", "total_duration": 15.0, "slides": slides}
    (tmp_path / "slide_script.json").write_text(json.dumps(ss, ensure_ascii=False), encoding="utf-8")

    audit = audit_light_glass_project(tmp_path)
    assert not audit["passed"]
    assert any("không cùng giá trị chuẩn hóa" in v for v in audit["violations"])


def test_audit_fails_on_empty_scenes(tmp_path: Path):
    """Audit must fail when a scene has < 2 text elements or an empty card."""
    brief_data = {
        "topic": "Kiểm tra rỗng",
        "facts": [
            {"id": 1, "claim": "Nội dung kiểm tra.", "evidence_quote": "Nội dung", "source_name": "Báo X", "source_url": "https://baox.vn", "published_at": "2026-05-10"}
        ]
    }
    (tmp_path / "brief.json").write_text(json.dumps(brief_data, ensure_ascii=False), encoding="utf-8")

    slides = [
        {
            "id": "slide_1",
            "layout": "kit_title",
            # Only 1 text element
            "slots": {"title": "Chỉ Một Tiêu Đề"},
            "narration": "Chỉ có một tiêu đề duy nhất.",
            "duration": 5.0,
            "t_start": 0.0,
            "t_end": 5.0,
        },
        {
            "id": "slide_2",
            "layout": "kit_outro",
            "slots": {},  # completely empty card
            "narration": "Kết thúc.",
            "duration": 5.0,
            "t_start": 5.0,
            "t_end": 10.0,
        }
    ]
    ss = {"topic": "Kiểm tra", "total_duration": 10.0, "slides": slides}
    (tmp_path / "slide_script.json").write_text(json.dumps(ss, ensure_ascii=False), encoding="utf-8")

    audit = audit_light_glass_project(tmp_path)
    assert not audit["passed"]
    assert any("rỗng" in v for v in audit["violations"])


def test_slide_planner_60s_fixture_produces_10_to_14_scenes():
    """Slide planner on a 60s script must produce 10-14 slides, each 4.0-6.5s, none < 3s."""
    # 12 sentences, total duration 60.0s
    sentences = []
    t = 0.0
    for i in range(12):
        dur = 5.0
        sentences.append({
            "id": i + 1,
            "text": f"Đây là câu tường thuật chi tiết số {i + 1} của kịch bản bản tin công nghệ hạ tầng đô thị hiện đại.",
            "start": round(t, 2),
            "end": round(t + dur, 2),
            "duration": dur,
        })
        t += dur

    ss = create_heuristic_slide_script(sentences, total_duration=60.0)
    slides = ss.slides

    assert 10 <= len(slides) <= 14, f"Expected 10-14 slides for 60s video, got {len(slides)}"
    for idx, sl in enumerate(slides):
        assert 4.0 <= sl.duration <= 6.5, f"Slide {idx} duration {sl.duration}s outside [4.0, 6.5]s"
        assert sl.duration >= 3.0, f"Slide {idx} duration {sl.duration}s is < 3.0s"


def test_kit_outro_no_fake_button_no_hardcoded_brand():
    """Verify that kit_outro generates no fake 'Theo Dõi' button and no fallback brand 'TIN CÔNG NGHỆ'."""
    sentences = [
        {"id": 1, "text": "Mở đầu.", "start": 0.0, "end": 5.0, "duration": 5.0},
        {"id": 2, "text": "Nội dung.", "start": 5.0, "end": 10.0, "duration": 5.0},
        {"id": 3, "text": "Chi tiết.", "start": 10.0, "end": 15.0, "duration": 5.0},
        {"id": 4, "text": "Kết thúc theo dõi.", "start": 15.0, "end": 20.0, "duration": 5.0},
    ]
    ss = create_heuristic_slide_script(sentences, total_duration=20.0, brand_name="")
    outro = ss.slides[-1]
    assert outro.layout == "kit_outro"
    assert "button_text" not in outro.slots, "Fake button_text must not exist"
    assert outro.slots.get("channel_name", "") != "TIN CÔNG NGHỆ", "Hardcoded brand must not exist"
    assert "Theo dõi kênh để đón xem" not in str(outro.slots.get("call_to_action", ""))
