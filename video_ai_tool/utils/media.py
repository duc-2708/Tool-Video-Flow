# file: utils/media.py
"""Đo media bằng FFmpeg đi kèm; không để thư viện media tự nạp .env."""
import math
from pathlib import Path
import subprocess
from imageio_ffmpeg import get_ffmpeg_exe, read_frames


def measured_audio_duration(path: Path) -> float:
    # Đếm sample đã decode, gồm phần silence chủ động; không ước tính từ số chữ/bitrate.
    result = subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-vn", "-t", "900", "-ac", "1", "-ar", "24000", "-f", "f32le", "pipe:1"],
        check=True, capture_output=True, timeout=60)
    duration = len(result.stdout) / (24000 * 4)
    if duration <= 0 or duration >= 900:
        raise ValueError("Audio rỗng hoặc vượt giới hạn đo 900 giây/cảnh.")
    return duration


def pad_audio_to(path: Path,duration: float,timeout=60):
    """Only append silence; keep narration intact, using bundled FFmpeg."""
    import uuid
    from utils.atomic_io import replace_file_retry,discard_temp_file
    path=Path(path);temporary=path.with_name(f".{path.stem}-{uuid.uuid4().hex}.mp3")
    try:
        subprocess.run([get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y","-i",str(path),"-af","apad","-t",str(duration),"-c:a","libmp3lame",str(temporary)],capture_output=True,check=True,timeout=timeout)
        replace_file_retry(temporary,path)
        return measured_audio_duration(path)
    finally: discard_temp_file(temporary)


def video_info(path: Path) -> tuple[int, int, float]:
    reader = read_frames(str(path), pix_fmt="rgb24", output_params=["-frames:v", "1"])
    try:
        metadata = next(reader)
        next(reader)
        duration = float(metadata["duration"])
        width, height = metadata["size"]
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Không đọc được thời lượng video hợp lệ.")
        return int(width), int(height), duration
    finally:
        reader.close()
