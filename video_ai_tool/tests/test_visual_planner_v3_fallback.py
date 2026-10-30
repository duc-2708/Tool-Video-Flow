"""Tests for Visual Planner v3 Resilience, Rule-based keyword fallback, and Anti-Repetition Scheduler."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from agents.visual_planner_v3 import create_visual_plan_v3
from editor.motion.scheduler import schedule_recipes_no_repeat, suggest_metaphor_recipe
from schemas.edit_plan import EditPlan, Scene, Shot, Music
from schemas.motion_scene import SceneAnnotation
from utils.cache import cache_key


def _sample_shot(duration: float = 4.0) -> Shot:
    return Shot(
        type="stock_video",
        query="energy",
        duration_sec=duration,
        planning_duration=True,
        effect="zoom_in",
        text_overlay=None,
    )


class FailingProvider:
    def generate(self, prompt: str) -> str:
        raise RuntimeError("LLM API Timeout")


def test_scene_annotation_json_serializable():
    """Ensure SceneAnnotation objects do not cause TypeError during json serialization or cache_key."""
    annot = SceneAnnotation(
        type="strike",
        target="cân bằng",
        text="phân tích"
    )
    data = {
        "visual_plan": {
            "scene_type": "balance_scale",
            "annotations": [annot]
        }
    }
    # Should not raise TypeError: Object of type SceneAnnotation is not JSON serializable
    key = cache_key(data)
    assert isinstance(key, str) and len(key) == 64


def test_visual_planner_v3_llm_failure_keyword_fallback(tmp_path):
    """When LLM router fails all retries, planner must fall back to keyword-driven metaphor recipes and save status files."""
    scenes = [
        Scene(id=1, role="hook", narration="Nguy cơ tấn công mạng đang đe dọa an ninh dữ liệu.", shots=[_sample_shot(4.0)]),
        Scene(id=2, role="body", narration="Trước đây quy trình rất chậm nhưng nay đã lột xác hoàn toàn.", shots=[_sample_shot(4.0)]),
        Scene(id=3, role="body", narration="Hệ thống gồm nhiều lớp bóc tách từng tầng kiến trúc phức tạp.", shots=[_sample_shot(4.0)]),
        Scene(id=4, role="body", narration="Hai bên đang giằng co quyết liệt từng điểm phần trăm thị phần.", shots=[_sample_shot(4.0)]),
        Scene(id=5, role="cta", narration="Tổng kết lại toàn bộ các tiêu chí then chốt cần thực hiện ngay.", shots=[_sample_shot(4.0)]),
    ]
    plan = EditPlan(
        title="An ninh mạng và cải tổ quy trình",
        format="tiktok",
        voice="vi-VN-NamMinhNeural",
        music=Music(mood="calm", volume=0.08),
        scenes=scenes
    )

    status_file = tmp_path / "planner_status.json"
    state_file = tmp_path / "director_state.visual_v3.json"

    res_plan = create_visual_plan_v3(
        plan,
        provider=FailingProvider(),
        settings=MagicMock(),
        diagnostics=MagicMock(),
        state_path=state_file
    )

    # Status file must record llm_ok = False
    assert status_file.is_file(), "planner_status.json must be created"
    status_data = json.loads(status_file.read_text(encoding="utf-8"))
    assert status_data["llm_ok"] is False
    assert status_data["fallback_used"] is True

    # Prompt, response, and decisions logs must be created
    assert (tmp_path / "planner_prompt.txt").is_file()
    assert (tmp_path / "planner_response.json").is_file()
    assert (tmp_path / "planner_decisions.json").is_file()

    # All scenes must have valid visual_plans with non-empty recipes (no stat_number empty placeholders)
    recipes = [s.visual_plan.scene_type for s in res_plan.scenes]
    assert len(recipes) == 5
    # Recap scene (scene 5) must use one of recap recipes: checklist, layered_onion, orbit_system
    assert recipes[-1] in {"checklist", "layered_onion", "orbit_system"}
    # Metaphor matching: scene 1 has 'an ninh'/'tan cong' -> shield_hit
    assert recipes[0] == "shield_hit"


def test_scheduler_recap_and_meaningful_beats():
    """Ensure recap scene uses high-motion recap recipe, and idle_breath is not counted as an event."""
    scenes = [
        {"scene_type": "stat_number", "narration": "Con số 100 tỷ đồng", "evidence": "100", "beats": [
            {"at_sec": 0.5, "action": "idle_breath"},
            {"at_sec": 1.2, "action": "idle_breath"},
        ]},
        {"scene_type": "bar_race", "narration": "Tốc độ bứt phá", "beats": []},
        {"scene_type": "conveyor_belt", "narration": "Tổng kết quy trình", "top_headline": "ĐÂY LÀ TIÊU ĐỀ RẤT DÀI VƯỢT QUÁ SÁU TỪ ĐƠN", "beats": []},
    ]

    scheduled, notes = schedule_recipes_no_repeat(scenes)
    assert len(scheduled) == 3

    # Cảnh cuối cùng phải được ép thành recap recipe
    assert scheduled[-1]["scene_type"] in {"checklist", "layered_onion", "orbit_system"}

    # Cảnh 1 có 2 idle_breath, scheduler phải bổ sung meaningful beats để >= 3 events
    meaningful = [b for b in scheduled[0]["beats"] if "idle_breath" not in b.get("action", "").lower()]
    assert len(meaningful) >= 3

    # Headline dài phải được rút gọn <= 6 từ
    hl = scheduled[-1].get("top_headline", "")
    assert len(hl.split()) <= 6


def test_no_placeholder_labels_in_visual_plan():
    """Placeholder strings like 'Minh họa ý tưởng' must never be generated."""
    from agents.visual_diversity import concept_card
    from agents.presentation import clean_semantic_label
    
    # concept_card should not return 'Minh họa ý tưởng'
    label, ok = concept_card("Cảnh phân tích tình hình chung")
    assert "Minh họa ý tưởng" not in label
    assert "Minh họa nội dung" not in label

    # clean_semantic_label should return empty for placeholders
    assert clean_semantic_label("Minh họa ý tưởng cảnh 1") == ""
    assert clean_semantic_label("Minh họa ý chính") == ""
    assert clean_semantic_label("Minh họa nội dung vụ án") == ""
