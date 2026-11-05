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


def test_audit_video_with_two_seconds_blank_fails(tmp_path, monkeypatch):
    """Video with >= 2.0 seconds of blank frames must strictly FAIL the audit."""
    import numpy as np
    from tools import audit_style

    # Create 5 valid slides
    slides = [
        SlideItem(
            id=f"slide_{i}",
            layout=["kit_title", "kit_list", "kit_quote", "kit_stat", "kit_outro"][i],
            sentence_ids=[i + 1],
            slots={"headline": f"Tiêu đề {i}", "value": 100, "unit": "%"} if i == 3 else {"headline": f"Tiêu đề {i}"},
            t_start=float(i * 5.0),
            t_end=float((i + 1) * 5.0),
            duration=5.0,
            narration=f"Nội dung cảnh {i} phát triển công nghệ.",
        )
        for i in range(5)
    ]
    script = SlideScript(topic="Test 2s Blank", total_duration=25.0, slides=slides)
    (tmp_path / "slide_script.json").write_text(json.dumps(script.model_dump(mode="json")), encoding="utf-8")
    dummy_video = tmp_path / "test.mp4"
    dummy_video.write_bytes(b"dummy")

    # Generate 100 frames at 4 fps (25 seconds total).
    # Normal frames have content (high std dev).
    # Frames from t=10.0 to t=14.0 (17 frames = 4.0s, > 2.5s in hold interval > 2.0s threshold) are blank.
    normal_frame = np.full((960, 540, 3), 245, dtype=np.uint8)
    normal_frame[200:400, 100:400] = 15  # text box with contrast
    blank_frame = np.full((960, 540, 3), 245, dtype=np.uint8)  # empty solid card

    fake_frames = []
    fps = 4.0
    for idx in range(100):
        t = idx / fps
        if 10.0 <= t <= 14.0:
            fake_frames.append((t, blank_frame.copy()))
        else:
            fake_frames.append((t, normal_frame.copy()))

    monkeypatch.setattr(audit_style, "extract_video_frames", lambda path, fps=4.0: fake_frames)

    res = audit_style.audit_kit_project(tmp_path, video_path=dummy_video, slide_script=script)
    assert res["passed"] is False, "Video with >= 2.0s blank frames must fail"
    pixel_check = res["checks"]["pixel_audit"]
    assert pixel_check["passed"] is False
    assert pixel_check["has_2s_blank"] is True
    assert pixel_check["max_consecutive_blank_sec"] >= 2.0
    assert any(">= 2.0s threshold" in v for v in res["violations"])


def test_audit_fails_on_duplicate_images(tmp_path):
    img_file = tmp_path / "img1.png"
    img_file.write_bytes(b"duplicate_content_bytes")

    slides = [
        SlideItem(
            id=f"slide_{i}",
            layout=["kit_title", "kit_list", "kit_stat", "kit_title", "kit_outro"][i],
            sentence_ids=[i + 1],
            slots={"title": f"Cảnh {i} hợp lệ", "text": "Nội dung đầy đủ", "image_url": str(img_file)} if i in (0, 1) else {"title": f"Cảnh {i} hợp lệ", "text": "Nội dung đầy đủ"},
            duration=5.0,
            narration="Nội dung cảnh hợp lệ.",
        )
        for i in range(5)
    ]
    script = SlideScript(topic="Test Dup Images", total_duration=25.0, slides=slides)
    (tmp_path / "slide_script.json").write_text(json.dumps(script.model_dump(mode="json")), encoding="utf-8")

    res = audit_light_glass_project(tmp_path, slide_script=script)
    assert res["passed"] is False
    assert res["checks"]["content_quality_and_dedup"]["duplicate_image_count"] > 0
    assert any("duplicate image" in v.lower() for v in res["violations"])


def test_audit_fails_on_forbidden_template_strings(tmp_path):
    slides = [
        SlideItem(
            id="slide_1",
            layout="kit_compare",
            sentence_ids=[1],
            slots={"title": "So Sánh Đối Chiếu", "left": {"text": "Phương án ban đầu"}, "right": {"text": "Giải pháp đột phá"}},
            duration=5.0,
            narration="So sánh các phương án.",
        ),
        SlideItem(
            id="slide_2",
            layout="kit_list",
            sentence_ids=[2],
            slots={"title": "Điểm Đáng Chú Ý", "items": ["Một điểm"]},
            duration=5.0,
            narration="Các điểm đáng chú ý.",
        ),
        SlideItem(
            id="slide_3",
            layout="kit_quote",
            sentence_ids=[3],
            slots={"quote": "Câu trích", "author": "Nhận định"},
            duration=5.0,
            narration="Lời trích dẫn nhận định.",
        ),
        SlideItem(
            id="slide_4",
            layout="kit_title",
            sentence_ids=[4],
            slots={"title": "Tiêu đề hợp lệ", "text": "Nội dung đầy đủ"},
            duration=5.0,
            narration="Nội dung chi tiết.",
        ),
        SlideItem(
            id="slide_5",
            layout="kit_outro",
            sentence_ids=[5],
            slots={"title": "Tổng kết hợp lệ", "text": "Nội dung đầy đủ"},
            duration=5.0,
            narration="Tổng kết cuối video.",
        ),
    ]
    script = SlideScript(topic="Test Forbidden", total_duration=25.0, slides=slides)
    (tmp_path / "slide_script.json").write_text(json.dumps(script.model_dump(mode="json")), encoding="utf-8")

    res = audit_light_glass_project(tmp_path, slide_script=script)
    assert res["passed"] is False
    assert res["checks"]["content_quality_and_dedup"]["forbidden_template_count"] >= 3
    assert any("forbidden template string" in v.lower() for v in res["violations"])


def test_audit_fails_on_cutoff_and_corrupted_date(tmp_path):
    slides = [
        SlideItem.model_construct(
            id="slide_1",
            layout="kit_title",
            sentence_ids=[1],
            slots={"title": "Địa chất đô thị đan xen nhiều tầng đòi", "text": "Nội dung"},
            duration=5.0,
            narration="Địa chất đô thị đan xen nhiều tầng đòi hỏi thiết bị cao.",
        ),
        SlideItem.model_construct(
            id="slide_2",
            layout="kit_title",
            sentence_ids=[2],
            slots={"title": "Làm sao để tiêu chuẩn kỹ", "text": "Nội dung"},
            duration=5.0,
            narration="Làm sao để tiêu chuẩn kỹ thuật giúp tự chủ.",
        ),
        SlideItem.model_construct(
            id="slide_3",
            layout="kit_stat",
            sentence_ids=[3],
            slots={"value": 1541, "unit": "km", "label": "Chiều dài", "text": "Đoạn đường sắt"},
            duration=5.0,
            narration="Tuyến đường dài 1541 km.",
        ),
        SlideItem.model_construct(
            id="slide_4",
            layout="kit_list",
            sentence_ids=[4],
            slots={"title": "Chi tiết kỹ thuật", "items": ["Hệ thống chuẩn"]},
            duration=5.0,
            narration="Hệ thống chuẩn đồng bộ.",
        ),
        SlideItem.model_construct(
            id="slide_5",
            layout="kit_outro",
            sentence_ids=[5],
            slots={"title": "Tổng kết", "text": "Nội dung", "source_date": "01/01/"},
            duration=5.0,
            narration="Tổng kết bài học.",
        ),
    ]
    script = SlideScript.model_construct(topic="Test Cutoff Date", total_duration=25.0, slides=slides)
    (tmp_path / "slide_script.json").write_text(json.dumps(script.model_dump(mode="json")), encoding="utf-8")

    res = audit_light_glass_project(tmp_path, slide_script=script)
    assert res["passed"] is False
    cq = res["checks"]["content_quality_and_dedup"]
    assert cq["cut_off_strings_count"] >= 2
    assert len(cq["corrupted_dates"]) >= 1

