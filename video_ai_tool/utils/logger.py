# file: utils/logger.py
"""Log console/file UTF-8 với bộ lọc API key phổ biến."""
import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from utils.console import configure_console


class RedactSecrets(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        message = re.sub(r"(?i)([?&](?:key|api_key|access_token)=)[^&\s]+", r"\1[REDACTED]", message)
        message = re.sub(r"(?i)((?:authorization|x-goog-api-key)\s*[:=]\s*)(?:Bearer\s+)?[^\s,;]+", r"\1[REDACTED]", message)
        record.msg, record.args = message, ()
        return True


def get_logger(log_dir: Path, level: str = "INFO") -> logging.Logger:
    configure_console()
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("video_ai_tool")
    logger.setLevel(level)
    logger.propagate = False
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    for handler in (logging.StreamHandler(), file_handler):
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        handler.addFilter(RedactSecrets())
        logger.addHandler(handler)
    return logger
