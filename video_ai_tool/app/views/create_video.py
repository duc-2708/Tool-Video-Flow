"""One screen to start a fresh project or resume a durable pipeline."""
from config.storytelling import DURATIONS,STYLES
from agents.story_style import data_advice
from schemas.research_brief import ResearchBrief
from pathlib import Path
from datetime import datetime,timezone
import streamlit as st
from app.style_controls import select_style,select_category
from pipeline.run_all import RunConfig,saved_config,LABELS,STEPS
from pipeline.run_all_jobs import PipelineJobs
from pipeline.projects import read_json
from editor.timeline import confined
from providers.video_gateway import MODELS,allowed_models,VideoRequest
from utils.cache import cache_key
from app.views.render import show_result
from app.views.edit_plan import render as edit_plan_page
from app.views.ai_video import recovery_controls,ai_video_jobs,failed_job_details
from pipeline.ai_video import load_job
from schemas.languages import LABELS as LANGUAGE_LABELS


@st.cache_resource
def pipeline_jobs():
    return PipelineJobs()


def read_ui_state(project, snapshot=None):
    """A torn/locked checkpoint must not break a Streamlit rerun."""
    if snapshot and snapshot.get("state") and (project is None or snapshot.get("project") == str(project)):
        return snapshot["state"]
    if project is not None:
        try:
            return read_json(confined(project,"run_state.json"), allow_stale=True)
        except (OSError, ValueError):
            pass
    if snapshot and (project is None or snapshot.get("project") == str(project)):
        return snapshot.get("state")
    return None


def render(settings,project,topic,debug,diagnostics):
    prefill=st.session_state.pop("discovery_prefill",None)
    if prefill:
        st.session_state.pop("create_style_preset_context",None)
        st.session_state["create_topic"]=prefill["topic"]
        suggestion=prefill.get("suggestion")
        st.session_state["create_discovery"]={"category":prefill["category"],"suggestion":suggestion} if suggestion else None
        if suggestion: st.session_state["create_type"]=suggestion["suggested_type"]
        if prefill.get("category"):
            from config.categories import resolve_category
            st.session_state["create_category"]=resolve_category(settings,prefill["category"]).category_id
    st.title("Tạo video")
    st.caption("Research → Kịch bản → Assets → Clip AI tùy chọn → Render. Mỗi lượt mới có project riêng; có thể tiếp tục lượt đang dở.")
    manager = pipeline_jobs()
    active = manager.active()
    category = select_category(settings,key="create_category")
    entered_topic = st.text_input("Chủ đề",value=topic or "",max_chars=500,key="create_topic")
    left,right = st.columns(2)
    video_type = left.selectbox("Loại video",["news","review","story"],key="create_type")
    video_format = right.selectbox("Khổ video",["tiktok","youtube"],format_func=lambda value:"TikTok · 9:16" if value == "tiktok" else "YouTube · 16:9",key="create_format")
    preset = left.selectbox("Mốc thời lượng",["Tùy chỉnh",*DURATIONS],key="create_duration_preset")
    style_preset = select_style(settings,key="create_style_preset",category=category,video_type=video_type,current=prefill.get("style_preset") if prefill else None)
    script_style = right.selectbox("Phong cách",list(STYLES),format_func=STYLES.get,key="create_script_style")
    explainer_v2=st.checkbox("Explainer v2: giảng giải chuyên sâu",value=False,key="create_explainer_v2")
    duration = left.number_input("Độ dài mong muốn (giây)",min_value=6.,max_value=600.,value=45.,step=1.,key="create_duration")
    duration = float(preset) if preset != "Tùy chỉnh" else duration
    if project is not None and (project/"brief.json").exists():
        try:
            advice = data_advice(ResearchBrief.model_validate(read_json(project/"brief.json")),duration)
            if advice["thin"]: st.warning(advice["warning"]+f"; đề xuất {advice['suggested_duration']:g} giây.")
        except (ValueError,OSError): pass
    voices = ["vi-VN-HoaiMyNeural","vi-VN-NamMinhNeural"]
    voice = right.selectbox("Giọng đọc",voices,index=voices.index(settings.default_voice),key="create_voice")
    mode = left.selectbox("Chế độ",["auto","review"],format_func=lambda value:"Tự động" if value == "auto" else "Duyệt kịch bản trước khi dựng",key="create_mode")
    render_mode = right.selectbox("Chất lượng dựng",["preview","final"],format_func=lambda value:"Xem nhanh" if value == "preview" else "Bản cuối",key="create_render_mode")
    youtube = st.checkbox("Dùng YouTube trends",value=False,key="create_youtube")
    source_languages = st.multiselect("Ngôn ngữ nguồn",list(LANGUAGE_LABELS),default=["vi","en"],format_func=LANGUAGE_LABELS.get,key="create_source_languages")
    output_language = st.selectbox("Ngôn ngữ kịch bản",["vi"],format_func=LANGUAGE_LABELS.get,key="create_output_language")
    web_limit = left.number_input("Số nguồn web tối đa",min_value=1,max_value=12,value=6,step=1,key="create_web_limit")
    days = right.number_input("YouTube: số ngày gần đây",min_value=1,max_value=3650,value=14,step=1,key="create_days")
    if not allowed_models(settings):
        st.warning("GATEWAY_ALLOWED_MODELS không có model được hỗ trợ; chọn veo-3.1 hoặc seedance-2.5-30s.")
    stop_on_ai_error = st.checkbox("Dừng pipeline khi Clip AI lỗi", value=False, key="create_stop_ai_error")
    ai_enabled = st.checkbox("Dùng clip AI (có tính phí)",value=False,disabled=settings.ai_clip_max_per_run == 0 or not allowed_models(settings),key="create_ai") and settings.ai_clip_max_per_run > 0
    ai_count,ai_model,ai_seconds,confirmed = 0,"veo-3.1",4,False
    if ai_enabled and settings.ai_clip_max_per_run:
        ai_count = st.number_input("Số clip AI tối đa trong lượt",min_value=1,max_value=settings.ai_clip_max_per_run,value=1,step=1,key="create_ai_count")
        names = allowed_models(settings)
        ai_model = st.selectbox("Model clip AI",names,index=names.index(settings.gateway_video_model) if settings.gateway_video_model in names else 0,key="create_ai_model")
        ai_seconds = st.selectbox("Thời lượng mỗi clip AI (giây)",MODELS[ai_model],index=MODELS[ai_model].index(settings.ai_clip_seconds) if settings.ai_clip_seconds in MODELS[ai_model] else 0,key=f"create_ai_seconds_{ai_model}")
        estimate = VideoRequest(model=ai_model,seconds=ai_seconds,prompt="Estimate").estimated_cost_vnd*int(ai_count)
        st.info(f"Sẽ tạo {ai_count} clip, model {ai_model}, thời lượng {ai_seconds} giây/clip. Giá niêm yết tham khảo tổng: {estimate:,} VNĐ; gateway áp dụng gói/giá thực tế.")
        st.caption("Nếu generation_failed, mỗi clip chỉ tự thử lại 1 lần với prompt an toàn; lần thử lại có thể tính phí. Timeout/thiếu ID không tự tạo job mới.")
        signature = cache_key([ai_count,ai_model,ai_seconds,video_format])[:12]
        nonce = st.session_state.get("create_ai_approval_nonce",0)
        confirmed = st.checkbox("Tôi xác nhận số clip, model, thời lượng và chi phí AI trước khi bắt đầu",key=f"create_ai_approval_{signature}_{nonce}")
        if not settings.gateway_api_key.get_secret_value().strip():
            st.warning("Thiếu GATEWAY_API_KEY. Điền trong cấu hình local hoặc tắt clip AI.")
    from providers.llm.router import route_ready
    ready = bool(source_languages and entered_topic.strip() and route_ready(settings,"researcher") and
                 route_ready(settings,"director") and (not ai_enabled or (confirmed and settings.gateway_api_key.get_secret_value().strip())))
    if st.button("Tạo video",type="primary",width="stretch",disabled=bool(active) or not ready):
        try:
            config = RunConfig(topic=entered_topic,category=category,video_type=video_type,video_format=video_format,duration_sec=float(duration),voice=voice,
                mode=mode,youtube_trends=youtube,youtube_days=int(days),web_limit=int(web_limit),ai_clips=int(ai_count),
                source_languages=source_languages,output_language=output_language,script_style=script_style,style_preset=style_preset,discovery=st.session_state.get("create_discovery"),content_mode="explainer_v2" if explainer_v2 else "event_only",
                ai_model=ai_model,ai_seconds=ai_seconds,ai_confirmed=confirmed,render_mode=render_mode,ai_failure_action="stop" if stop_on_ai_error else "skip")
            key = manager.submit(config,settings)
            st.session_state["pipeline_worker"] = key
            st.session_state["pipeline_follow"] = key
            # Confirmation applies to this new run only. Resume uses the
            # persisted approval, including after the script-review pause.
            st.session_state["create_ai_approval_nonce"] = st.session_state.get("create_ai_approval_nonce",0)+1
            st.rerun()
        except Exception as error:
            diagnostics.record_exception(error,"UI bắt đầu pipeline")
            st.error(diagnostics.redact(str(error)))
    key = active or st.session_state.get("pipeline_worker")
    current = manager.snapshot(key) if key else None
    if current and st.session_state.get("pipeline_follow") == key and current.get("project"):
        st.session_state["pending_project"] = Path(current["project"]).name
        st.session_state.pop("pipeline_follow",None)
        st.rerun()
    if active and st.button("Hủy",key="pipeline_cancel"):
        manager.cancel(active)
        st.info("Đã yêu cầu dừng ở điểm an toàn. Tác vụ API đang chạy có thể cần chờ trả về; job AI đã gửi vẫn được lưu để tiếp tục.")
    running = bool(current and current["status"] in {"queued","running"})

    @st.fragment(run_every=1 if running else None)
    def progress_panel():
        snapshot = manager.snapshot(key) if key else None
        selected = project
        # While starting a new run, show that worker's project, then let the
        # sidebar follow it once; switching pages does not interrupt the worker.
        if snapshot and (st.session_state.get("pipeline_follow") == key or selected is None):
            selected = Path(snapshot["project"]) if snapshot.get("project") else selected
        state = read_ui_state(selected, snapshot)
        if selected and state is None and (selected/"run_state.json").exists():
            st.caption("Chưa đọc được trạng thái; sẽ thử lại khi cập nhật trang.")
        if state:
            if state.get("state_write_warning"):
                st.warning(state["state_write_warning"])
            statuses = {"pending":"Chờ","running":"Đang chạy","done":"Xong","failed":"Lỗi","skipped":"Bỏ qua","cancelled":"Đã hủy"}
            for name in STEPS:
                entry = state["steps"][name]
                fraction = 1. if entry["status"] in {"done","skipped"} else state.get("step_progress",0.) if state.get("current_step") == name else 0.
                elapsed = entry["elapsed_sec"]
                if entry["status"] == "running" and entry.get("started_at"):
                    elapsed += max(0.,(datetime.now(timezone.utc)-datetime.fromisoformat(entry["started_at"])).total_seconds())
                st.progress(fraction,text=f"{LABELS[name]} · {statuses.get(entry['status'],entry['status'])} · {elapsed:.1f}s")
            st.caption("Trạng thái lượt: "+state["status"])
            if state.get("error"):
                st.error(diagnostics.redact(state["error"]))
            with st.expander("Nhật ký ngắn",expanded=state["status"] != "done"):
                st.text(diagnostics.redact("\n".join(state.get("log",[])[-20:])))
        if snapshot and snapshot["status"] == "failed":
            st.error(snapshot["error"])
            if debug:
                with st.expander("Traceback pipeline đã che key"):
                    st.code(snapshot["traceback"],language="text")
        if st.session_state.get("pipeline_follow") == key and snapshot and snapshot.get("project"):
            st.rerun()
        if running and snapshot and snapshot["status"] not in {"queued","running"}:
            st.rerun()
    progress_panel()
    if project is None:
        return
    try:
        state = read_ui_state(project, current)
        if state is None:
            return
        ai_folder = confined(project,"ai_video")
        if state["steps"]["ai_video"]["status"] == "skipped" and ai_folder.exists():
            with st.expander("Clip AI lỗi — đã dùng b-roll thay thế"):
                for path in sorted(ai_folder.glob("*.json")):
                    failed_job_details(load_job(path),diagnostics)
        if state["status"] == "waiting_review":
            st.info("Kịch bản đã sẵn sàng. Duyệt/sửa bên dưới, lưu chỉnh sửa rồi tiếp tục.")
            edit_plan_page(settings,project,topic,debug,diagnostics)
            if st.button("Tiếp tục tạo video",type="primary",disabled=bool(active)):
                config = saved_config(project,continue_after_review=True)
                st.session_state["pipeline_worker"] = manager.submit(config,settings)
                st.rerun()
        elif state["status"] == "waiting_ai_choice" or (state["status"] == "failed" and state["steps"]["ai_video"]["status"] == "failed"):
            st.warning("Bước Clip AI lỗi. Bạn có thể giữ video bằng cách render tiếp với b-roll thường, hoặc dừng.")
            choice = st.radio("Xử lý khi Clip AI lỗi",["Bỏ qua clip AI và render bằng b-roll thường","Dừng pipeline"],
                index=0,key=f"ai_failure_choice_{project.name}")
            busy = bool(active or ai_video_jobs().active(project))
            if st.button("Áp dụng lựa chọn",type="primary",disabled=busy):
                config = saved_config(project,ai_failure_decision="skip" if choice.startswith("Bỏ qua") else "stop")
                st.session_state["pipeline_worker"] = manager.submit(config,settings)
                st.rerun()
            with st.expander("Khôi phục Clip AI trước khi thử lại"):
                for path in sorted(confined(project,"ai_video").glob("*.json")):
                    data = load_job(path)
                    failed_job_details(data,diagnostics)
                    if not data.get("remote_id"):
                        st.caption("Job: "+path.name)
                        recovery_controls(project,path,data,settings,disabled=busy,key_prefix="pipeline_recovery")
                if st.button("Thử lại bước Clip AI",disabled=busy):
                    st.session_state["pipeline_worker"] = manager.submit(saved_config(project),settings)
                    st.rerun()
        elif state["status"] in {"failed","cancelled","paused","running"} and not active:
            if st.button("Tiếp tục từ bước đang dở",type="primary"):
                st.session_state["pipeline_worker"] = manager.submit(saved_config(project),settings)
                st.rerun()
        elif state["status"] == "done":
            summary = state.get("summary",{})
            st.success(f"Hoàn tất · {summary.get('elapsed_sec',0):.1f}s xử lý · {summary.get('facts_used',0)} fact / {summary.get('sources_used',0)} nguồn đã dùng")
            show_result(state["render_result"],project,diagnostics)
            for filename,label in [("render/credits.txt","Tải credits.txt"),("report.md","Tải báo cáo")]:
                path = confined(project,filename)
                if path.is_file():
                    st.download_button(label,path.read_bytes(),file_name=path.name,mime="text/plain" if path.suffix == ".txt" else "text/markdown")
    except Exception as error:
        diagnostics.record_exception(error,"UI đọc checkpoint pipeline")
        st.error(diagnostics.redact(str(error)))
