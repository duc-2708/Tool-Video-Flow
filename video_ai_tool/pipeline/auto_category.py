"""Category -> existing run_all, with durable discovery and up to three topics."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from config.settings import get_settings
from pipeline.projects import create_project,read_json
from pipeline.run_all import RunConfig,run_all,saved_config,STEPS,RunCancelled,ApprovalRequired
from pipeline.topics_history import already_made,history_rows
from schemas.topic_discovery import DiscoveryHint,TopicSuggestion
from sources.topic_discovery import discover_topics
from config.trends import load_trends
from pipeline.trend_scout import scout
from agents.researcher import NoResearchDataError
from utils.atomic_io import write_json_atomic,write_text_atomic,cleanup_tmp_files
from utils.file_lock import file_lock
from utils.diagnostics import Diagnostics
from utils.console import configure_console

class AutoCategoryError(RuntimeError): pass

class AutoConfig(BaseModel):
    content_mode: Literal["event_only","explainer_v2"] = Field(default="event_only",exclude_if=lambda v:v=="event_only")
    model_config=ConfigDict(extra="forbid")
    category: str=Field(min_length=1,max_length=120)
    region: Literal["vn","global","both"]="both"
    time_window_days: Literal[1,3,7]=3
    duration: float=Field(default=60,ge=6,le=600)
    format: Literal["tiktok","youtube"]="tiktok"
    creative_license: Literal["strict","balanced","story"]="strict"
    style_preset: str | None = Field(default=None,exclude_if=lambda v:v is None)
    style: Literal["storytelling","news","explain","review"]="storytelling"
    review: bool=False
    use_youtube: bool=False
    ai_clips: int=Field(default=0,ge=0,le=20)
    ai_model: str="veo-3.1"
    ai_seconds: int=4
    render_mode: Literal["preview","final"]="final"


def stamp(): return datetime.now(timezone.utc).isoformat()


def empty_step():
    return {"status":"pending","elapsed_sec":0.,"started_at":None,"finished_at":None,"attempts":0,"warnings":[],"artifacts":{},"error":None}


def is_no_data(error):
    seen=set()
    while error is not None and id(error) not in seen:
        if isinstance(error,NoResearchDataError): return True
        seen.add(id(error));error=error.__cause__ or error.__context__
    return False


def auto_report(project,state,diagnostics):
    meta=state["auto_category"];cfg=meta["config"]
    path=project/"report.md"
    marker="\n\n## Tự động theo danh mục"
    original=path.read_text(encoding="utf-8") if path.exists() else "# Báo cáo tạo video tự động"
    original=original.split(marker)[0]
    actual=state.get("render_result",{}).get("duration_sec",state.get("effective_duration_sec"))
    lines=[marker,f"Danh mục: {cfg['category']}",f"Chủ đề: {meta.get('selected_topic') or 'Chưa chọn'}",
        f"Lý do chọn: {meta.get('selection_reason') or 'Chưa có'}",f"Trạng thái: {state['status']}",
        f"Thời lượng yêu cầu {cfg['duration']:g}s; thực tế {actual:g}s"+(" vì dữ liệu mỏng/đã căn theo audio." if actual<cfg['duration'] else ".") if actual is not None else f"Thời lượng yêu cầu {cfg['duration']:g}s; chưa có bản dựng.",
        f"Fact: {state.get('summary',{}).get('facts',0)}; nguồn đã dùng: {state.get('summary',{}).get('sources_used',0)}.",
        "Mức sáng tạo: "+cfg["creative_license"]+"; mọi khẳng định vẫn cần fact có bằng chứng.","Nội dung có hỗ trợ AI.","", "### Các chủ đề đã bỏ"]
    lines.extend(f"- {a['topic']}: {a['reason']}" for a in meta.get("skipped",[]))
    if not meta.get("skipped"): lines.append("- Không có.")
    for warning in meta.get("warnings",[]): lines.append("- "+warning)
    if state.get("error"): lines.append("- Lỗi: "+state["error"])
    write_text_atomic(path,diagnostics.redact(original+"\n"+"\n".join(lines)+"\n"))


def run_auto(category=None,region="both",time_window_days=3,duration=60,format="tiktok",creative_license="strict",style="storytelling",
             use_ai_clips=False,progress_cb=None,*,settings=None,resume=None,review=False,use_youtube=False,
             ai_clips=0,ai_confirmed=False,cancel_event=None,render_mode="final",style_preset=None,content_mode="event_only"):
    settings=settings or get_settings()
    if resume is not None:
        project=Path(resume).resolve()
        if project.parent!=settings.output_dir.resolve(): raise ValueError("Chỉ resume project trực tiếp trong output/.")
        state=read_json(project/"run_state.json")
        if "auto_category" not in state: raise ValueError("Project không thuộc chế độ danh mục tự động.")
        meta=state["auto_category"];cfg=AutoConfig.model_validate(meta["config"])
        if state["status"]=="done": return project
    else:
        count=ai_clips or (1 if use_ai_clips else 0)
        cfg=AutoConfig(category=category,region=region,time_window_days=time_window_days,duration=duration,format=format,
            creative_license=creative_license,style=style,style_preset=style_preset,review=review,use_youtube=use_youtube,ai_clips=count,content_mode=content_mode,
            ai_model=settings.gateway_video_model,ai_seconds=settings.ai_clip_seconds,render_mode=render_mode)
        if count>settings.ai_clip_max_per_run: raise ValueError("Số clip vượt AI_CLIP_MAX_PER_RUN.")
        if count and not ai_confirmed:
            raise ApprovalRequired(f"Sẽ tạo tối đa {count} clip, model {cfg.ai_model}, {cfg.ai_seconds}s/clip; generation_failed có tối đa một job thử lại có thể tính phí. Cần xác nhận trước khi khám phá.")
        if count and not settings.gateway_api_key.get_secret_value().strip(): raise ValueError("Thiếu GATEWAY_API_KEY.")
        project=create_project(settings.output_dir,"auto "+cfg.category).resolve()
        meta={"config":cfg.model_dump(mode="json"),"topics":[],"selected_topic":None,"selection_reason":None,
            "active_index":0,"skipped":[],"warnings":[],"ai_confirmed":bool(count and ai_confirmed)}
        state={"version":1,"created_at":stamp(),"status":"running","config":RunConfig(topic="Danh mục "+cfg.category).model_dump(mode="json"),
            "auto_category":meta,"steps":{s:empty_step() for s in ("discovery",*STEPS)},"log":[],"error":None,"current_step":"discovery","step_progress":0.}
    diagnostics=Diagnostics(settings.logs_dir,filename="auto_category_errors.log",secrets=[settings.gemini_api_key.get_secret_value(),settings.gateway_api_key.get_secret_value(),settings.youtube_api_key.get_secret_value()])
    def save():
        state["auto_category"]=deepcopy(meta);state["updated_at"]=stamp()
        write_json_atomic(project/"run_state.json",state)
    def emit(step,message):
        state["current_step"]=step
        state["log"]=(state.get("log",[])+[diagnostics.redact(message)])[-60:]
        save()
        if progress_cb: progress_cb({"project":str(project),"step":step,"message":message,"state":deepcopy(state)})
    def check():
        if cancel_event is not None and cancel_event.is_set(): raise RunCancelled("Đã hủy ở điểm an toàn; có thể tiếp tục lượt này.")
    def forward(event):
        nonlocal state
        state=event["state"];state["auto_category"]=deepcopy(meta)
        save()
        if progress_cb: progress_cb({**event,"state":deepcopy(state)})
    with file_lock(project/"auto_category.lock",timeout=1):
        cleanup_tmp_files(project)
        try:
            check()
            if state["steps"]["discovery"]["status"]!="done":
                step=state["steps"]["discovery"];step.update(status="running",started_at=stamp())
                step["attempts"]+=1
                emit("discovery","Đang khám phá chủ đề và kiểm tra lịch sử…")
                import time
                started=time.perf_counter()
                trends_config=load_trends(settings)
                if trends_config.enabled:
                    try:
                        result=scout(cfg.category,settings,config=trends_config,region=cfg.region,count=10,
                            use_youtube=cfg.use_youtube,progress_cb=lambda message:emit("discovery",message))
                    except Exception as error:
                        diagnostics.record_exception(error,"Trend Scout lỗi; dùng khám phá RSS/news hiện có")
                        result={"topics":[],"warnings":["Trend Scout lỗi: "+diagnostics.redact(str(error))]}
                    meta["topic_provider"]="trend_scout"
                    write_json_atomic(project/"trend_scout.json",result)
                    if not result["topics"]:
                        notices=result["warnings"]+["Trend Scout chưa có chủ đề mới; tiếp tục RSS/news hiện có."]
                        result=discover_topics(cfg.category,settings,region=cfg.region,time_window_days=cfg.time_window_days,count=10,use_youtube=cfg.use_youtube,progress_cb=lambda message:emit("discovery",message))
                        result["warnings"]=notices+result["warnings"]
                        meta["topic_provider"]="rss_fallback"
                else:
                    result=discover_topics(cfg.category,settings,region=cfg.region,time_window_days=cfg.time_window_days,count=10,use_youtube=cfg.use_youtube,progress_cb=lambda message:emit("discovery",message))
                meta["warnings"]=result["warnings"]
                history=history_rows(settings.output_dir)
                meta["topics"]=[t for t in result["topics"] if not already_made(t["topic"],history,source_urls=t["source_urls"])][:3]
                step.update(status="done",finished_at=stamp(),elapsed_sec=time.perf_counter()-started)
                write_json_atomic(project/"topic_candidates.json",result)
                save();check()
            if not meta["topics"]: raise AutoCategoryError("Không có chủ đề mới chưa trùng lịch sử; đổi danh mục hoặc tăng khoảng ngày.")
            if len(meta["skipped"])>=len(meta["topics"]):
                raise AutoCategoryError("Các chủ đề đã hết dữ liệu: "+"; ".join(a["topic"]+": "+a["reason"] for a in meta["skipped"]))
            for index in range(meta["active_index"],len(meta["topics"])):
                check();suggestion=TopicSuggestion.model_validate(meta["topics"][index])
                same=meta.get("selected_topic")==suggestion.topic and state.get("config",{}).get("topic")==suggestion.topic
                meta.update(active_index=index,selected_topic=suggestion.topic,selection_reason=suggestion.score_reason+" "+suggestion.why_now)
                emit("research","Đã chọn: "+suggestion.topic+" · "+meta["selection_reason"])
                project_meta=read_json(project/"project.json");project_meta["topic"]=suggestion.topic
                write_json_atomic(project/"project.json",project_meta)
                if same:
                    run_cfg=saved_config(project,continue_after_review=state["status"]=="waiting_review")
                else:
                    run_cfg=RunConfig(topic=suggestion.topic,category=cfg.category,video_type=suggestion.suggested_type,video_format=cfg.format,duration_sec=cfg.duration,
                        script_style=cfg.style,style_preset=cfg.style_preset,creative_license=cfg.creative_license,mode="review" if cfg.review else "auto",youtube_trends=cfg.use_youtube,content_mode=cfg.content_mode,
                        discovery=DiscoveryHint(category=cfg.category,suggestion=suggestion),project_dir=project,
                        ai_clips=cfg.ai_clips,ai_model=cfg.ai_model,ai_seconds=cfg.ai_seconds,ai_confirmed=meta["ai_confirmed"],ai_failure_action="skip",render_mode=cfg.render_mode)
                try:
                    run_all(run_cfg,forward,settings=settings,cancel_event=cancel_event)
                    state=read_json(project/"run_state.json")
                    state["auto_category"]=deepcopy(meta);save();auto_report(project,state,diagnostics)
                    return project
                except Exception as error:
                    if is_no_data(error):
                        reason=diagnostics.redact(str(error))
                        meta["skipped"].append({"topic":suggestion.topic,"reason":reason,"index":index})
                        meta["active_index"]=index+1
                        diagnostics.record_exception(error,f"Bỏ chủ đề {index+1}/3: {suggestion.topic}")
                        emit("research","Bỏ chủ đề do không có nguồn/fact hợp lệ: "+suggestion.topic+" · "+reason)
                        auto_report(project,state,diagnostics)
                        continue
                    raise
            raise AutoCategoryError(f"Tất cả {len(meta['topics'])} chủ đề đều thất bại: "+"; ".join(a["topic"]+": "+a["reason"] for a in meta["skipped"]))
        except RunCancelled as error:
            state.update(status="cancelled",error=diagnostics.redact(str(error)))
            save();auto_report(project,state,diagnostics);return project
        except Exception as error:
            diagnostics.record_exception(error,"Tự động theo danh mục")
            state.update(status="failed",error=diagnostics.redact(str(error)))
            if state["steps"]["discovery"]["status"]=="running": state["steps"]["discovery"]["status"]="failed"
            save();auto_report(project,state,diagnostics)
            raise AutoCategoryError(str(state["error"])+f" · Project: {project}") from error


def main():
    configure_console()
    parser=argparse.ArgumentParser(description="Danh mục → video tự động; mặc định không dừng duyệt, AI clip tắt.")
    parser.add_argument("--category")
    parser.add_argument("--explainer-v2",action="store_true")
    parser.add_argument("--region",choices=["vn","global","both"],default="both")
    parser.add_argument("--days",type=int,choices=[1,3,7],default=3)
    parser.add_argument("--duration",type=float,default=60)
    parser.add_argument("--format",choices=["tiktok","youtube"],default="tiktok")
    parser.add_argument("--style-preset")
    parser.add_argument("--style",choices=["storytelling","news","explain","review"],default="storytelling")
    parser.add_argument("--creative-license",choices=["strict","balanced","story"],default="strict")
    parser.add_argument("--review",action="store_true")
    parser.add_argument("--youtube-trends",action="store_true")
    parser.add_argument("--ai-clips",type=int,default=0)
    parser.add_argument("--confirm-ai",action="store_true")
    parser.add_argument("--resume",type=Path)
    parser.add_argument("--count",type=int,default=1,help="Tạo tuần tự N video; dừng hàng đợi nếu đang chờ duyệt hoặc đã hủy")
    args=parser.parse_args()
    if args.count<1 or args.count>20: parser.error("--count cần từ 1 đến 20.")
    if not args.category and not args.resume: parser.error("Cần --category hoặc --resume.")
    settings=get_settings()
    diagnostics=Diagnostics(settings.logs_dir,filename="auto_category_errors.log",secrets=[settings.gemini_api_key.get_secret_value(),settings.gateway_api_key.get_secret_value(),settings.youtube_api_key.get_secret_value()])
    try:
        for index in range(args.count):
            project=run_auto(args.category,args.region,args.days,args.duration,args.format,args.creative_license,args.style,
                settings=settings,resume=args.resume if index==0 else None,review=args.review,use_youtube=args.youtube_trends,
                ai_clips=args.ai_clips,ai_confirmed=args.confirm_ai,style_preset=args.style_preset,content_mode="explainer_v2" if args.explainer_v2 else "event_only",progress_cb=lambda e:print(diagnostics.redact(e["message"]),flush=True))
            state=read_json(project/"run_state.json")
            print(f"Project: {project} · {state['status']} · Báo cáo: {project/'report.md'}")
            if state["status"]!="done":
                print(f'Tiếp tục/đã duyệt: python -m pipeline.auto_category --resume "{project}"');break
        return 0
    except Exception as error:
        diagnostics.record_exception(error,"CLI danh mục tự động")
        print(diagnostics.redact(str(error)));return 1

if __name__=="__main__": raise SystemExit(main())
