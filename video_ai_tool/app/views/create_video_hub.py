"""Trang Tạo Video Trung Tâm: Tạo đơn lẻ hoặc Tạo hàng loạt (nhập 10 tạo 10 video)."""
from datetime import datetime, timezone
from pathlib import Path
import streamlit as st

from agents.story_style import data_advice
from app.style_controls import select_category, select_style
from app.views.ai_video import ai_video_jobs, failed_job_details, recovery_controls
from app.views.edit_plan import render as edit_plan_page
from app.views.render import show_result
from config.categories import categories_for
from config.storytelling import DURATIONS, STYLES
from editor.timeline import confined
from pipeline.ai_video import load_job
from pipeline.batch_jobs import BatchJobs
from pipeline.projects import read_json
from pipeline.run_all import LABELS, RunConfig, STEPS, saved_config
from pipeline.run_all_jobs import PipelineJobs
from providers.llm.router import route_ready
from providers.video_gateway import allowed_models, MODELS, VideoRequest
from schemas.languages import LABELS as LANGUAGE_LABELS
from schemas.research_brief import ResearchBrief
from utils.cache import cache_key


@st.cache_resource
def pipeline_jobs():
    return PipelineJobs()


@st.cache_resource
def batch_jobs():
    return BatchJobs()


def read_ui_state(project, snapshot=None):
    if snapshot and snapshot.get("state") and (project is None or snapshot.get("project") == str(project)):
        return snapshot["state"]
    if project is not None:
        try:
            return read_json(confined(project, "run_state.json"), allow_stale=True)
        except (OSError, ValueError):
            pass
    if snapshot and (project is None or snapshot.get("project") == str(project)):
        return snapshot.get("state")
    return None


def render(settings, project, topic, debug, diagnostics):
    st.markdown("""
        <div class="main-card">
            <h2 style="margin: 0; color: #ffd60a; font-weight: 800; font-size: 1.8rem;">
                ⚡ Tạo Video Tự Động Với AI
            </h2>
            <p style="margin: 4px 0 0 0; color: #a1a1aa; font-size: 0.95rem;">
                Tạo 1 video chi tiết hoặc nhập số lượng (ví dụ: 10) để AI tự động tìm kiếm các chủ đề khác nhau và dựng thành 10 video độc lập.
            </p>
        </div>
    """, unsafe_allow_html=True)

    manager = pipeline_jobs()
    active_single = manager.active()
    b_manager = batch_jobs()
    b_running = b_manager.is_running()

    tab_single, tab_batch = st.tabs(["🎯 Tạo 1 Video Theo Chủ Đề", "🚀 Tạo Hàng Loạt (Auto Multi-Videos)"])

    # =========================================================================
    # TAB 1: TẠO 1 VIDEO
    # =========================================================================
    with tab_single:
        category = select_category(settings, key="create_category")
        entered_topic = st.text_input("Chủ đề video", value=topic or "", max_chars=500, key="create_topic", placeholder="Nhập chủ đề muốn làm video (ví dụ: Ra mắt chip xử lý M4...)")

        col1, col2 = st.columns(2)
        video_type = col1.selectbox("Loại video", ["news", "review", "story"], key="create_type")
        video_format = col2.selectbox("Khổ khung hình", ["tiktok", "youtube"], format_func=lambda v: "TikTok / Shorts · 9:16 (Dọc)" if v == "tiktok" else "YouTube · 16:9 (Ngang)", key="create_format")

        preset = col1.selectbox("Mốc thời lượng", ["Tùy chỉnh", *DURATIONS], key="create_duration_preset")
        style_preset = select_style(settings, key="create_style_preset", category=category, video_type=video_type)
        script_style = col2.selectbox("Phong cách kịch bản", list(STYLES), format_func=STYLES.get, key="create_script_style")
        explainer_v2 = st.checkbox("Bật Explainer v2: Phân tích chuyên sâu kèm mỏ neo ẩn dụ", value=True, key="create_explainer_v2")

        duration = col1.number_input("Độ dài mong muốn (giây)", min_value=6.0, max_value=600.0, value=45.0, step=1.0, key="create_duration")
        duration = float(preset) if preset != "Tùy chỉnh" else duration

        voices = ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"]
        voice = col2.selectbox("Giọng đọc thuyết minh", voices, index=voices.index(settings.default_voice) if settings.default_voice in voices else 0, key="create_voice")

        mode = col1.selectbox("Chế độ chạy", ["auto", "review"], format_func=lambda v: "Tự động hoàn toàn (Auto-pilot)" if v == "auto" else "Dừng để duyệt/sửa kịch bản", key="create_mode")
        render_mode = col2.selectbox("Chất lượng dựng", ["final", "preview"], format_func=lambda v: "Bản hoàn thiện sắc nét (Final 1080p)" if v == "final" else "Xem nhanh (Preview draft)", key="create_render_mode")

        with st.expander("🛠️ Tùy chọn nâng cao (Nguồn tìm kiếm & Clip AI)", expanded=False):
            youtube = st.checkbox("Tham khảo YouTube Trends", value=False, key="create_youtube")
            source_languages = st.multiselect("Ngôn ngữ tìm kiếm", list(LANGUAGE_LABELS), default=["vi", "en"], format_func=LANGUAGE_LABELS.get, key="create_source_languages")
            web_limit = st.slider("Số nguồn web tối đa", min_value=1, max_value=12, value=6, key="create_web_limit")

            ai_enabled = st.checkbox("Dùng Clip AI Veo/Seedance (có tính phí)", value=False, disabled=settings.ai_clip_max_per_run == 0 or not allowed_models(settings), key="create_ai")
            ai_count, ai_model, ai_seconds, confirmed = 0, "veo-3.1", 4, False
            if ai_enabled and settings.ai_clip_max_per_run:
                ai_count = st.number_input("Số clip AI", min_value=1, max_value=settings.ai_clip_max_per_run, value=1, key="create_ai_count")
                names = allowed_models(settings)
                ai_model = st.selectbox("Model clip AI", names, index=names.index(settings.gateway_video_model) if settings.gateway_video_model in names else 0, key="create_ai_model")
                ai_seconds = st.selectbox("Thời lượng mỗi clip AI", MODELS[ai_model], index=0, key=f"create_ai_sec_{ai_model}")
                confirmed = st.checkbox("Xác nhận chi phí tạo clip AI", key="create_ai_confirm_cb")

        ready = bool(entered_topic.strip() and route_ready(settings, "researcher") and route_ready(settings, "director") and (not ai_enabled or confirmed))

        col_btn1, col_btn2 = st.columns([2, 1])
        if col_btn1.button("🎬 BẮT ĐẦU TẠO VIDEO", type="primary", use_container_width=True, disabled=bool(active_single or b_running or not ready)):
            try:
                config = RunConfig(
                    topic=entered_topic, category=category, video_type=video_type, video_format=video_format,
                    duration_sec=float(duration), voice=voice, mode=mode, youtube_trends=youtube, youtube_days=14,
                    web_limit=int(web_limit), ai_clips=int(ai_count), source_languages=source_languages,
                    output_language="vi", script_style=script_style, style_preset=style_preset,
                    content_mode="explainer_v2" if explainer_v2 else "event_only", ai_model=ai_model,
                    ai_seconds=ai_seconds, ai_confirmed=confirmed, render_mode=render_mode, ai_failure_action="skip"
                )
                key = manager.submit(config, settings)
                st.session_state["pipeline_worker"] = key
                st.session_state["pipeline_follow"] = key
                st.rerun()
            except Exception as error:
                diagnostics.record_exception(error, "UI bắt đầu pipeline")
                st.error(diagnostics.redact(str(error)))

        if active_single and col_btn2.button("⛔ Hủy Tác Vụ", type="secondary", use_container_width=True):
            manager.cancel(active_single)
            st.info("Đã yêu cầu hủy tác vụ ở điểm an toàn.")

        # Progress tracking for single video
        key = active_single or st.session_state.get("pipeline_worker")
        current = manager.snapshot(key) if key else None
        running = bool(current and current["status"] in {"queued", "running"})

        @st.fragment(run_every=1 if running else None)
        def progress_panel():
            if not key:
                return
            snapshot = manager.snapshot(key)
            selected = project
            if snapshot and (st.session_state.get("pipeline_follow") == key or selected is None):
                selected = Path(snapshot["project"]) if snapshot.get("project") else selected
            state = read_ui_state(selected, snapshot)
            if state:
                st.markdown("<br>", unsafe_allow_html=True)
                st.write(f"**Trạng thái Pipeline:** `{state['status'].upper()}`")
                for name in STEPS:
                    entry = state["steps"].get(name, {})
                    st_val = entry.get("status", "pending")
                    frac = 1.0 if st_val in {"done", "skipped"} else state.get("step_progress", 0.0) if state.get("current_step") == name else 0.0
                    st.progress(frac, text=f"{LABELS[name]} · {st_val.upper()}")
                with st.expander("📜 Nhật ký tiến trình", expanded=running):
                    st.text("\n".join(state.get("log", [])[-15:]))

        progress_panel()

    # =========================================================================
    # TAB 2: TẠO HÀNG LOẠT (MULTI-VIDEOS)
    # =========================================================================
    with tab_batch:
        st.markdown("""
            <div style="background: rgba(255, 214, 10, 0.05); border: 1px solid rgba(255, 214, 10, 0.2); border-radius: 10px; padding: 14px; margin-bottom: 20px;">
                <span style="color: #ffd60a; font-weight: 700;">🤖 Cơ chế Auto-Discovery:</span>
                Nhập số lượng video bạn muốn tạo (ví dụ: 10). AI sẽ liên tục quét các xu hướng mới, tự động chọn ra <b>10 chủ đề hoàn toàn khác nhau</b>, kiểm tra chống trùng lặp với kho lịch sử, và lần lượt dựng thành 10 video độc lập!
            </div>
        """, unsafe_allow_html=True)

        col_b1, col_b2 = st.columns(2)
        try:
            available_cats = [c.name for c in categories_for(settings).categories if c.enabled]
        except Exception:
            available_cats = ["cong-nghe", "tin-tuc"]

        batch_cat = col_b1.selectbox("Lĩnh vực tìm kiếm", available_cats, key="batch_cat")
        batch_count = col_b2.number_input(
            "Số lượng video muốn tạo",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            help="AI sẽ tạo lần lượt từng video với chủ đề mới không trùng lặp"
        )

        col_b3, col_b4 = st.columns(2)
        batch_duration = col_b3.selectbox("Thời lượng mỗi video", DURATIONS, index=1, key="batch_duration")
        batch_format = col_b4.selectbox("Tỉ lệ video", ["tiktok", "youtube"], format_func=lambda v: "TikTok · 9:16 (Dọc)" if v == "tiktok" else "YouTube · 16:9 (Ngang)", key="batch_format")

        col_start, col_cancel = st.columns([2, 1])

        if col_start.button(f"🚀 BẮT ĐẦU TẠO LOẠT {batch_count} VIDEO", type="primary", use_container_width=True, disabled=b_running or bool(active_single)):
            params = {
                "category": batch_cat,
                "region": "both",
                "time_window_days": 3,
                "duration": batch_duration,
                "format": batch_format,
                "creative_license": "strict",
                "style": "storytelling",
                "review": False,
                "use_youtube": False,
                "ai_clips": 0,
                "content_mode": "explainer_v2"
            }
            b_manager.start_batch(params, count=int(batch_count), settings=settings)
            st.rerun()

        if b_running and col_cancel.button("🛑 DỪNG TẠO LOẠT", type="secondary", use_container_width=True):
            b_manager.cancel()
            st.warning("Đã gửi yêu cầu dừng sau khi hoàn tất video hiện tại.")
            st.rerun()

        # Batch progress display
        @st.fragment(run_every=2 if b_running else None)
        def batch_progress_panel():
            snap = b_manager.snapshot()
            if snap["status"] != "idle":
                st.markdown("<br>", unsafe_allow_html=True)
                st.write(f"**Trạng thái Batch:** `{snap['status'].upper()}`")
                total = snap["total_count"] or 1
                curr = snap["current_index"]
                st.progress(min(1.0, curr / total), text=f"Tiến độ tổng: Đang xử lý video {curr}/{total}")

                st.write(f"Đã tạo thành công: **{len(snap['created_projects'])}** video")
                with st.expander("📋 Nhật ký chạy hàng loạt", expanded=True):
                    st.text("\n".join(snap["log"]))

        batch_progress_panel()
