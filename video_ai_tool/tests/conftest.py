# file: tests/conftest.py
"""Cô lập mọi test khỏi cấu hình máy và file .env thật của dự án."""
from contextlib import contextmanager
import os
from pathlib import Path
import pytest
from dotenv.main import DotEnv
import config.settings as configuration

PREFIXES = ("GEMINI_", "YOUTUBE_", "PEXELS_", "PIXABAY_", "GATEWAY_", "STYLE_")
CONFIG_NAMES = {name.upper() for name in configuration.Settings.model_fields if name != "root_dir"}
CONFIG_NAMES.update({"FFMPEG_BINARY", "FFPLAY_BINARY", "IMAGEIO_FFMPEG_EXE",
    "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"})
REAL_ENV = configuration.ROOT_DIR / ".env"


@pytest.fixture(autouse=True)
def isolate_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Dọn env từng test; redirect cả settings/diagnostics sang file rỗng tạm."""
    for name in list(os.environ):
        normalized = name.upper()
        if normalized.startswith(PREFIXES) or normalized in CONFIG_NAMES:
            monkeypatch.delenv(name, raising=False)
    # Chặn thư viện bên thứ ba tự load_dotenv; dotenv_values(file tạm) vẫn hoạt động.
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    empty = tmp_path / "isolated.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setattr(configuration, "DEFAULT_ENV_FILE", empty)
    import agents.validation_rules as validation_policy
    rules=tmp_path / "isolated_validation.yaml"
    rules.write_text("rules: {}\n",encoding="utf-8")
    monkeypatch.setattr(validation_policy,"DEFAULT_VALIDATION",rules)

    # Fail rõ ràng nếu code nào vô tình quay lại đọc file thật qua python-dotenv.
    original_stream = DotEnv._get_stream
    @contextmanager
    def guarded_stream(self):
        if self.dotenv_path and Path(self.dotenv_path).resolve() == REAL_ENV.resolve():
            raise AssertionError("Test không được đọc .env thật của dự án; hãy dùng file tạm.")
        with original_stream(self) as stream:
            yield stream
    monkeypatch.setattr(DotEnv, "_get_stream", guarded_stream)
    return empty
