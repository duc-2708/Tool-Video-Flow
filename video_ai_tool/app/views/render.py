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
    st.video(str(path))
    st.download_button("Tải MP4",data=path.read_bytes(),file_name=path.name,mime="video/mp4",key=f"download_{result['mode']}")
    if result.get("warnings"):
        with st.expander("Các shot dùng fallback / cảnh báo"):
            for warning in result["warnings"]:
                st.write(diagnostics.redact(warning))
    st.caption("Phụ đề dùng timing từ nếu có sidecar hợp lệ; nếu chưa có thì ước lượng theo số ký tự, chưa phải căn chỉnh giọng nói chính xác.")


def render(settings,project,topic,debug,diagnostics):
    st.header("Render")
    st.caption("Dựng video từ Assets đã chuẩn bị. Mọi kết quả nằm trong render/; các đầu vào được giữ nguyên.")
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
    left,right = st.columns(2)
    for column,label,mode in [(left,"Render xem nhanh","preview"),(right,"Render bản cuối","final")]:
        if column.button(label,disabled=bool(active),width="stretch"):
            st.session_state[state_key] = manager.submit(plan,mode,settings,diagnostics.secrets)
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
