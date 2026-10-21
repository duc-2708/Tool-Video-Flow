from schemas.topic_discovery import DiscoveryHint
# file: schemas/research_brief.py
"""Research Brief: mọi fact và tín hiệu đều phải trỏ về nguồn HTTP(S)."""
from typing import Annotated, Literal
from pydantic import Field, HttpUrl
from schemas.base import NonEmptyText, StrictModel
from schemas.languages import SourceLanguage


class AngleCandidate(StrictModel):
    angle: NonEmptyText
    why: NonEmptyText


class Fact(StrictModel):
    claim: NonEmptyText
    source_name: NonEmptyText
    source_url: HttpUrl
    confidence: Literal["high", "medium", "low"]
    evidence_quote: str | None = None
    source_lang: SourceLanguage = "vi"
    fact_vi: str | None = Field(default=None, exclude_if=lambda value:value is None)
    published_at: str | None = Field(default=None, exclude_if=lambda value:value is None)
    pronunciation_hint: str | None = Field(default=None, exclude_if=lambda value:value is None)


class SearchQuery(StrictModel):
    source_lang: SourceLanguage
    query: NonEmptyText = Field(max_length=300)
    region: NonEmptyText


class Trend(StrictModel):
    signal: NonEmptyText
    platform: Literal["web", "youtube"]
    evidence_url: HttpUrl


class TrendSignal(StrictModel):
    platform: Literal["youtube"] = "youtube"
    title: NonEmptyText
    channel: NonEmptyText
    url: HttpUrl
    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    published_at: NonEmptyText
    hashtags: list[NonEmptyText] = Field(default_factory=list, max_length=30)
    top_comments: list[NonEmptyText] = Field(default_factory=list, max_length=10)


class TrendInsight(StrictModel):
    text: NonEmptyText = Field(max_length=300)
    reason: NonEmptyText = Field(max_length=300)
    evidence_urls: Annotated[list[HttpUrl], Field(min_length=1, max_length=5)]


class TrendInsights(StrictModel):
    hook_patterns: list[TrendInsight] = Field(default_factory=list, max_length=8)
    keywords: list[TrendInsight] = Field(default_factory=list, max_length=8)
    common_questions: list[TrendInsight] = Field(default_factory=list, max_length=8)
    angles: list[TrendInsight] = Field(default_factory=list, max_length=8)


class ResearchBrief(StrictModel):
    discovery_hint: DiscoveryHint | None = Field(default=None,exclude_if=lambda v:v is None)
    research_depth: Literal["legacy","deep"] = Field(default="legacy",exclude_if=lambda value:value == "legacy")
    story_angles: list[AngleCandidate] = Field(default_factory=list,exclude_if=lambda value:not value)
    key_numbers: list["BriefDetail"] = Field(default_factory=list,exclude_if=lambda value:not value)
    timeline: list["BriefDetail"] = Field(default_factory=list,exclude_if=lambda value:not value)
    why_it_matters: list["BriefDetail"] = Field(default_factory=list,exclude_if=lambda value:not value)
    counterpoints: list["BriefDetail"] = Field(default_factory=list,exclude_if=lambda value:not value)
    glossary: list["BriefDetail"] = Field(default_factory=list,exclude_if=lambda value:not value)
    topic: NonEmptyText
    language: Literal["vi"]
    source_languages: list[SourceLanguage] = Field(default_factory=lambda:["vi","en"])
    output_language: Literal["vi"] = "vi"
    search_queries: list[SearchQuery] = Field(default_factory=list, exclude_if=lambda value:not value)
    angle_candidates: Annotated[list[AngleCandidate], Field(min_length=1)]
    facts: list[Fact]
    trends: list[Trend]
    hooks: Annotated[list[NonEmptyText], Field(min_length=1)]
    audience_questions: list[NonEmptyText]
    keywords: Annotated[list[NonEmptyText], Field(min_length=1)]
    risks: list[NonEmptyText]
    trend_signals: list[TrendSignal] = Field(default_factory=list, exclude_if=lambda value: not value)
    trend_insights: TrendInsights = Field(default_factory=TrendInsights,
        exclude_if=lambda value: not any((value.hook_patterns, value.keywords, value.common_questions, value.angles)))


class BriefDetail(StrictModel):
    text: NonEmptyText
    fact_ids: list[int] = Field(min_length=1)


ResearchBrief.model_rebuild()
