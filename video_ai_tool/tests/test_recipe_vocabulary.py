"""Unit and regression tests for Phase 7 Motion Vocabulary Recipes (All 28 Recipes + Scheduler + Themes)."""
import hashlib
from pathlib import Path
import pytest

from editor.motion.recipes import (
    RecipeMetadata,
    RecipeStage,
    RECIPES_PHASE_A,
    RECIPES_PHASE_B,
    RECIPES_PHASE_C,
    ALL_RECIPES,
    bundle_vocabulary,
)
from editor.motion.engine import bundle_engine
from editor.motion.registry import REGISTRY
from editor.motion.scheduler import (
    MotionFamily,
    get_recipe_family,
    suggest_metaphor_recipe,
    schedule_recipes_no_repeat,
    RECIPE_FAMILY_MAP
)
from editor.motion.theme import load_motion_theme
from pipeline.render_motion import html_document
from config.settings import ROOT_DIR


def test_recipe_descriptors_metadata():
    """All 28 recipes must have >=3 stages, max_words<=3, and bbox in safe area."""
    assert len(RECIPES_PHASE_A) == 8, "Must contain exactly 8 Phase A recipes"
    assert len(RECIPES_PHASE_B) == 12, "Must contain exactly 12 Phase B recipes"
    assert len(RECIPES_PHASE_C) == 8, "Must contain exactly 8 Phase C recipes"
    assert len(ALL_RECIPES) == 28, "Must contain exactly 28 total recipes"

    for name, meta in ALL_RECIPES.items():
        assert meta.name == name
        assert meta.max_words <= 3, f"{name}: max_words must be <= 3"
        assert len(meta.stages) >= 3, f"{name}: must define at least 3 motion stages"

        # Check stage progression
        stage_names = [s["name"] for s in meta.stages]
        assert "enter" in stage_names, f"{name}: missing enter stage"
        assert "action" in stage_names, f"{name}: missing action stage"
        assert "impact" in stage_names, f"{name}: missing impact stage"

        # Check BBox safe zone [70, 1010] x [240, 1330]
        bx, by, bw, bh = meta.default_bbox
        assert bx >= 70, f"{name}: bbox x ({bx}) < 70"
        assert bx + bw <= 1010, f"{name}: bbox right ({bx+bw}) > 1010"
        assert by >= 240, f"{name}: bbox y ({by}) < 240"
        assert by + bh <= 1330, f"{name}: bbox bottom ({by+bh}) > 1330"


def test_recipe_registration_and_fallback():
    """All 28 recipes must be registered in REGISTRY with valid fallback types."""
    assert len(ALL_RECIPES) == 28

    for type_name in ALL_RECIPES:
        assert REGISTRY.is_registered(type_name), f"{type_name} must be registered"
        elem = REGISTRY.get(type_name)
        assert elem is not None
        fb = REGISTRY.find_fallback(type_name)
        assert fb in REGISTRY._registry, f"{type_name} fallback {fb} must be a registered element"


def test_bundle_vocabulary():
    """bundle_vocabulary returns valid non-empty JS bundle and is included in bundle_engine."""
    _, js_vocab, digest = bundle_vocabulary()
    assert len(js_vocab) > 40000, "vocabulary.js must not be empty"
    assert len(digest) == 64, "Digest must be 64-char sha256"

    # Must define MotionVocabulary with all 28 recipes
    assert "window.MotionVocabulary" in js_vocab
    for name in ALL_RECIPES:
        assert name in js_vocab, f"vocabulary.js must include {name}"

    # Must be embedded in engine bundle
    _, js_engine, _ = bundle_engine()
    assert "window.MotionVocabulary" in js_engine
    for name in ALL_RECIPES:
        assert name in js_engine, f"bundle_engine must include {name}"


def test_anti_repetition_scheduler_rules():
    """Anti-repetition scheduler must swap consecutive identical families and enforce >=4 families."""
    # Input with consecutive repeated families:
    # 0: slot_counter (NUMBER_STAT)
    # 1: strike_replace (NUMBER_STAT) -> Should be swapped to non-NUMBER_STAT
    # 2: odometer (NUMBER_STAT) -> Should be swapped
    # 3: balance_scale (COMPARE_VS)
    # 4: vs_flip_cards (COMPARE_VS) -> Should be swapped
    # 5: conveyor_belt (PROCESS_FLOW)
    scenes = [
        {"scene_type": "slot_counter", "narration": "Con số tăng trưởng vọt đạt mốc kỷ lục"},
        {"scene_type": "strike_replace", "narration": "Thay vì phương án cũ, chúng ta chuyển đổi toàn diện"},
        {"scene_type": "odometer", "narration": "Tích lũy hàng triệu giờ vận hành an toàn"},
        {"scene_type": "balance_scale", "narration": "Cán cân lợi ích nghiêng hẳn về giải pháp mới"},
        {"scene_type": "vs_flip_cards", "narration": "Đối đầu trực diện giữa hai mô hình công nghệ"},
        {"scene_type": "conveyor_belt", "narration": "Dây chuyền tự động hóa hoàn tất kiểm định"}
    ]

    scheduled, notes = schedule_recipes_no_repeat(scenes, min_distinct_families=4)

    assert len(scheduled) == len(scenes)
    assert len(notes) >= 2, "Must detect and repair consecutive family repetitions"

    # Verify no two consecutive scenes share the same family
    for i in range(1, len(scheduled)):
        fam_prev = scheduled[i - 1]["motion_family"]
        fam_curr = scheduled[i]["motion_family"]
        assert fam_prev != fam_curr, f"Scene {i} and {i-1} still have same family '{fam_curr}'"

    # Verify at least 4 distinct families
    distinct_families = {sc["motion_family"] for sc in scheduled}
    assert len(distinct_families) >= 4, f"Must have >=4 distinct families, got {distinct_families}"


def test_metaphor_keyword_matching():
    """suggest_metaphor_recipe accurately detects metaphor keywords."""
    recipe_compare = suggest_metaphor_recipe("Cán cân lợi ích nghiêng về bên nào?", previous_recipe="slot_counter")
    assert recipe_compare == "balance_scale"

    recipe_risk = suggest_metaphor_recipe("Tấm khiên phòng thủ an ninh mạng vững vàng", previous_recipe="balance_scale")
    assert recipe_risk == "shield_hit"

    recipe_process = suggest_metaphor_recipe("Phản ứng dây chuyền domino bùng nổ", previous_recipe="shield_hit")
    assert recipe_process == "domino_chain"

    recipe_ui = suggest_metaphor_recipe("Cuộc trò chuyện tin nhắn qua chatbot thông minh", previous_recipe="domino_chain")
    assert recipe_ui == "chat_thread"


def test_light_themes_contrast_and_palette():
    """clean_white and paper_brand provide valid contrast ratios and clean palettes."""
    theme_white = load_motion_theme(ROOT_DIR, name="clean_white")
    assert theme_white["name"] == "clean_white"
    assert theme_white["card"] == "#ffffff"
    assert theme_white["foreground"] == "#0f172a"
    assert len(theme_white["warnings"]) == 0

    theme_paper = load_motion_theme(ROOT_DIR, name="paper_brand")
    assert theme_paper["name"] == "paper_brand"
    assert theme_paper["card"] == "#ffffff"


def test_top_headline_caption_generation():
    """html_document properly supports top_headline and speech captions."""
    from editor.captions import find_font
    font_path = find_font(ROOT_DIR)

    if not font_path:
        pytest.skip("Font file not found in test environment")

    payload = {
        "width": 1080,
        "height": 1920,
        "duration": 4.0,
        "words": [{"text": "Bứt", "start": 0.5, "end": 1.0}, {"text": "phá", "start": 1.0, "end": 1.5}],
        "top_headline": "TIÊU ĐỀ ĐỘT PHÁ CÔNG NGHỆ",
        "captions": {"enabled": True, "top_headline": "TIÊU ĐỀ ĐỘT PHÁ CÔNG NGHỆ"},
        "shots": [{
            "start": 0,
            "duration": 4.0,
            "template": "text_focus",
            "data": {"label": "Chỉ số"},
            "beats": []
        }],
        "theme": {"name": "clean_white"},
        "visual_plan": {
            "scene_type": "orbit_system",
            "top_headline": "TIÊU ĐỀ ĐỘT PHÁ CÔNG NGHỆ",
            "data": {"center_node": "AI CORE"},
            "beats": []
        }
    }

    html = html_document(payload, font_path)
    assert "top-headline" in html
    assert "orbit_system" in html
    assert "theme-clean_white" in html
