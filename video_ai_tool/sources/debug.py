# file: sources/debug.py
"""CLI debug từng nguồn, không in payload hoặc lỗi mạng thô."""
import argparse
import logging
from typing import Literal
from config.settings import get_settings
from utils.cache import JsonCache, cache_key, write_json
from utils.console import configure_console


def run_debug(kind: Literal["web", "youtube", "transcript"]) -> int:
    configure_console()
    logging.getLogger().setLevel(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=f"Debug nguồn {kind}; chỉ lưu dữ liệu nghiên cứu")
    parser.add_argument("query", help="Chủ đề tìm kiếm hoặc video ID (transcript)")
    parser.add_argument("--limit", type=int, choices=range(1, 11), default=3)
    args = parser.parse_args()
    try:
        settings = get_settings()
        cache = JsonCache(settings.cache_dir, settings.cache_ttl_sec)
        if kind == "web":
            from sources.web_search import WebSearch
            docs, warnings = WebSearch(settings, cache).collect(args.query, args.limit)
            payload = {"sources": [doc.model_dump(mode="json") for doc in docs], "warnings": warnings}
        elif kind == "youtube":
            from sources.youtube import YouTubeSource
            docs, warnings = YouTubeSource(settings, cache).collect(args.query, args.limit)
            payload = {"sources": [doc.model_dump(mode="json") for doc in docs], "warnings": warnings}
        else:
            import re
            from sources.transcripts import YouTubeTranscriptProvider
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", args.query):
                print("Video ID phải gồm 11 ký tự hợp lệ.")
                return 1
            text = YouTubeTranscriptProvider(cache, settings.request_timeout_sec, settings.retry_attempts).fetch(args.query)
            payload = {"video_id": args.query, "transcript": text}
        path = settings.output_dir / "source_debug" / f"{kind}-{cache_key(args.query)[:12]}.json"
        write_json(path, payload)
        print(f"Đã lưu kết quả debug: {path}")
        return 0
    except KeyboardInterrupt:
        print("Đã dừng debug nguồn.")
        return 130
    except Exception:
        print("Không debug được nguồn. Kiểm tra cấu hình, mạng và quyền ghi. Không in lỗi thô để bảo vệ key.")
        return 1
