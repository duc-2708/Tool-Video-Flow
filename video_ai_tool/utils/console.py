# file: utils/console.py
"""Giữ tiếng Việt khi stdout/stderr được PowerShell chuyển qua pipe."""
import sys


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
