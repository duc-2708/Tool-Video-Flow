# file: app/streamlit_app.py
"""UI web local hiện đại: Phong cách Đen - Vàng - Trắng (Black - Gold - White)."""
from pathlib import Path
import sys

# Streamlit chạy file trong app/; thêm project root để import package dùng chung.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from pydantic import ValidationError
from providers.llm.router import model_for, route_ready
from config.settings import get_settings
from pipeline.projects import list_projects
from utils.diagnostics import Diagnostics
from utils.atomic_io import cleanup_tmp_files
from utils.file_lock import file_lock
from app.ui_kit import chip_html

from app.views.create_video_hub import render as render_create_video_hub
from app.views.video_warehouse import render as render_video_warehouse
from app.views.settings_view import render as render_settings_view
from app.views.research import render as render_research
from app.views.edit_plan import render as render_edit_plan
from app.views.assets import render as render_assets
from app.views.render import render as render_video
from app.views.ai_video import render as render_ai_video
from app.views.discover import render as render_discover
from app.views.auto_category import render as render_auto_category
from app.views.style_samples import render as render_style_samples
from app.views.templates import render as render_templates
from app.views.trend_scout import render as render_trend_scout
from app.views.motion_gallery import render as render_motion_gallery

NEW_PROJECT = "__new_project__"

# Danh bạ toàn bộ các trang (Giữ nguyên tên khóa tương thích 100% test suite)
# Đặt "Tạo video theo danh mục" đầu tiên để thỏa mãn test_first_ui_page_and_manual_handoff
PAGES = {
    "Tạo video theo danh mục": render_auto_category,
    "Khám phá chủ đề": render_discover,
    "Tạo video": render_create_video_hub,
    "Research": render_research,
    "Edit Plan": render_edit_plan,
    "Assets": render_assets,
    "AI Video": render_ai_video,
    "Render": render_video,
    "Kho video đã làm": render_video_warehouse,
    "Phong cách mẫu": render_style_samples,
    "Xem trước mẫu": render_templates,
    "Trend Scout": render_trend_scout,
    "Phòng thử hiệu ứng": render_motion_gallery,
    "Cài đặt Token & AI": render_settings_view,
}


def new_project() -> None:
    st.session_state["project_choice"] = NEW_PROJECT
    st.session_state["research_topic_new"] = ""
    st.session_state.pop("research_error", None)
    st.session_state.pop("research_notice", None)
    st.session_state.pop("create_topic", None)
    st.session_state.pop("create_discovery", None)
    st.session_state.pop("discovery_prefill", None)


def main() -> None:
    st.set_page_config(page_title="Video AI Tool", page_icon="V", layout="wide")

    # Inject CSS Theme Đen - Vàng - Trắng
    css_path = Path(__file__).parent / "theme.css"
    if css_path.is_file():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

    try:
        settings = get_settings()
        diagnostics = Diagnostics(settings.logs_dir, secrets=[
            getattr(settings, f"{provider}_api_key").get_secret_value()
            for provider in ("gemini", "youtube", "pexels", "pixabay", "gateway", "scrapecreators", "openai")
        ])
    except ValidationError as error:
        names = sorted({str(item["loc"][0]).upper() for item in error.errors(include_input=False) if item["loc"]})
        st.error("Không nạp được cấu hình. Biến cần kiểm tra: " + ", ".join(names) + ". Không hiển thị giá trị khóa.")
        st.stop()
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
                    pass
            st.session_state["tmp_cleanup_done"] = True
    except Exception:
        st.error("Không đọc được danh sách project trong output/. Kiểm tra quyền truy cập thư mục.")
        st.stop()

    by_name = {project.name: project for project in projects}
    options = [NEW_PROJECT, *by_name]

    inspiration = st.session_state.pop("pending_research_topic", None)
    if inspiration:
        st.session_state["project_choice"] = NEW_PROJECT
        st.session_state["research_topic_new"] = inspiration

    pending = st.session_state.pop("pending_project", None)
    if pending in by_name:
        st.session_state["project_choice"] = pending

    if st.session_state.get("project_choice") not in options:
        st.session_state["project_choice"] = projects[0].name if projects else NEW_PROJECT

    pending_page = st.session_state.pop("pending_page", None)
    if pending_page in PAGES:
        st.session_state["ui_page"] = pending_page

    # SIDEBAR: Điều hướng Đen - Vàng - Trắng có phân cấp nhóm rõ ràng
    with st.sidebar:
        # Logo ô vuông bo 12px chữ V nền vàng + tên "VIDEO AI TOOL" (không emoji)
        st.markdown("""
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px; padding: 4px 0;">
                <div style="width: 38px; height: 38px; background: #FFD400; color: #0A0A0A; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; font-weight: 900; box-shadow: 0 2px 8px rgba(255, 212, 0, 0.3);">
                    V
                </div>
                <div>
                    <div style="color: #FFFFFF; font-weight: 800; font-size: 1.15rem; letter-spacing: -0.02em; line-height: 1.1;">VIDEO AI TOOL</div>
                    <div style="color: #A8A8A8; font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em;">Studio Edition</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        choice = st.selectbox(
            "Project đang chọn",
            options,
            key="project_choice",
            format_func=lambda name: "— Project mới —" if name == NEW_PROJECT else diagnostics.redact(
                f"{by_name[name].topic} · {name[-8:]}"
            ),
            label_visibility="collapsed"
        )
        st.caption(f"{len(projects)} project đã lưu")
        st.button("Tạo project mới", on_click=new_project, use_container_width=True)

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        # Điều hướng phân cấp nhóm trực quan
        page = st.radio("Trang", list(PAGES), key="ui_page")

        debug = st.checkbox("Chế độ debug", value=False, key="ui_debug")

        st.divider()

        # Trạng thái API Keys hiển thị dạng chip nhỏ gọn, không lộ secret
        st.markdown("<div style='color: #A8A8A8; font-size: 0.75rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;'>TRẠNG THÁI HỆ THỐNG</div>", unsafe_allow_html=True)
        for provider in ("gemini", "openai", "pixabay", "pexels", "youtube", "gateway", "scrapecreators"):
            present = bool(getattr(settings, f"{provider}_api_key").get_secret_value().strip())
            chip_t = "gold" if present else "neutral"
            chip_label = "Đã có" if present else "Chưa có"
            st.markdown(
                f"<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; font-size: 0.85rem;'>"
                f"<span style='color: #DDDDDD;'>{provider.upper()}</span>"
                f"{chip_html(chip_label, chip_t)}"
                f"</div>",
                unsafe_allow_html=True
            )

        st.caption("Model: " + diagnostics.redact(settings.gemini_model or "Chưa cấu hình"))
        for step, label in (("researcher", "Researcher"), ("director", "Director"), ("trend", "Trend")):
            provider = getattr(settings, "llm_provider_" + step)
            st.caption(f"LLM {label}: " + diagnostics.redact(f"{provider} / {model_for(settings, provider, step) or 'Chưa có model'}"))
            if not route_ready(settings, step):
                st.caption(f"{label}: chưa đủ cấu hình provider đã chọn.")
        for warning in settings.llm_configuration_warnings:
            st.warning(warning)
        st.caption("Chỉ chạy local tại 127.0.0.1.")

    notice = st.session_state.pop("research_notice", None)
    if notice:
        st.success(notice)

    settings_saved = st.session_state.pop("settings_saved_notice", None)
    if settings_saved:
        st.success(settings_saved)

    selected = by_name.get(choice)
    PAGES[page](
        settings,
        selected.path if selected else None,
        diagnostics.redact(selected.topic) if selected else "",
        debug,
        diagnostics
    )


if __name__ == "__main__":
    main()
