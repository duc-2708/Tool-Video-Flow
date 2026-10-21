# file: tests/test_sources.py
"""Quota, retry, fallback nguồn: mọi network đều được mock."""
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
import requests
from pydantic import SecretStr
from config.settings import Settings
from sources.web_search import WebSearch, allowed_web_url, ensure_public_url
from sources.youtube import QuotaExceeded, YouTubeSource
from sources.transcripts import TimeoutSession, YouTubeTranscriptProvider
from utils.cache import JsonCache


def test_social_and_private_urls_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    for url in ["https://youtube.com/watch?v=x", "https://m.tiktok.com/test", "file:///x", "https://user:pass@example.com", "https://example.com:444/"]:
        assert not allowed_web_url(url)
    monkeypatch.setattr("sources.web_search.socket.getaddrinfo", lambda *a: [(2, 1, 6, "", ("127.0.0.1", 0))])
    with pytest.raises(ValueError):
        ensure_public_url("http://localhost/")


def test_web_snippets_are_discarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = WebSearch(Settings(root_dir=tmp_path), JsonCache(tmp_path / "cache"))
    monkeypatch.setattr(source, "_search", lambda *a: [{"href": "https://example.com/a", "title": "Fixture", "body": "Snippet fixture"}])
    monkeypatch.setattr(source, "_article", Mock(side_effect=requests.Timeout))
    docs, warnings = source.collect("fixture")
    assert docs == [] and warnings


def test_article_cache_preserves_observed_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = JsonCache(tmp_path)
    observed = "2026-10-19T01:02:03Z"
    cache.set("article-deep-v3", {"url": "https://example.com/a"},
              {"url": "https://example.com/a", "text": "Fixture "*50, "retrieved_at": observed})
    monkeypatch.setattr("sources.web_search.requests.Session", Mock(side_effect=AssertionError("Không được gọi mạng")))
    assert WebSearch(Settings(root_dir=tmp_path), cache)._article("https://example.com/a") == ("Fixture "*50, "https://example.com/a", observed)


def test_youtube_quota_persists_and_fails_closed(tmp_path: Path) -> None:
    settings = Settings(root_dir=tmp_path, youtube_daily_quota=101)
    source = YouTubeSource(settings, JsonCache(settings.cache_dir))
    source._reserve(100, True)
    second = YouTubeSource(settings, JsonCache(settings.cache_dir))
    second._reserve(1, False)
    with pytest.raises(QuotaExceeded):
        second._reserve(1, False)
    (settings.cache_dir / "youtube_quota.json").write_text("broken", encoding="utf-8")
    with pytest.raises(QuotaExceeded):
        second._reserve(1, False)


def test_search_per_run_limit(tmp_path: Path) -> None:
    settings = Settings(root_dir=tmp_path, youtube_max_searches_per_run=1)
    source = YouTubeSource(settings, JsonCache(settings.cache_dir))
    source._reserve(100, True)
    with pytest.raises(QuotaExceeded):
        source._reserve(100, True)


def test_youtube_missing_key_without_network(tmp_path: Path) -> None:
    docs, warnings = YouTubeSource(Settings(root_dir=tmp_path), JsonCache(tmp_path)).collect("fixture")
    assert not docs and warnings


def test_youtube_cache_skips_requests_and_transcript_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(root_dir=tmp_path, youtube_api_key=SecretStr("fixture-only"))
    transcript = Mock()
    transcript.fetch.side_effect = RuntimeError("fixture error")
    source = YouTubeSource(settings, JsonCache(settings.cache_dir), transcript)
    calls: list[str] = []

    def response(endpoint: str, params: dict) -> dict:
        calls.append(endpoint)
        if endpoint == "search":
            return {"items": [{"id": {"videoId": "abcdefghijk"}, "snippet": {"title": "Fixture", "channelTitle": "Test"}}]}
        return {"items": [{"id": "abcdefghijk", "snippet": {"description": "Fixture"}, "statistics": {"viewCount": "12"}}]}

    monkeypatch.setattr(source, "_request", response)
    docs, warnings = source.collect("fixture")
    assert docs[0].statistics == {"viewCount": 12} and warnings
    source.collect("fixture")
    assert calls == ["search", "videos"]


def test_transcript_skip_and_negative_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    api = Mock(side_effect=RuntimeError("No transcript fixture"))
    monkeypatch.setattr("sources.transcripts.YouTubeTranscriptApi", api)
    provider = YouTubeTranscriptProvider(JsonCache(tmp_path))
    assert provider.fetch("abcdefghijk") is None
    assert provider.fetch("abcdefghijk") is None
    assert api.call_count == 1


def test_transcript_session_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    request = Mock(return_value=Mock())
    monkeypatch.setattr(requests.Session, "request", request)
    with TimeoutSession(7) as session:
        session.get("https://example.com")
    assert request.call_args.kwargs["timeout"] == 7


def test_quota_charged_for_failed_request_and_api_key_in_header(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(root_dir=tmp_path, youtube_api_key=SecretStr("fixture-only"))
    response = Mock()
    error_response = requests.Response()
    error_response.status_code = 403
    response.raise_for_status.side_effect = requests.HTTPError(response=error_response)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    get = Mock(return_value=response)
    monkeypatch.setattr("sources.youtube.requests.get", get)
    docs, warnings = YouTubeSource(settings, JsonCache(settings.cache_dir)).collect("fixture")
    assert not docs and warnings and get.call_count == 1
    ledger = json.loads((settings.cache_dir / "youtube_quota.json").read_text(encoding="utf-8"))
    assert ledger["estimated_units"] == 100 and ledger["search_calls"] == 1
    assert "key" not in get.call_args.kwargs["params"]
    assert get.call_args.kwargs["timeout"] == settings.request_timeout_sec
