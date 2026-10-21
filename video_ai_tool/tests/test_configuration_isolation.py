# file: tests/test_configuration_isolation.py
"""Hồi quy cấu hình: precedence, side effect và chặn .env thật."""
import importlib.util
import os
from pathlib import Path
import pytest
import config.settings as configuration
from config.settings import get_settings
from utils.diagnostics import Diagnostics


def test_default_settings_and_diagnostics_use_only_isolated_file(isolate_configuration: Path) -> None:
    isolate_configuration.write_text("GEMINI_API_KEY=isolated-fixture\nREQUEST_TIMEOUT_SEC=17\n", encoding="utf-8")
    settings = get_settings()
    assert settings.request_timeout_sec == 17
    assert settings.require_key("gemini") == "isolated-fixture"
    assert "isolated-fixture" in Diagnostics(isolate_configuration.parent / "logs").secrets
    assert "GEMINI_API_KEY" not in os.environ


def test_explicit_file_ignores_other_default_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    default, explicit = tmp_path / "default.env", tmp_path / "chosen.env"
    default.write_text("REQUEST_TIMEOUT_SEC=30\n", encoding="utf-8")
    explicit.write_text("REQUEST_TIMEOUT_SEC=15\n", encoding="utf-8")
    monkeypatch.setattr(configuration, "DEFAULT_ENV_FILE", default)
    assert get_settings(explicit).request_timeout_sec == 15
    assert "REQUEST_TIMEOUT_SEC" not in os.environ


def test_environment_still_has_priority_over_explicit_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "chosen.env"
    path.write_text("REQUEST_TIMEOUT_SEC=15\n", encoding="utf-8")
    monkeypatch.setenv("REQUEST_TIMEOUT_SEC", "23")
    assert get_settings(path).request_timeout_sec == 23


def test_real_project_env_is_never_read() -> None:
    with pytest.raises(AssertionError, match="không được đọc"):
        get_settings(configuration.ROOT_DIR / ".env")


def test_manual_gemini_script_has_no_import_side_effects(capsys: pytest.CaptureFixture) -> None:
    before = dict(os.environ)
    spec = importlib.util.spec_from_file_location("manual_gemini_diagnostic", configuration.ROOT_DIR / "test_gemini.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.main)
    assert os.environ == before
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
