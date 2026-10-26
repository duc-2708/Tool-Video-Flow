"""Render page: background worker, periodic progress, playback and download."""
from pathlib import Path
import streamlit as st
from editor.jobs import RenderJobs
from editor.timeline import confined
from pipeline.projects import read_json


@st.cache_resource
def render_jobs():
    return RenderJobs()


def show_result(result,project,diagnostics):
    root = confined(project,"render")
    path = confined(root,Path(result["filename"]).name)
    if not path.is_file():
        st.warning("File MP4 chưa có hoặc đã được di chuyển.")
        return
    st.caption(f"{result['duration_sec']:.2f} giây · {result['width']} × {result['height']} · {result['fps']} fps · {path.stat().st_size/1024**2:.2f} MB · Dựng trong {result['render_seconds']:.1f} giây")
    if result.get('quality_summary'):
        qc=result['quality_summary']
        st.caption(f"Kiểm tra hình ảnh: {qc['template_types']} loại mẫu · {qc['warning_count']} cảnh báo · {qc['deferred_dom_samples']} mẫu DOM chưa hiện đủ.")
        if 'illustration_coverage_percent' in qc:
            st.caption(f"Minh họa: {qc['illustration_coverage_percent']:.1f}% thời lượng · {qc['scene_type_count']} loại cảnh hoạt họa.")
            if qc['illustration_coverage_percent']<85 and result.get('illustrations_requested'): st.warning('Hình minh họa dưới85%; xem quality_report.json để biết cảnh thiếu dữ liệu hoặc đang fallback.')
        with st.expander('Báo cáo chất lượng hình ảnh'):
            try:
                report=read_json(confined(project,Path(result['quality_report']).name))
                st.json(report)
            except (OSError,ValueError): st.info('Chưa đọc được báo cáo chất lượng.')
    st.video(str(path))
    st.download_button("Tải MP4",data=path.read_bytes(),file_name=path.name,mime="video/mp4",key=f"download_{path.name}")
    sheet=confined(project/"review_frames",Path(result.get("contact_sheet") or "contact_sheet.png").name)
    if sheet.is_file() and result.get("motion_enabled"):
        with st.expander("Khung hình kiểm tra và ghi chú Motion"):
            st.image(str(sheet))
            for note in result.get("review_notes",[]): st.write(diagnostics.redact(note))
    if result.get("warnings"):
        with st.expander("Các shot dùng fallback / cảnh báo"):
            for warning in result["warnings"]:
                st.write(diagnostics.redact(warning))
    st.caption("Phụ đề dùng timing từ nếu có sidecar hợp lệ; nếu chưa có thì ước lượng theo số ký tự, chưa phải căn chỉnh giọng nói chính xác.")


def render(settings,project,topic,debug,diagnostics):
    st.header("Render")
    st.caption("Dựng video từ Assets đã chuẩn bị. Mọi kết quả nằm trong render/; các đầu vào được giữ nguyên.")
    if settings.motion_enabled:
        st.info(f"Motion graphics bật · {settings.motion_fps} fps · scale {settings.motion_scale:g}. Thiếu Playwright/Chromium sẽ dùng đồ họa Pillow. Tiến độ chụp cảnh kèm thời gian còn lại ước tính.")
    if project is None:
        st.info("Chọn một project đã tạo Assets.")
        return
    plan = project/"edit_plan.resolved.json"
    if not plan.is_file():
        st.info("Hãy tạo Assets trước để có edit_plan.resolved.json và audio.")
        return
    manager = render_jobs()
    state_key = f"render_job_{project.name}"
    active = manager.active(project)
    from editor.motion.theme import theme_names
    motion=st.toggle("Bật Motion",value=settings.motion_enabled,disabled=bool(active))
    mascot=st.toggle("Bật mascot hình khối riêng",value=settings.mascot_enabled,disabled=bool(active))
    scenes_on=st.toggle('Bật cảnh minh họa hoạt họa',value=settings.motion_scenes_enabled,disabled=bool(active) or not motion)
    fps=st.selectbox('FPS Motion bản nháp',[24,30],index=0 if settings.motion_fps==24 else 1,disabled=bool(active))
    themes=["auto",*theme_names(settings.root_dir)]
    theme=st.selectbox("Theme Motion",themes,index=themes.index(settings.motion_theme) if settings.motion_theme in themes else 0,disabled=bool(active))
    settings=settings.model_copy(update={"motion_enabled":motion,"mascot_enabled":mascot,"motion_theme":theme,'motion_scenes_enabled':scenes_on,'motion_fps':fps})
    ai_on=st.toggle('Clip AI làm nền (có phí)',value=bool(settings.ai_clips_per_video),disabled=bool(active) or not motion)
    ai_count=0;ai_confirmed=False
    if ai_on and motion:
        from pipeline.controlled_ai import estimate
        from pipeline.ai_budget import remaining
        from schemas.assets import ResolvedEditPlan
        try:
            data=ResolvedEditPlan.model_validate(read_json(plan))
            info=estimate(data,settings,count=max(1,settings.ai_clips_per_video))
            ai_count=info['count']
            st.caption(f"Sẽ dùng tối đa {ai_count} clip hook/cao trào · {info['model']} · {info['seconds']}s · ngân sách còn {remaining(settings)} lượt POST hôm nay.")
            st.warning(f"Tham khảo {info['estimated_vnd_per_job']:,}đ/job; tối đa {info['estimated_vnd_max_with_retry']:,}đ nếu generation_failed phải thử lại. Giá thực xem dashboard. Không retry POST khi timeout/thiếu ID.")
            ai_confirmed=st.checkbox('Tôi xác nhận số clip, model, thời lượng và chi phí dự kiến',disabled=bool(active))
            if not settings.gateway_api_key.get_secret_value().strip():
                ai_confirmed=False;st.info('Thiếu GATEWAY_API_KEY; dùng gradient hoặc điền key bằng editor.')
        except (OSError,ValueError) as error: st.warning(diagnostics.redact(str(error)))
    settings=settings.model_copy(update={'ai_clips_per_video':ai_count if ai_on else 0})
    try: scene_ids=[scene["id"] for scene in read_json(plan)["scenes"]]
    except (OSError,ValueError,KeyError): scene_ids=[]
    if scene_ids:
        with st.expander("Xem trước / render lại một cảnh"):
            scene_id=st.selectbox("Cảnh",scene_ids)
            a,b=st.columns(2)
            preview_settings=settings.model_copy(update={"motion_scale":.5})
            if a.button("Xem trước cảnh",disabled=bool(active)):
                st.session_state[state_key]=manager.submit(plan,"preview",preview_settings,diagnostics.secrets,scene_id=scene_id)
                st.rerun()
            if b.button("Render lại chỉ cảnh này",disabled=bool(active)):
                st.session_state[state_key]=manager.submit(plan,"preview",preview_settings,diagnostics.secrets,scene_id=scene_id,force_scene=scene_id)
                st.rerun()
    left,right = st.columns(2)
    for column,label,mode in [(left,"Render xem nhanh","preview"),(right,"Render bản cuối","final")]:
        if column.button(label,disabled=bool(active) or bool(ai_count and not ai_confirmed),width="stretch"):
            options={'ai_background_count':ai_count,'ai_confirmed':True} if ai_count else {}
            st.session_state[state_key] = manager.submit(plan,mode,settings,diagnostics.secrets,**options)
            st.rerun()
    job_id = st.session_state.get(state_key) or active
    job = manager.snapshot(job_id) if job_id else None
    running = bool(job and job["status"] in {"queued","running"})

    @st.fragment(run_every=1 if running else None)
    def progress_panel():
        current = manager.snapshot(job_id) if job_id else None
        if not current:
            return
        st.progress(current["progress"],text=current["message"])
        if current["status"] == "failed":
            st.error("Render thất bại: "+current["error"])
            if debug:
                with st.expander("Traceback gốc (đã che thông tin nhạy cảm)"):
                    st.code(current["traceback"],language="text")
        elif current["status"] == "complete":
            st.success("Render hoàn tất. Có thể xem và tải MP4 bên dưới.")
            if current.get("result",{}).get("scene_id") is not None: show_result(current["result"],project,diagnostics)
        if running and current["status"] in {"complete","failed"}:
            st.rerun()
    progress_panel()
    for mode,label in [("preview","Bản xem nhanh"),("final","Bản cuối")]:
        report_path = project/"render"/f"{mode}.json"
        if report_path.is_file():
            try:
                result = read_json(confined(project/"render",f"{mode}.json"))
                st.subheader(label)
                show_result(result,project,diagnostics)
            except Exception as error:
                diagnostics.record_exception(error,"Đọc kết quả Render trên UI")
                st.error("Không đọc được kết quả Render: "+diagnostics.redact(str(error)))
