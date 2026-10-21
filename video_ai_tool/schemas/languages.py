"""Supported source languages; speech/captions remain Vietnamese."""
from typing import Literal
from pydantic import BaseModel, Field

SourceLanguage = Literal["vi", "en", "zh", "ko", "ja"]
REGIONS = {"vi":"vn-vi", "en":"us-en", "zh":"cn-zh", "ko":"kr-kr", "ja":"jp-jp"}
LABELS = {"vi":"Tiếng Việt", "en":"Tiếng Anh", "zh":"Tiếng Trung", "ko":"Tiếng Hàn", "ja":"Tiếng Nhật"}


class LanguageOptions(BaseModel):
    source_languages: list[SourceLanguage] = Field(default_factory=lambda:["vi","en"],min_length=1,max_length=5)
    output_language: Literal["vi"] = "vi"
