"""Tests for Scene Director (Phase 8): Presentation Mode Decisions & Guardrails."""
import json
import pytest
from pathlib import Path

from schemas.edit_plan import EditPlan
from schemas.scene_director import (
    ScenePlanResponse,
    ScenePlanItem,
    MotionBrief,
    KeyBeatBrief,
    AiClipBrief,
)
from agents.scene_director import (
    clean_prompt_en,
    validate_and_repair_scene_plan,
    build_scene_director_prompt,
    generate_heuristic_scene_plan,
    run_scene_director,
)

ROOT_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def sample_edit_plan():
    real_plan_path = ROOT_DIR / "output" / "auto-cong-nghe-d56d3ebe" / "edit_plan.json"
    if real_plan_path.is_file():
        data = json.loads(real_plan_path.read_text(encoding="utf-8"))
        return EditPlan.model_validate(data)

    # Fallback to minimal valid EditPlan
    from schemas.edit_plan import Scene, Shot
    scenes = [
        Scene(id=1, narration="Apple vừa công bố dòng MacBook Pro trang bị màn hình OLED cảm ứng đầu tiên trong lịch sử.", role="hook", shots=[Shot(duration=3.0)]),
        Scene(id=2, narration="Màn hình PROLED XDR đạt độ sáng đỉnh hai nghìn nit cùng tần số quét 120Hz.", role="explain", shots=[Shot(duration=3.0)]),
        Scene(id=3, narration="Phiên bản MacBook Pro 14 inch trang bị chip M6 tiến trình 2nm giá 54,99 triệu đồng.", role="explain", shots=[Shot(duration=3.0)]),
        Scene(id=4, narration="MacBook Pro mới chuyển từ tai thỏ sang hệ thống camera dạng Dynamic Island.", role="explain", shots=[Shot(duration=3.0)]),
        Scene(id=5, narration="Mức giá 80 triệu đồng khiến nhiều người cân nhắc nâng cấp.", role="evaluate", shots=[Shot(duration=3.0)]),
        Scene(id=6, narration="Liệu màn hình cảm ứng có thực sự cần thiết trên laptop?", role="cta", shots=[Shot(duration=3.0)]),
    ]
    return EditPlan(
        title="MacBook Pro OLED",
        format="tiktok",
        voice="vi-VN-NamMinhNeural",
        music="lofi",
        scenes=scenes
    )


def test_clean_prompt_en():
    raw_prompt = "Cinematic shot of Apple iPhone on a table with text logo and Tim Cook standing near"
    cleaned, reps = clean_prompt_en(raw_prompt)
    assert "Apple" not in cleaned
    assert "iPhone" not in cleaned
    assert "logo" not in cleaned
    assert "Tim Cook" not in cleaned
    assert "text" not in cleaned
    assert len(reps) >= 4


def test_scene_director_numeric_forces_motion(sample_edit_plan):
    # Scene 2 & Scene 3 have heavy statistics (120Hz, 2nm, 54,99 triệu)
    scene_plan = ScenePlanResponse(
        scenes=[
            ScenePlanItem(
                scene_id=1,
                mode="ai_clip",
                motion_brief=MotionBrief(visual_idea="Mở đầu", recipe_candidates=["before_after_wipe"]),
                ai_clip=AiClipBrief(prompt_en="a sleek laptop opening smoothly on a desk", fallback_recipe="before_after_wipe")
            ),
            ScenePlanItem(
                scene_id=2,
                mode="ai_clip", # Vi phạm: Cảnh 2 có 120Hz, 2000 nit làm chủ thể
                motion_brief=MotionBrief(visual_idea="Màn hình", recipe_candidates=["gauge_needle"]),
                ai_clip=AiClipBrief(prompt_en="screen glowing", fallback_recipe="gauge_needle")
            ),
            ScenePlanItem(
                scene_id=3,
                mode="hybrid", # Vi phạm: Cảnh 3 có chip 2nm, 54.99 triệu
                motion_brief=MotionBrief(visual_idea="Chip", recipe_candidates=["slot_counter"]),
                ai_clip=AiClipBrief(prompt_en="microchip macro shot", fallback_recipe="slot_counter")
            ),
            ScenePlanItem(
                scene_id=4,
                mode="motion",
                motion_brief=MotionBrief(visual_idea="Dynamic Island", recipe_candidates=["puzzle_snap"])
            ),
            ScenePlanItem(
                scene_id=5,
                mode="motion",
                motion_brief=MotionBrief(visual_idea="Cân nhắc", recipe_candidates=["balance_scale"])
            ),
            ScenePlanItem(
                scene_id=6,
                mode="motion",
                motion_brief=MotionBrief(visual_idea="Độ bền", recipe_candidates=["shield_hit"])
            ),
        ]
    )

    notes = validate_and_repair_scene_plan(scene_plan, sample_edit_plan, ai_clips_max=2)
    
    # Scene 2 & 3 must be forced to motion
    assert scene_plan.scenes[1].mode == "motion"
    assert scene_plan.scenes[2].mode == "motion"
    assert any("chứa số liệu chủ thể" in n for n in notes)


def test_scene_director_no_consecutive_ai_clips(sample_edit_plan):
    # Scene 1 and Scene 4 are qualitative (no numbers). Let's test Scene 1 and Scene 1+1 (if Scene 1 and Scene 2 were both qualitative)
    # Temporarily remove numbers from Scene 5 narration for this unit test
    plan_copy = sample_edit_plan.model_copy(deep=True)
    plan_copy.scenes[4].narration = "Thiết kế mỏng nhẹ mang lại cảm giác cầm nắm vô cùng ấn tượng."

    scene_plan = ScenePlanResponse(
        scenes=[
            ScenePlanItem(scene_id=1, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(scene_id=2, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(scene_id=3, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(
                scene_id=4,
                mode="ai_clip",
                motion_brief=MotionBrief(recipe_candidates=["puzzle_snap"]),
                ai_clip=AiClipBrief(prompt_en="sleek display notch morphing", fallback_recipe="puzzle_snap")
            ),
            ScenePlanItem(
                scene_id=5,
                mode="hybrid", # Vi phạm: Liền kề cảnh 4 (ai_clip)
                motion_brief=MotionBrief(recipe_candidates=["balance_scale"]),
                ai_clip=AiClipBrief(prompt_en="sleek laptop design", fallback_recipe="balance_scale")
            ),
            ScenePlanItem(scene_id=6, mode="motion", motion_brief=MotionBrief(recipe_candidates=["shield_hit"])),
        ]
    )

    notes = validate_and_repair_scene_plan(scene_plan, plan_copy, ai_clips_max=2)

    # Scene 5 must be demoted to motion
    assert scene_plan.scenes[3].mode == "ai_clip"
    assert scene_plan.scenes[4].mode == "motion"
    assert any("tránh 2 clip AI liền kề" in n for n in notes)



def test_scene_director_max_clip_ratio(sample_edit_plan):
    scene_plan = ScenePlanResponse(
        scenes=[
            ScenePlanItem(scene_id=1, mode="ai_clip", motion_brief=MotionBrief(recipe_candidates=["before_after_wipe"]), ai_clip=AiClipBrief(prompt_en="laptop opening", fallback_recipe="before_after_wipe")),
            ScenePlanItem(scene_id=2, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(scene_id=3, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(scene_id=4, mode="ai_clip", motion_brief=MotionBrief(recipe_candidates=["puzzle_snap"]), ai_clip=AiClipBrief(prompt_en="display morphing", fallback_recipe="puzzle_snap")),
            ScenePlanItem(scene_id=5, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(scene_id=6, mode="hybrid", motion_brief=MotionBrief(recipe_candidates=["shield_hit"]), ai_clip=AiClipBrief(prompt_en="protective shield", fallback_recipe="shield_hit")),
        ]
    )

    notes = validate_and_repair_scene_plan(scene_plan, sample_edit_plan, ai_clips_max=1)
    
    # Must keep at most 1 AI scene (Hook Scene 1)
    ai_count = sum(1 for s in scene_plan.scenes if s.mode in ("ai_clip", "hybrid"))
    assert ai_count <= 1
    assert scene_plan.scenes[0].mode == "ai_clip"
    assert scene_plan.scenes[3].mode == "motion"
    assert scene_plan.scenes[5].mode == "motion"
    assert any("vượt hạn mức AI clip" in n for n in notes)


def test_scene_director_fallback_recipe_assignment(sample_edit_plan):
    scene_plan = ScenePlanResponse(
        scenes=[
            ScenePlanItem(
                scene_id=1,
                mode="ai_clip",
                motion_brief=MotionBrief(recipe_candidates=["before_after_wipe"]),
                ai_clip=AiClipBrief(prompt_en="cinematic laptop opening", fallback_recipe="") # Thiếu fallback_recipe
            ),
            ScenePlanItem(scene_id=2, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(scene_id=3, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(scene_id=4, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(scene_id=5, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(scene_id=6, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
        ]
    )

    validate_and_repair_scene_plan(scene_plan, sample_edit_plan, ai_clips_max=2)
    assert scene_plan.scenes[0].ai_clip.fallback_recipe == "before_after_wipe"


def test_scene_director_run_e2e(tmp_path, sample_edit_plan):
    project_dir = tmp_path / "test_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    res = run_scene_director(project_dir, sample_edit_plan)
    assert res is not None
    assert len(res.scenes) == len(sample_edit_plan.scenes)
    
    saved_file = project_dir / "scene_plan.json"
    assert saved_file.is_file()
    
    data = json.loads(saved_file.read_text(encoding="utf-8"))
    assert "scenes" in data
    assert len(data["scenes"]) == 6
    assert data["ai_label_required"] is True
