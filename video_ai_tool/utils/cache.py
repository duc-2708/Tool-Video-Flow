# file: utils/cache.py
"""Cache JSON theo hash; ghi atomic để tránh file dở khi tiến trình bị ngắt."""
import hashlib
import json
import time
from pathlib import Path
from typing import Any
from utils.atomic_io import write_json_atomic


def cache_key(value: Any) -> str:
    def _json_default(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        if hasattr(obj, "dict"):
            return obj.dict()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False, default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# Backwards-compatible entry point for all existing pipeline callers.
write_json = write_json_atomic


class JsonCache:
    def __init__(self, directory: Path, ttl_sec: int = 86400) -> None:
        if ttl_sec < 1:
            raise ValueError("TTL cache phải lớn hơn 0.")
        self.directory = directory
        self.ttl_sec = ttl_sec

    def get(self, namespace: str, inputs: Any) -> Any | None:
        path = self.directory / f"{cache_key([namespace, inputs])}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            created_at = payload["created_at"]
            if not isinstance(created_at, (int, float)) or not 0 <= time.time() - created_at <= self.ttl_sec:
                return None
            return payload["data"]
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def set(self, namespace: str, inputs: Any, data: Any) -> None:
        path = self.directory / f"{cache_key([namespace, inputs])}.json"
        write_json(path, {"created_at": time.time(), "data": data})
