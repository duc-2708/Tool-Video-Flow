# file: providers/stock_pixabay.py
"""Pixabay ưu tiên video, filter orientation ở phía client, cache tối thiểu 24h."""
from config.settings import Settings
from providers.stock_base import StockItem, StockProvider
from providers.stock_http import stock_json
from utils.cache import JsonCache
from utils.diagnostics import Diagnostics
from utils.rate_limit import RateLimiter


class PixabayProvider(StockProvider):
    def __init__(self, settings: Settings, diagnostics: Diagnostics) -> None:
        self.settings, self.diagnostics = settings, diagnostics
        self.cache = JsonCache(settings.cache_dir / "stock_search", max(86400, settings.cache_ttl_sec))
        self.limiter = RateLimiter(settings.cache_dir / "pixabay_rate.json")

    def search(self, query: str, video_format: str, kind: str) -> list[StockItem]:
        inputs = {"query": query.lower().strip(), "format": video_format, "kind": kind}
        cached = self.cache.get("pixabay-v1", inputs)
        if isinstance(cached, list):
            return [StockItem.model_validate(row) for row in cached]
        if not self.settings.pixabay_api_key.get_secret_value().strip():
            return []
        params = {"key": self.settings.require_key("pixabay"), "q": query[:100], "per_page": 30, "safesearch": "true"}
        if kind == "image":
            params.update(image_type="photo", orientation="vertical" if video_format == "tiktok" else "horizontal")
        url = "https://pixabay.com/api/videos/" if kind == "video" else "https://pixabay.com/api/"
        data = stock_json(url, self.settings, self.diagnostics, params=params, limiter=self.limiter)
        items = []
        for hit in data.get("hits", []):
            try:
                if kind == "video":
                    streams = [v for v in hit.get("videos", {}).values() if v.get("url") and v.get("width") and v.get("height")]
                    if not streams:
                        continue
                    # Tránh tải 4K không cần thiết; ưu tiên stream vừa đủ cho MVP.
                    stream = min(streams, key=lambda v: abs(max(v["width"], v["height"]) - 1280))
                    download, width, height = stream["url"], stream["width"], stream["height"]
                else:
                    download = hit.get("largeImageURL") or hit.get("webformatURL")
                    width, height = hit["imageWidth"], hit["imageHeight"]
                items.append(StockItem(provider="pixabay", asset_id=str(hit["id"]), kind=kind,
                    download_url=download, source_url=hit["pageURL"], author=hit["user"],
                    width=width, height=height, duration_sec=float(hit["duration"]) if kind == "video" else None))
            except (KeyError, TypeError, ValueError) as error:
                self.diagnostics.record_exception(error, "Pixabay bỏ qua metadata asset không hợp lệ")
        self.cache.set("pixabay-v1", inputs, [item.model_dump(mode="json") for item in items])
        return items
