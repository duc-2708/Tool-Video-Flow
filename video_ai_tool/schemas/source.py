# file: schemas/source.py
"""Tài liệu có xuất xứ; tách web khỏi tín hiệu xã hội."""
from typing import Literal
from pydantic import Field, HttpUrl, model_validator
from schemas.base import NonEmptyText, StrictModel
from schemas.languages import SourceLanguage


class SourceDocument(StrictModel):
    content_length: int = 0

    @model_validator(mode="after")
    def measured_length(self):
        self.content_length = len(self.text)
        return self

    title: NonEmptyText
    url: HttpUrl
    source_name: NonEmptyText
    platform: Literal["web", "youtube"]
    text: str
    retrieved_at: NonEmptyText
    published_at: str | None = None
    content_kind: Literal["article", "snippet", "social_signal"]
    statistics: dict[str, int] = Field(default_factory=dict)
    transcript: str | None = None
    source_lang: SourceLanguage = Field(default="vi", exclude_if=lambda value:value == "vi")
