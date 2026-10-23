# file: app/streamlit_app.py
"""UI web local mỏng; chạy bằng streamlit run, không gọi subprocess."""
from pathlib import Path
import sys

# Streamlit chạy file trong app/; thêm project root để import package dùng chung.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from config.settings import get_settings
from pipeline.projects import list_projects
from utils.diagnostics import Diagnostics
from utils.atomic_io import cleanup_tmp_files
from utils.file_lock import file_lock
from app.views.research import render as render_research
from app.views.edit_plan import render as render_edit_plan
from app.views.assets import render as render_assets
from app.views.render import render as render_video
from app.views.ai_video import render as render_ai_video
from app.views.create_video import render as render_create_video
from app.views.discover import render as render_discover
from app.views.auto_category import render as render_auto_category
from app.views.style_samples import render as render_style_samples
from app.views.templates import render as render_templates

NEW_PROJECT = "__new_project__"
# Thêm trang mới tại đây; mỗi render có cùng signature với trang Research.
PAGES = {"Tạo video theo danh mục":render_auto_category,"Khám phá chủ đề":render_discover, "Tạo video": render_create_video, "Research": render_research, "Edit Plan": render_edit_plan, "Assets": render_assets, "AI Video": render_ai_video, "Render": render_video, "Phong cách mẫu":render_style_samples}
PAGES["Xem trước mẫu"]=render_templates


def new_project() -> None:
    st.session_state["project_choice"] = NEW_PROJECT
    st.session_state["research_topic_new"] = ""
    st.session_state.pop("research_error", None)
    st.session_state.pop("research_notice", None)
    st.session_state.pop("create_topic", None)
    st.session_state.pop("create_discovery", None)
    st.session_state.pop("discovery_prefill", None)


def main() -> None:
    st.set_page_config(page_title="Video AI Tool", page_icon="🎬", layout="wide")
    try:
        settings = get_settings()
        diagnostics = Diagnostics(settings.logs_dir, secrets=[
            getattr(settings, f"{provider}_api_key").get_secret_value()
            for provider in ("gemini", "youtube", "pexels", "pixabay", "gateway")])
    except Exception:
        st.error("Không nạp được cấu hình. Hãy kiểm tra kiểu và khoảng giá trị theo .env.example bằng trình soạn thảo.")
        st.stop()
    try:
        projects = list_projects(settings.output_dir)
        if not st.session_state.get("tmp_cleanup_done"):
            for project in projects:
                try:
                    with file_lock(project.path / "run_all.lock", timeout=0):
                        cleanup_tmp_files(project.path)
                except OSError:
                    pass  # Another worker may still be writing this project.
            st.session_state["tmp_cleanup_done"] = True
    except Exception:
        st.error("Không đọc được danh sách project trong output/. Kiểm tra quyền truy cập thư mục.")
        st.stop()
    by_name = {project.name: project for project in projects}
    options = [NEW_PROJECT, *by_name]
    pending = st.session_state.pop("pending_project", None)
    if pending in by_name:
        st.session_state["project_choice"] = pending
    if st.session_state.get("project_choice") not in options:
        st.session_state["project_choice"] = projects[0].name if projects else NEW_PROJECT
    pending_page=st.session_state.pop("pending_page",None)
    if pending_page in PAGES: st.session_state["ui_page"]=pending_page
    with st.sidebar:
        st.title("Video AI Tool")
        st.caption("Pipeline local · Giai đoạn 5")
        st.button("Project mới", on_click=new_project, width="stretch")
        choice = st.selectbox("Project trong output/", options, key="project_choice",
            format_func=lambda name: "— Project mới —" if name == NEW_PROJECT else diagnostics.redact(
                f"{by_name[name].topic} · {name[-8:]}"))
        st.caption(f"{len(projects)} project đã lưu")
        page = st.radio("Trang", list(PAGES),key="ui_page")
        debug = st.checkbox("Chế độ debug", value=False, key="ui_debug")
        st.divider()
        st.subheader("Trạng thái cấu hình")
        for provider in ("gemini", "youtube", "pexels", "pixabay", "gateway"):
            present = bool(getattr(settings, f"{provider}_api_key").get_secret_value().strip())
            st.text(f"{provider.upper()}_API_KEY: {'Đã có' if present else 'Chưa có'}")
        st.text("Model: " + diagnostics.redact(settings.gemini_model or "Chưa cấu hình"))
        st.text("Model Director: " + diagnostics.redact(settings.gemini_director_model.strip() or settings.gemini_model or "Chưa cấu hình"))
        st.caption("Trạng thái key chỉ cho biết đã nhập, chưa xác minh quyền sử dụng.")
        st.caption("Chỉ chạy local tại 127.0.0.1. Không có trình xem hoặc nhập API key trên UI.")
    notice = st.session_state.pop("research_notice", None)
    if notice:
        st.success(notice)
    selected = by_name.get(choice)
    PAGES[page](settings, selected.path if selected else None,
                diagnostics.redact(selected.topic) if selected else "", debug, diagnostics)


if __name__ == "__main__":
    main()
