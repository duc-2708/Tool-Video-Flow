# file: sources/transcripts.py
"""Transcript có thể thay provider; lỗi thì bỏ qua, không tải media."""
from typing import Any, Protocol
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from utils.cache import JsonCache
from utils.retry import network_retry
from utils.text import clean_text


class TranscriptProvider(Protocol):
    def fetch(self, video_id: str) -> str | None:
        """Trả văn bản tín hiệu hoặc None nếu không khả dụng."""
        raise NotImplementedError


class TimeoutSession(requests.Session):
    def __init__(self, timeout: float) -> None:
        super().__init__()
        self.timeout = timeout

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs["timeout"] = self.timeout
        return super().request(method, url, **kwargs)


class YouTubeTranscriptProvider:
    def __init__(self, cache: JsonCache, timeout: float = 30, attempts: int = 3) -> None:
        self.cache, self.timeout, self.attempts = cache, timeout, attempts

    def fetch(self, video_id: str) -> str | None:
        inputs = {"id": video_id, "languages": ["vi", "en"]}
        cached = self.cache.get("transcript-v1", inputs)
        if isinstance(cached, dict):
            return cached.get("text")
        try:
            @network_retry(self.attempts)
            def download() -> str:
                with TimeoutSession(self.timeout) as session:
                    segments = YouTubeTranscriptApi(http_client=session).fetch(video_id, languages=["vi", "en"])
                    return clean_text(" ".join(segment.text for segment in segments))[:12000]
            text = download() or None
        except Exception:
            # Thư viện không chính thức có thể bị chặn hoặc video không có phụ đề.
            text = None
        self.cache.set("transcript-v1", inputs, {"text": text})
        return text


if __name__ == "__main__":
    from sources.debug import run_debug
    raise SystemExit(run_debug("transcript"))
