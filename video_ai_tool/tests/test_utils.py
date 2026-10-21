# file: tests/test_utils.py
"""Kiểm tra cache, cấu hình và phân loại retry mà không gọi mạng."""
import json
import os
import subprocess
import sys
from pathlib import Path
import requests
import pytest
from config.settings import Settings, get_settings
from utils.cache import JsonCache, cache_key
from utils.retry import is_transient_error
from utils.text import slugify, split_sentences


def test_vietnamese_slug() -> None:
    assert slugify("Đồ họa & dựng video!") == "do-hoa-dung-video"
    assert slugify("CON") == "video-con"
    assert "/" not in slugify("../../secret")
    assert split_sentences("Xin chào!  Bắt đầu nhé.") == ["Xin chào!", "Bắt đầu nhé."]


def test_cache_roundtrip_corruption_expiry(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    assert cache_key({"a": 1, "b": 2}) == cache_key({"b": 2, "a": 1})
    cache.set("test", {"x": 1}, {"text": "Tiếng Việt"})
    assert cache.get("test", {"x": 1}) == {"text": "Tiếng Việt"}
    assert cache.get("other", {"x": 1}) is None
    path = next(tmp_path.glob("*.json"))
    path.write_text(json.dumps({"created_at": 0, "data": {}}), encoding="utf-8")
    assert cache.get("test", {"x": 1}) is None
    path.write_text("broken", encoding="utf-8")
    assert cache.get("test", {"x": 1}) is None


def test_env_precedence_and_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=file-secret\nREQUEST_TIMEOUT_SEC=15\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "process-secret")
    settings = get_settings(env)
    assert settings.require_key("gemini") == "process-secret"
    assert "process-secret" not in repr(settings)
    assert settings.request_timeout_sec == 15


def test_missing_key_only_fails_when_requested() -> None:
    settings = Settings()
    with pytest.raises(ValueError, match="Thiếu GEMINI_API_KEY"):
        settings.require_key("gemini")
    with pytest.raises(ValueError, match="Thiếu GEMINI_MODEL"):
        settings.require_gemini_model()


def test_check_handles_windows_legacy_encoding(isolate_configuration: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    # Monkeypatch fixture không truyền sang process con: bootstrap cùng file cô lập.
    bootstrap = ("import runpy,sys; from pathlib import Path; import config.settings as config; "
                 "config.DEFAULT_ENV_FILE=Path(sys.argv[1]); "
                 "sys.argv=[sys.argv[2], '--check']; runpy.run_path(sys.argv[0],run_name='__main__')")
    result = subprocess.run([sys.executable, "-c", bootstrap, str(isolate_configuration), str(root / "main.py")],
                            cwd=root, env={**os.environ, "PYTHONIOENCODING": "cp1252"},
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    assert "cấu hình hợp lệ" in result.stdout


@pytest.mark.parametrize("status,expected", [(401, False), (403, False), (404, False), (429, True), (503, True)])
def test_retry_only_transient(status: int, expected: bool) -> None:
    response = requests.Response()
    response.status_code = status
    assert is_transient_error(requests.HTTPError(response=response)) is expected
