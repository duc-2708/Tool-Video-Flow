"""Bounded HTTP, metadata cache and isolated errors for trend providers."""
import json
import math
import re
from urllib.parse import urlsplit
import requests
from schemas.trends import TrendItem
from utils.cache import JsonCache
from utils.diagnostics import Diagnostics
from utils.file_lock import file_lock


def count(value):
    try:
        number = float(value or 0)
        return max(0, int(number)) if math.isfinite(number) else 0
    except (TypeError, ValueError, OverflowError):
        return 0


def short_text(value, limit=600):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def safe_link(value):
    try:
        from ipaddress import ip_address
        parsed = urlsplit(str(value))
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
            return False
        if parsed.hostname in {"localhost"} or "." not in parsed.hostname:
            return False
        try:
            return ip_address(parsed.hostname).is_global
        except ValueError:
            return True
    except ValueError:
        return False


class BaseProvider:
    name = "base"

    def __init__(self, settings, config, *, region=None, repository=None):
        self.settings, self.config = settings, config
        self.region = region or config.region
        self.repository = repository
        self.cache = JsonCache(settings.cache_dir / "trends", config.cache_ttl_sec)
        self.diagnostics = Diagnostics(settings.logs_dir, filename="trend_scout_errors.log",
            secrets=[settings.scrapecreators_api_key.get_secret_value(), settings.gemini_api_key.get_secret_value()])
        self.warnings = []

    def warn(self, message, error=None):
        value = self.diagnostics.redact(self.name + ": " + message)
        self.warnings.append(value)
        if error is not None:
            self.diagnostics.record_exception(error, value)
        else:
            self.diagnostics.record(value)

    def request(self, url, params=None, headers=None, *, text=False):
        # URLs are fixed provider endpoints, never media URLs returned by an API.
        with requests.get(url, params=params, headers=headers or {"User-Agent": "LocalVideoTrendScout/1.0"},
                          timeout=min(self.settings.request_timeout_sec, 30), allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code}; nguồn tạm bỏ qua, không vượt chặn.")
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 3_000_000:
                    raise ValueError("Metadata vượt giới hạn 3 MB.")
            decoded = bytes(body).decode("utf-8-sig")
            return decoded if text else json.loads(decoded)

    def cached(self, query, loader):
        inputs = {"query": query, "region": self.region, "version": 1}
        from utils.cache import cache_key
        lock = self.settings.cache_dir / "trends" / (cache_key([self.name, inputs]) + ".lock")
        with file_lock(lock):
            records = self.cache.get(self.name, inputs)
            if isinstance(records, list):
                try:
                    return [TrendItem.model_validate(row) for row in records]
                except ValueError:
                    pass
            result = loader()
            # Persist only the strict, small TrendItem projection, never API/media payloads.
            self.cache.set(self.name, inputs, [r.model_dump(mode="json") for r in result])
            return result

    def fetch(self, category, limit):
        try:
            return self._fetch(category, limit)[:limit]
        except Exception as error:
            self.warn(str(error), error)
            return []

    def category_options(self, category):
        return self.config.categories.get(category.category_id, {})

    def relevant(self, title, category):
        from pipeline.topics_history import normalized
        words = set(normalized(title).split())
        keywords = self.category_options(category).get("keywords") or category.keywords_en + category.keywords_vi
        return category.category_id == "tin-tuc" or any(words & set(normalized(k).split()) for k in keywords)
