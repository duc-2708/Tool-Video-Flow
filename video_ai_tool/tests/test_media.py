# file: tests/test_media.py
"""FFmpeg probe thật và hồi quy việc import media không tự nạp .env."""
import os
from pathlib import Path
import subprocess
import sys
from imageio_ffmpeg import get_ffmpeg_exe
from config.settings import ROOT_DIR
from utils.media import video_info


def test_video_probe_reads_real_orientation_and_duration(tmp_path: Path) -> None:
    video = tmp_path / "fixture.mp4"
    subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=black:s=96x160:d=2:r=5", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
                   capture_output=True, check=True, timeout=20)
    width, height, duration = video_info(video)
    assert (width, height) == (96, 160) and 1.9 <= duration <= 2.1


def test_media_import_never_exports_dotenv_into_process_environment(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("MEDIA_DOTENV_MARKER=fixture-only\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT_DIR)}
    env.pop("MEDIA_DOTENV_MARKER", None)
    result = subprocess.run([sys.executable, "-c", "import os; import pipeline.assets; print('MEDIA_DOTENV_MARKER' in os.environ)"],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and result.stdout.strip() == "False"
