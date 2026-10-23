# file: sources/youtube.py
"""YouTube Data API: chỉ metadata/tín hiệu, cache và quota bảo thủ lưu trên đĩa."""
from datetime import datetime
import json
import re
from zoneinfo import ZoneInfo
from typing import Any
import requests
from config.settings import Settings
from schemas.source import SourceDocument
from sources.transcripts import TranscriptProvider
from utils.cache import JsonCache, write_json
from utils.file_lock import file_lock
from utils.retry import network_retry


class QuotaExceeded(RuntimeError):
    """Trần quota local; không phải số liệu quota của Google Cloud Console."""


class YouTubeSource:
    def __init__(self, settings: Settings, cache: JsonCache, transcripts: TranscriptProvider | None = None) -> None:
        self.settings, self.cache, self.transcripts = settings, cache, transcripts
        self.searches_this_run = 0

    def _reserve(self, cost: int, search: bool) -> None:
        path = self.settings.cache_dir / "youtube_quota.json"
        with file_lock(path.with_suffix(".lock")):
            day = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
            state = {"day": day, "estimated_units": 0, "search_calls": 0}
            if path.exists():
                try:
                    stored = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(stored, dict) or not isinstance(stored["day"], str):
                        raise ValueError
                    for field in ("estimated_units", "search_calls"):
                        if type(stored[field]) is not int or stored[field] < 0:
                            raise ValueError
                    if stored["day"] == day:
                        state = stored
                        # Migrate today's old undercounted trends ledger
                        # conservatively: existing searches cost at least 100.
                        if stored.get("cost_version") != 2:
                            state["estimated_units"] += 99*state["search_calls"]
                except (ValueError, KeyError, TypeError):
                    raise QuotaExceeded("File quota local không hợp lệ; không gọi YouTube để tránh vượt quota.") from None
            if search and (self.searches_this_run >= self.settings.youtube_max_searches_per_run
                           or state["search_calls"] >= getattr(self,"daily_search_limit",100)):
                raise QuotaExceeded("Đã đạt giới hạn số lần search YouTube local.")
            if state["estimated_units"] + cost > self.settings.youtube_daily_quota:
                raise QuotaExceeded(f"Vượt YOUTUBE_DAILY_QUOTA={self.settings.youtube_daily_quota}: đã dùng {state['estimated_units']}, cần thêm {cost} đơn vị.")
            state["estimated_units"] += cost
            state["search_calls"] += int(search)
            state["cost_version"] = 2
            write_json(path, state)
            self.searches_this_run += int(search)

    def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        key = self.settings.require_key("youtube")

        @network_retry(self.settings.retry_attempts)
        def send() -> dict[str, Any]:
            # Mỗi lần retry đều đặt trước quota; lỗi API cũng có thể tốn quota.
            self._reserve(100 if endpoint == "search" else 1, endpoint == "search")
            with requests.get("https://www.googleapis.com/youtube/v3/" + endpoint,
                              params=params, headers={"X-Goog-Api-Key": key},
                              timeout=self.settings.request_timeout_sec) as response:
                response.raise_for_status()
                return response.json()
        return send()

    def collect(self, topic: str, limit: int = 5) -> tuple[list[SourceDocument], list[str]]:
        if not 1 <= limit <= 10:
            raise ValueError("Số video YouTube phải từ 1 đến 10.")
        if not self.settings.youtube_api_key.get_secret_value().strip():
            return [], ["Thiếu YOUTUBE_API_KEY; tiếp tục nghiên cứu bằng nguồn web."]
        warnings: list[str] = []
        inputs = {"topic": topic, "limit": limit}
        records = self.cache.get("youtube-search-v2", inputs)
        if not isinstance(records, list):
            try:
                raw = self._request("search", {"part": "snippet", "q": topic, "type": "video",
                    "maxResults": limit, "relevanceLanguage": "vi", "safeSearch": "moderate"})
                records = []
                for item in raw.get("items", []):
                    video_id = item.get("id", {}).get("videoId", "")
                    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                        continue
                    snippet = item.get("snippet", {})
                    records.append({"id": video_id, "title": snippet.get("title") or "YouTube",
                        "description": snippet.get("description", ""), "channel": snippet.get("channelTitle") or "YouTube",
                        "published_at": snippet.get("publishedAt"),
                        "retrieved_at": datetime.now(ZoneInfo("UTC")).isoformat()})
                self.cache.set("youtube-search-v2", inputs, records)
            except Exception:
                return [], ["YouTube search không khả dụng hoặc đạt quota; tiếp tục dùng nguồn web."]
        if not records:
            return [], warnings
        ids = [record["id"] for record in records]
        details = self.cache.get("youtube-details-v2", {"ids": ids})
        if not isinstance(details, dict):
            try:
                raw = self._request("videos", {"part": "snippet,statistics", "id": ",".join(ids)})
                details = {}
                for item in raw.get("items", []):
                    snippet = item.get("snippet", {})
                    stats = {name: int(value) for name, value in item.get("statistics", {}).items()
                             if name in {"viewCount", "likeCount", "commentCount"} and str(value).isdigit()}
                    details[item["id"]] = {"description": snippet.get("description", "")[:12000], "statistics": stats,
                                          "retrieved_at": datetime.now(ZoneInfo("UTC")).isoformat()}
                self.cache.set("youtube-details-v2", {"ids": ids}, details)
            except Exception:
                details = {}
                warnings.append("Không lấy được thống kê YouTube; chỉ dùng metadata tìm kiếm.")
        documents: list[SourceDocument] = []
        for index, record in enumerate(records):
            extra = details.get(record["id"], {})
            transcript = None
            if self.transcripts and index < 2:
                try:
                    transcript = self.transcripts.fetch(record["id"])
                except Exception:
                    transcript = None
                if transcript is None:
                    warnings.append("Transcript YouTube không khả dụng cho một số video; chỉ dùng metadata.")
            documents.append(SourceDocument(title=record["title"], url="https://www.youtube.com/watch?v=" + record["id"],
                source_name=record["channel"], platform="youtube", content_kind="social_signal",
                text=extra.get("description", record["description"]),
                retrieved_at=extra.get("retrieved_at", record.get("retrieved_at", datetime.now(ZoneInfo("UTC")).isoformat())),
                published_at=record["published_at"],
                statistics=extra.get("statistics", {}), transcript=transcript))
        return documents, list(dict.fromkeys(warnings))


if __name__ == "__main__":
    from sources.debug import run_debug
    raise SystemExit(run_debug("youtube"))
