"""MoviePy must never implicitly export the project's .env into os.environ."""
import os
from imageio_ffmpeg import get_ffmpeg_exe

_previous = os.environ.get("PYTHON_DOTENV_DISABLED")
_previous_ffmpeg = os.environ.get("FFMPEG_BINARY")
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["FFMPEG_BINARY"] = get_ffmpeg_exe()
try:
    from moviepy import AudioClip, AudioFileClip, VideoClip, VideoFileClip
    from moviepy import config
    config.FFMPEG_BINARY = get_ffmpeg_exe()
finally:
    if _previous is None:
        os.environ.pop("PYTHON_DOTENV_DISABLED", None)
    else:
        os.environ["PYTHON_DOTENV_DISABLED"] = _previous
    if _previous_ffmpeg is None:
        os.environ.pop("FFMPEG_BINARY",None)
    else:
        os.environ["FFMPEG_BINARY"] = _previous_ffmpeg
