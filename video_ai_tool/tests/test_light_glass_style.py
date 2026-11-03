"""Regression tests for Light Glass motion style (theme, 6 recipes, fixed frame, layout audit)."""
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

from editor.motion.scheduler import (
    LIGHT_GLASS_RECIPES,
    suggest_light_glass_recipe,
    schedule_light_glass_shots,
)
from pipeline.render_motion import html_document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FONT_PATH = str(PROJECT_ROOT / "assets" / "fonts" / "Inter-Regular.ttf")


def test_scheduler_no_consecutive_duplicates():
    """Verify scheduler strictly prevents any consecutive recipe repetitions."""
    shots = [
        {"narration": "Kiến trúc chip xử lý thế hệ mới vừa được ra mắt."},
        {"narration": "Hiệu năng xử lý tăng 78% so với phiên bản tiền nhiệm."},
        {"narration": "Tốc độ xử lý cũng đạt 95% ở các tác vụ nặng."},
        {"narration": "So với thế hệ cũ 14 nhân, vi xử lý mới sở hữu 24 nhân."},
        {"narration": "So với các đối thủ cạnh tranh trên thị trường hiện nay."},
        {"narration": "Ba điểm nổi bật gồm tính năng, băng thông và tiết kiệm điện."},
        {"narration": "Chuyên gia đánh giá đây là bước đột phá công nghệ lớn."},
        {"narration": "Đăng ký theo dõi kênh để cập nhật tin tức mỗi ngày."},
    ]
    scheduled = schedule_light_glass_shots(shots)
    assert len(scheduled) == len(shots)

    # Check no two consecutive shots share the same recipe
    for i in range(1, len(scheduled)):
        assert scheduled[i] != scheduled[i - 1], f"Duplicate consecutive recipe at index {i}: {scheduled[i]}"

    # Shot 0 should be source headline
    assert scheduled[0] == "lg_source_headline"
    # Last shot should be cta profile
    assert scheduled[-1] == "lg_cta_profile"
    # Shot 1 has number -> lg_stat_hero
    assert scheduled[1] == "lg_stat_hero"
    # Shot 2 has number but cannot repeat stat_hero -> picks alternative
    assert scheduled[2] != "lg_stat_hero"


def test_suggest_light_glass_recipe_heuristics():
    """Verify heuristic matching based on sentence keywords."""
    r1 = suggest_light_glass_recipe("Tin tức công nghệ mới", shot_index=0, total_shots=4)
    assert r1 == "lg_source_headline"

    r_num = suggest_light_glass_recipe("Tốc độ tăng 85% so với năm ngoái", shot_index=1, total_shots=4, previous_recipe="lg_source_headline")
    assert r_num == "lg_stat_hero"

    r_cmp = suggest_light_glass_recipe("So với đối thủ, giải pháp mới vượt trội hơn", shot_index=2, total_shots=4, previous_recipe="lg_stat_hero")
    assert r_cmp == "lg_vs_compare"

    r_cta = suggest_light_glass_recipe("Hãy theo dõi để cập nhật thêm", shot_index=3, total_shots=4, previous_recipe="lg_vs_compare")
    assert r_cta == "lg_cta_profile"


def _make_light_glass_payload(shots):
    return {
        "width": 1080,
        "height": 1920,
        "duration": sum(s["duration"] for s in shots),
        "theme": {
            "name": "light_glass",
            "top": "#f4f5f8",
            "bottom": "#e8ecf2",
            "card": "#ffffff",
            "foreground": "#1a1446",
            "accent": "#2563eb",
            "secondary": "#3d2bb0"
        },
        "brand_name": "TIN CÔNG NGHỆ",
        "brand_label": "BẢN TIN CÔNG NGHỆ",
        "brand_logo_path": "",
        "brand_logo_data_uri": "",
        "source_domain": "theverge.com",
        "captions": {"enabled": False},
        "shots": shots,
        "words": [],
        "caption_words": []
    }


def test_empty_slot_no_na_placeholder():
    """Verify missing/optional fields do not create 'N/A', '0000', or 'undefined'."""
    shots = [
        {
            "start": 0.0,
            "duration": 5.0,
            "template": "lg_stat_hero",
            "data": {
                "label": "TỶ LỆ TĂNG TRƯỞNG",
                "value": 78,
                # unit, number_text, text are omitted
            },
            "visual_plan": {
                "scene_type": "lg_stat_hero",
                "recipe": "lg_stat_hero",
                "data": {"label": "TỶ LỆ TĂNG TRƯỞNG", "value": 78}
            }
        },
        {
            "start": 5.0,
            "duration": 5.0,
            "template": "lg_note_card",
            "data": {
                # author is omitted
                "text": "Nhận định quan trọng về tương lai phần cứng máy tính."
            },
            "visual_plan": {
                "scene_type": "lg_note_card",
                "recipe": "lg_note_card",
                "data": {"text": "Nhận định quan trọng về tương lai phần cứng máy tính."}
            }
        }
    ]
    payload = _make_light_glass_payload(shots)
    html_str = html_document(payload, FONT_PATH)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-gpu"])
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html_str, wait_until="load")

        # Test Shot 1 at t=2.5s
        page.evaluate("() => window.renderAt(2.5)")
        content_text_1 = page.inner_text("#stage")
        assert "N/A" not in content_text_1
        assert "0000" not in content_text_1
        assert "undefined" not in content_text_1
        assert "null" not in content_text_1

        # Test Shot 2 at t=7.5s
        page.evaluate("() => window.renderAt(7.5)")
        content_text_2 = page.inner_text("#stage")
        assert "N/A" not in content_text_2
        assert "undefined" not in content_text_2
        assert "null" not in content_text_2

        browser.close()


def test_fixed_frame_persistence():
    """Verify #lg-fixed-frame persists across shot changes without being recreated."""
    shots = [
        {
            "start": 0.0,
            "duration": 4.0,
            "template": "lg_source_headline",
            "source_domain": "theverge.com",
            "data": {"title": "TIÊU ĐỀ BẢN TIN SỐ 1"},
            "visual_plan": {"scene_type": "lg_source_headline", "recipe": "lg_source_headline", "data": {"title": "TIÊU ĐỀ BẢN TIN SỐ 1"}}
        },
        {
            "start": 4.0,
            "duration": 4.0,
            "template": "lg_stat_hero",
            "source_domain": "techcrunch.com",
            "data": {"value": 85, "unit": "%"},
            "visual_plan": {"scene_type": "lg_stat_hero", "recipe": "lg_stat_hero", "data": {"value": 85, "unit": "%"}}
        }
    ]
    payload = _make_light_glass_payload(shots)
    html_str = html_document(payload, FONT_PATH)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-gpu"])
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html_str, wait_until="load")

        # Shot 1
        page.evaluate("() => window.renderAt(2.0)")
        has_frame_1 = page.evaluate("() => Boolean(document.getElementById('lg-fixed-frame'))")
        assert has_frame_1 is True

        pill_text_1 = page.evaluate("() => document.getElementById('lg-source-pill-text')?.textContent")
        assert "theverge.com" in pill_text_1

        # Add a custom marker to the DOM node
        page.evaluate("() => document.getElementById('lg-fixed-frame').dataset.testMarker = 'persistent'")

        # Shot 2
        page.evaluate("() => window.renderAt(6.0)")
        has_frame_2 = page.evaluate("() => Boolean(document.getElementById('lg-fixed-frame'))")
        assert has_frame_2 is True

        # Verify marker is still present (proves node was NOT destroyed and recreated)
        marker = page.evaluate("() => document.getElementById('lg-fixed-frame').dataset.testMarker")
        assert marker == "persistent", "Fixed frame DOM node was destroyed and recreated across shots!"

        pill_text_2 = page.evaluate("() => document.getElementById('lg-source-pill-text')?.textContent")
        assert "techcrunch.com" in pill_text_2

        browser.close()


def test_layout_audit_passes_all_recipes():
    """Verify all 6 Light Glass recipes pass getLayoutAudit (safe-area, no clip, no empty card)."""
    shots = [
        {
            "start": 0.0,
            "duration": 5.0,
            "template": "lg_source_headline",
            "data": {
                "source": "THE VERGE",
                "title": "BẢN TIN ĐỘT PHÁ CÔNG NGHỆ BÁN DẪN",
                "highlight": ["ĐỘT PHÁ", "BÁN DẪN"]
            },
            "visual_plan": {"scene_type": "lg_source_headline", "recipe": "lg_source_headline", "data": {"title": "BẢN TIN ĐỘT PHÁ CÔNG NGHỆ BÁN DẪN"}}
        },
        {
            "start": 5.0,
            "duration": 5.0,
            "template": "lg_stat_hero",
            "data": {
                "label": "TĂNG TRƯỞNG HIỆU SUẤT",
                "value": 78,
                "unit": "%",
                "number_text": "78%"
            },
            "visual_plan": {"scene_type": "lg_stat_hero", "recipe": "lg_stat_hero", "data": {"value": 78, "unit": "%", "label": "TĂNG TRƯỞNG HIỆU SUẤT"}}
        },
        {
            "start": 10.0,
            "duration": 5.0,
            "template": "lg_shot_features",
            "data": {
                "title": "TÍNH NĂNG MỚI",
                "items": [
                    "Băng thông mở rộng gấp đôi cho AI",
                    "Giảm điện năng tiêu thụ 35 phần trăm",
                    "Hỗ trợ hoàn toàn hệ sinh thái hiện hành"
                ]
            },
            "visual_plan": {"scene_type": "lg_shot_features", "recipe": "lg_shot_features", "data": {"title": "TÍNH NĂNG MỚI", "items": ["Băng thông", "Điện năng", "Hỗ trợ"]}}
        },
        {
            "start": 15.0,
            "duration": 5.0,
            "template": "lg_vs_compare",
            "data": {
                "title": "SO SÁNH HAI THẾ HỆ",
                "bars": [
                    {"label": "Thế hệ cũ: 14 nhân", "value": 45},
                    {"label": "Thế hệ mới: 24 nhân", "value": 85}
                ]
            },
            "visual_plan": {"scene_type": "lg_vs_compare", "recipe": "lg_vs_compare", "data": {"title": "SO SÁNH", "bars": [{"label": "Cũ", "value": 45}, {"label": "Mới", "value": 85}]}}
        },
        {
            "start": 20.0,
            "duration": 5.0,
            "template": "lg_note_card",
            "data": {
                "label": "NHẬN ĐỊNH CHUYÊN GIA",
                "text": "Một bước chuyển đổi kiến trúc có tính đột phá sâu rộng.",
                "author": "Chuyên gia phân tích"
            },
            "visual_plan": {"scene_type": "lg_note_card", "recipe": "lg_note_card", "data": {"text": "Một bước chuyển đổi kiến trúc."}}
        },
        {
            "start": 25.0,
            "duration": 5.0,
            "template": "lg_cta_profile",
            "data": {
                "text": "BẤM THEO DÕI ĐỂ CẬP NHẬT TIN MỚI NHẤT MỖI NGÀY",
                "channel_name": "TIN CÔNG NGHỆ",
                "channel_handle": "@tincongnghe"
            },
            "visual_plan": {"scene_type": "lg_cta_profile", "recipe": "lg_cta_profile", "data": {"text": "THEO DÕI KÊNH", "channel_name": "TIN CÔNG NGHỆ"}}
        }
    ]
    payload = _make_light_glass_payload(shots)
    html_str = html_document(payload, FONT_PATH)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-gpu"])
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html_str, wait_until="load")

        # Test mid-point of each recipe
        check_times = [2.5, 7.5, 12.5, 17.5, 22.5, 27.5]
        for idx, t in enumerate(check_times):
            page.evaluate(f"() => window.renderAt({t})")
            audit = page.evaluate(f"() => window.getLayoutAudit ? window.getLayoutAudit({t}) : null")
            assert audit is not None, f"Audit returned None for shot {idx+1} at t={t}"
            assert audit["clipped_rows"] == 0, f"Shot {idx+1} ({shots[idx]['template']}) has clipped rows: {audit['clipped_rows']}"
            assert audit["caption_collisions"] == 0, f"Shot {idx+1} has caption collisions: {audit['caption_collisions']}"
            assert audit["is_empty_card"] is False, f"Shot {idx+1} ({shots[idx]['template']}) flagged as empty card!"
            assert audit["min_font_size"] >= 24, f"Shot {idx+1} min font size too small: {audit['min_font_size']}"

        # Test near shot end (t=4.8s) to ensure card opacity does NOT blackout to 0.0
        page.evaluate("() => window.renderAt(4.8)")
        exit_opacity = page.evaluate("() => { const r = document.querySelector('.lg-recipe'); return r ? parseFloat(getComputedStyle(r).opacity) : 1.0; }")
        assert exit_opacity >= 0.85, f"Exit opacity dropped too low ({exit_opacity} < 0.85), causing blank void gap!"

        browser.close()
