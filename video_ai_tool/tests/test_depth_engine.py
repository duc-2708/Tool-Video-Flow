"""Unit and regression tests for Phase 6 3D Depth Engine (CSS 3D & Isometric Perspective)."""
import hashlib
from pathlib import Path
import pytest

from config.settings import Settings, get_settings
from editor.depth import bundle_depth
from editor.depth.style import (
    compute_3face_shading,
    validate_3d_bbox,
    SAFE_X_MIN,
    SAFE_X_MAX,
    SAFE_Y_MIN,
    SAFE_Y_MAX,
    CAPTION_Y_MIN
)
from pipeline.render_motion import html_document


def test_depth_settings_default_and_toggle():
    """Flag DEPTH_3D_ENABLED defaults to False; can be explicitly enabled."""
    cfg = get_settings()
    assert cfg.depth_3d_enabled is False, "depth_3d_enabled must default to False"

    enabled_cfg = cfg.model_copy(update={"depth_3d_enabled": True})
    assert enabled_cfg.depth_3d_enabled is True


def test_bundle_depth_assets():
    """bundle_depth returns valid non-empty CSS and JS bundles with sha256 hash."""
    css, js, digest = bundle_depth()
    assert len(css) > 100, "depth.css must not be empty"
    assert len(js) > 500, "depth.js must not be empty"
    assert len(digest) == 64, "SHA-256 digest must be 64 hex characters"
    assert ".depth-stage-wrapper" in css
    assert "renderPerspectiveFloor" in js
    assert "renderBarCompare3D" in js
    assert "renderGaugeRing3D" in js
    assert "renderVersusSplit3D" in js


def test_depth_3face_shading_rule():
    """Verify 3-face lighting: top is brightest, left is midtone, right is darkest."""
    base_color = "#00f5d4"
    shading = compute_3face_shading(base_color)

    assert "top" in shading and "left" in shading and "right" in shading
    # Parse hex RGB brightness approx
    def hex_lum(hex_str):
        hex_str = hex_str.lstrip("#")
        r, g, b = (int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        return 0.299 * r + 0.587 * g + 0.114 * b

    lum_top = hex_lum(shading["top"])
    lum_left = hex_lum(shading["left"])
    lum_right = hex_lum(shading["right"])

    assert lum_top > lum_left, f"Top face ({lum_top}) must be brighter than left ({lum_left})"
    assert lum_left > lum_right, f"Left face ({lum_left}) must be brighter than right face ({lum_right})"


def test_depth_bbox_validation_within_safe_area():
    """Verify post-transform bounding box validation rules."""
    # Valid element centered in content area
    valid_box = {"x": 200, "y": 450, "width": 680, "height": 620}
    res_valid = validate_3d_bbox(valid_box)
    assert res_valid["passed"] is True
    assert len(res_valid["errors"]) == 0
    assert abs(res_valid["center_y"] - 760) < 50

    # Invalid: encroaches into bottom caption safe zone (y1380-1700)
    caption_clash_box = {"x": 200, "y": 900, "width": 680, "height": 550} # y_max = 1450 > 1330
    res_clash = validate_3d_bbox(caption_clash_box)
    assert res_clash["passed"] is False
    assert any("vùng phụ đề" in err for err in res_clash["errors"])

    # Invalid: overflows right margin (> 1010)
    right_overflow_box = {"x": 500, "y": 500, "width": 550, "height": 400} # x_max = 1050 > 1010
    res_overflow = validate_3d_bbox(right_overflow_box)
    assert res_overflow["passed"] is False
    assert any("tràn lề phải" in err for err in res_overflow["errors"])


def test_depth_html_document_injects_flag():
    """html_document properly includes 3D Depth scripts and sets window.DEPTH_3D_ENABLED."""
    font_path = Path("assets/fonts/BeVietnamPro-Regular.ttf")
    if not font_path.is_file():
        # Fallback to any file for font encoding in test
        font_path = Path(__file__)

    payload_off = {
        "width": 1080, "height": 1920, "duration": 4.0, "words": [],
        "caption_words": [], "shots": [{"template": "text_focus", "duration": 4.0, "start": 0}]
    }
    html_off = html_document(payload_off, font_path)
    assert "window.DEPTH_3D_ENABLED = false;" in html_off
    assert "renderPerspectiveFloor" in html_off

    payload_on = {
        "width": 1080, "height": 1920, "duration": 4.0, "words": [],
        "caption_words": [], "depth_3d": True, "shots": [{"template": "text_focus", "duration": 4.0, "start": 0}]
    }
    html_on = html_document(payload_on, font_path)
    assert "window.DEPTH_3D_ENABLED = true;" in html_on


def test_bundle_depth_step_b_recipes():
    """Verify Phase 6 Step (b) 3D recipes and camera are included in JS bundle."""
    css, js, digest = bundle_depth()
    assert "renderHubSpoke3D" in js
    assert "renderChecklist3D" in js
    assert "renderStatNumber3D" in js
    assert "renderFlowChain3D" in js
    assert "renderTerminal3D" in js
    assert "renderRoadTracker3D" in js
    assert "applyDepthCamera" in js

    # CSS classes for step b
    assert ".hub-spoke-center-3d" in css
    assert ".checklist-slab-3d" in css
    assert ".stat-extrusion-hero" in css
    assert ".flow-station-cuboid" in css
    assert ".terminal-window-3d" in css
    assert ".road-milestone-cuboid" in css


def test_depth_camera_limits_validation():
    """Verify 3D camera validation constraints."""
    from editor.depth.style import validate_depth_camera, DEPTH_SUPPORTED_RECIPES

    # Valid camera
    res_valid = validate_depth_camera({"move": "dolly_in", "amount": 0.05, "impact_bump": 1.2})
    assert res_valid["passed"] is True
    assert len(res_valid["errors"]) == 0

    # Invalid: amount > 0.12
    res_overflow = validate_depth_camera({"move": "dolly_in", "amount": 0.25})
    assert res_overflow["passed"] is False
    assert any("too large" in err for err in res_overflow["errors"])

    # Invalid: unknown move
    res_unknown = validate_depth_camera({"move": "warp_speed"})
    assert res_unknown["passed"] is False
    assert any("Unknown camera move" in err for err in res_unknown["errors"])

    # Supported recipes list
    assert len(DEPTH_SUPPORTED_RECIPES) >= 9
    assert "hub_spoke" in DEPTH_SUPPORTED_RECIPES
    assert "checklist" in DEPTH_SUPPORTED_RECIPES
    assert "stat_number" in DEPTH_SUPPORTED_RECIPES
    assert "flow_chain" in DEPTH_SUPPORTED_RECIPES
    assert "terminal_typing" in DEPTH_SUPPORTED_RECIPES
    assert "road_tracker" in DEPTH_SUPPORTED_RECIPES

