# file: providers/tts_edge.py
"""Edge TTS từng cảnh, cache theo narration/voice và đo MP3 bằng FFmpeg."""
from utils.atomic_io import discard_temp_file, replace_file_retry
import math
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4
import aiohttp
import edge_tts
from edge_tts.exceptions import NoAudioReceived
from imageio_ffmpeg import get_ffmpeg_exe
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter
from config.settings import Settings
from utils.cache import cache_key
from utils.diagnostics import Diagnostics
from utils.file_lock import file_lock
from utils.media import measured_audio_duration


def audio_duration(path: Path) -> float:
    duration = measured_audio_duration(path)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Không đọc được độ dài audio hợp lệ.")
    return duration


class EdgeTTSProvider:
    def __init__(self, settings: Settings, diagnostics: Diagnostics) -> None:
        self.settings, self.diagnostics = settings, diagnostics

    def synthesize(self, text: str, voice: str, destination: Path) -> float:
        key = cache_key({"text": text, "voice": voice, "rate": "+0%", "version": 1})
        cached = self.settings.cache_dir / "tts" / (key + ".mp3")
        cached.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(cached.with_suffix(".lock"), timeout=30):
            valid = False
            if cached.exists():
                try:
                    valid = audio_duration(cached) >= 1.5
                except Exception as error:
                    self.diagnostics.record_exception(error, "TTS cache hỏng, tạo lại")
            if not valid:
                temporary = cached.with_name(key + "-" + uuid4().hex + ".tmp.mp3")
                @retry(retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError, NoAudioReceived)),
                       stop=stop_after_attempt(self.settings.retry_attempts),
                       wait=wait_exponential_jitter(initial=1, max=30), reraise=True)
                def generate() -> None:
                    try:
                        edge_tts.Communicate(text, voice=voice, connect_timeout=int(self.settings.request_timeout_sec),
                            receive_timeout=int(self.settings.request_timeout_sec)).save_sync(str(temporary))
                        if audio_duration(temporary) < 1.5:
                            padded = temporary.with_name(temporary.stem + "-padded.mp3")
                            try:
                                subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                                    "-i", str(temporary), "-af", "apad", "-t", "1.5", "-c:a", "libmp3lame", str(padded)],
                                    capture_output=True, check=True, timeout=self.settings.request_timeout_sec)
                                replace_file_retry(padded, temporary)
                            finally:
                                discard_temp_file(padded)
                    except Exception as error:
                        self.diagnostics.record_exception(error, "Edge TTS tạo audio")
                        raise
                try:
                    generate()
                    replace_file_retry(temporary, cached)
                finally:
                    discard_temp_file(temporary)
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Copy atomic; file scene cũ không bị hỏng khi giọng mới chưa tạo xong.
            temporary_copy = destination.with_name(destination.stem + "-" + uuid4().hex + ".tmp.mp3")
            try:
                shutil.copyfile(cached, temporary_copy)
                replace_file_retry(temporary_copy, destination)
            finally:
                discard_temp_file(temporary_copy)
        return audio_duration(destination)
