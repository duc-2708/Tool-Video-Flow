import pytest
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock
from imageio_ffmpeg import get_ffmpeg_exe

from config.settings import Settings
from pipeline.assets import run_assets, load_assets, sync_visual_plan_assets
from pipeline.asset_hashes import (
    compute_audio_hash, compute_clip_hash, compute_visual_hash,
    compute_scene_audio_hash, detect_plan_changes, source_script_hash
)
from schemas.assets import AssetsManifest, ResolvedEditPlan
from schemas.edit_plan import EditPlan
from schemas.motion_scene import MotionScenePlan
from tests.test_director import fixture_plan
from utils.cache import write_json
from pipeline.projects import read_json


@pytest.fixture
def sample_mp3(tmp_path: Path) -> Path:
    path = tmp_path / "sample.mp3"
    subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=2.2", str(path)], check=True, capture_output=True, timeout=20)
    return path


class FakeTTS:
    """Mock TTS provider that records calls and produces silent dummy audio."""
    def __init__(self, sample_mp3: Path):
        self.sample_mp3 = sample_mp3
        self.calls = []

    def synthesize(self, text: str, voice: str, path: Path, scene_id: int = 1, duration_sec: float = 3.0) -> float:
        self.calls.append((scene_id, text, voice))
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.sample_mp3, path)
        return 3.0


@pytest.fixture
def test_project(tmp_path: Path, sample_mp3: Path) -> tuple[Path, Settings, FakeTTS]:
    proj = tmp_path / "test_proj"
    proj.mkdir(parents=True, exist_ok=True)
    plan_data = fixture_plan()
    write_json(proj / "edit_plan.json", plan_data)
    settings = Settings(root_dir=tmp_path, retry_attempts=1)
    fake_tts = FakeTTS(sample_mp3)
    return proj, settings, fake_tts


def test_visual_plan_change_does_not_invalidate_assets_or_rerun_tts(test_project: tuple[Path, Settings, FakeTTS]):
    proj, settings, fake_tts = test_project
    plan_path = proj / "edit_plan.json"

    # 1. Run assets initially
    run_assets(plan_path, settings, tts=fake_tts)
    initial_tts_calls = len(fake_tts.calls)
    assert initial_tts_calls == len(fixture_plan()['scenes'])

    # 2. Modify only visual_plan / recipe (narration & voice remain identical)
    plan = EditPlan.model_validate(read_json(plan_path))
    plan.scenes[0].visual_plan = MotionScenePlan(
        scene_type="slot_counter",
        layout="center_hero",
        beats=[],
        data={"value": 500, "text": "500 tỷ"}
    )
    plan.scenes[1].visual_plan = MotionScenePlan(
        scene_type="balance_scale",
        layout="split_2",
        beats=[],
        data={"value": 300, "text": "So sánh vốn"}
    )
    write_json(plan_path, plan.model_dump(mode="json"))

    # 3. Verify load_assets DOES NOT fail with 'Edit Plan gốc đã đổi'
    orig, res, manifest = load_assets(plan_path)
    assert orig is not None
    assert manifest is not None

    # 4. Run assets again: TTS must NOT be called for any scene because audio_hash is unchanged!
    fake_tts.calls.clear()
    run_assets(plan_path, settings, tts=fake_tts)
    assert len(fake_tts.calls) == 0, f"Expected 0 TTS calls on visual edit, got {len(fake_tts.calls)}"


def test_change_narration_single_scene_only_reruns_that_scene_tts(test_project: tuple[Path, Settings, FakeTTS]):
    proj, settings, fake_tts = test_project
    plan_path = proj / "edit_plan.json"

    # 1. Initial assets run
    run_assets(plan_path, settings, tts=fake_tts)
    fake_tts.calls.clear()

    # 2. Change narration ONLY for Scene 2
    plan = EditPlan.model_validate(read_json(plan_path))
    plan.scenes[1].narration = "Lời đọc mới hoàn toàn cho cảnh 2 để kiểm tra tái sử dụng audio."
    write_json(plan_path, plan.model_dump(mode="json"))

    # 3. load_assets must detect exactly Scene 2 changed
    manifest = AssetsManifest.model_validate(read_json(proj / "assets.json"))
    changes = detect_plan_changes(manifest, plan)
    assert changes["audio_changed"] is True
    assert 2 in changes["changed_audio_scenes"]
    assert 1 not in changes["changed_audio_scenes"]
    assert "Cảnh 2: Lời đọc kịch bản đã thay đổi" in changes["explanation"]

    # 4. load_assets raises clear error detailing Scene 2
    with pytest.raises(ValueError, match="Cảnh 2: Lời đọc kịch bản đã thay đổi"):
        load_assets(plan_path)

    # 5. Rerun run_assets: TTS must be called ONLY for Scene 2! Scene 1 is reused!
    run_assets(plan_path, settings, tts=fake_tts)
    called_scene_ids = [call[0] for call in fake_tts.calls]
    assert called_scene_ids == [2], f"Expected only Scene 2 TTS call, got {called_scene_ids}"


def test_ai_clip_prompt_change_leaves_audio_hash_unchanged(test_project: tuple[Path, Settings, FakeTTS]):
    proj, settings, fake_tts = test_project
    plan_path = proj / "edit_plan.json"

    plan = EditPlan.model_validate(read_json(plan_path))
    hash_audio_before = compute_audio_hash(plan)
    hash_clip_before = compute_clip_hash(plan)

    # Modify ai_prompt on Scene 1, Shot 1
    plan.scenes[0].shots[0].ai_prompt = "Cinematic slow motion shot of tech data server room"
    hash_audio_after = compute_audio_hash(plan)
    hash_clip_after = compute_clip_hash(plan)

    # Audio hash MUST remain unchanged!
    assert hash_audio_before == hash_audio_after
    # Clip hash MUST change!
    assert hash_clip_before != hash_clip_after


def test_sync_visual_plan_assets_option(test_project: tuple[Path, Settings, FakeTTS]):
    proj, settings, fake_tts = test_project
    plan_path = proj / "edit_plan.json"

    run_assets(plan_path, settings, tts=fake_tts)

    # Update visual plan
    plan = EditPlan.model_validate(read_json(plan_path))
    plan.scenes[0].visual_plan = MotionScenePlan(
        scene_type="terminal_command_run",
        layout="center_hero",
        beats=[],
        data={"text": "echo hello"}
    )
    write_json(plan_path, plan.model_dump(mode="json"))

    # Call option: Giữ audio cũ, chỉ dựng lại hình
    synced_path = sync_visual_plan_assets(plan_path, settings)
    assert synced_path.exists()

    # Verify load_assets now passes and visual_plan is updated
    orig, res, manifest = load_assets(plan_path)
    assert res.scenes[0].visual_plan.scene_type == "terminal_command_run"
