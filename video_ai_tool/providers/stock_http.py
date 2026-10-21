# file: providers/stock_http.py
"""HTTP cho stock: timeout/retry, chẩn đoán và giới hạn tốc độ API."""
from email.utils import parsedate_to_datetime
import time
from typing import Any
import requests
from config.settings import Settings
from utils.diagnostics import Diagnostics
from utils.rate_limit import RateLimiter
from utils.retry import network_retry


def stock_json(url: str, settings: Settings, diagnostics: Diagnostics, *, params: dict,
               headers: dict | None = None, limiter: RateLimiter | None = None) -> dict[str, Any]:
    @network_retry(settings.retry_attempts)
    def send() -> dict:
        if limiter:
            limiter.acquire()
        try:
            with requests.get(url, params=params, headers=headers, timeout=settings.request_timeout_sec) as response:
                if limiter and (response.status_code == 429 or response.headers.get("X-RateLimit-Remaining") == "0"):
                    value = response.headers.get("Retry-After") or response.headers.get("X-RateLimit-Reset") or "60"
                    try:
                        delay = float(value)
                    except ValueError:
                        try:
                            delay = parsedate_to_datetime(value).timestamp() - time.time()
                        except (ValueError, TypeError, OverflowError):
                            delay = 60.0
                    limiter.cooldown(max(delay, 1.0))
                if response.status_code >= 400:
                    diagnostics.record(f"Stock HTTP {response.status_code}: {response.text[:2000]}")
                response.raise_for_status()
                return response.json()
        except Exception as error:
            diagnostics.record_exception(error, "Stock API request")
            raise
    return send()
