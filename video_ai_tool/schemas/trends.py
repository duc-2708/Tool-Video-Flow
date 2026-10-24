"""Discovery metadata only; intentionally separate from ResearchBrief/Fact."""
from datetime import datetime, timezone
from typing import Protocol
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Metrics(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)


class TrendItem(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(default="", max_length=600)
    url: HttpUrl
    platform: str
    language: str = "und"
    region: str = ""
    score_raw: float = Field(default=0, ge=0)
    metrics: Metrics = Field(default_factory=Metrics)
    hashtags: list[str] = Field(default_factory=list, max_length=30)
    fetched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TrendProvider(Protocol):
    def fetch(self, category, limit: int) -> list[TrendItem]: ...


class TrendTopic(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    topic_title_vi: str = Field(min_length=1, max_length=220)
    why_hot: str = Field(min_length=1, max_length=600)
    angle_suggestions: list[str] = Field(min_length=2, max_length=3)
    score_hot: float = Field(ge=0, le=10)
    score_fit_category: float = Field(ge=0, le=10)
    score_vietnam_audience: float = Field(ge=0, le=10)
    sources: list[HttpUrl] = Field(min_length=1, max_length=30)

    @property
    def score(self):
        return round(.4*self.score_hot + .3*self.score_fit_category + .3*self.score_vietnam_audience, 2)


class TrendBatch(BaseModel):
    topics: list[TrendTopic] = Field(max_length=20)
