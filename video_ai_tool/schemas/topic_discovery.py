"""Typed discovery metadata; these fields are never facts."""
from typing import Literal
from pydantic import Field, HttpUrl
from schemas.base import StrictModel, NonEmptyText

class FeedSpec(StrictModel):
    name: NonEmptyText
    url: HttpUrl
    region: Literal["vn","global"]
    enabled: bool = True
    include_keywords: list[str] = Field(default_factory=list)

class Category(StrictModel):
    name: NonEmptyText
    enabled: bool = True
    keywords_vi: list[NonEmptyText] = Field(min_length=1,max_length=10)
    keywords_en: list[NonEmptyText] = Field(min_length=1,max_length=10)
    rss: list[FeedSpec]
    suggested_type: Literal["news","review","story"] = "news"

class CategoryFile(StrictModel):
    categories: list[Category] = Field(min_length=1,max_length=50)

class TopicQueries(StrictModel):
    vi: list[NonEmptyText] = Field(min_length=1,max_length=3)
    en: list[NonEmptyText] = Field(min_length=1,max_length=3)

class TopicSuggestion(StrictModel):
    cluster_id: NonEmptyText
    topic: NonEmptyText = Field(max_length=220)
    why_now: NonEmptyText = Field(max_length=600)
    angle: NonEmptyText = Field(max_length=500)
    suggested_type: Literal["news","review","story"]
    search_queries: TopicQueries
    score: int = Field(ge=1,le=10)
    score_reason: NonEmptyText = Field(max_length=600)
    source_urls: list[HttpUrl] = Field(min_length=1,max_length=30)

class TopicBatch(StrictModel):
    topics: list[TopicSuggestion] = Field(max_length=30)

class DiscoveryHint(StrictModel):
    category: NonEmptyText
    suggestion: TopicSuggestion
