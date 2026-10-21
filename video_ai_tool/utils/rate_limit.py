# file: utils/rate_limit.py
"""Sliding window lưu trên đĩa, dùng chung giữa các tiến trình Pixabay."""
import json
import math
from pathlib import Path
import time
from utils.cache import write_json
from utils.file_lock import file_lock


class RateLimiter:
    def __init__(self, path: Path, limit: int = 90, window: float = 60) -> None:
        self.path, self.limit, self.window = path, limit, window

    def _read(self) -> dict:
        if not self.path.exists():
            return {"times": [], "blocked_until": 0.0}
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(state, dict) or not isinstance(state["times"], list):
                raise ValueError
            state["times"] = [float(t) for t in state["times"]]
            state["blocked_until"] = float(state["blocked_until"])
            if not all(math.isfinite(t) and t >= 0 for t in state["times"] + [state["blocked_until"]]):
                raise ValueError
            return state
        except (ValueError, TypeError, KeyError):
            raise ValueError("File giới hạn tốc độ không hợp lệ; không gọi API để tránh vượt hạn mức.") from None

    def acquire(self) -> None:
        while True:
            with file_lock(self.path.with_suffix(".lock")):
                now = time.time()
                state = self._read()
                state["times"] = [t for t in state["times"] if t > now - self.window]
                wait = max(0.0, state["blocked_until"] - now)
                if len(state["times"]) >= self.limit:
                    wait = max(wait, min(state["times"]) + self.window - now + 0.05)
                if wait <= 0:
                    state["times"].append(now)
                    write_json(self.path, state)
                    return
            time.sleep(min(wait, 5.0))

    def cooldown(self, seconds: float) -> None:
        with file_lock(self.path.with_suffix(".lock")):
            state = self._read()
            state["blocked_until"] = max(state["blocked_until"], time.time() + max(seconds, 1.0))
            write_json(self.path, state)
