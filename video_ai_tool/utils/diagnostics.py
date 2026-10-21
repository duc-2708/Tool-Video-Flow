# file: utils/diagnostics.py
"""Ghi traceback đầy đủ sau khi che credentials, không ghi locals/.env."""
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import traceback
from urllib.parse import quote, quote_plus
from config.settings import read_configuration_values


class Diagnostics:
    def __init__(self, log_dir: Path, *, debug: bool = False, secrets: list[str] | None = None,
                 filename: str = "researcher_errors.log") -> None:
        self.path = log_dir / filename
        self.debug = debug
        # Chỉ thu thập credentials để lọc; không lưu/in các giá trị cấu hình.
        values = read_configuration_values()
        credentials = [value for name, value in values.items()
                       if value and re.search(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", name, re.I)]
        self.secrets = sorted({value for value in credentials + (secrets or []) if value}, key=len, reverse=True)

    def redact(self, text: str) -> str:
        for secret in self.secrets:
            for variant in {secret, quote(secret, safe=""), quote_plus(secret)}:
                text = text.replace(variant, "[REDACTED]")
        text = re.sub(r"AIza[\w-]{20,}", "[REDACTED]", text)
        text = re.sub(r"(?i)([?&](?:key|api_key|access_token)=)[^&\s\"']+", r"\1[REDACTED]", text)
        text = re.sub(r"(?i)((?:authorization|x-goog-api-key|api[_-]?key)[\"']?\s*[:=]\s*[\"']?)(?:Bearer\s+)?[^\s,;\"'}]+", r"\1[REDACTED]", text)
        return text

    def record_exception(self, error: BaseException, context: str) -> None:
        self.record(context + "\n" + self.format_exception(error))

    def format_exception(self, error: BaseException) -> str:
        """Traceback an toàn để CLI/UI hiển thị mà không đọc file log."""
        return self.redact("".join(traceback.format_exception(type(error), error, error.__traceback__)))

    def record(self, message: str) -> None:
        safe = self.redact(message)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(f"\n[{datetime.now(timezone.utc).isoformat()}] {safe}\n")
        if self.debug:
            print(safe, file=sys.stderr)
