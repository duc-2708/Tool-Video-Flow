# file: tests/test_stock.py
"""Stock API: cache query/format, orientation, download và giới hạn tốc độ."""
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock
import pytest
import requests
from PIL import Image
from pydantic import SecretStr
from config.settings import Settings
from pipeline.stock_assets import MediaDownloader, resolve_stock
from providers.stock_base import StockItem
from providers.stock_pixabay import PixabayProvider
from providers.stock_pexels import PexelsProvider
from schemas.edit_plan import Shot
from utils.diagnostics import Diagnostics
from utils.rate_limit import RateLimiter


def item(kind: str = "image", asset_id: str = "1", **kwargs) -> StockItem:
    return StockItem(provider="pixabay", asset_id=asset_id, kind=kind,
        download_url=f"https://cdn.pixabay.com/photo/{asset_id}.jpg", source_url=f"https://pixabay.com/photos/test-{asset_id}/",
        author="Fixture author", width=540, height=960, duration_sec=5.0 if kind == "video" else None, **kwargs)


def test_optional_pexels_is_silent_and_never_calls_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    api = Mock(side_effect=AssertionError("Không được gọi API"))
    monkeypatch.setattr("providers.stock_pexels.stock_json", api)
    assert PexelsProvider(Settings(root_dir=tmp_path), Diagnostics(tmp_path / "logs")).search("video editing", "tiktok", "video") == []
    assert api.call_count == 0


def test_pixabay_cache_query_format_and_kind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    api = Mock(return_value={"hits": [{"id": 1, "pageURL": "https://pixabay.com/videos/id-1/", "user": "Fixture author", "duration": 6,
        "videos": {"medium": {"url": "https://cdn.pixabay.com/video/1.mp4", "width": 540, "height": 960}}}]})
    monkeypatch.setattr("providers.stock_pixabay.stock_json", api)
    settings = Settings(root_dir=tmp_path, pixabay_api_key=SecretStr("fixture-only"))
    provider = PixabayProvider(settings, Diagnostics(tmp_path / "logs"))
    assert provider.search("video editing", "tiktok", "video")[0].author == "Fixture author"
    provider.search("video editing", "tiktok", "video")
    assert api.call_count == 1
    provider.search("video editing", "youtube", "video")
    assert api.call_count == 2 and provider.cache.ttl_sec >= 86400


def test_media_download_cache_and_reject_social_redirect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    content = BytesIO()
    Image.new("RGB", (20, 40)).save(content, format="JPEG")
    response = Mock()
    response.status_code, response.headers = 200, {"Content-Type": "image/jpeg"}
    response.iter_content.return_value = [content.getvalue()]
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    session = Mock()
    session.get.return_value = response
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("pipeline.stock_assets.requests.Session", Mock(return_value=session))
    downloader = MediaDownloader(Settings(root_dir=tmp_path), Diagnostics(tmp_path / "logs"))
    path = downloader.download(item())
    assert path.is_file() and downloader.download(item()) == path and session.get.call_count == 1
    response.status_code, response.headers = 302, {"Location": "https://www.youtube.com/watch?v=fixture"}
    with pytest.raises(ValueError):
        downloader.download(item(asset_id="2"))
    assert session.get.call_count == 2


def test_sliding_window_waits_and_persists_cooldown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [1000.0]
    monkeypatch.setattr("utils.rate_limit.time.time", lambda: clock[0])
    monkeypatch.setattr("utils.rate_limit.time.sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    limiter = RateLimiter(tmp_path / "rate.json", limit=2)
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()
    assert clock[0] >= 1060
    limiter.cooldown(30)
    RateLimiter(tmp_path / "rate.json", limit=2).acquire()
    assert clock[0] >= 1090


def test_resolver_prefers_orientation_and_long_video(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    long = item("video", "long")
    short = long.model_copy(update={"asset_id": "short", "duration_sec": 1.0})
    landscape = long.model_copy(update={"asset_id": "landscape", "width": 960, "height": 540})
    provider = Mock()
    provider.search.return_value = [landscape, short, long]
    file = tmp_path / "fake.mp4"
    file.write_bytes(b"fixture")
    downloader = Mock()
    downloader.download.return_value = file
    monkeypatch.setattr("pipeline.stock_assets.probe_media", lambda *args: (540, 960, 5.0))
    shot = Shot(type="stock_video", query="video editing", duration_sec=3.0, effect="none", text_overlay=None)
    asset = resolve_stock(shot, 1, 1, "Fixture", "tiktok", tmp_path / "project", [provider], downloader, Diagnostics(tmp_path / "logs"))
    assert asset.asset_id == "long" and not asset.fallback


def test_stock_429_retries_honors_cooldown_and_redacts_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from providers.stock_http import stock_json
    first, second = requests.Response(), requests.Response()
    first.status_code, first.url = 429, "https://pixabay.com/api/?key=fixture-api-secret"
    first._content = b"API rate limit exceeded fixture-api-secret"
    first.headers["Retry-After"] = "60"
    second.status_code, second._content = 200, b'{"hits": []}'
    get = Mock(side_effect=[first, second])
    monkeypatch.setattr("providers.stock_http.requests.get", get)
    limiter = Mock()
    diagnostics = Diagnostics(tmp_path / "logs", secrets=["fixture-api-secret"])
    result = stock_json("https://pixabay.com/api/", Settings(root_dir=tmp_path, retry_attempts=2), diagnostics,
                        params={"key": "fixture-api-secret"}, limiter=limiter)
    assert result == {"hits": []} and get.call_count == 2
    assert limiter.acquire.call_count == 2 and limiter.cooldown.call_args.args == (60.0,)
    assert "fixture-api-secret" not in diagnostics.path.read_text(encoding="utf-8")


def test_pexels_parses_optional_video_provider_and_caches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    api = Mock(return_value={"videos": [{"id": 123, "url": "https://www.pexels.com/video/fixture-123/",
        "duration": 6, "user": {"name": "Fixture author"}, "video_files": [{"file_type": "video/mp4", "width": 720,
        "height": 1280, "link": "https://videos.pexels.com/video-files/fixture.mp4"}]}]})
    monkeypatch.setattr("providers.stock_pexels.stock_json", api)
    provider = PexelsProvider(Settings(root_dir=tmp_path, pexels_api_key=SecretStr("fixture-only")), Diagnostics(tmp_path / "logs"))
    assert provider.search("video editing", "tiktok", "video")[0].author == "Fixture author"
    provider.search("video editing", "tiktok", "video")
    assert api.call_count == 1 and api.call_args.args[0].endswith("/v1/videos/search")
    assert api.call_args.kwargs["params"]["orientation"] == "portrait"
