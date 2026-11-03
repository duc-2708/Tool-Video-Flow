# file: app/streamlit_app.py
"""UI web local hiện đại: Phong cách Đen - Vàng - Trắng (Black - Gold - White)."""
import html
from pathlib import Path
import os
import sys

# Đảm bảo import được các module từ thư mục gốc APP
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from pydantic import ValidationError

from config.settings import get_settings
from pipeline.projects import list_projects
from providers.llm.router import model_for, route_ready
from utils.atomic_io import cleanup_tmp_files
from utils.diagnostics import Diagnostics
from utils.file_lock import file_lock


# Tự động nạp mã mới nhất cho các module UI, chống lỗi cache RAM của Streamlit
import importlib
if "pytest" not in sys.modules and not os.environ.get("PYTEST_CURRENT_TEST"):
    for _m in ("app.style_controls", "app.views.create_video_hub", "app.views.create_video"):
        if _m in sys.modules:
            try:
                importlib.reload(sys.modules[_m])
            except Exception:
                pass

from app.ui_kit import chip_html, section_header
from app.views.ai_video import render as render_ai_video
from app.views.assets import render as render_assets
from app.views.auto_category import render as render_auto_category
from app.views.create_video import render as render_create_video
from app.views.discover import render as render_discover
from app.views.edit_plan import render as render_edit_plan
from app.views.motion_gallery import render as render_motion_gallery
from app.views.render import render as render_video
from app.views.research import render as render_research
from app.views.settings_view import render as render_settings_view
from app.views.style_samples import render as render_style_samples
from app.views.templates import render as render_templates
from app.views.trend_scout import render as render_trend_scout
from app.views.video_warehouse import render as render_video_warehouse

NEW_PROJECT = "__new_project__"

# Danh bạ toàn bộ các trang: "Tạo video" đứng đầu làm trang mặc định
PAGES = {
    # TẠO VIDEO
    "Tạo video": render_create_video,
    "Tạo video theo danh mục": render_auto_category,
    "Khám phá chủ đề": render_discover,
    "Trend Scout": render_trend_scout,
    # XỬ LÝ
    "Research": render_research,
    "Edit Plan": render_edit_plan,
    "Assets": render_assets,
    "AI Video": render_ai_video,
    "Render": render_video,
    # THƯ VIỆN
    "Kho video đã làm": render_video_warehouse,
    "Phong cách mẫu": render_style_samples,
    "Xem trước mẫu": render_templates,
    "Phòng thử hiệu ứng": render_motion_gallery,
    # HỆ THỐNG
    "Cài đặt Token & AI": render_settings_view,
}

NAV_GROUPS = {
    "TẠO VIDEO": ["Tạo video", "Tạo video theo danh mục", "Khám phá chủ đề", "Trend Scout"],
    "XỬ LÝ": ["Research", "Edit Plan", "Assets", "AI Video", "Render"],
    "THƯ VIỆN": ["Kho video đã làm", "Phong cách mẫu", "Xem trước mẫu", "Phòng thử hiệu ứng"],
    "HỆ THỐNG": ["Cài đặt Token & AI"],
}

PAGE_NAMES_VI = {
    "Tạo video": "Tạo video",
    "Tạo video theo danh mục": "Tự động theo danh mục",
    "Khám phá chủ đề": "Khám phá chủ đề",
    "Trend Scout": "Trend Scout",
    "Research": "Research",
    "Edit Plan": "Edit Plan",
    "Assets": "Assets",
    "AI Video": "AI Video",
    "Render": "Render",
    "Kho video đã làm": "Kho video đã làm",
    "Phong cách mẫu": "Phong cách mẫu",
    "Xem trước mẫu": "Xem trước mẫu",
    "Phòng thử hiệu ứng": "Phòng thử hiệu ứng",
    "Cài đặt Token & AI": "Cài đặt Token & AI",
}

PAGE_META = {
    "Tạo video": ("BẮT ĐẦU", "Hôm nay làm video gì?", "Tạo một hoặc nhiều video tự động từ chủ đề, danh mục hoặc xu hướng."),
    "Tạo video theo danh mục": ("TỰ ĐỘNG", "Tạo video theo danh mục", "Tự động chọn chủ đề tối ưu theo danh mục và tạo video trọn gói."),
    "Khám phá chủ đề": ("XU HƯỚNG", "Khám phá chủ đề", "Quét tin tức, RSS và đối chiếu lịch sử 14 ngày để tìm đề tài nóng."),
    "Trend Scout": ("TÌM KIẾM", "Trend Scout", "Quét tín hiệu xu hướng YouTube, tin tức và tìm kiếm mạng xã hội."),
    "Research": ("THU THẬP", "Nghiên cứu & Đối chiếu facts", "Thu thập nguồn tin đối chiếu, trích dẫn bằng chứng và xây dựng Research Brief."),
    "Edit Plan": ("KỊCH BẢN", "Edit Plan", "Director 2 lượt tạo kịch bản, lời thoại từng cảnh, phân bổ thời lượng và visual specs."),
    "Assets": ("TÀI NGUYÊN", "Tài nguyên & Minh họa", "Tải media, b-roll stock Pexels/Pixabay và tạo voice thuyết minh."),
    "AI Video": ("CLIP AI", "Tạo clip bằng AI", "Tạo clip chuyển động trả phí qua Video Gateway (Veo-3.1 / Seedance)."),
    "Render": ("XUẤT VIDEO", "Dựng & Xuất video hoàn chỉnh", "Ghép audio, visual, phụ đề karaoke và render file MP4 9:16."),
    "Kho video đã làm": ("THƯ VIỆN", "Kho video đã sản xuất", "Quản lý, xem lại và tải về các video đã dựng thành công."),
    "Phong cách mẫu": ("PHONG CÁCH", "Học phong cách từ mẫu", "Phân tích video tham khảo và trích xuất Style Profile."),
    "Xem trước mẫu": ("XEM TRƯỚC", "Thư viện mẫu đồ họa", "Xem trước các mẫu bố cục, thẻ thông tin và hiệu ứng chuyển động."),
    "Phòng thử hiệu ứng": ("PHÒNG THỬ", "Thử nghiệm hiệu ứng đồ họa", "Kiểm tra chất lượng render đồ họa chuyển động HTML/SVG trong Playwright."),
    "Cài đặt Token & AI": ("HỆ THỐNG", "Cài đặt Token & Cấu hình AI", "Quản lý khóa API bí mật local và định tuyến model LLM theo từng vai trò."),
}


def new_project() -> None:
    st.session_state["project_choice"] = NEW_PROJECT
    for key in (
        "create_topic", "topic_input", "director_plan", "director_error", "director_notice",
        "assets_worker", "assets_error", "render_worker", "render_error", "create_discovery",
        "create_category", "create_style_preset", "create_type", "batch_proposed_topics"
    ):
        st.session_state.pop(key, None)


def main() -> None:
    st.set_page_config(page_title="Video AI Tool", page_icon="V", layout="wide")

    # Nạp CSS Theme Đen - Vàng - Trắng (100% offline)
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

    # Đặt trang mặc định khi mở app = "Tạo video" (hub)
    st.session_state.setdefault("ui_page", "Tạo video")

    # =========================================================================
    # SIDEBAR: Điều hướng gọn gàng, có phân cấp nhóm
    # =========================================================================
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
            label_visibility="collapsed",
        )
        st.caption(f"{len(projects)} project đã lưu")
        st.button("Project mới", on_click=new_project, use_container_width=True)

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        # Điều hướng phân cấp nhóm: Giữ MỘT st.radio(key="ui_page") với format_func thân thiện
        page = st.radio(
            "Trang",
            list(PAGES),
            key="ui_page",
            format_func=lambda k: PAGE_NAMES_VI.get(k, k),
            label_visibility="collapsed",
        )

        st.divider()

        # Expander Trạng thái hệ thống ở cuối sidebar: Gọn gàng, bảo toàn 100% test contract
        with st.expander("Trạng thái hệ thống", expanded=False):
            debug = st.toggle("Chế độ debug", value=False, key="ui_debug")
            st.markdown("<div style='color: #A8A8A8; font-size: 0.75rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; margin: 8px 0;'>API KEYS & PROVIDERS</div>", unsafe_allow_html=True)
            for provider in ("gemini", "youtube", "pexels", "pixabay", "gateway", "scrapecreators", "openai"):
                present = bool(getattr(settings, f"{provider}_api_key").get_secret_value().strip())
                st.text(f"{provider.upper()}_API_KEY: {'Đã có' if present else 'Chưa có'}")
            st.text("Model: " + diagnostics.redact(settings.gemini_model or "Chưa cấu hình"))
            st.text("Model Director: " + diagnostics.redact(settings.gemini_director_model.strip() or settings.gemini_model or "Chưa cấu hình"))
            for step, label in (("researcher", "Researcher"), ("director", "Director"), ("trend", "Trend")):
                provider = getattr(settings, "llm_provider_" + step)
                st.text(f"LLM {label}: " + diagnostics.redact(f"{provider} / {model_for(settings, provider, step) or 'Chưa có model'}"))
                if not route_ready(settings, step):
                    st.caption(f"{label}: chưa đủ cấu hình provider đã chọn.")
            st.caption("Style Learner: chỉ Gemini, không chuyển sang OpenAI.")
            for warning in settings.llm_configuration_warnings:
                st.warning(warning)
            st.caption("Trạng thái key chỉ cho biết đã nhập, chưa xác minh quyền sử dụng.")
            st.caption("Chỉ chạy local tại 127.0.0.1.")

    notice = st.session_state.pop("research_notice", None)
    if notice:
        st.success(notice)

    settings_saved = st.session_state.pop("settings_saved_notice", None)
    if settings_saved:
        st.success(settings_saved)

    selected = by_name.get(choice)

    # Hiển thị tiêu đề chuẩn cho các trang (trừ các trang đã tự vẽ tiêu đề riêng)
    PAGES_WITH_INTERNAL_HEADER = {"Tạo video", "Edit Plan", "Assets", "Research", "Phong cách mẫu"}
    if page not in PAGES_WITH_INTERNAL_HEADER and page in PAGE_META:
        eyebrow, p_title, p_desc = PAGE_META[page]
        section_header(eyebrow, p_title)
        if p_desc:
            st.caption(p_desc)

    PAGES[page](
        settings,
        selected.path if selected else None,
        diagnostics.redact(selected.topic) if selected else "",
        st.session_state.get("ui_debug", False),
        diagnostics,
    )


if __name__ == "__main__":
    main()
