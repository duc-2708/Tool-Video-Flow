# file: providers/stock_pexels.py
"""Pexels tùy chọn; thiếu key trả rỗng êm, không gọi mạng và không báo lỗi."""
from config.settings import Settings
from providers.stock_base import StockItem, StockProvider
from providers.stock_http import stock_json
from utils.cache import JsonCache
from utils.diagnostics import Diagnostics


class PexelsProvider(StockProvider):
    def __init__(self, settings: Settings, diagnostics: Diagnostics) -> None:
        self.settings, self.diagnostics = settings, diagnostics
        self.cache = JsonCache(settings.cache_dir / "stock_search", max(86400, settings.cache_ttl_sec))

    def search(self, query: str, video_format: str, kind: str) -> list[StockItem]:
        if not self.settings.pexels_api_key.get_secret_value().strip():
            return []
        inputs = {"query": query.lower().strip(), "format": video_format, "kind": kind}
        cached = self.cache.get("pexels-v1", inputs)
        if isinstance(cached, list):
            return [StockItem.model_validate(row) for row in cached]
        params = {"query": query, "per_page": 30, "orientation": "portrait" if video_format == "tiktok" else "landscape"}
        endpoint = "https://api.pexels.com/v1/videos/search" if kind == "video" else "https://api.pexels.com/v1/search"
        data = stock_json(endpoint, self.settings, self.diagnostics, params=params,
                          headers={"Authorization": self.settings.require_key("pexels")})
        items = []
        for hit in data.get("videos" if kind == "video" else "photos", []):
            try:
                if kind == "video":
                    streams = [v for v in hit.get("video_files", []) if v.get("file_type") == "video/mp4" and v.get("width") and v.get("height")]
                    if not streams:
                        continue
                    stream = min(streams, key=lambda v: abs(max(v["width"], v["height"]) - 1280))
                    download, width, height = stream["link"], stream["width"], stream["height"]
                    author = hit["user"]["name"]
                else:
                    download, width, height, author = hit["src"]["large2x"], hit["width"], hit["height"], hit["photographer"]
                items.append(StockItem(provider="pexels", asset_id=str(hit["id"]), kind=kind, download_url=download,
                    source_url=hit["url"], author=author, width=width, height=height,
                    duration_sec=float(hit["duration"]) if kind == "video" else None))
            except (KeyError, TypeError, ValueError) as error:
                self.diagnostics.record_exception(error, "Pexels bỏ qua metadata asset không hợp lệ")
        self.cache.set("pexels-v1", inputs, [item.model_dump(mode="json") for item in items])
        return items
