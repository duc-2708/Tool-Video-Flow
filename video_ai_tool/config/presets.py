# file: config/presets.py
"""Các preset dùng chung cho CLI, Director và editor."""
from dataclasses import dataclass
from typing import Literal

VideoType = Literal["news", "review", "story"]
VideoFormat = Literal["tiktok", "youtube"]
VOICES = ("vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural")
SHOT_MIN_SECONDS = 1.5
SHOT_MAX_SECONDS = 4.0
DURATION_TOLERANCE = 0.10


@dataclass(frozen=True)
class FormatPreset:
    width: int
    height: int
    preview_width: int
    preview_height: int
    caption_safe_bottom_ratio: float
    fps: int = 30


FORMATS: dict[str, FormatPreset] = {
    "tiktok": FormatPreset(1080, 1920, 360, 640, 0.22),
    "youtube": FormatPreset(1920, 1080, 640, 360, 0.12),
}
VIDEO_TYPES: dict[str, str] = {
    "news": "Thông tin chính → bối cảnh → ý nghĩa → theo dõi cập nhật",
    "review": "Nhu cầu → tiêu chí → ưu/nhược điểm có nguồn → gợi ý phù hợp",
    "story": "Mở nút thắt → diễn biến → bước ngoặt → thông điệp",
}
