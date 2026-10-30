"""Tests for Visual Planner v3 Resilience, Rule-based keyword fallback, and Anti-Repetition Scheduler."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agents.visual_planner_v3 import create_visual_plan_v3
from editor.motion.scheduler import schedule_recipes_no_repeat, schedule_shots_no_repeat, suggest_metaphor_recipe
from schemas.edit_plan import EditPlan, Scene, Shot, Music
from schemas.motion_scene import SceneAnnotation, MotionScenePlan
from schemas.style import CaptionStyle
from schemas.visual import VisualData, VisualBeat
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
        Scene(id=1, role="hook", narration="Nguy cơ tấn công mạng đang đe dọa an ninh dữ liệu.", shots=[_sample_shot(4.0) for _ in range(4)]),
        Scene(id=2, role="body", narration="Trước đây quy trình rất chậm nhưng nay đã lột xác hoàn toàn.", shots=[_sample_shot(4.0) for _ in range(4)]),
        Scene(id=3, role="body", narration="Hệ thống gồm nhiều lớp bóc tách từng tầng kiến trúc phức tạp.", shots=[_sample_shot(4.0) for _ in range(4)]),
        Scene(id=4, role="body", narration="Hai bên đang giằng co quyết liệt từng điểm phần trăm thị phần.", shots=[_sample_shot(4.0) for _ in range(4)]),
        Scene(id=5, role="cta", narration="Tổng kết lại toàn bộ các tiêu chí then chốt cần thực hiện ngay.", shots=[_sample_shot(4.0) for _ in range(4)]),
    ]
    plan = EditPlan(
        title="An ninh mạng và cải tổ quy trình",
        format="tiktok",
        voice="vi-VN-NamMinhNeural",
        music=Music(mood="calm", volume=0.08),
        content_timed=True,
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

    # Per-shot scheduling: Each scene must have >= 3 distinct recipes across its shots
    for sc in res_plan.scenes:
        shot_recipes = [sh.visual_plan.scene_type for sh in sc.shots if sh.visual_plan]
        assert len(set(shot_recipes)) >= 3, f"Scene {sc.id} must have >= 3 distinct shot recipes, got: {shot_recipes}"


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


def test_fallback_diverse_not_always_balance_scale():
    """When enough() is False, fallback in render_motion must use suggest_metaphor_recipe and not always return balance_scale."""
    from pipeline.render_motion import scene_payload

    class MockShot:
        def __init__(self):
            self.start = 0.0
            self.duration = 4.0
            self.visual = None
            self.spec = MagicMock()
            self.spec.visual = None
            self.spec.visual_plan = None
            self.visual_plan = None

    class MockSceneSpec:
        def __init__(self, id, narration, scene_type="timeline"):
            self.id = id
            self.narration = narration
            self.role = "body"
            self.fact_ids = []
            # Visual plan requires items for timeline, but data has no items -> enough() will be False
            self.visual_plan = MotionScenePlan(
                scene_type=scene_type,
                layout="center_hero",
                data=VisualData(text=narration)
            )

    class MockScene:
        def __init__(self, id, narration, scene_type="timeline", prev_recipe=None):
            self.shots = [MockShot()]
            self.spec = MockSceneSpec(id, narration, scene_type)
            self.spec.shots = self.shots
            self.start = 0.0
            self.duration = 4.0
            self.audio = Path(f"scene_{id}.mp3")
            self.previous_recipe = prev_recipe

    # Mock read_words and align_words
    with patch("pipeline.render_motion.read_words", return_value=[]), \
         patch("pipeline.render_motion.align_words", return_value=([], "projected")):
        
        # Scene 1: Security context
        sc1 = MockScene(1, "Cuộc tấn công mạng quy mô lớn nhắm vào tấm khiên bảo mật quốc gia.")
        p1 = scene_payload(sc1, (540, 960), CaptionStyle())
        recipe1 = p1["visual_plan"]["scene_type"]
        assert recipe1 == "shield_hit", f"Expected shield_hit for security context, got: {recipe1}"

        # Scene 2: Process / pipeline context
        sc2 = MockScene(2, "Quy trình chuyển giao qua đường ống dẫn và van điều phối.", prev_recipe=recipe1)
        p2 = scene_payload(sc2, (540, 960), CaptionStyle())
        recipe2 = p2["visual_plan"]["scene_type"]
        assert recipe2 == "pipeline_pipes", f"Expected pipeline_pipes for pipeline context, got: {recipe2}"

        # Recipe 1 and Recipe 2 must be different and not always balance_scale
        assert recipe1 != recipe2
        assert recipe1 != "balance_scale" or recipe2 != "balance_scale"


def test_audit_failure_preserves_motion_not_text_focus():
    """Audit retries must gently repair layout (shrink font, clip words) but never mutate motion recipe into text_focus."""
    render_motion_path = Path(__file__).parent.parent / "pipeline" / "render_motion.py"
    src = render_motion_path.read_text(encoding="utf-8")
    assert "window.MOTION_DATA.visual_plan.scene_type = 'text_focus'" not in src, \
        "Audit retry round 2 must not force scene_type = 'text_focus'!"


def test_meta_json_scene_type_accurate_with_video():
    """Result illustration scene_type must accurately reflect the payload visual_plan recipe, not declare false motion."""
    # Verify mapping in render_motion.py
    render_motion_path = Path(__file__).parent.parent / "pipeline" / "render_motion.py"
    src = render_motion_path.read_text(encoding="utf-8")
    assert "'scene_type':(payload.get('visual_plan') or {}).get('scene_type','text_focus')" in src or \
           "'scene_type': (payload.get('visual_plan') or {}).get('scene_type', 'text_focus')" in src or \
           "'scene_type':final_scene_type" in src
