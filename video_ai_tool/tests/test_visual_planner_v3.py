"""Regression and validation tests for Visual Planner v3 (Prompt B) and Element Registry."""
import json
import pytest
from pathlib import Path
from typing import Any

from config.settings import Settings
from schemas.edit_plan import EditPlan, Scene, Shot
from schemas.visual_v3 import (
    VisualPlanResponse,
    VisualScene,
    VisualElement,
    VisualAnnotation,
    normalize_visual_v3_payload,
)
from schemas.motion_scene import MotionScenePlan
from editor.motion.registry import REGISTRY, ElementRegistry, ElementDefinition
from agents.visual_planner_v3 import (
    render_visual_prompt,
    normalize_phrase_token,
    match_at_phrase_to_seconds,
    validate_and_repair_visual_plan,
    map_visual_scene_to_motion_scene_plan,
    create_visual_plan_v3,
)


class MockLLMProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        return self.response_text


def _sample_shot(duration: float = 4.0) -> Shot:
    return Shot(
        type="stock_video",
        query="energy",
        duration_sec=duration,
        planning_duration=True,
        effect="zoom_in",
        text_overlay=None,
    )


def _sample_edit_plan() -> EditPlan:
    return EditPlan(
        title="Khủng hoảng năng lượng",
        format="tiktok",
        voice="vi-VN-HoaiMyNeural",
        music={"mood": "calm", "volume": 0.08},
        scenes=[
            Scene(
                id=1,
                role="hook",
                narration="Châu Âu đối mặt mức tăng giá năng lượng kỷ lục 50 phần trăm.",
                shots=[_sample_shot(4.0)],
                fact_ids=[1],
            ),
            Scene(
                id=2,
                role="body",
                narration="Hệ thống lưu trữ khí đốt chỉ còn một nửa dung lượng so với năm ngoái.",
                shots=[_sample_shot(6.0)],
                fact_ids=[2],
            ),
            Scene(
                id=3,
                role="cta",
                narration="Bạn nghĩ giải pháp nào là khả thi nhất hiện nay?",
                shots=[_sample_shot(4.0)],
                fact_ids=[],
            ),
        ],
    )


def test_render_visual_prompt():
    plan = _sample_edit_plan()
    template = "VAI TRÒ: Visual Planner\n{ELEMENT_CATALOG}\nTHỜI LƯỢNG: {SECONDS}s\nKỊCH BẢN:\n<<<DÁN KỊCH BẢN VÀO ĐÂY>>>"
    rendered = render_visual_prompt(template, plan, registry=REGISTRY)
    assert "DANH MỤC PHẦN TỬ" in rendered
    assert "container_fill" in rendered
    assert "bar_compare" in rendered
    assert "stat_number" in rendered
    assert "flow_chain" in rendered
    assert "steps_ladder" in rendered
    assert "gauge_ring" in rendered
    assert "CẢNH 1 (hook)" in rendered
    assert "CẢNH 2 (body)" in rendered
    assert "Châu Âu đối mặt" in rendered


def test_normalize_phrase_token():
    assert normalize_phrase_token("Năng suất,") == "nangsuat"
    assert normalize_phrase_token("Đồng hồ đo %") == "donghodo"
    assert normalize_phrase_token("AI & Cloud!") == "aicloud"


def test_fuzzy_match_at_phrase_to_seconds():
    words = [
        {"text": "Châu", "start": 0.0, "end": 0.3},
        {"text": "Âu", "start": 0.3, "end": 0.6},
        {"text": "đối", "start": 0.6, "end": 0.9},
        {"text": "mặt", "start": 0.9, "end": 1.2},
        {"text": "mức", "start": 1.2, "end": 1.5},
        {"text": "tăng", "start": 1.5, "end": 1.8},
        {"text": "giá", "start": 1.8, "end": 2.1},
    ]

    # Exact match
    sec, matched = match_at_phrase_to_seconds("đối mặt", words, 5.0)
    assert matched is True
    assert sec == 0.6

    # Match with punctuation and uppercase
    sec, matched = match_at_phrase_to_seconds("Tăng giá,", words, 5.0)
    assert matched is True
    assert sec == 1.5

    # Match with unaccented token
    sec, matched = match_at_phrase_to_seconds("chau au", words, 5.0)
    assert matched is True
    assert sec == 0.0

    # Unmatched fallback to evenly spaced timestamp
    sec, matched = match_at_phrase_to_seconds("từ lạ hoàn toàn", words, 6.0, elem_idx=1, total_elems=3)
    assert matched is False
    assert sec > 0.0


def test_registry_unregistered_fallback():
    raw_payload = {
        "theme": "neon_dark",
        "central_metaphor": {"name": "Bình nước giới hạn", "anchor_element": "bình nước"},
        "scenes": [
            {
                "scene_id": 1,
                "purpose": "hook",
                "layout": "center_hero",
                "elements": [
                    {"id": "e1", "type": "unregistered_gadget", "zone": "center", "content": {}},
                    {"id": "e2", "type": "stat_number", "zone": "bottom", "content": {}},
                ],
            }
        ],
    }
    normalized = normalize_visual_v3_payload(raw_payload)
    resp = VisualPlanResponse.model_validate(normalized)
    plan = _sample_edit_plan()

    repaired, notes = validate_and_repair_visual_plan(resp, plan, registry=REGISTRY)
    # funnel is not registered in priority 6, falls back to container_fill
    assert repaired.scenes[0].elements[0].type == "text_focus"
    assert any("unregistered_gadget" in n and "chưa hỗ trợ" in n for n in notes)


def test_number_evidence_grounding():
    plan = _sample_edit_plan()
    raw_payload = {
        "theme": "neon_dark",
        "central_metaphor": {"name": "Thước đo", "anchor_element": "thước đo"},
        "scenes": [
            {
                "scene_id": 1,
                "purpose": "hook",
                "elements": [
                    {
                        "id": "e1",
                        "type": "stat_number",
                        "content": {"value": 50, "unit": "%"},
                        "evidence": "mức tăng giá năng lượng kỷ lục 50 phần trăm",
                        "no_numbers": False,
                    },
                    {
                        "id": "e2",
                        "type": "stat_number",
                        "content": {"value": 999, "unit": "tỷ"},
                        "evidence": "con số bịa đặt hoàn toàn không có trong kịch bản",
                        "no_numbers": False,
                    },
                ],
            }
        ],
    }
    resp = VisualPlanResponse.model_validate(normalize_visual_v3_payload(raw_payload))
    repaired, notes = validate_and_repair_visual_plan(resp, plan, registry=REGISTRY)

    # e1 has valid evidence from narration -> keeps numbers
    assert repaired.scenes[0].elements[0].no_numbers is False
    assert repaired.scenes[0].elements[0].content["value"] == 50

    # e2 has invalid evidence -> converts to no_numbers=True and clears value
    assert repaired.scenes[0].elements[1].no_numbers is True
    assert repaired.scenes[0].elements[1].content["value"] is None
    assert any("e2" in n and "no_numbers=true" in n for n in notes)


def test_annotation_semantics_auto_repair():
    plan = _sample_edit_plan()
    raw_payload = {
        "theme": "paper_brand",
        "scenes": [
            {
                "scene_id": 1,
                "purpose": "hook",
                "elements": [{"id": "e1", "type": "stat_number"}],
                "annotations": [
                    {"type": "strike", "target": "e1", "text": "số liệu chính xác đã được xác nhận"},
                    {"type": "check", "target": "e1", "text": "thất bại và lỗi hệ thống"},
                ],
            }
        ],
    }
    resp = VisualPlanResponse.model_validate(normalize_visual_v3_payload(raw_payload))
    repaired, notes = validate_and_repair_visual_plan(resp, plan)

    # strike on positive content auto-repaired to check
    assert repaired.scenes[0].annotations[0].type == "check"
    # check on error content auto-repaired to cross
    assert repaired.scenes[0].annotations[1].type == "cross"


def test_layout_diversity_and_hook_density():
    plan = _sample_edit_plan()
    raw_payload = {
        "theme": "whiteboard_sketch",
        "scenes": [
            {
                "scene_id": 1,
                "purpose": "hook",
                "layout": "center_hero",
                # Hook has 3 elements -> should trim to 2
                "elements": [
                    {"id": "e1", "type": "stat_number"},
                    {"id": "e2", "type": "stat_number"},
                    {"id": "e3", "type": "stat_number"},
                ],
            },
            {
                "scene_id": 2,
                "purpose": "explain",
                # Duplicate consecutive layout center_hero -> should change
                "layout": "center_hero",
                "elements": [{"id": "e4", "type": "bar_compare"}],
            },
        ],
    }
    resp = VisualPlanResponse.model_validate(normalize_visual_v3_payload(raw_payload))
    repaired, notes = validate_and_repair_visual_plan(resp, plan)

    # Hook elements trimmed to 2
    assert len(repaired.scenes[0].elements) == 2
    # Scene 2 layout auto-differentiated
    assert repaired.scenes[1].layout != "center_hero"
    assert any("trùng layout" in n for n in notes)


def test_map_visual_scene_to_motion_scene_plan():
    v_scene = VisualScene(
        scene_id=1,
        purpose="explain",
        section_title="So sánh năng lực",
        layout="split_2",
        elements=[
            VisualElement(
                id="e1",
                type="bar_compare",
                zone="left",
                content={
                    "text": "Tỷ lệ tăng trưởng",
                    "bars": [
                        {"label": "Năm 2023", "value": 30.0, "unit": "%"},
                        {"label": "Năm 2024", "value": 45.0, "unit": "%"},
                    ],
                },
                evidence="tăng giá 50 phần trăm",
                no_numbers=False,
            )
        ],
        annotations=[
            VisualAnnotation(type="circle_highlight", target="e1", text="Điểm nhấn")
        ],
    )
    motion_plan = map_visual_scene_to_motion_scene_plan(v_scene, duration_sec=5.0, central_metaphor="Thước đo")
    assert isinstance(motion_plan, MotionScenePlan)
    assert motion_plan.scene_type in {"bar_grow", "bar_compare"}
    assert motion_plan.layout == "split_2"
    assert motion_plan.zone == "left"
    assert motion_plan.evidence == "tăng giá 50 phần trăm"
    assert motion_plan.no_numbers is False
    assert len(motion_plan.data.bars) == 2
    assert len(motion_plan.beats) == 2


def test_per_scene_failure_isolation(tmp_path):
    plan = _sample_edit_plan()
    # Mock LLM returns response with one malformed scene
    mock_json = {
        "theme": "neon_dark",
        "central_metaphor": {"name": "Ẩn dụ mẫu", "anchor_element": "neo"},
        "scenes": [
            {
                "scene_id": 1,
                "purpose": "hook",
                "layout": "center_hero",
                "elements": [{"id": "e1", "type": "stat_number", "content": {"text": "Hook hợp lệ"}}],
            },
            {
                "scene_id": 2,
                "purpose": "explain",
                "layout": "split_2",
                "elements": [{"id": "e2", "type": "bar_compare", "content": {"text": "Cảnh 2 hợp lệ"}}],
            },
            {
                "scene_id": 3,
                "purpose": "cta",
                "layout": "center_hero",
                "elements": [],
            },
        ],
    }
    provider = MockLLMProvider(json.dumps(mock_json))
    settings = Settings(root_dir=tmp_path)

    updated_plan = create_visual_plan_v3(
        plan=plan,
        words_by_scene={1: [], 2: [], 3: []},
        provider=provider,
        settings=settings,
        state_path=tmp_path / "director_state.visual_v3.json",
    )

    assert len(updated_plan.scenes) == 3
    for sc in updated_plan.scenes:
        assert sc.visual_plan is not None
        assert isinstance(sc.visual_plan, MotionScenePlan)
    assert (tmp_path / "director_state.visual_v3.json").is_file()


def test_all_registry_elements():
    types = REGISTRY.list_registered_types()
    assert "versus_split" in types
    assert "terminal_typing" in types
    assert "checklist" in types
    assert "line_chart_draw" in types
    assert "hub_spoke" in types
    assert "magnifier_check" in types
    assert "progress_tracker" in types
    assert "chat_bubble_poll" in types
    assert "source_badge" in types
    assert "icon_tile" in types
    
    annots = REGISTRY.list_supported_annotations()
    for an in ("strike", "check", "cross", "underline", "circle_highlight", "stamp", "question", "arrow", "tag", "pencil"):
        assert an in annots


def test_ui_theme_loading_from_visual_plan():
    from editor.motion.theme import load_motion_theme
    root = Path(__file__).resolve().parents[1]
    plan = _sample_edit_plan()
    plan.scenes[0].visual_plan = MotionScenePlan(theme="paper_brand")
    theme = load_motion_theme(root, plan=plan, name="auto")
    assert theme["name"] == "paper_brand"
    assert theme["card"] == "#ffffff"


def test_anchor_element_and_metaphor_state_propagation(tmp_path):
    plan = _sample_edit_plan()
    mock_json = {
        "theme": "whiteboard_sketch",
        "central_metaphor": {
            "name": "Nhiệt kế chịu tải",
            "anchor_element": "nhiệt kế",
            "states_by_scene": {"1": "30 độ", "2": "50 độ", "3": "100 độ"}
        },
        "scenes": [
            {"scene_id": 1, "purpose": "hook", "layout": "center_hero", "elements": [{"id": "e1", "type": "stat_number"}]},
            {"scene_id": 2, "purpose": "explain", "layout": "split_2", "elements": [{"id": "e2", "type": "bar_compare"}]},
            {"scene_id": 3, "purpose": "cta", "layout": "center_hero", "elements": []},
        ],
    }
    provider = MockLLMProvider(json.dumps(mock_json))
    settings = Settings(root_dir=tmp_path)

    updated_plan = create_visual_plan_v3(
        plan=plan,
        words_by_scene={1: [], 2: [], 3: []},
        provider=provider,
        settings=settings,
        state_path=tmp_path / "director_state.visual_v3.json",
    )

    assert updated_plan.scenes[0].visual_plan.theme == "whiteboard_sketch"
    assert updated_plan.scenes[0].visual_plan.central_metaphor == "Nhiệt kế chịu tải"
    assert updated_plan.scenes[0].visual_plan.anchor == "nhiệt kế"
    assert updated_plan.scenes[0].visual_plan.metaphor_state == "30 độ"
    assert updated_plan.scenes[1].visual_plan.metaphor_state == "50 độ"
    assert updated_plan.scenes[2].visual_plan.metaphor_state == "100 độ"
