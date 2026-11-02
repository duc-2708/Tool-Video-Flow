"""Tests for Automated Quality and Style Auditor."""
import json
from pathlib import Path

from schemas.slide_script import SlideScript, SlideItem, EmphasisItem
from tools.audit_style import audit_light_glass_project


def test_audit_passing_scenario(tmp_path):
    # Create 5 valid slides with 4 distinct layouts and grounded data
    slides = [
        SlideItem(
            id="slide_1",
            layout="lg_source_headline",
            sentence_ids=[1],
            slots={"title": "Đột phá AI 2026", "pill": "TIN NÓNG", "text": "Việt Nam công bố chiến lược AI."},
            emphasis=[EmphasisItem(phrase="chiến lược AI", kind="term")],
            duration=5.5,
            narration="Việt Nam công bố chiến lược AI với mục tiêu phát triển.",
        ),
        SlideItem(
            id="slide_2",
            layout="lg_stat_hero",
            sentence_ids=[2],
            slots={"value": 35, "unit": "%", "label": "Tăng trưởng"},
            emphasis=[EmphasisItem(phrase="35%", kind="number")],
            duration=5.8,
            narration="Dự kiến tốc độ tăng trưởng đạt 35% trong năm nay.",
        ),
        SlideItem(
            id="slide_3",
            layout="lg_shot_features",
            sentence_ids=[3],
            slots={"title": "Tính năng", "items": ["Điểm nổi bật 1", "Điểm nổi bật 2"]},
            duration=5.2,
            narration="Hệ thống mang lại nhiều tính năng nổi bật cho người dùng.",
        ),
        SlideItem(
            id="slide_4",
            layout="lg_vs_compare",
            sentence_ids=[4],
            slots={"left": {"label": "CŨ", "text": "Hệ thống cũ"}, "right": {"label": "MỚI", "text": "Hệ thống mới"}},
            duration=5.5,
            narration="So sánh hiệu năng giữa hệ thống mới và hệ thống cũ.",
        ),
        SlideItem(
            id="slide_5",
            layout="lg_cta_profile",
            sentence_ids=[5],
            slots={"channel_name": "TIN CÔNG NGHỆ", "pill": "ĐĂNG KÝ NGAY"},
            duration=5.0,
            narration="Hãy đăng ký kênh để đón xem video mới nhất.",
        ),
    ]
    script = SlideScript(topic="AI 2026", total_duration=27.0, slides=slides)

    # Project directory with brief and edit_plan containing the facts
    brief = {
        "topic": "AI 2026",
        "facts": [{"claim": "Tăng trưởng 35%", "source_name": "VnExpress", "source_url": "https://vnexpress.net"}]
    }
    (tmp_path / "brief.json").write_text(json.dumps(brief), encoding="utf-8")
    (tmp_path / "slide_script.json").write_text(json.dumps(script.model_dump(mode="json")), encoding="utf-8")

    res = audit_light_glass_project(tmp_path, slide_script=script)
    assert res["passed"] is True
    assert res["total_score"] >= 90
    assert len(res["violations"]) == 0
    assert (tmp_path / "audit_style.json").is_file()


def test_audit_failing_scenario_leaked_debug_and_fabrication(tmp_path):
    # Failing script:
    # 1. Leaked debug string 'undefined'
    # 2. Fabricated number 9999%
    # 3. Only 2 slides (violates [5, 10])
    # 4. Consecutive duplicate layouts
    slides = [
        SlideItem(
            id="slide_1",
            layout="lg_source_headline",
            sentence_ids=[1],
            slots={"title": "Tiêu đề undefined bị lỗi"},
            duration=2.0,  # too short (< 4.0s)
            narration="Tiêu đề có chữ lạ.",
        ),
        SlideItem(
            id="slide_2",
            layout="lg_source_headline",  # duplicated adjacent layout!
            sentence_ids=[2],
            slots={"value": 9999, "unit": "%"},  # ungrounded number!
            duration=12.0,  # too long (> 9.0s)
            narration="Nội dung không hề có số 9999.",
        ),
    ]
    script = SlideScript(topic="Test Fail", total_duration=14.0, slides=slides)

    (tmp_path / "slide_script.json").write_text(json.dumps(script.model_dump(mode="json")), encoding="utf-8")

    res = audit_light_glass_project(tmp_path, slide_script=script)
    assert res["passed"] is False
    assert res["total_score"] < 90
    assert len(res["violations"]) >= 3
    # Check specific violations caught
    viol_str = " ".join(res["violations"])
    assert "undefined" in viol_str
    assert "Slide count 2 outside [5, 10]" in viol_str
