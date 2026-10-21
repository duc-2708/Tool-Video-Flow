# file: providers/stock_base.py
"""Interface stock dùng chung; chỉ các nguồn có quyền sử dụng đã chọn."""
from abc import ABC, abstractmethod
from typing import Literal
from pydantic import Field, HttpUrl
from schemas.base import NonEmptyText, StrictModel


class StockItem(StrictModel):
    provider: Literal["pixabay", "pexels"]
    asset_id: NonEmptyText
    kind: Literal["video", "image"]
    download_url: HttpUrl
    source_url: HttpUrl
    author: NonEmptyText
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    duration_sec: float | None = Field(default=None, gt=0)


class StockProvider(ABC):
    @abstractmethod
    def search(self, query: str, video_format: str, kind: str) -> list[StockItem]:
        raise NotImplementedError
