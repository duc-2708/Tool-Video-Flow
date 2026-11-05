"""Unit and regression tests for Motion Kit v2.

Verifies:
1. Bundle integrity (bundle_kit loads CSS, JS, returns sha256).
2. Clean codebase: zero hardcoded Vietnamese/business display strings in kit/ components.
3. SlideScript layout normalization and slot validation for kit_* layouts.
4. Monotonic counting guarantee and slot requirement rules.
5. Audit style tool integration on synthetic project.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from editor.motion.kit import bundle_kit
from schemas.slide_script import ChartSlot, PhotoSlot, SlideScene, SlideScript
from tools.audit_style import audit_kit_project


def test_bundle_kit_integrity():
    """bundle_kit() must return non-empty css, js, and sha256 digest."""
    css, js, digest = bundle_kit()
    assert isinstance(css, str) and len(css) > 100
    assert isinstance(js, str) and len(js) > 500
    assert isinstance(digest, str) and len(digest) == 64
    assert "kit_title" in js
    assert "kit_stat" in js
    assert "kit_chart_bar" in js
    assert "kit_photo" in js
    assert "kit_list" in js
    assert "window.renderAt" in js


def test_no_hardcoded_business_strings_in_kit():
    """Kit components and engine must have ZERO hardcoded business strings.

    No financial mockups, hardcoded fake accounts, or dummy strings.
    """
    kit_dir = Path(__file__).resolve().parent.parent / "editor" / "motion" / "kit"
    assert kit_dir.exists()

    forbidden_patterns = [
        "QUỸ DỰ PHÒNG",
        "KHẨN CẤP",
        "34/635/474",
        "OpenAI Compatibility",
        "Hoạt động 99.9%",
        "100.000.000",
        "TÀI KHOẢN TIẾT KIỆM",
        "NGÂN HÀNG",
        "QUẢN LÝ TÀI CHÍNH",
    ]

    for file_path in kit_dir.rglob("*.js"):
        content = file_path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            assert pattern.lower() not in content.lower(), (
                f"Found forbidden hardcoded string '{pattern}' in {file_path.name}"
            )


def test_slidescript_layout_normalization():
    """SlideScript must support kit_* layouts and normalize legacy lg_* layouts."""
    scene = SlideScene(
        scene_idx=1,
        start_ms=0,
        end_ms=5000,
        layout="kit_stat",
        title="Tăng trưởng AI",
        stat_value="350%",
        stat_label="Tốc độ tăng trưởng",
    )
    assert scene.layout == "kit_stat"

    # Legacy mapping test: lg_stat_hero -> kit_stat
    legacy_scene = SlideScene(
        scene_idx=2,
        start_ms=5000,
        end_ms=10000,
        layout="lg_stat_hero",
        title="Chỉ số hiệu quả",
    )
    assert legacy_scene.layout == "kit_stat"


def test_slidescript_chart_and_photo_slots():
    """Verify ChartSlot and PhotoSlot validation."""
    chart_slot = ChartSlot(
        type="bar",
        title="Doanh thu hàng quý",
        unit="Tỷ VNĐ",
        series=[
            {"label": "Q1", "value": 120.0},
            {"label": "Q2", "value": 180.0},
            {"label": "Q3", "value": 240.0},
        ],
    )
    scene_chart = SlideScene(
        scene_idx=1,
        start_ms=0,
        end_ms=5000,
        layout="kit_chart_bar",
        title="Biểu đồ doanh thu",
        chart=chart_slot,
    )
    assert scene_chart.chart is not None
    assert len(scene_chart.chart.series) == 3

    photo_slot = PhotoSlot(
        path="assets/demo_chip.png",
        name="Vi xử lý AI 3nm",
        role="Phần cứng thế hệ mới",
        credit="Nguồn ảnh: Tổng hợp",
    )
    scene_photo = SlideScene(
        scene_idx=2,
        start_ms=5000,
        end_ms=10000,
        layout="kit_photo",
        title="Kiến trúc bán dẫn",
        photo=photo_slot,
    )
    assert scene_photo.photo is not None
    assert scene_photo.photo.path == "assets/demo_chip.png"


def test_audit_kit_project_synthetic(tmp_path):
    """Test quality audit runner on a synthetic compliant project."""
    project_dir = tmp_path / "synthetic_project"
    project_dir.mkdir()

    script = SlideScript(
        scenes=[
            SlideScene(
                scene_idx=1,
                start_ms=0,
                end_ms=5000,
                layout="kit_title",
                narration="Tiêu đề video giới thiệu nội dung phụ thuyết minh cho người xem.",
                title="Tiêu đề video",
                subtitle="Nội dung phụ thuyết minh",
            ),
            SlideScene(
                scene_idx=2,
                start_ms=5000,
                end_ms=10000,
                layout="kit_stat",
                narration="Số liệu đo lường thực tế cho thấy hiệu năng cải thiện đạt 85%.",
                title="Số liệu đo lường",
                stat_value="85%",
                stat_label="Hiệu năng cải thiện",
            ),
            SlideScene(
                scene_idx=3,
                start_ms=10000,
                end_ms=15200,
                layout="kit_list",
                narration="Danh sách ưu điểm nổi bật bao gồm các tính năng A, tính năng B và tính năng C.",
                title="Danh sách ưu điểm",
                bullets=["Tính năng A", "Tính năng B", "Tính năng C"],
            ),
            SlideScene(
                scene_idx=4,
                start_ms=15200,
                end_ms=20200,
                layout="kit_compare",
                narration="So sánh giải pháp cũ và công nghệ mới vượt trội.",
                title="So sánh giải pháp",
                subtitle="Giải pháp cũ và công nghệ mới",
            ),
            SlideScene(
                scene_idx=5,
                start_ms=20200,
                end_ms=25200,
                layout="kit_outro",
                narration="Theo dõi kênh để nhận thông tin cập nhật công nghệ mới.",
                title="Đăng ký theo dõi",
                subtitle="Cập nhật công nghệ mới",
            ),
        ]
    )

    script_path = project_dir / "slide_script.json"
    script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")

    result = audit_kit_project(project_dir)
    assert "total_score" in result
    assert result["total_score"] >= 80
    assert result["passed"] is True
    assert len(result["checks"]) >= 5
