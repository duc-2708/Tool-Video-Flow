"""Unit & Integration tests for Hybrid Rendering Engine (Phase 8)."""
import json
from pathlib import Path
import pytest
from PIL import Image

from config.settings import Settings
from pipeline.hybrid_render import (
    calculate_luma,
    check_subtitle_contrast,
    apply_caption_gradient,
    apply_vignette,
    process_clip_to_frames,
    prepare_scene_hybrid_payload,
)
from schemas.scene_director import ScenePlanResponse, ScenePlanItem, MotionBrief, AiClipBrief


def test_subtitle_contrast_and_gradient_protection():
    # Create bright image (simulating bright AI clip)
    bright_img = Image.new("RGB", (1080, 1920), (220, 220, 220))
    initial_luma = check_subtitle_contrast(bright_img, y_start=1380, y_end=1700)
    assert initial_luma > 200, "Initial white image should have high luminance"

    # Apply caption gradient
    protected_img = apply_caption_gradient(bright_img, y_start=1220, y_end=1750, max_alpha=210)
    final_luma = check_subtitle_contrast(protected_img, y_start=1380, y_end=1700)

    # Subtitle zone must be darkened enough for WCAG AA (luma < 80)
    assert final_luma < 80, f"Protected subtitle zone luma ({final_luma}) must be < 80"


def test_apply_vignette():
    img = Image.new("RGB", (360, 640), (150, 150, 150))
    vignetted = apply_vignette(img, strength=0.5)

    # Center should remain brighter than corners
    center_pixel = vignetted.getpixel((180, 320))
    corner_pixel = vignetted.getpixel((10, 10))

    assert center_pixel[0] > corner_pixel[0], "Center should be brighter than corners"
    assert corner_pixel[0] < 120, "Corners must be noticeably darkened"


def test_ai_clip_mode_off_returns_pure_motion(tmp_path):
    # Prepare mock project with scene_plan.json
    sp = ScenePlanResponse(
        style_prefix_en="cinematic",
        ai_label_required=True,
        scenes=[
            ScenePlanItem(
                scene_id=1,
                mode="hybrid",
                rationale="test",
                motion_brief=MotionBrief(
                    visual_idea="test idea",
                    recipe_candidates=["balance_scale"],
                    metaphor_link="scale",
                    key_beats=[]
                ),
                ai_clip=AiClipBrief(
                    prompt_en="a glowing technology device",
                    negative_en="text, letters",
                    duration_sec=4,
                    camera="pan",
                    fallback_recipe="balance_scale"
                )
            )
        ]
    )
    (tmp_path / "scene_plan.json").write_text(sp.model_dump_json(), encoding="utf-8")

    settings = Settings(ai_clip_mode="off")
    res = prepare_scene_hybrid_payload(
        scene_id=1,
        scene_duration=5.0,
        project_dir=tmp_path,
        settings=settings,
    )

    assert res["mode"] == "motion"
    assert len(res["ai_backgrounds"]) == 0
    assert res["fallback_to_motion"] is False
    assert res["badge_label"] is None


def test_fallback_when_clip_missing(tmp_path):
    sp = ScenePlanResponse(
        style_prefix_en="cinematic",
        ai_label_required=True,
        scenes=[
            ScenePlanItem(
                scene_id=1,
                mode="hybrid",
                rationale="test",
                motion_brief=MotionBrief(
                    visual_idea="test",
                    recipe_candidates=["slot_counter"],
                    metaphor_link="numbers",
                    key_beats=[]
                ),
                ai_clip=AiClipBrief(
                    prompt_en="a futuristic laboratory",
                    negative_en="text",
                    duration_sec=4,
                    camera="static",
                    fallback_recipe="slot_counter"
                )
            )
        ]
    )
    (tmp_path / "scene_plan.json").write_text(sp.model_dump_json(), encoding="utf-8")

    # In manual mode with empty ai_clips_manual/
    (tmp_path / "ai_clips_manual").mkdir()
    settings = Settings(ai_clip_mode="manual")

    res = prepare_scene_hybrid_payload(
        scene_id=1,
        scene_duration=5.0,
        project_dir=tmp_path,
        settings=settings,
    )

    assert res["mode"] == "motion"
    assert res["fallback_to_motion"] is True
    assert res["fallback_recipe"] == "slot_counter"
    assert len(res["ai_backgrounds"]) == 0
    assert "fallback" in res["reason"].lower() or "không tìm thấy" in res["reason"].lower()


def test_process_clip_to_frames_with_real_clip():
    real_clip = Path("output/auto-cong-nghe-d56d3ebe/ai_clips_manual/scene_1.mp4")
    if not real_clip.is_file():
        pytest.skip("Test video scene_1.mp4 not found in output/auto-cong-nghe-d56d3ebe")

    # Process 3 seconds at 8 fps = 24 frames
    frames = process_clip_to_frames(
        clip_path=real_clip,
        scene_duration=3.0,
        mode="hybrid",
        fps=8,
        target_width=270,
        target_height=480,
    )

    assert len(frames) == 24
    assert frames[0].startswith("data:image/jpeg;base64,")


def test_prepare_scene_hybrid_payload_success_manual(tmp_path):
    real_clip = Path("output/auto-cong-nghe-d56d3ebe/ai_clips_manual/scene_1.mp4")
    if not real_clip.is_file():
        pytest.skip("Test video scene_1.mp4 not found")

    manual_dir = tmp_path / "ai_clips_manual"
    manual_dir.mkdir()
    import shutil
    shutil.copy2(real_clip, manual_dir / "scene_1.mp4")

    sp = ScenePlanResponse(
        style_prefix_en="cinematic",
        ai_label_required=True,
        scenes=[
            ScenePlanItem(
                scene_id=1,
                mode="hybrid",
                rationale="test",
                motion_brief=MotionBrief(
                    visual_idea="test idea",
                    recipe_candidates=["balance_scale"],
                    metaphor_link="scale",
                    key_beats=[]
                ),
                ai_clip=AiClipBrief(
                    prompt_en="a glowing device",
                    negative_en="text",
                    duration_sec=4,
                    camera="pan",
                    fallback_recipe="balance_scale"
                )
            )
        ]
    )
    (tmp_path / "scene_plan.json").write_text(sp.model_dump_json(), encoding="utf-8")

    settings = Settings(ai_clip_mode="manual")
    res = prepare_scene_hybrid_payload(
        scene_id=1,
        scene_duration=4.0,
        project_dir=tmp_path,
        settings=settings,
    )

    assert res["mode"] == "hybrid"
    assert res["fallback_to_motion"] is False
    assert res["badge_label"] == "hình mô phỏng"
    assert len(res["ai_backgrounds"]) == 1
    bg = res["ai_backgrounds"][0]
    assert bg["mode"] == "hybrid"
    assert bg["badge"] == "hình mô phỏng"
    assert len(bg["frames"]) == 32  # 4s * 8fps
