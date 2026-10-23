"""Thin, durable orchestration of existing stages. No API generation on import."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
from pathlib import Path
import time
from typing import Literal
from pydantic import AliasChoices,BaseModel,ConfigDict,Field,ValidationError,field_validator

from agents.researcher import run_research,NoResearchDataError
from agents.director import run_director,save_edit_plan,validate_plan,DirectorRequest
from config.settings import get_settings
from editor.render import run_render
from editor.timeline import confined
from pipeline.assets import run_assets,load_assets,safe_asset_path
from pipeline.projects import create_project,read_json
from pipeline.run_all_ai import prepare_ai_bundle,copy_artifact
from providers.video_gateway import VideoRequest,require_allowed_model
from schemas.edit_plan import EditPlan
from schemas.assets import AssetsManifest
from schemas.research_brief import ResearchBrief
from schemas.topic_discovery import DiscoveryHint
from utils.cache import write_json
from utils.atomic_io import cleanup_tmp_files, write_text_atomic
from utils.console import configure_console
from utils.diagnostics import Diagnostics
from utils.file_lock import file_lock
from utils.text import clean_text
from schemas.languages import SourceLanguage
from utils.source_credits import source_credit_lines

STEPS = ("research","director","assets","ai_video","render")
LABELS = {"discovery":"Khám phá chủ đề","research":"Research","director":"Kịch bản","assets":"Assets","ai_video":"Clip AI","render":"Render"}


class RunConfig(BaseModel):
    content_mode: Literal["event_only","explainer_v2"] = Field(default="event_only",exclude_if=lambda v:v=="event_only")
    category: str | None = Field(default=None,exclude_if=lambda v:v is None)
    model_config = ConfigDict(extra="forbid")
    project_dir: Path | None = Field(default=None,exclude=True)
    creative_license: Literal["strict","balanced","story"] = Field(default="strict",exclude_if=lambda v:v=="strict")
    discovery: DiscoveryHint | None = Field(default=None,exclude_if=lambda v:v is None)
    topic: str = Field(min_length=1,max_length=500)
    video_type: Literal["news","review","story"] = Field(default="news",validation_alias=AliasChoices("video_type","type"))
    video_format: Literal["tiktok","youtube"] = Field(default="tiktok",validation_alias=AliasChoices("video_format","format"))
    duration_sec: float = Field(default=45.,ge=6,le=600,validation_alias=AliasChoices("duration_sec","duration"))
    voice: Literal["vi-VN-HoaiMyNeural","vi-VN-NamMinhNeural"] = "vi-VN-HoaiMyNeural"
    source_languages: list[SourceLanguage] = Field(default_factory=lambda:["vi","en"],min_length=1,max_length=5)
    output_language: Literal["vi"] = "vi"
    mode: Literal["auto","review"] = "auto"
    youtube_trends: bool = False
    youtube_days: int = Field(default=14,ge=1,le=3650)
    web_limit: int = Field(default=6,ge=1,le=12)
    style_preset: str | None = Field(default=None,exclude_if=lambda v:v is None)
    script_style: Literal["storytelling","news","explain","review"] = "storytelling"
    ai_clips: int = Field(default=0,ge=0,le=20)
    ai_model: str = "veo-3.1"
    ai_seconds: int = 4
    render_mode: Literal["preview","final"] = "preview"
    ai_failure_action: Literal["skip","stop","ask"] = "skip"
    ai_failure_decision: Literal["skip","stop"] | None = Field(default=None,exclude=True)
    resume: Path | None = Field(default=None,exclude=True)
    force: bool = Field(default=False,exclude=True)
    continue_after_review: bool = Field(default=False,exclude=True)
    ai_confirmed: bool = Field(default=False,exclude=True)

    @field_validator("topic")
    @classmethod
    def topic_text(cls,value):
        value = clean_text(value)
        if not value:
            raise ValueError("Chủ đề không được trống.")
        return value


class PipelineError(RuntimeError):
    pass


class ApprovalRequired(PipelineError):
    pass


class RunCancelled(PipelineError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def saved_config(project,**updates):
    config = RunConfig.model_validate(read_json(Path(project)/"run_state.json")["config"])
    return config.model_copy(update={"resume":Path(project),**updates})


def fingerprints(project,paths):
    result = {}
    for path in paths:
        path = confined(project,str(Path(path).relative_to(project)))
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Artifact thiếu/rỗng: {path.relative_to(project)}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b""):
                digest.update(chunk)
        result[path.relative_to(project).as_posix()] = digest.hexdigest()
    return result


def asset_files(project,plan_path):
    original,resolved,manifest = load_assets(plan_path)
    broken=[scene.scene_id for scene in manifest.scenes if not scene.audio_path or scene.audio_error and not scene.audio_silent]
    if broken:
        ids=", ".join(map(str,broken))
        raise ValueError(f"TTS lỗi ở cảnh {ids}; chưa có audio/im lặng hợp lệ. Chạy lại riêng audio cảnh đó trên trang Assets hoặc dùng --scene ID.")
    if manifest.status!="complete":
        raise ValueError("Assets chưa hoàn tất; chạy lại Assets trước khi Render.")
    if {scene.scene_id for scene in manifest.scenes} != {scene.id for scene in resolved.scenes}:
        raise ValueError("Assets thiếu cảnh so với kế hoạch.")
    files = [plan_path,plan_path.parent/"edit_plan.resolved.json",plan_path.parent/"assets.json",plan_path.parent/"credits.txt"]
    for scene in manifest.scenes:
        expected = next(item for item in resolved.scenes if item.id == scene.scene_id)
        if {shot.shot_id for shot in scene.shots} != set(range(1,len(expected.shots)+1)):
            raise ValueError(f"Assets thiếu shot của cảnh {scene.scene_id}.")
        files.append(safe_asset_path(plan_path.parent,scene.audio_path))
        files.extend(safe_asset_path(plan_path.parent,shot.path) for shot in scene.shots)
    return files,list(manifest.warnings)


def report(project,state,diagnostics):
    brief = ResearchBrief.model_validate(read_json(project/"brief.json")) if state["steps"]["research"]["status"] == "done" else None
    plan = EditPlan.model_validate(read_json(project/"edit_plan.json")) if state["steps"]["director"]["status"] == "done" else None
    used_ids = sorted({fact_id for scene in plan.scenes for fact_id in scene.fact_ids}) if plan else []
    source_urls = {str(brief.facts[index-1].source_url) for index in used_ids} if brief else set()
    if plan:
        source_urls.update(str(source.url) for scene in plan.scenes if scene.review_notes for fact in scene.review_notes.facts for source in fact.sources)
    from agents.director import claim_identity,vietnamese_fact
    unique_used={claim_identity(vietnamese_fact(brief.facts[i-1])) for i in used_ids} if brief else set()
    state["summary"] = {"facts":len(brief.facts) if brief else 0,"facts_used":len(unique_used),"sources_used":len(source_urls),
                        "elapsed_sec":round(sum(item["elapsed_sec"] for item in state["steps"].values()),2)}
    lines = [f"# Báo cáo: {state['config']['topic']}",f"Trạng thái: {state['status']}",
        f"Fact trong brief: {state['summary']['facts']}; fact dùng trong kịch bản: {len(unique_used)}; nguồn fact đã dùng: {len(source_urls)}.",
        f"Thời gian xử lý: {state['summary']['elapsed_sec']:.2f} giây.","","## Các bước"]
    lines.extend(f"- {LABELS[name]}: {item['status']} · {item['elapsed_sec']:.2f}s" for name,item in state["steps"].items())
    lines.extend(["","## Nguồn fact đã dùng",*(f"- {url}" for url in sorted(source_urls))])
    if plan:
        actual=state.get("render_result",{}).get("duration_sec",plan.duration_sec)
        wanted=state["config"]["duration_sec"]
        lines.extend(["","## Thời lượng",f"Yêu cầu {wanted:g}s; kế hoạch {plan.duration_sec:.1f}s; thực tế {actual:.1f}s."])
        if actual<wanted*.8: lines.append("Dữ liệu mỏng: tăng số nguồn hoặc chọn chủ đề khác; không kéo dài bằng lặp ý.")
        if plan.content_mode=="explainer_v2":
            lines.extend(["","## Explainer v2","Câu event đối chiếu brief; explain/opinion là diễn giải nền có độ mềm, không phải dữ kiện đã xác minh."])
            for scene in plan.scenes:
                lines.append(f"- Cảnh {scene.id} ({scene.information_kind}): {scene.new_information}")
            if plan.script_critic: lines.append("Critic trước sửa: "+plan.script_critic.model_dump_json())
    if brief:
        lines.extend(["","## Nguồn đối chiếu trong brief",*(f"- {str(fact.source_url)}" for fact in brief.facts)])
        if brief.trend_signals:
            lines.extend(["","## Tín hiệu YouTube (không phải nguồn fact)",*(f"- {signal.title}: {signal.url}" for signal in brief.trend_signals)])
    warnings = list(dict.fromkeys(warning for item in state["steps"].values() for warning in item["warnings"]))
    if (project/"assets.json").is_file():
        current_assets=AssetsManifest.model_validate(read_json(project/"assets.json"))
        warnings=list(dict.fromkeys(warnings+[w for scene in current_assets.scenes for w in scene.audio_warnings]))
    lines.extend(["","## Cảnh báo",*(f"- {warning}" for warning in warnings)])
    if plan and plan.style_profile:
        lines.extend(["", "## Phong cách mẫu",plan.style_profile.name+"; chỉ học cách kể/nhịp, không sử dụng hình hay âm thanh video mẫu."])
    lines.extend(["","## Tự sửa và cảnh báo Director"])
    if plan:
        for event in plan.validation_events:
            lines.append(f"- {('Cảnh '+str(event.scene_id)) if event.scene_id else 'Video'} · {event.rule_id} · nhóm {event.group} · {event.action}: {event.message}")
    draft_path=project/"edit_plan.draft.json"
    if draft_path.exists() and (not plan or read_json(draft_path).get("status")!="resolved"):
        draft=read_json(draft_path)
        for event in (draft.get("plan") or {}).get("validation_events",[]):
            lines.append(f"- Bản nháp · cảnh {event.get('scene_id') or 'video'} · {event['rule_id']} · nhóm {event['group']} · {event['action']}: {event['message']}")
        for event in draft.get("validation_errors",[]):
            lines.append(f"- Cần sửa: cảnh {event.get('scene_id','video')} · {event['rule_id']}: {event['message']}")
    if state.get("error"):
        lines.append("- Lỗi: "+state["error"])
    lines.extend(["","## Clip AI đã dùng"])
    for clip in state.get("ai_clips_used",[]):
        lines.append(f"- Cảnh {clip['scene_id']}, shot {clip['shot_id']}: {clip['model']}, {clip['seconds']}s; job {clip['remote_id']}; {clip['clip_path']}")
    lines.extend(["","## Video",state.get("render_result",{}).get("path","Chưa có video hoàn tất.")])
    lines.extend(source_credit_lines(project))
    write_text_atomic(confined(project,"report.md"), diagnostics.redact("\n".join(lines)+"\n"))


def run_all(config,progress_cb=None,stop_after=None,*,settings=None,cancel_event=None):
    config = config if isinstance(config,RunConfig) else RunConfig.model_validate(config)
    settings = settings or get_settings()
    if "voice" not in config.model_fields_set and config.resume is None:
        config = config.model_copy(update={"voice":settings.default_voice})
    if config.resume is None:
        defaults = {}
        if "ai_model" not in config.model_fields_set:
            defaults["ai_model"] = settings.gateway_video_model
        if "ai_seconds" not in config.model_fields_set:
            from config.video_models import VIDEO_MODELS
            selected = defaults.get("ai_model",config.ai_model)
            defaults["ai_seconds"] = settings.ai_clip_seconds if selected == settings.gateway_video_model else VIDEO_MODELS.get(selected,(4,))[0]
        config = config.model_copy(update=defaults)
    settings = settings.model_copy(update={"default_voice":config.voice})
    if stop_after is not None and stop_after not in STEPS:
        raise ValueError("stop_after phải là tên bước trong pipeline.")
    approval = {"count":config.ai_clips,"model":config.ai_model,"seconds":config.ai_seconds}
    resuming = config.resume is not None and not config.force
    if resuming:
        project = Path(config.resume).resolve()
        if project.parent != settings.output_dir.resolve():
            raise ValueError("Chỉ resume project trực tiếp trong output/ của app.")
        state = read_json(confined(project,"run_state.json"))
        if RunConfig.model_validate(state["config"]).model_dump(mode="json") != config.model_dump(mode="json"):
            raise ValueError("Cấu hình khác lượt đã lưu. Dùng cấu hình của project để resume; --force tạo project mới.")
        approved = state.get("ai_approval") == approval
    else:
        approved = False
    if config.ai_failure_decision is not None and (not resuming or state["steps"]["ai_video"]["status"] != "failed"):
        raise ValueError("Chỉ chọn bỏ qua/dừng Clip AI khi resume một project có bước Clip AI bị lỗi.")
    ai_pending = config.ai_failure_decision is None and not (resuming and state["steps"]["ai_video"]["status"] in {"done","skipped"})
    if ai_pending and config.ai_clips > settings.ai_clip_max_per_run:
        raise ValueError(f"Số clip AI vượt AI_CLIP_MAX_PER_RUN={settings.ai_clip_max_per_run}.")
    if ai_pending and config.ai_clips and not (approved or config.ai_confirmed):
        raise ApprovalRequired(f"Sẽ tạo {config.ai_clips} clip, model {config.ai_model}, thời lượng {config.ai_seconds} giây/clip. Cần xác nhận trước khi bắt đầu pipeline.")
    if ai_pending and config.ai_clips and not settings.gateway_api_key.get_secret_value().strip():
        raise ValueError("Thiếu GATEWAY_API_KEY để tạo clip AI; chưa bắt đầu pipeline.")
    if not resuming:
        initial_auto=None
        if config.project_dir is not None:
            project=config.project_dir.resolve()
            if project.parent!=settings.output_dir.resolve() or not (project/"run_state.json").exists():
                raise ValueError("Project điều phối phải nằm trực tiếp trong output/ và có checkpoint.")
            initial_auto=read_json(project/"run_state.json")
            if "auto_category" not in initial_auto: raise ValueError("Project không phải lượt tự động theo danh mục.")
        else:
            project = create_project(settings.output_dir,config.topic).resolve()
        state = {"version":1,"config":config.model_dump(mode="json"),"created_at":timestamp(),"status":"pending","error":None,
            "review_approved":False,"ai_approval":approval if config.ai_clips and config.ai_confirmed else None,
            "steps":{name:{"status":"pending","started_at":None,"finished_at":None,"elapsed_sec":0.,"attempts":0,"warnings":[],"artifacts":{},"error":None} for name in STEPS},"log":[]}
    if not resuming and initial_auto is not None:
        state["auto_category"]=initial_auto["auto_category"]
        if "discovery" in initial_auto.get("steps",{}): state["steps"]["discovery"]=initial_auto["steps"]["discovery"]
    if config.discovery is not None and not resuming:
        write_json(project/"topic_discovery.json",config.discovery.model_dump(mode="json"))
    diagnostics = Diagnostics(settings.logs_dir,filename="run_all_errors.log",secrets=[settings.gateway_api_key.get_secret_value(),settings.gemini_api_key.get_secret_value(),settings.youtube_api_key.get_secret_value(),settings.pexels_api_key.get_secret_value(),settings.pixabay_api_key.get_secret_value()])
    if config.ai_clips and config.ai_confirmed:
        state["ai_approval"] = approval
    state_path = confined(project,"run_state.json")
    def save():
        state["updated_at"] = timestamp()
        state.pop("state_write_warning", None)
        try:
            write_json(state_path,state)
        except OSError as error:
            # A status-file failure must not turn a completed stage into failure.
            # Durable AI job intents and other artifacts still fail strictly.
            state["state_write_warning"] = "Không lưu được run_state.json; trạng thái đang giữ trong bộ nhớ. Kiểm tra quyền ghi trước khi đóng app/resume."
            try:
                diagnostics.record_exception(error, state["state_write_warning"])
            except OSError:
                pass
    def check_cancel():
        if cancel_event is not None and cancel_event.is_set():
            raise RunCancelled("Đã hủy ở điểm an toàn; có thể resume từ checkpoint.")
    def emit(step,message,fraction=0.):
        check_cancel()
        message = diagnostics.redact(str(message))[:1500]
        state["current_step"] = step
        state["step_progress"] = max(0.,min(1.,fraction))
        state["log"] = (state["log"]+[f"{LABELS.get(step,step)}: {message}"])[-60:]
        save()
        if progress_cb:
            progress_cb({"project":str(project),"step":step,"message":message,"state":deepcopy(state)})
    def finish(status):
        state["status"] = status
        if status=="done" and config.discovery is not None:
            from pipeline.topics_history import record_topic
            record_topic(settings.output_dir,config.topic,config.discovery.category,project,
                original_topic=config.discovery.suggestion.topic,source_urls=[str(u) for u in config.discovery.suggestion.source_urls])
        report(project,state,diagnostics)
        save()
        if progress_cb:
            progress_cb({"project":str(project),"step":state.get("current_step"),"message":status,"state":deepcopy(state)})
        return project
    with file_lock(confined(project,"run_all.lock"),timeout=1):
        cleanup_tmp_files(project)
        state["status"],state["error"] = "running",None
        save()
        for step in STEPS:
            entry = state["steps"][step]
            started = None
            try:
                check_cancel()
                if step == "ai_video" and entry["status"] == "failed" and config.ai_failure_decision == "stop":
                    state["error"] = entry.get("error")
                    return finish("failed")
                if entry["status"] == "done":
                    if not entry["artifacts"]:
                        raise ValueError(f"Checkpoint {LABELS[step]} thiếu artifact để xác nhận; không được bỏ qua.")
                    actual = fingerprints(project,[confined(project,path) for path in entry["artifacts"]])
                    if actual != entry["artifacts"]:
                        review_edit = step == "director" and state.get("review_approved") is False and state["steps"]["assets"]["status"] == "pending"
                        if not review_edit:
                            raise ValueError(f"Artifact của bước {LABELS[step]} đã đổi; không dùng dữ liệu cũ. Kiểm tra file hoặc dùng --force tạo project mới.")
                        brief = ResearchBrief.model_validate(read_json(project/"brief.json"))
                        validate_plan(EditPlan.model_validate(read_json(project/"edit_plan.json")),brief,
                            DirectorRequest(video_type=config.video_type,video_format=config.video_format,duration_sec=config.duration_sec))
                        save_edit_plan(project/"brief.json",read_json(project/"edit_plan.json"),settings)
                        entry["artifacts"] = fingerprints(project,[project/"edit_plan.json"])
                        entry["warnings"].append("Đã tiếp nhận kịch bản chỉnh sửa trong chế độ duyệt.")
                    emit(step,"Bỏ qua bước đã hoàn tất, artifact còn khớp",1.)
                elif step == "ai_video" and (not config.ai_clips or entry["status"] == "skipped" or
                        (entry["status"] == "failed" and config.ai_failure_decision == "skip")):
                    entry.update(status="skipped",finished_at=timestamp())
                    state.pop("ai_render_plan",None)
                    state.pop("ai_clips_used",None)
                    state["error"] = None
                    if config.ai_clips:
                        entry["warnings"].append("Đã bỏ qua Clip AI theo lựa chọn người dùng; render bằng b-roll thường. Job đã gửi có thể vẫn tính phí.")
                    emit(step,"Bỏ qua Clip AI; dùng b-roll thường",1.)
                else:
                    entry.update(status="running",started_at=timestamp(),finished_at=None,attempts=entry["attempts"]+1,error=None)
                    started = time.perf_counter()
                    emit(step,"Bắt đầu")
                    check_cancel()
                    files,warnings = [],[]
                    if step == "research":
                        run_research(config.topic,settings,web_limit=config.web_limit,use_youtube=config.youtube_trends,
                            youtube_days=config.youtube_days,output_dir=project,progress=lambda message:emit(step,message),
                            source_languages=config.source_languages,output_language=config.output_language,discovery_hint=config.discovery,content_mode=config.content_mode)
                        brief = ResearchBrief.model_validate(read_json(project/"brief.json"))
                        source_data = read_json(project/"sources.json")
                        if not brief.facts:
                            raise NoResearchDataError("Research có 0 fact hợp lệ; cần đổi chủ đề hoặc tìm lại nguồn.")
                        files,warnings = [project/"brief.json",project/"sources.json"],list(dict.fromkeys(brief.risks+source_data.get("warnings",[])))
                    elif step == "director":
                        run_director(project/"brief.json",settings,video_type=config.video_type,video_format=config.video_format,
                            duration_sec=config.duration_sec,progress=lambda message:emit(step,message),
                            source_languages=config.source_languages,output_language=config.output_language,ai_clip_limit=config.ai_clips,script_style=config.script_style,creative_license=config.creative_license,style_preset=config.style_preset,category=config.category or (config.discovery.category if config.discovery else None),content_mode=config.content_mode)
                        plan = EditPlan.model_validate(read_json(project/"edit_plan.json"))
                        validate_plan(plan,ResearchBrief.model_validate(read_json(project/"brief.json")),
                            DirectorRequest(video_type=config.video_type,video_format=config.video_format,duration_sec=config.duration_sec))
                        state["effective_duration_sec"]=plan.duration_sec
                        if state["effective_duration_sec"]<config.duration_sec:
                            warnings.append(f"Thời lượng yêu cầu {config.duration_sec:g}s, kế hoạch {state['effective_duration_sec']:g}s vì dữ liệu mỏng.")
                        if plan.voice != config.voice:
                            raise ValueError("Giọng đọc trong Edit Plan khác cấu hình lượt chạy.")
                        warnings.extend(w for scene in plan.scenes if scene.review_notes for w in scene.review_notes.warnings)
                        warnings.extend(plan.review_notes)
                        files = [project/"edit_plan.json"]
                    elif step == "assets":
                        run_assets(project/"edit_plan.json",settings,progress=lambda done,total,message:emit(step,message,done/max(1,total)))
                        files,warnings = asset_files(project,project/"edit_plan.json")
                    elif step == "ai_video":
                        require_allowed_model(settings, config.ai_model)
                        VideoRequest(model=config.ai_model,seconds=config.ai_seconds,prompt="Preflight",format=config.video_format)
                        render_plan,used = prepare_ai_bundle(project,config,settings,
                            lambda fraction,message:emit(step,message,fraction),check_cancel,diagnostics)
                        state["ai_clips_used"] = used
                        state["ai_render_plan"] = render_plan.relative_to(project).as_posix()
                        files,warnings = asset_files(project,render_plan.parent/"edit_plan.json")
                        files += [confined(project,clip["job_path"]) for clip in used]
                    elif step == "render":
                        plan_path = confined(project,state["ai_render_plan"]) if state["steps"]["ai_video"]["status"] == "done" and state.get("ai_render_plan") else project/"edit_plan.resolved.json"
                        result = run_render(plan_path,mode=config.render_mode,settings=settings,progress=lambda fraction,message:emit(step,message,fraction))
                        source = confined(project,str(Path(result["path"]).resolve().relative_to(project)))
                        target = confined(project,"render/"+source.name)
                        copy_artifact(source,target)
                        copy_artifact(source.parent/"credits.txt",confined(project,"render/credits.txt"))
                        result["path"] = str(target)
                        write_json(confined(project,f"render/{config.render_mode}.json"),result)
                        files = [target,project/"render/credits.txt",project/f"render/{config.render_mode}.json"]
                        warnings = result.get("warnings",[])
                        state["render_result"] = result
                    check_cancel()
                    entry.update(status="done",finished_at=timestamp(),elapsed_sec=entry["elapsed_sec"]+time.perf_counter()-started,
                        artifacts=fingerprints(project,files),warnings=[diagnostics.redact(str(warning)) for warning in warnings])
                    started = None
                    emit(step,"Hoàn tất",1.)
                if step == "director" and config.mode == "review" and not state.get("review_approved"):
                    if not config.continue_after_review:
                        return finish("waiting_review")
                    state["review_approved"] = True
                    save()
                if stop_after == step:
                    return finish("paused")
            except (RunCancelled,KeyboardInterrupt) as error:
                if started is not None:
                    entry["elapsed_sec"] += time.perf_counter()-started
                if entry["status"] != "done":
                    entry.update(status="cancelled",finished_at=timestamp())
                state["error"] = "Đã hủy; bước đang gọi API/render chỉ dừng tại điểm an toàn."
                if entry["status"] == "cancelled":
                    entry["error"] = state["error"]
                finish("cancelled")
                return project
            except Exception as error:
                if started is not None:
                    entry["elapsed_sec"] += time.perf_counter()-started
                entry.update(status="failed",finished_at=timestamp())
                state["error"] = diagnostics.redact(f"Bước {LABELS[step]} lỗi: {error}")
                entry["error"] = state["error"]
                diagnostics.record_exception(error,f"run_all step={step}")
                if step == "ai_video" and config.ai_failure_action != "stop":
                    entry["warnings"].append(state["error"]+" · Job đã gửi có thể vẫn tính phí; bỏ qua không hủy job.")
                    entry["status"] = "skipped"
                    state.pop("ai_render_plan",None)
                    state.pop("ai_clips_used",None)
                    state["error"] = None
                    emit(step,"Clip AI lỗi; bỏ qua và render tiếp bằng b-roll thường",1.)
                    if stop_after == step:
                        return finish("paused")
                    continue
                finish("failed")
                raise PipelineError(state["error"]+f" · Project: {project}") from error
        return finish("done")


def main():
    configure_console()
    parser = argparse.ArgumentParser(description="Research → Director → Assets → AI tùy chọn → Render; checkpoint/resume.")
    parser.add_argument("--topic")
    parser.add_argument("--explainer-v2",action="store_true")
    parser.add_argument("--source-languages",nargs="+",choices=["vi","en","zh","ko","ja"])
    parser.add_argument("--output-language",choices=["vi"])
    parser.add_argument("--type",choices=["news","review","story"],dest="video_type")
    parser.add_argument("--format",choices=["tiktok","youtube"],dest="video_format")
    parser.add_argument("--style-preset")
    parser.add_argument("--category")
    parser.add_argument("--style",dest="script_style",choices=["storytelling","news","explain","review"])
    parser.add_argument("--duration",type=float,dest="duration_sec")
    parser.add_argument("--voice",choices=["vi-VN-HoaiMyNeural","vi-VN-NamMinhNeural"])
    parser.add_argument("--review",action="store_true")
    parser.add_argument("--youtube-trends",action="store_true")
    parser.add_argument("--youtube-days",type=int)
    parser.add_argument("--web-limit",type=int)
    parser.add_argument("--ai-clips",type=int)
    parser.add_argument("--ai-model",choices=["veo-3.1","seedance-2.5-30s"])
    parser.add_argument("--ai-seconds",type=int)
    parser.add_argument("--confirm-ai",action="store_true",help="Xác nhận số clip/model/thời lượng AI trước khi chạy")
    parser.add_argument("--resume",type=Path)
    parser.add_argument("--force",action="store_true",help="Chạy từ đầu trong project MỚI, giữ project cũ")
    parser.add_argument("--continue",action="store_true",dest="continue_after_review",help="Đã duyệt kịch bản, tiếp tục Assets/Render")
    parser.add_argument("--render-mode",choices=["preview","final"])
    parser.add_argument("--stop-after",choices=STEPS)
    parser.add_argument("--ai-on-error",choices=["skip","stop","ask"])
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument("--skip-ai",action="store_true")
    decision.add_argument("--stop-ai",action="store_true")
    args = parser.parse_args()
    try:
        settings = get_settings()
        values = saved_config(args.resume).model_dump() if args.resume else {"voice":settings.default_voice,"ai_model":settings.gateway_video_model,"ai_seconds":settings.ai_clip_seconds}
        for key in ("category","style_preset","script_style","topic","video_type","video_format","duration_sec","voice","youtube_days","web_limit","ai_clips","ai_model","ai_seconds","render_mode","source_languages","output_language"):
            value = getattr(args,key)
            if value is not None:
                values[key] = value
        if args.review:
            values["mode"] = "review"
        if args.explainer_v2: values["content_mode"]="explainer_v2"
        if args.youtube_trends:
            values["youtube_trends"] = True
        if args.ai_on_error:
            values["ai_failure_action"] = args.ai_on_error
        values["ai_failure_decision"] = "skip" if args.skip_ai else "stop" if args.stop_ai else None
        if args.ai_model is not None and args.ai_seconds is None and not args.resume:
            from config.video_models import VIDEO_MODELS
            if args.ai_model != settings.gateway_video_model:
                values["ai_seconds"] = VIDEO_MODELS[args.ai_model][0]
        values.update(resume=args.resume,force=args.force,continue_after_review=args.continue_after_review,ai_confirmed=args.confirm_ai)
        config = RunConfig.model_validate(values)
        if config.ai_clips:
            print(f"Sẽ tạo {config.ai_clips} clip, model {config.ai_model}, thời lượng {config.ai_seconds} giây/clip.")
        project = run_all(config,lambda event:print(f"[{LABELS.get(event['step'],event['step'])}] {event['message']}",flush=True),args.stop_after,settings=settings)
        state = read_json(project/"run_state.json")
        print(f"Project: {project}\nTrạng thái: {state['status']}\nBáo cáo: {project / 'report.md'}")
        if state["status"] == "waiting_review":
            print(f'Xem/sửa Edit Plan rồi chạy: python -m pipeline.run_all --resume "{project}" --continue')
        if state["status"] == "waiting_ai_choice":
            print(f'Clip AI lỗi. Render bằng b-roll: python -m pipeline.run_all --resume "{project}" --skip-ai ; hoặc dừng bằng --stop-ai.')
        return 130 if state["status"] == "cancelled" else 1 if state["status"] == "failed" else 0
    except ApprovalRequired as error:
        print(str(error)+" Thêm --confirm-ai để xác nhận.")
        return 2
    except ValidationError:
        print("Cấu hình hoặc tham số không hợp lệ. Kiểm tra --help và .env.example; không in nội dung cấu hình.")
        return 1
    except Exception as error:
        diagnostics = Diagnostics(Path(__file__).resolve().parents[1]/"logs",filename="run_all_errors.log")
        diagnostics.record_exception(error,"run_all CLI")
        print("Không hoàn tất: "+diagnostics.redact(str(error))[:1800])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
