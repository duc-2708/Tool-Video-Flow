"""Atomic local writes with Windows sharing-violation recovery.

Locks are per canonical destination, shared by readers and writers in this
process. run_all.lock additionally serializes orchestrators across processes.
Only UI readers may opt into a previous good snapshot; resume must read disk.
"""
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time

LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "atomic_io.log"
_guard = threading.RLock()
_locks = {}
_active = set()
_snapshots = OrderedDict()
_DELAYS = (.05, .1, .2, .4, .6, .8, 1.)


def _key(path):
    return os.path.normcase(str(Path(path).resolve()))


def path_lock(path):
    with _guard:
        return _locks.setdefault(_key(path), threading.RLock())


def _warning(action, error=None):
    # Never log data, paths, exception messages, or configuration/credentials.
    detail = f" {type(error).__name__}; winerror={getattr(error, 'winerror', None)}" if error else ""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _guard, LOG_PATH.open("a", encoding="utf-8") as stream:
            stream.write(f"[{datetime.now(timezone.utc).isoformat()}] Cảnh báo I/O: {action}.{detail}\n")
    except OSError:
        pass  # A logging failure must not mask the original I/O operation.


def _retry(operation):
    for attempt in range(8):
        try:
            return operation()
        except OSError as error:
            if not (isinstance(error, PermissionError) or getattr(error, "winerror", None) in (5, 32)) or attempt == 7:
                raise
            time.sleep(_DELAYS[attempt])


def discard_temp_file(path):
    try:
        Path(path).unlink(missing_ok=True)
    except OSError as error:
        _warning("Không xóa được file tạm; sẽ dọn lại khi khởi động", error)


@contextmanager
def _temporary(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Register before cleanup can see the newly created file.
    with _guard:
        fd, name = tempfile.mkstemp(prefix="." + path.name + "-", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        _active.add(_key(temporary))
    try:
        with os.fdopen(fd, "wb") as stream:
            yield temporary, stream
    finally:
        with _guard:
            discard_temp_file(temporary)
            _active.discard(_key(temporary))


def replace_file_retry(source, destination):
    """Publish a closed media/temp file; stream fallback without loading MP4s."""
    source, destination = Path(source), Path(destination)
    with path_lock(destination):
        try:
            _retry(lambda: os.replace(source, destination))
        except OSError as error:
            if not (isinstance(error, PermissionError) or getattr(error, "winerror", None) in (5, 32)):
                raise
            _warning("Thay thế file bị khóa sau 8 lần; chuyển sang ghi trực tiếp", error)
            def direct():
                with source.open("rb") as incoming, destination.open("wb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
            _retry(direct)
            discard_temp_file(source)


def _remember(path, data):
    with _guard:
        key = _key(path)
        _snapshots[key] = deepcopy(data)
        _snapshots.move_to_end(key)
        while len(_snapshots) > 256:
            _snapshots.popitem(last=False)


def write_text_atomic(path, text):
    write_bytes_atomic(path,text.encode("utf-8"))


def write_bytes_atomic(path, encoded):
    path = Path(path)
    with path_lock(path), _temporary(path) as (temporary, stream):
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()  # Required on Windows before replacement.
        replace_file_retry(temporary, path)


def write_json_atomic(path, data):
    """Persist JSON or raise if even direct writing fails (no false success)."""
    path = Path(path)
    with path_lock(path):
        write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))
        if path.name == "run_state.json":
            _remember(path, data)


def copy_file_atomic(source, destination):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        return
    with path_lock(destination), _temporary(destination) as (temporary, stream):
        with source.open("rb") as incoming:
            shutil.copyfileobj(incoming, stream, 1024 * 1024)
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()
        replace_file_retry(temporary, destination)


def read_json_atomic(path, *, allow_stale=False):
    path = Path(path)
    with path_lock(path):
        for attempt in range(4):
            try:
                if path.is_symlink():
                    raise ValueError("Không đọc artifact qua liên kết tượng trưng.")
                if path.stat().st_size > 20_000_000:
                    raise ValueError("Artifact vượt giới hạn đọc 20 MB.")
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Artifact phải là một JSON object.")
                if path.name == "run_state.json":
                    _remember(path, data)
                return data
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
                if attempt < 3:
                    time.sleep(.05 * (attempt + 1))
                    continue
                if allow_stale and path.name == "run_state.json":
                    with _guard:
                        previous = _snapshots.get(_key(path))
                        if previous is not None:
                            _warning("Đọc trạng thái tạm lỗi; dùng bản đọc tốt gần nhất", error)
                            return deepcopy(previous)
                raise


def cleanup_tmp_files(project, *, min_age_sec=3600):
    """Remove old orphan *.tmp files, confined to project; never follow links.

One hour grace protects legacy temps produced by another process/page. Active
temps from these helpers are protected even when min_age_sec is zero.
"""
    project = Path(project)
    if project.is_symlink() or not project.is_dir():
        return 0
    root = project.resolve()
    removed = 0
    for path in root.rglob("*.tmp"):
        with _guard:
            try:
                if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
                    continue
                if _key(path) in _active or time.time() - path.stat().st_mtime < min_age_sec:
                    continue
                path.unlink()
                removed += 1
            except OSError as error:
                _warning("Bỏ qua file tạm đang khóa khi dọn project", error)
    return removed
