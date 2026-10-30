"""Tests for AI Clip Manager (Phase 8 Step b): Governance, Manual Imports & Caching."""
import json
import pytest
from pathlib import Path

from config.settings import Settings, get_settings
from schemas.scene_director import ScenePlanResponse, ScenePlanItem, MotionBrief, AiClipBrief
from pipeline.ai_clip_manager import (
    get_manual_clip_path,
    calculate_clip_cache_key,
    find_cached_ai_clip,
    estimate_ai_clips_cost,
    resolve_scene_ai_clip,
    save_prompt_approvals,
    load_prompt_approvals,
)


@pytest.fixture
def sample_scene_plan():
    return ScenePlanResponse(
        scenes=[
            ScenePlanItem(
                scene_id=1,
                mode="ai_clip",
                motion_brief=MotionBrief(recipe_candidates=["before_after_wipe"]),
                ai_clip=AiClipBrief(
                    prompt_en="cinematic shot representing modern laptop concept, subtle lighting",
                    fallback_recipe="before_after_wipe",
                    duration_sec=4
                )
            ),
            ScenePlanItem(
                scene_id=2,
                mode="motion",
                motion_brief=MotionBrief(recipe_candidates=["gauge_needle"])
            ),
            ScenePlanItem(
                scene_id=3,
                mode="hybrid",
                motion_brief=MotionBrief(recipe_candidates=["slot_counter"]),
                ai_clip=AiClipBrief(
                    prompt_en="microchip macro shot, high tech clean room",
                    fallback_recipe="slot_counter",
                    duration_sec=4
                )
            )
        ]
    )


def test_calculate_clip_cache_key():
    k1 = calculate_clip_cache_key("a sleek laptop", "veo-3.1", 4)
    k2 = calculate_clip_cache_key("a sleek laptop", "veo-3.1", 4)
    k3 = calculate_clip_cache_key("a different prompt", "veo-3.1", 4)
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 64


def test_ai_clip_cost_estimation(sample_scene_plan):
    settings = get_settings().model_copy(update={"ai_clips_max_per_video": 2, "ai_clip_model": "veo-3.1"})
    est = estimate_ai_clips_cost(sample_scene_plan, settings)
    assert est["count"] == 2
    assert est["total_cost_vnd"] == 2 * est["unit_cost_vnd"]
    assert est["estimated_wait_sec"] == 120


def test_ai_clip_mode_off_fallbacks(tmp_path, sample_scene_plan):
    settings = get_settings().model_copy(update={"ai_clip_mode": "off"})
    res = resolve_scene_ai_clip(tmp_path, sample_scene_plan.scenes[0], settings=settings)
    assert res["resolved"] is False
    assert res["fallback_to_motion"] is True
    assert res["recipe"] == "before_after_wipe"
    assert "AI_CLIP_MODE=off" in res["reason"]


def test_ai_clip_mode_manual_with_file(tmp_path, sample_scene_plan):
    manual_dir = tmp_path / "ai_clips_manual"
    manual_dir.mkdir(parents=True, exist_ok=True)
    
    # Create fake manual mp4 file
    test_clip = manual_dir / "scene_1.mp4"
    test_clip.write_bytes(b"\x00" * 2048) # > 1024 bytes

    settings = get_settings().model_copy(update={"ai_clip_mode": "manual"})
    res = resolve_scene_ai_clip(tmp_path, sample_scene_plan.scenes[0], settings=settings)
    
    assert res["resolved"] is True
    assert res["fallback_to_motion"] is False
    assert res["source"] == "AI_manual"
    assert res["ai_generated"] is True
    assert res["label"] == "AI"
    assert "clips/scene_1_ai_manual.mp4" in res["clip_path"]
    
    dest_file = tmp_path / res["clip_path"]
    assert dest_file.is_file()


def test_ai_clip_mode_manual_missing_file_fallbacks(tmp_path, sample_scene_plan):
    settings = get_settings().model_copy(update={"ai_clip_mode": "manual"})
    # No file in ai_clips_manual
    res = resolve_scene_ai_clip(tmp_path, sample_scene_plan.scenes[0], settings=settings)
    assert res["resolved"] is False
    assert res["fallback_to_motion"] is True
    assert res["recipe"] == "before_after_wipe"
    assert "Không tìm thấy clip nhập tay" in res["reason"]


def test_prompt_approval_persistence(tmp_path):
    approvals = {
        1: {"approved": True, "prompt_en": "cinematic laptop opening"},
        3: {"approved": False, "prompt_en": "macro chip"}
    }
    save_prompt_approvals(tmp_path, approvals)
    loaded = load_prompt_approvals(tmp_path)
    assert loaded[1]["approved"] is True
    assert loaded[1]["prompt_en"] == "cinematic laptop opening"
    assert loaded[3]["approved"] is False
