"""Bounded metadata-only probe. Never persist authors, media URLs or credentials."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests
from config.settings import read_configuration_values
from db.repository import Repository
from utils.atomic_io import write_json_atomic
from utils.diagnostics import Diagnostics
from utils.console import configure_console

BASE = "https://api.scrapecreators.com"
PROBES = (
    ("trending_vn", "/v1/tiktok/get-trending-feed", {"region": "VN"}),
    ("trending_us", "/v1/tiktok/get-trending-feed", {"region": "US"}),
    ("keyword_ai", "/v1/tiktok/search/keyword", {"query": "AI"}),
    ("hashtag_ai", "/v1/tiktok/search/hashtag", {"hashtag": "AI"}),
)


def field_types(value, prefix="", result=None):
    """Describe observed shape without any personal field values."""
    result = {} if result is None else result
    if len(result) > 1500:
        return result
    result[prefix or "$root"] = type(value).__name__
    if isinstance(value, dict):
        for key, item in value.items():
            field_types(item, f"{prefix}.{key}".lstrip("."), result)
    elif isinstance(value, list):
        for item in value[:1]:
            field_types(item, prefix + "[]", result)
    return result


def private_text(value, diagnostics):
    text = diagnostics.redact(str(value or ""))
    text = re.sub(r"https?://\S+|@[\w.]+|[\w.+-]+@[\w.-]+", "[redacted]", text)
    return text[:600]


def project_response(raw, diagnostics):
    """Preserve native metadata field names; discard ALL nonallowlisted content."""
    if not isinstance(raw, dict):
        return {"unexpected_type": type(raw).__name__}
    result = {k: raw[k] for k in ("success", "status_code", "credits_charged", "credits_remaining", "cursor", "has_more")
              if isinstance(raw.get(k), (bool, int, float, str))}
    for key in ("message", "error"):
        if key in raw:
            result[key] = private_text(raw[key] if isinstance(raw[key], str) else "API error object; see field_types", diagnostics)
    for key in ("aweme_list", "search_item_list", "item_list", "data"):
        rows = raw.get(key)
        if not isinstance(rows, list):
            continue
        result[key] = []
        for record in rows[:30]:
            if not isinstance(record, dict):
                continue
            video = record.get("aweme_info") if isinstance(record.get("aweme_info"), dict) else record
            item = {k: video[k] for k in ("aweme_id", "id", "desc_language", "region", "create_time")
                    if isinstance(video.get(k), (str, int, float))}
            if "desc" in video:
                item["desc"] = private_text(video["desc"], diagnostics)
            stats = video.get("statistics")
            if isinstance(stats, dict):
                item["statistics"] = {k: v for k, v in stats.items() if k in
                    {"play_count", "digg_count", "share_count", "comment_count"} and isinstance(v, (int, float, str))}
            url = str(video.get("url") or "")
            match = re.search(r"/(video|photo)/(\d+)", url)
            if match:
                item["url"] = f"https://www.tiktok.com/@redacted/{match[1]}/{match[2]}"
            result[key].append({"aweme_info": item} if "aweme_info" in record else item)
    return result


def probe(root=ROOT, *, maximum=4):
    root = Path(root)
    key = str(read_configuration_values(root / ".env").get("SCRAPECREATORS_API_KEY") or "").strip()
    target = root / "tests/fixtures"
    diagnostics = Diagnostics(root / "logs", filename="trend_scout_errors.log", secrets=[key])
    report = {"observed_at": datetime.now(timezone.utc).isoformat(), "requests": [], "status": "no_key"}
    if not key:
        report["note"] = "CHƯA XÁC NHẬN: thiếu SCRAPECREATORS_API_KEY; 0 HTTP request, không có fixture API thật."
        write_json_atomic(target / "scrapecreators_probe_report.json", report)
        print(report["note"])
        return report
    repo = Repository(root / "data/app.db")
    previous = target / "scrapecreators_probe_report.json"
    if previous.exists():
        try:
            report["requests"] = json.loads(previous.read_text(encoding="utf-8")).get("requests", [])
        except (OSError, ValueError):
            pass
    report["status"] = "finished"
    # Four endpoints, no HTTP retry/redirect; an interrupted call still counts.
    for name, endpoint, params in PROBES[:max(0, min(int(maximum), 6))]:
        if (target / f"scrapecreators_{name}.json").exists():
            continue  # A repeat invocation does not silently buy the same fixtures.
        if len(report["requests"]) >= 6:
            report["status"] = "probe_limit_reached"
            break
        token = repo.reserve_trend_call("scrapecreators", 30, endpoint)
        if token is None:
            report["status"] = "budget_exhausted"
            break
        entry = {"endpoint": endpoint, "params": params, "credits_charged": None}
        try:
            response = requests.get(BASE + endpoint, params=params, headers={"x-api-key": key},
                                    timeout=30, allow_redirects=False)
            entry["http_status"] = response.status_code
            raw = response.json()
            charged = raw.get("credits_charged") if isinstance(raw, dict) else None
            repo.finish_trend_call(token, charged)
            entry["credits_charged"] = charged
            write_json_atomic(target / f"scrapecreators_{name}.json", {
                "provenance": "live_probe", "request": {"endpoint": endpoint, "params": params},
                "http_status": response.status_code, "field_types": field_types(raw),
                "payload": project_response(raw, diagnostics)})
        except Exception as error:
            diagnostics.record_exception(error, "ScrapeCreators probe " + name)
            entry["error"] = diagnostics.redact(str(error))
        report["requests"].append(entry)
        write_json_atomic(target / "scrapecreators_probe_report.json", report)
    return report


def main():
    configure_console()
    parser = argparse.ArgumentParser(description="Khảo sát tối đa 4 request metadata; không tải media.")
    parser.parse_args()
    result = probe()
    for entry in result["requests"]:
        print(f"{entry['endpoint']}: HTTP {entry.get('http_status', '?')}; credits_charged={entry['credits_charged']}")
    return 2 if result["status"] == "no_key" else 0


if __name__ == "__main__":
    raise SystemExit(main())
