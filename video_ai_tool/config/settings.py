# file: config/settings.py
"""Nạp cấu hình local, không yêu cầu API key cho bước kiểm tra offline."""
import os
import json
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator, model_validator

from config.video_models import VIDEO_MODELS

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    root_dir: Path = ROOT_DIR
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    gemini_director_model: str = ""
    gemini_fallback_model: str = ""
    gemini_timeout_sec: float = Field(default=120,gt=0,le=600)
    gemini_style_model: str = ""
    style_max_videos_per_run: int = Field(default=5, ge=1, le=20)
    style_max_file_mb: int = Field(default=200, ge=1, le=2000)
    style_max_duration_sec: float = Field(default=600, ge=1, le=3600)
    style_timeout_sec: float = Field(default=180, ge=10, le=300)
    style_max_output_tokens: int = Field(default=8192,ge=1024,le=65536)
    style_media_resolution: Literal["low","medium","none"] = "low"
    style_use_response_schema: bool = True
    style_schema_mode: Literal["flat","essential"] = "flat"
    style_compact_output: bool = False
    style_max_video_sec: float = Field(default=180,gt=0,le=600)
    style_video_fps: float = Field(default=.5, gt=0, le=1)
    style_tpm_limit: int = Field(default=250000, ge=1000)
    style_rpm_limit: int = Field(default=2, ge=1, le=1000)
    style_request_interval_sec: float = Field(default=5, ge=0, le=300)
    scan_max_video_sec: float = Field(default=180, ge=1, le=3600)
    scan_max_age_days: int = Field(default=180, ge=1, le=3650)
    scan_max_new_videos: int = Field(default=5, ge=1, le=20)
    gateway_api_key: SecretStr = SecretStr("")
    gateway_base_url: str = "https://api.buihuuthang.com/v1"
    gateway_video_model: str = "veo-3.1"
    gateway_allowed_models: list[str] = Field(default_factory=lambda: ["veo-3.1", "seedance-2.5-30s"])
    ai_clip_seconds: int = Field(default=4, ge=1, le=30)
    ai_clip_max_per_run: int = Field(default=3, ge=0, le=20)
    youtube_api_key: SecretStr = SecretStr("")
    pexels_api_key: SecretStr = SecretStr("")
    pixabay_api_key: SecretStr = SecretStr("")
    default_voice: Literal["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"] = "vi-VN-HoaiMyNeural"
    default_voice_fallback: Literal["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"] = "vi-VN-NamMinhNeural"
    request_timeout_sec: float = Field(default=30, gt=0, le=300)
    retry_attempts: int = Field(default=3, ge=1, le=8)
    cache_ttl_sec: int = Field(default=86400, ge=1)
    youtube_daily_quota: int = Field(default=10000, ge=1, le=10000)
    youtube_max_searches_per_run: int = Field(default=2, ge=0, le=10)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("gateway_allowed_models", mode="before")
    @classmethod
    def parse_allowed_models(cls, value):
        if isinstance(value, str):
            value = json.loads(value) if value.strip().startswith("[") else value.split(",")
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))

    @model_validator(mode="after")
    def validate_gateway_defaults(self):
        if self.gateway_video_model not in VIDEO_MODELS:
            raise ValueError("GATEWAY_VIDEO_MODEL chỉ nhận veo-3.1 hoặc seedance-2.5-30s.")
        if "ai_clip_seconds" not in self.model_fields_set:
            object.__setattr__(self, "ai_clip_seconds", VIDEO_MODELS[self.gateway_video_model][0])
        if self.ai_clip_seconds not in VIDEO_MODELS[self.gateway_video_model]:
            raise ValueError(f"AI_CLIP_SECONDS không hợp lệ cho {self.gateway_video_model}; chọn {VIDEO_MODELS[self.gateway_video_model]}.")
        if any(model not in VIDEO_MODELS for model in self.gateway_allowed_models):
            raise ValueError("GATEWAY_ALLOWED_MODELS chỉ nhận veo-3.1, seedance-2.5-30s.")
        return self

    @property
    def cache_dir(self) -> Path:
        return self.root_dir / ".cache"

    @property
    def output_dir(self) -> Path:
        return self.root_dir / "output"

    @property
    def logs_dir(self) -> Path:
        return self.root_dir / "logs"

    @property
    def prompts_dir(self) -> Path:
        return self.root_dir / "prompts"

    def ensure_directories(self) -> None:
        for path in (self.cache_dir, self.output_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)

    def require_key(self, provider: Literal["gemini", "youtube", "pexels", "pixabay"]) -> str:
        value = getattr(self, f"{provider}_api_key").get_secret_value().strip()
        if not value:
            raise ValueError(f"Thiếu {provider.upper()}_API_KEY. Hãy điền trong {self.root_dir / '.env'}.")
        return value

    def require_gemini_model(self) -> str:
        if not self.gemini_model.strip():
            raise ValueError("Thiếu GEMINI_MODEL. Hãy chọn model đang có trong tài khoản và điền vào .env.")
        return self.gemini_model.strip()

    def require_director_model(self) -> str:
        return self.gemini_director_model.strip() or self.require_gemini_model()

    def require_style_model(self) -> str:
        return self.gemini_style_model.strip() or self.require_gemini_model()


def read_configuration_values(env_file: Path | None = None) -> dict[str, str | None]:
    """Một nơi chọn file cấu hình; không gọi load_dotenv hoặc sửa os.environ."""
    path = DEFAULT_ENV_FILE if env_file is None else env_file
    return {**dotenv_values(path), **os.environ}


def get_settings(env_file: Path | None = None) -> Settings:
    """Biến môi trường ưu tiên hơn file chỉ định; không nạp thêm .env khác."""
    values = read_configuration_values(env_file)
    fields = Settings.model_fields.keys() - {"root_dir"}
    return Settings(**{key: values[key.upper()] for key in fields if values.get(key.upper()) is not None})


if __name__ == "__main__":
    from utils.console import configure_console

    configure_console()
    try:
        settings = get_settings()
        settings.ensure_directories()
    except (ValidationError, ValueError, OSError):
        raise SystemExit("Cấu hình không hợp lệ hoặc không thể ghi thư mục. Kiểm tra .env theo .env.example.") from None
    print(f"Cấu hình hợp lệ. Thư mục dự án: {settings.root_dir}")
    print("API key không được in ra log. Kiểm tra offline không cần key.")
