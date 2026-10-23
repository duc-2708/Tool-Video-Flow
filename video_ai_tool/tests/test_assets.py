# file: tests/test_assets.py
"""Assets offline: audio thật local, timing, fallback, cache và thay riêng shot."""
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock
import pytest
from imageio_ffmpeg import get_ffmpeg_exe
from config.settings import Settings
from pipeline.assets import load_assets, refresh_shot, retime_scene, run_assets, safe_asset_path
from pipeline.stock_assets import MediaDownloader, allowed_media_url
from providers.tts_edge import EdgeTTSProvider, audio_duration
from schemas.assets import AssetsManifest, ResolvedEditPlan
from schemas.edit_plan import EditPlan
from tests.test_director import fixture_plan
from utils.cache import write_json
from utils.diagnostics import Diagnostics


@pytest.fixture
def sample_mp3(tmp_path: Path) -> Path:
    path = tmp_path / "sample.mp3"
    subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=2.2", str(path)], check=True, capture_output=True, timeout=20)
    return path


@pytest.fixture
def asset_settings(tmp_path: Path) -> Settings:
    return Settings(root_dir=tmp_path, retry_attempts=1)


@pytest.mark.parametrize("duration", [1.5, 1.54, 2.99, 5.5, 12.37, 40.2])
def test_retime_matches_real_length_and_keeps_shot_bounds(duration: float) -> None:
    scene = EditPlan.model_validate(fixture_plan()).scenes[0]
    resolved = retime_scene(scene, duration)
    assert abs(resolved.duration_sec - duration) < 0.000001
    assert all(1.5 <= shot.duration_sec <= 4 for shot in resolved.shots)
    assert scene.duration_sec == 3


def test_resolved_hook_can_exceed_three_seconds_without_weakening_original_schema() -> None:
    plan = EditPlan.model_validate(fixture_plan())
    data = plan.model_dump(mode="json")
    data["scenes"][0] = retime_scene(plan.scenes[0], 5.5).model_dump(mode="json")
    repaired=EditPlan.model_validate(data)
    assert repaired.scenes[0].duration_sec==3 and repaired.validation_events
    resolved = ResolvedEditPlan.model_validate({**data, "source_plan_hash": "fixture"})
    assert resolved.scenes[0].duration_sec == 5.5


def test_edge_tts_audio_cache_and_voice_invalidation(sample_mp3: Path, asset_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    class FakeCommunicate:
        def __init__(self, text: str, voice: str, **kwargs):
            calls.append((text, voice, kwargs))
        def save_sync(self, path: str):
            shutil.copyfile(sample_mp3, path)
    monkeypatch.setattr("providers.tts_edge.edge_tts.Communicate", FakeCommunicate)
    tts = EdgeTTSProvider(asset_settings, Diagnostics(asset_settings.logs_dir))
    first = asset_settings.output_dir / "test/audio/scene_1.mp3"
    duration = tts.synthesize("Fixture", "vi-VN-HoaiMyNeural", first)
    tts.synthesize("Fixture", "vi-VN-HoaiMyNeural", first)
    assert duration == audio_duration(first) and len(calls) == 1
    tts.synthesize("Fixture", "vi-VN-NamMinhNeural", first)
    assert len(calls) == 2
    assert calls[0][2]["connect_timeout"] == asset_settings.request_timeout_sec


def test_pipeline_keeps_original_and_refreshes_only_one_shot(asset_settings: Settings, sample_mp3: Path) -> None:
    plan_path = asset_settings.output_dir / "test/edit_plan.json"
    write_json(plan_path, fixture_plan())
    original = plan_path.read_bytes()
    class FakeTTS:
        def synthesize(self, text: str, voice: str, destination: Path) -> float:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sample_mp3, destination)
            return audio_duration(destination)
    progress = []
    result = run_assets(plan_path, asset_settings, tts=FakeTTS(), providers=[],
                        progress=lambda *args: progress.append(args))
    _, resolved, manifest = load_assets(plan_path)
    assert result.name == "assets.json" and manifest.status == "complete"
    assert len(manifest.scenes) == 8 and progress[-1][0] == 8
    assert plan_path.read_bytes() == original
    for scene, data in zip(resolved.scenes, manifest.scenes):
        assert scene.duration_sec == pytest.approx(data.audio_duration_sec)
        assert all(asset.fallback and asset.media_type == "color" for asset in data.shots)
    audio_before = [(plan_path.parent / scene.audio_path).read_bytes() for scene in manifest.scenes]
    other_before = manifest.scenes[1].model_dump()
    refresh_shot(plan_path, asset_settings, 1, 1, "editing software", providers=[])
    _, changed, assets = load_assets(plan_path)
    assert assets.scenes[0].shots[0].query == "editing software"
    assert assets.scenes[1].model_dump() == other_before
    assert audio_before == [(plan_path.parent / scene.audio_path).read_bytes() for scene in assets.scenes]
    assert plan_path.read_bytes() == original
    run_assets(plan_path, asset_settings, tts=FakeTTS(), providers=[])
    assert load_assets(plan_path)[2].scenes[0].shots[0].query == "editing software"
    assert "nền màu/chữ" in (plan_path.parent / "credits.txt").read_text(encoding="utf-8")


def test_tts_failure_is_explicit_silence_and_remains_renderable(asset_settings: Settings) -> None:
    plan_path = asset_settings.output_dir / "test/edit_plan.json"
    write_json(plan_path, fixture_plan())
    tts = Mock()
    tts.synthesize.side_effect = TimeoutError("Fixture network timeout")
    result = run_assets(plan_path, asset_settings, tts=tts, providers=[])
    manifest = AssetsManifest.model_validate_json(result.read_text(encoding="utf-8"))
    assert manifest.status == "complete" and all(scene.audio_path and scene.audio_silent for scene in manifest.scenes)
    assert all(scene.audio_error for scene in manifest.scenes)
    assert all(scene.audio_warnings for scene in manifest.scenes)
    assert "không có giọng đọc" in (plan_path.parent/"report.md").read_text(encoding="utf-8")
    from pipeline.run_all import asset_files
    files,warnings=asset_files(plan_path.parent,plan_path)
    assert files and warnings
    assert tts.synthesize.call_count == 8


@pytest.mark.parametrize("url", ["https://www.youtube.com/a", "https://tiktok.com/a", "https://facebook.com/a",
                                 "https://cdn.pixabay.com.evil/a", "https://cdn.pixabay.com@evil.example/a"])
def test_social_and_other_hosts_rejected(url: str) -> None:
    assert not allowed_media_url(url, "pixabay")


def test_asset_paths_cannot_read_outside_project(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        safe_asset_path(tmp_path, "../.env")


def test_short_audio_is_padded_before_timing(asset_settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    short = tmp_path / "short.mp3"
    subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=0.3", str(short)], check=True, capture_output=True, timeout=20)
    communicator = Mock()
    communicator.save_sync.side_effect = lambda target: shutil.copyfile(short, target)
    monkeypatch.setattr("providers.tts_edge.edge_tts.Communicate", Mock(return_value=communicator))
    tts = EdgeTTSProvider(asset_settings, Diagnostics(asset_settings.logs_dir))
    path = tmp_path / "project/audio/scene_1.mp3"
    duration = tts.synthesize("Ngắn", "vi-VN-HoaiMyNeural", path)
    assert 1.5 <= duration < 2 and duration == audio_duration(path)
