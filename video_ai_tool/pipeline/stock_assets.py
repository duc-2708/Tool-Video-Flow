# file: pipeline/stock_assets.py
"""Tải stock đã kiểm soát nguồn và tạo nền màu fallback bằng code."""
from utils.atomic_io import discard_temp_file, replace_file_retry
import os
from pathlib import Path
import shutil
from urllib.parse import urljoin, urlsplit
from uuid import uuid4
import requests
from PIL import Image, ImageDraw, ImageFont
from config.settings import Settings
from providers.stock_base import StockItem, StockProvider
from schemas.assets import ShotAsset
from schemas.edit_plan import Shot
from utils.cache import cache_key
from utils.diagnostics import Diagnostics
from utils.retry import network_retry
from utils.media import video_info


def allowed_media_url(url: str, provider: str, *, source: bool = False) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    roots = {"pixabay": {"pixabay.com", "www.pixabay.com", "cdn.pixabay.com"},
             "pexels": {"pexels.com", "www.pexels.com", "videos.pexels.com", "images.pexels.com"}}
    allowed = roots.get(provider, set())
    if source:
        allowed = {provider + ".com", "www." + provider + ".com"}
    return parts.scheme == "https" and not parts.username and not parts.password and parts.port in {None, 443} and host in allowed


def orientation_matches(width: int, height: int, video_format: str) -> bool:
    return height > width if video_format == "tiktok" else width > height


def probe_media(path: Path, kind: str) -> tuple[int, int, float | None]:
    if kind == "image":
        with Image.open(path) as image:
            size = image.size
            image.verify()
        return size[0], size[1], None
    return video_info(path)


class MediaDownloader:
    def __init__(self, settings: Settings, diagnostics: Diagnostics) -> None:
        self.settings, self.diagnostics = settings, diagnostics

    def download(self, item: StockItem) -> Path:
        url = str(item.download_url)
        if not allowed_media_url(url, item.provider) or not allowed_media_url(str(item.source_url), item.provider, source=True):
            raise ValueError("Asset không có URL media/nguồn thuộc Pixabay hoặc Pexels được phép.")
        if any(secret in url or secret in str(item.source_url) for secret in self.diagnostics.secrets):
            raise ValueError("URL asset chứa credentials; không tải hoặc cache.")
        suffix = ".mp4" if item.kind == "video" else ".jpg"
        path = self.settings.cache_dir / "stock_files" / (cache_key([item.provider, item.asset_id, url]) + suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            try:
                probe_media(path, item.kind)
                return path
            except Exception as error:
                self.diagnostics.record_exception(error, "Stock cache hỏng; tải lại")
        temporary = path.with_name(path.stem + "-" + uuid4().hex + ".tmp" + suffix)
        @network_retry(self.settings.retry_attempts)
        def fetch() -> None:
            try:
                current = url
                with requests.Session() as session:
                    for _ in range(5):
                        if not allowed_media_url(current, item.provider):
                            raise ValueError("Chặn chuyển hướng ra ngoài CDN stock cho phép.")
                        with session.get(current, stream=True, allow_redirects=False, timeout=self.settings.request_timeout_sec) as response:
                            if response.status_code in {301, 302, 303, 307, 308}:
                                current = urljoin(current, response.headers.get("Location", ""))
                                continue
                            response.raise_for_status()
                            content_type = response.headers.get("Content-Type", "").lower()
                            if not (content_type.startswith("video/") if item.kind == "video" else content_type.startswith("image/")):
                                raise ValueError("CDN không trả đúng loại video/ảnh.")
                            total = 0
                            with temporary.open("wb") as stream:
                                for block in response.iter_content(65536):
                                    total += len(block)
                                    if total > 200_000_000:
                                        raise ValueError("Stock vượt giới hạn tải 200 MB.")
                                    stream.write(block)
                            probe_media(temporary, item.kind)
                            return
                raise ValueError("CDN chuyển hướng quá nhiều lần.")
            except Exception as error:
                self.diagnostics.record_exception(error, "Stock media download")
                raise
        try:
            fetch()
            replace_file_retry(temporary, path)
        finally:
            discard_temp_file(temporary)
        return path


def color_card(path: Path, text: str, video_format: str) -> None:
    size = (540, 960) if video_format == "tiktok" else (960, 540)
    image = Image.new("RGB", size, "#182237")
    draw = ImageDraw.Draw(image)
    font = None
    candidates = [Path(os.environ.get("WINDIR", "")) / "Fonts" / "segoeui.ttf", Path("DejaVuSans.ttf")]
    for candidate in candidates:
        try:
            font = ImageFont.truetype(str(candidate), 30)
            break
        except OSError:
            continue
    font = font or ImageFont.load_default(size=28)
    lines, current = [], ""
    for word in text.split():
        proposed = (current + " " + word).strip()
        if draw.textbbox((0, 0), proposed, font=font)[2] > size[0] - 70 and current:
            lines.append(current)
            current = word
        else:
            current = proposed
    if current:
        lines.append(current)
    lines = lines[:10]
    y = (size[1] - len(lines) * 42) / 2
    for line in lines:
        draw.text((size[0] / 2, y), line, font=font, fill="white", anchor="mt", stroke_width=1)
        y += 42
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")


def resolve_stock(shot: Shot, scene_id: int, shot_id: int, narration: str, video_format: str,
                  project: Path, providers: list[StockProvider], downloader: MediaDownloader,
                  diagnostics: Diagnostics, exclude: tuple[str, str] | None = None) -> ShotAsset:
    failures = []
    graphic=bool(shot.visual and shot.visual.template!="stock")
    if shot.type != "text_card" and not graphic:
        # Duyệt hết video trước khi fallback ảnh; Pixabay luôn đứng trước Pexels.
        for kind in ("video", "image"):
            for provider in providers:
                try:
                    candidates = provider.search(shot.query, video_format, kind)
                except Exception as error:
                    diagnostics.record_exception(error, "Stock search fallback")
                    failures.append("Nguồn stock lỗi API hoặc chưa có key")
                    continue
                matching = [item for item in candidates if orientation_matches(item.width, item.height, video_format)]
                # Video sai orientation không được tải; ảnh khác tỷ lệ có thể crop ở editor sau.
                candidates = matching if kind == "video" else matching + [item for item in candidates if item not in matching]
                candidates = sorted(candidates, key=lambda item: (not orientation_matches(item.width, item.height, video_format),
                    (item.duration_sec or 0) < shot.duration_sec if kind == "video" else False))
                for item in candidates[:4]:
                    if exclude == (item.provider, item.asset_id):
                        continue
                    try:
                        cached = downloader.download(item)
                        width, height, duration = probe_media(cached, kind)
                        if kind == "video" and not orientation_matches(width, height, video_format):
                            raise ValueError("Kích thước video thật khác orientation yêu cầu.")
                        destination = project / "clips" / f"scene_{scene_id}_shot_{shot_id}_{cached.name}"
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        temporary = destination.with_name(uuid4().hex + destination.suffix)
                        try:
                            shutil.copyfile(cached, temporary)
                            replace_file_retry(temporary, destination)
                        finally:
                            discard_temp_file(temporary)
                        loop = kind == "video" and bool(duration and duration + 0.02 < shot.duration_sec)
                        reasons = []
                        if kind == "image":
                            reasons.append("Dùng ảnh thay video")
                        if not orientation_matches(width, height, video_format):
                            reasons.append("Ảnh khác tỷ lệ; cần crop khi dựng")
                        if loop:
                            reasons.append("Video ngắn hơn shot; cần loop khi dựng")
                        return ShotAsset(shot_id=shot_id, query=shot.query, media_type=kind,
                            path=destination.relative_to(project).as_posix(), provider=item.provider,
                            asset_id=item.asset_id, author=item.author, source_url=str(item.source_url),
                            fallback=bool(reasons), fallback_reason="; ".join(reasons) or None,
                            media_duration_sec=duration, requires_loop=loop)
                    except Exception as error:
                        diagnostics.record_exception(error, "Bỏ qua stock không tải/đọc được")
                        failures.append("Clip không tải/đọc được")
    text = diagnostics.redact(shot.text_overlay or narration)
    path = project / "clips" / f"scene_{scene_id}_shot_{shot_id}_fallback_{cache_key([text, video_format])[:10]}.png"
    color_card(path, text, video_format)
    intentional = shot.type == "text_card" or graphic
    return ShotAsset(shot_id=shot_id, query=shot.query, media_type="color", path=path.relative_to(project).as_posix(),
        provider="generated", fallback=not intentional,
        fallback_reason=None if intentional else "Không có stock phù hợp; dùng nền màu và chữ. " + "; ".join(dict.fromkeys(failures)))
