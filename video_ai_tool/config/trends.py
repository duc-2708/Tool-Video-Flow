"""Validated, credential-free Trend Scout switches."""
from pathlib import Path
import re
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from config.settings import ROOT_DIR


class TrendConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    region: str = "VN"
    limit_per_source: int = Field(default=8, ge=1, le=30)
    TREND_DAILY_CREDIT_LIMIT: int = Field(default=30, ge=0, le=10000)
    cache_ttl_sec: int = Field(default=21600, ge=60)
    gemini_enabled: bool = True
    providers: dict[str, bool] = Field(default_factory=dict)
    categories: dict[str, dict[str, list[str]]] = Field(default_factory=dict)

    @field_validator("region")
    @classmethod
    def country(cls, value):
        if not re.fullmatch("[A-Za-z]{2}", value):
            raise ValueError("region phải là mã quốc gia hai chữ cái.")
        return value.upper()


def load_trends(settings):
    path = Path(settings.root_dir) / "config/trends.yaml"
    if not path.exists():
        path = ROOT_DIR / "config/trends.yaml"
    return TrendConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
