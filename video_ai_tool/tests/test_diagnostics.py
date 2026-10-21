# file: tests/test_diagnostics.py
"""Đảm bảo traceback vẫn đầy đủ nhưng không lộ credentials."""
from pathlib import Path
from urllib.parse import quote
import pytest
from utils.diagnostics import Diagnostics


def test_full_traceback_redacts_bare_and_encoded_secrets(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    secret = "fixture-secret/with+symbols"
    logger = Diagnostics(tmp_path, debug=True, secrets=[secret])
    try:
        try:
            raise ValueError(f"Original failure {secret} encoded={quote(secret, safe='')}")
        except ValueError as error:
            raise RuntimeError("Wrapper failure") from error
    except RuntimeError as error:
        logger.record_exception(error, "test stage")
    saved = logger.path.read_text(encoding="utf-8")
    console = capsys.readouterr().err
    for text in (saved, console):
        assert secret not in text and quote(secret, safe="") not in text
        assert "ValueError: Original failure" in text and "RuntimeError: Wrapper failure" in text
        assert "Traceback" in text and "[REDACTED]" in text


def test_header_key_patterns_and_debug_opt_in(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    logger = Diagnostics(tmp_path)
    logger.record("headers={'x-goog-api-key': 'unregistered-fixture'} ?key=other-fixture&safe=ok")
    saved = logger.path.read_text(encoding="utf-8")
    assert "unregistered-fixture" not in saved and "other-fixture" not in saved
    assert "safe=ok" in saved
    assert not capsys.readouterr().err
