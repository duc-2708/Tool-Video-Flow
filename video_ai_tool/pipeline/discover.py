"""Discover topics or launch the existing pipeline; AI clips stay OFF."""
import argparse
from pathlib import Path
from config.settings import get_settings
from pipeline.run_all import RunConfig,run_all
from pipeline.topics_history import already_made,history_rows
from schemas.topic_discovery import TopicSuggestion,DiscoveryHint
from sources.topic_discovery import discover_topics
from utils.cache import write_json
from utils.console import configure_console
from utils.diagnostics import Diagnostics


def topic_config(suggestion,category,*,topic=None,review=True,style_preset=None):
    suggestion=TopicSuggestion.model_validate(suggestion)
    return RunConfig(topic=topic or suggestion.topic,category=category,style_preset=style_preset,video_type=suggestion.suggested_type,mode="review" if review else "auto",
        discovery=DiscoveryHint(category=category,suggestion=suggestion),ai_clips=0)


def auto_pick(result,settings):
    rows=history_rows(settings.output_dir)
    return next((p for p in result["topics"] if not already_made(p["topic"],rows,source_urls=p["source_urls"])),None)


def launch_topic(suggestion,category,settings,*,review=True,topic=None):
    config=topic_config(suggestion,category,topic=topic,review=review)
    if already_made(config.topic,history_rows(settings.output_dir),source_urls=[str(u) for u in config.discovery.suggestion.source_urls]):
        raise ValueError("Chủ đề này đã có project trong 14 ngày gần nhất; chọn sự kiện khác.")
    return run_all(config,settings=settings)


def main():
    configure_console()
    parser=argparse.ArgumentParser(description="Khám phá chủ đề bằng RSS/news; tự chọn mặc định dừng duyệt kịch bản.")
    parser.add_argument("--category",required=True)
    parser.add_argument("--region",choices=["vn","global","both"],default="both")
    parser.add_argument("--days",type=int,choices=[1,3,7],default=3)
    parser.add_argument("--count",type=int,default=5)
    parser.add_argument("--youtube-trends",action="store_true")
    parser.add_argument("--auto-pick",action="store_true")
    parser.add_argument("--review",action="store_true",help="Mặc định auto-pick luôn dừng để duyệt kịch bản")
    args=parser.parse_args()
    settings=get_settings()
    diagnostics=Diagnostics(settings.logs_dir,filename="topic_discovery_errors.log")
    try:
        result=discover_topics(args.category,settings,region=args.region,time_window_days=args.days,count=args.count,use_youtube=args.youtube_trends)
        write_json(settings.output_dir/"topics_latest.json",result)
        for warning in result["warnings"]: print(diagnostics.redact(warning))
        for index,p in enumerate(result["topics"],1):
            print(f"{index}. {p['topic']} | {p['score']}/10 | {p['suggested_type']}")
            for url in p["source_urls"]: print("   "+url)
        if args.auto_pick:
            chosen=auto_pick(result,settings)
            if not chosen: print("Không có chủ đề mới để tự chọn.");return 2
            project=launch_topic(chosen,result["category"],settings,review=True)
            print(f"Project: {project} — đã dừng để duyệt kịch bản trong UI.")
        return 0
    except Exception as error:
        diagnostics.record_exception(error,"CLI khám phá chủ đề")
        print(diagnostics.redact(str(error)))
        return 1

if __name__=="__main__": raise SystemExit(main())
