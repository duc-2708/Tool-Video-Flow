"""Offline Windows sharing violations, stale snapshots and concurrent I/O."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from unittest.mock import Mock
import pytest
from utils import atomic_io as io


@pytest.fixture(autouse=True)
def local_io_log(tmp_path, monkeypatch):
    monkeypatch.setattr(io, "LOG_PATH", tmp_path / "logs" / "atomic_io.log")


def denied(winerror=5):
    error = PermissionError("fixture sharing violation")
    error.winerror = winerror
    return error


@pytest.mark.parametrize("winerror", [5, 32])
def test_replace_retry_then_success(tmp_path, monkeypatch, winerror):
    original = os.replace
    replace = Mock(side_effect=[denied(winerror), None])
    def publish(source, target):
        replace(source, target)
        if replace.call_count == 2:
            original(source, target)
    monkeypatch.setattr(io.os, "replace", publish)
    sleep = Mock()
    monkeypatch.setattr(io.time, "sleep", sleep)
    path = tmp_path / "run_state.json"
    io.write_json_atomic(path, {"text": "Tiếng Việt", "status": "done"})
    assert replace.call_count == 2
    sleep.assert_called_once_with(.05)
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "done"
    assert not list(tmp_path.glob("*.tmp"))


def test_replace_exhausted_direct_fallback_fsync_and_warning(tmp_path, monkeypatch):
    replace = Mock(side_effect=denied())
    monkeypatch.setattr(io.os, "replace", replace)
    sleep = Mock()
    monkeypatch.setattr(io.time, "sleep", sleep)
    fsync = Mock(wraps=os.fsync)
    monkeypatch.setattr(io.os, "fsync", fsync)
    path = tmp_path / "assets.json"
    io.write_json_atomic(path, {"status": "complete"})
    assert replace.call_count == 8
    assert [call.args[0] for call in sleep.call_args_list] == list(io._DELAYS)
    assert fsync.call_count == 2
    assert json.loads(path.read_text())["status"] == "complete"
    assert not list(tmp_path.glob("*.tmp"))
    assert "ghi trực tiếp" in io.LOG_PATH.read_text(encoding="utf-8")


def test_many_threads_never_observe_partial_json(tmp_path):
    path = tmp_path / "run_state.json"
    io.write_json_atomic(path, {"n": -1, "payload": "đ" * 5000})
    def work(index):
        for _ in range(8):
            io.write_json_atomic(path, {"n": index, "payload": "đ" * 5000})
            state = io.read_json_atomic(path)
            assert state["payload"] == "đ" * 5000
            assert -1 <= state["n"] < 12
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(work, range(12)))
    assert json.loads(path.read_text(encoding="utf-8"))["n"] in range(12)
    assert not list(tmp_path.glob("*.tmp"))


def test_locked_read_and_torn_json_retry_then_previous_snapshot(tmp_path, monkeypatch):
    path = tmp_path / "run_state.json"
    io.write_json_atomic(path, {"status": "running", "steps": {}})
    previous = io.read_json_atomic(path)
    path.write_text('{"status":', encoding="utf-8")
    monkeypatch.setattr(io.time, "sleep", Mock())
    assert io.read_json_atomic(path, allow_stale=True) == previous
    # Returned snapshots are independent, and resume never trusts stale disk.
    io.read_json_atomic(path, allow_stale=True)["status"] = "wrong"
    assert io.read_json_atomic(path, allow_stale=True) == previous
    with pytest.raises(json.JSONDecodeError):
        io.read_json_atomic(path)
    original = Path.read_text
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: (_ for _ in ()).throw(denied(32)) if self == path else original(self, **kw))
    assert io.read_json_atomic(path, allow_stale=True) == previous


def test_read_recovers_after_partial_external_write(tmp_path, monkeypatch):
    path = tmp_path / "run_state.json"
    path.write_text('{"status":', encoding="utf-8")
    sleep = Mock(side_effect=lambda _: path.write_text('{"status":"done"}', encoding="utf-8"))
    monkeypatch.setattr(io.time, "sleep", sleep)
    assert io.read_json_atomic(path)["status"] == "done"
    assert sleep.call_count == 1


def test_no_snapshot_ui_uses_worker_or_waits(tmp_path, monkeypatch):
    from app.views.create_video import read_ui_state
    path = tmp_path / "run_state.json"
    path.write_text("{", encoding="utf-8")
    monkeypatch.setattr(io.time, "sleep", Mock())
    state = {"status": "running", "steps": {}}
    assert read_ui_state(tmp_path) is None
    assert read_ui_state(tmp_path, {"project": str(tmp_path), "state": state}) == state
    assert read_ui_state(tmp_path, {"project": str(tmp_path / "other"), "state": state}) is None


def test_non_transient_errors_and_non_state_reads_stay_strict(tmp_path, monkeypatch):
    monkeypatch.setattr(io.os, "replace", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        io.write_json_atomic(tmp_path / "brief.json", {})
    assert not list(tmp_path.glob("*.tmp"))
    path = tmp_path / "brief.json"
    path.write_text("{", encoding="utf-8")
    monkeypatch.setattr(io.time, "sleep", Mock())
    with pytest.raises(json.JSONDecodeError):
        io.read_json_atomic(path, allow_stale=True)


def test_cleanup_confined_and_skips_active_temps(tmp_path):
    project = tmp_path / "output" / "project"
    project.mkdir(parents=True)
    old = project / "orphan.tmp"
    old.write_text("old")
    os.utime(old, (0, 0))
    recent = project / "recent.tmp"
    recent.write_text("maybe active in another process")
    outside = tmp_path / "outside.tmp"
    outside.write_text("keep")
    with io._temporary(project / "assets.json") as (active, stream):
        assert io.cleanup_tmp_files(project) == 1
        assert active.exists() and recent.exists()
        assert io.cleanup_tmp_files(project, min_age_sec=0) == 1
        assert active.exists()
    assert not old.exists() and outside.exists()


def test_large_media_copy_falls_back_without_read_bytes(tmp_path, monkeypatch):
    source, destination = tmp_path / "input.mp4", tmp_path / "output.mp4"
    content = b"fake media" * 300000
    source.write_bytes(content)
    monkeypatch.setattr(io.os, "replace", Mock(side_effect=denied(32)))
    monkeypatch.setattr(io.time, "sleep", Mock())
    monkeypatch.setattr(Path, "read_bytes", Mock(side_effect=AssertionError("must stream")))
    io.copy_file_atomic(source, destination)
    with destination.open("rb") as stream:
        assert stream.read() == content
    assert source.exists() and not list(tmp_path.glob("*.tmp"))


def test_locked_temp_cleanup_does_not_mask_success(tmp_path, monkeypatch):
    path = tmp_path / "media.tmp"
    path.write_text("temporary")
    original = Path.unlink
    def unlink(self, **kwargs):
        if self == path:
            raise denied(32)
        return original(self, **kwargs)
    monkeypatch.setattr(Path, "unlink", unlink)
    io.discard_temp_file(path)
    assert path.exists()
    assert "Không xóa được file tạm" in io.LOG_PATH.read_text(encoding="utf-8")
