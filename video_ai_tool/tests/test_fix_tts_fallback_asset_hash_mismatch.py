"""Regression test: TTS fallback voice and media type resolving must not trigger false positive Asset mismatch errors."""
import pytest
from pathlib import Path
from schemas.assets import AssetsManifest, SceneAssets, ShotAsset
from schemas.edit_plan import EditPlan, Scene, Shot, Music
from pipeline.asset_hashes import detect_plan_changes, source_script_hash, compute_audio_hash
from editor.timeline import build_timeline


def test_tts_fallback_voice_not_flagged_as_user_voice_change():
    """Verify that when TTS falls back to a backup voice with warning, detect_plan_changes doesn't flag audio_changed."""
    plan = EditPlan(
        title="Tin tức công nghệ",
        voice="vi-VN-HoaiMyNeural",
        format="tiktok",
        music=Music(mood="tech", volume=0.5),
        scenes=[
            Scene(
                id=1,
                role="hook",
                narration="Đây là câu hook mở màn kịch bản công nghệ",
                shots=[Shot(type="stock_video", query="hacker technology", duration_sec=3.5, effect="none", text_overlay="Cảnh báo an ninh")]
            ),
            Scene(
                id=2,
                role="development",
                narration="Đây là câu thứ hai phân tích chi tiết lỗ hổng",
                shots=[Shot(type="stock_video", query="server database", duration_sec=4.0, effect="none", text_overlay="Lỗ hổng hệ thống")]
            )
        ]
    )

    src_hash = source_script_hash(plan)
    aud_hash = compute_audio_hash(plan)

    # Manifest with TTS fallback to NamMinhNeural recorded in warnings
    manifest = AssetsManifest(
        source_plan_hash=src_hash,
        resolved_plan_hash="resolved_fake_hash",
        status="complete",
        audio_hash=aud_hash,
        warnings=[],
        scenes=[
            SceneAssets(
                scene_id=1,
                audio_path="audio/scene_1.mp3",
                audio_duration_sec=3.5,
                audio_error=None,
                audio_silent=False,
                audio_voice="vi-VN-NamMinhNeural",
                audio_warnings=["Cảnh 1, đoạn 1: dùng giọng dự phòng vi-VN-NamMinhNeural do TTS giọng vi-VN-HoaiMyNeural lỗi."],
                shots=[ShotAsset(shot_id=1, query="hacker technology", media_type="color", path="clips/scene_1_shot_1.mp4", provider="generated", fallback=True)]
            ),
            SceneAssets(
                scene_id=2,
                audio_path="audio/scene_2.mp3",
                audio_duration_sec=4.0,
                audio_error=None,
                audio_silent=False,
                audio_voice="vi-VN-HoaiMyNeural",
                audio_warnings=[],
                shots=[ShotAsset(shot_id=1, query="server database", media_type="video", path="clips/scene_2_shot_1.mp4", provider="pixabay", fallback=False)]
            )
        ]
    )

    changes = detect_plan_changes(manifest, plan)
    # Must NOT report audio_changed = True
    assert not changes["audio_changed"], f"TTS fallback was incorrectly flagged as audio_changed: {changes['explanation']}"
    assert changes["voice_changed"] is None
    assert not changes["clips_changed"]


def test_real_project_d2297dfb_timeline_builds_without_exception():
    """Verify project auto-cong-nghe-d2297dfb timeline builds smoothly without asset mismatch exception."""
    proj = Path("output/auto-cong-nghe-d2297dfb")
    if (proj / "edit_plan.resolved.json").is_file() and (proj / "assets.json").is_file():
        tl = build_timeline(proj / "edit_plan.resolved.json")
        assert tl is not None
        assert len(tl.scenes) == 6
        assert tl.duration > 40.0
