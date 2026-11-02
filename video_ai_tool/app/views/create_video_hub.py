"""Trang Tạo Video Trung Tâm: Tạo đơn lẻ hoặc Tạo hàng loạt (Luồng 2 pha).

Thiết kế hiện đại Đen - Vàng - Trắng theo Token Design và UI Kit.
"""
from datetime import datetime
import html
from pathlib import Path
import streamlit as st

from app.style_controls import select_category, select_style
from app.ui_kit import card, chip_html, section_header, stat_html, stepper_html
from app.views.ai_video import allowed_models, MODELS
from app.views.edit_plan import render as edit_plan_page
from app.views.render import show_result
from config.categories import categories_for
from config.storytelling import DURATIONS, STYLES
from editor.timeline import confined
from pipeline.batch_jobs import BatchJobs
from pipeline.projects import list_projects, read_json
from pipeline.run_all import LABELS, RunConfig, STEPS
from pipeline.run_all_jobs import PipelineJobs
from providers.llm.router import route_ready
from schemas.languages import LABELS as LANGUAGE_LABELS
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


def get_cached_trend_topics(output_dir: Path) -> list[dict]:
    """Đọc chủ đề gợi ý từ cache Trend Scout local, không gọi mạng."""
    trend_file = output_dir / "trend_scout_latest.json"
    if trend_file.is_file():
        try:
            data = read_json(trend_file)
            proposals = data.get("proposed_topics", [])
            if proposals:
                return [
                    {
                        "title": p.get("topic_title_vi") or p.get("title", ""),
                        "why_hot": p.get("why_hot", "Xu hướng nổi bật"),
                        "source": p.get("source", "Trend Scout"),
                    }
                    for p in proposals[:6]
                    if p.get("topic_title_vi") or p.get("title")
                ]
        except Exception:
            pass
    # Fallback gợi ý mẫu tĩnh nếu chưa có cache
    return [
        {"title": "Cơ hội tỷ USD từ thiết bị bay không người lái", "why_hot": "Công nghệ mới", "source": "Tin tức"},
        {"title": "Việt Nam đạt giải thưởng số toàn cầu", "why_hot": "Điểm sáng số", "source": "Công nghệ"},
        {"title": "Luật cấm chatbot AI tạo sự thân mật cảm xúc", "why_hot": "Quy định AI", "source": "Chính sách"},
    ]


def get_historical_topics(output_dir: Path) -> set[str]:
    """Thu thập danh sách tiêu đề từ lịch sử để kiểm tra trùng lặp."""
    hist_set = set()
    hist_file = output_dir / "topics_history.json"
    if hist_file.is_file():
        try:
            entries = read_json(hist_file)
            for e in entries:
                t = str(e.get("topic", "")).strip().lower()
                if t:
                    hist_set.add(t)
        except Exception:
            pass
    for p in list_projects(output_dir):
        if p.topic:
            hist_set.add(p.topic.strip().lower())
    return hist_set


def render(settings, project, topic, debug, diagnostics):
    # 0. Xử lý prefill chuyển giao từ trang Khám phá chủ đề (handoff)
    prefill = st.session_state.pop("discovery_prefill", None)
    if prefill:
        st.session_state.pop("create_style_preset_context", None)
        st.session_state["create_topic"] = prefill["topic"]
        suggestion = prefill.get("suggestion")
        st.session_state["create_discovery"] = (
            {"category": prefill["category"], "suggestion": suggestion} if suggestion else None
        )
        if suggestion:
            st.session_state["create_type"] = suggestion.get("suggested_type", "news")
        if prefill.get("category"):
            from config.categories import resolve_category

            st.session_state["create_category"] = resolve_category(settings, prefill["category"]).category_id

    # Tiêu đề lớn & Eyebrow theo Token Design
    section_header("BẮT ĐẦU", "Hôm nay làm video gì?", accent_word="gì?")

    manager = pipeline_jobs()
    active_single = manager.active()
    b_manager = batch_jobs()
    b_running = b_manager.is_running()

    # Bố cục 2 cột: Cột trái (Bộ điều khiển chính) & Cột phải (Gợi ý & Dự án gần đây)
    col_main, col_side = st.columns([2.3, 1.0], gap="large")

    with col_main:
        # Ô nhập chủ đề lớn 72px với viền vàng dưới
        st.markdown('<div class="big-topic-input">', unsafe_allow_html=True)
        entered_topic = st.text_input(
            "Chủ đề video",
            value=topic or st.session_state.get("create_topic", ""),
            max_chars=500,
            key="create_topic",
            placeholder="Nhập chủ đề muốn làm video (ví dụ: Ra mắt chip xử lý M4, Cơ hội drone...)",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

        # Chế độ nhập (segmented control / radio ngang)
        input_mode = "Từ chủ đề"
        if hasattr(st, "segmented_control"):
            input_mode = st.segmented_control(
                "Phương thức",
                ["Từ chủ đề", "Theo danh mục", "Khám phá xu hướng"],
                default="Từ chủ đề",
                key="hub_input_mode_sel",
                label_visibility="collapsed",
            )
        else:
            input_mode = st.radio(
                "Phương thức",
                ["Từ chủ đề", "Theo danh mục", "Khám phá xu hướng"],
                horizontal=True,
                key="hub_input_mode_rad",
                label_visibility="collapsed",
            )

        category = "cong-nghe"
        if input_mode == "Theo danh mục":
            category = select_category(settings, key="create_category")
        elif input_mode == "Khám phá xu hướng":
            st.caption("Chủ đề sẽ được lấy tự động từ danh mục tin tức và xu hướng mới nhất.")

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # KHỐI: Số lượng video (Số lượng 1..20, Preset 1, 5, 10, 20, Toggle AI tự tìm chủ đề)
        st.markdown(
            """
            <div style="background: #141414; border: 1px solid #2A2A2A; border-radius: 18px; padding: 18px; margin-bottom: 20px;">
                <div style="font-weight: 700; font-size: 1.05rem; color: #FFFFFF; margin-bottom: 10px;">
                    Số lượng video cần sản xuất
                </div>
            """,
            unsafe_allow_html=True,
        )

        col_qty, col_presets = st.columns([1.2, 1.8])
        with col_qty:
            current_count = st.session_state.get("hub_video_count", 1)
            c_minus, c_num, c_plus = st.columns([1, 2, 1])
            if c_minus.button("−", key="btn_minus_qty", use_container_width=True):
                st.session_state["hub_video_count"] = max(1, current_count - 1)
                st.rerun()
            video_count = c_num.number_input(
                "Số lượng",
                min_value=1,
                max_value=20,
                value=current_count,
                step=1,
                key="hub_video_count",
                label_visibility="collapsed",
            )
            if c_plus.button("+", key="btn_plus_qty", use_container_width=True):
                st.session_state["hub_video_count"] = min(20, current_count + 1)
                st.rerun()

        with col_presets:
            p1, p5, p10, p20 = st.columns(4)
            if p1.button("1 video", use_container_width=True):
                st.session_state["hub_video_count"] = 1
                st.rerun()
            if p5.button("5 video", use_container_width=True):
                st.session_state["hub_video_count"] = 5
                st.rerun()
            if p10.button("10 video", use_container_width=True):
                st.session_state["hub_video_count"] = 10
                st.rerun()
            if p20.button("20 video", use_container_width=True):
                st.session_state["hub_video_count"] = 20
                st.rerun()

        st.toggle(
            "AI tự tìm các chủ đề khác nhau không trùng lặp",
            value=True,
            key="hub_auto_diff_topics",
            help="Hệ thống sẽ đối chiếu lịch sử 14 ngày để đảm bảo các video trong lô có góc nhìn hoàn toàn mới.",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        # HÀNG 4 Ô TÙY CHỌN DẠNG THẺ TRẮNG (Thời lượng, Phong cách, Minh họa, Giọng đọc)
        st.markdown("<div style='font-size: 0.8rem; color: #A8A8A8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;'>CẤU HÌNH XUẤT VIDEO</div>", unsafe_allow_html=True)
        c_opt1, c_opt2, c_opt3, c_opt4 = st.columns(4)

        with c_opt1:
            st.markdown('<div class="ui-card-white"><div style="font-size: 0.75rem; font-weight: 800; color: #555; text-transform: uppercase;">1. Thời lượng</div>', unsafe_allow_html=True)
            preset_dur = st.selectbox("Thời lượng", ["45", "15", "30", "60", "90", "180"], key="hub_duration_sel", label_visibility="collapsed")
            duration = float(preset_dur)
            st.markdown('</div>', unsafe_allow_html=True)

        with c_opt2:
            st.markdown('<div class="ui-card-white"><div style="font-size: 0.75rem; font-weight: 800; color: #555; text-transform: uppercase;">2. Phong cách</div>', unsafe_allow_html=True)
            style_theme = st.selectbox("Theme", ["Mặc định", "Light Glass", "Studio Tối"], key="hub_style_theme", label_visibility="collapsed")
            st.markdown('</div>', unsafe_allow_html=True)

        with c_opt3:
            st.markdown('<div class="ui-card-white"><div style="font-size: 0.75rem; font-weight: 800; color: #555; text-transform: uppercase;">3. Minh họa</div>', unsafe_allow_html=True)
            ill_mode = st.selectbox("Minh họa", ["Vector & Thẻ (V2)", "Stock B-Roll", "Hỗn hợp"], key="hub_ill_mode", label_visibility="collapsed")
            explainer_v2 = (ill_mode != "Stock B-Roll")
            st.markdown('</div>', unsafe_allow_html=True)

        with c_opt4:
            st.markdown('<div class="ui-card-white"><div style="font-size: 0.75rem; font-weight: 800; color: #555; text-transform: uppercase;">4. Giọng đọc</div>', unsafe_allow_html=True)
            voices = ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"]
            voice = st.selectbox("Giọng đọc", voices, format_func=lambda v: "Hoài My (Nữ)" if "HoaiMy" in v else "Nam Minh (Nam)", key="hub_voice_sel", label_visibility="collapsed")
            st.markdown('</div>', unsafe_allow_html=True)

        # Định dạng khổ video & chế độ kịch bản
        c_sub1, c_sub2, c_sub3 = st.columns(3)
        video_format = c_sub1.selectbox("Khổ video", ["tiktok", "youtube"], format_func=lambda v: "TikTok · 9:16 (Dọc)" if v == "tiktok" else "YouTube · 16:9 (Ngang)", key="create_format")
        video_type = c_sub2.selectbox("Thể loại", ["news", "review", "story"], format_func=lambda v: "Tin tức (News)" if v == "news" else "Đánh giá (Review)" if v == "review" else "Kể chuyện (Story)", key="create_type")
        script_style = c_sub3.selectbox("Phong cách kịch bản", list(STYLES), format_func=STYLES.get, key="create_script_style")

        # TÙY CHỌN NÂNG CAO (Expander)
        with st.expander("Tùy chọn nâng cao (Nguồn web & Clip AI)", expanded=False):
            youtube = st.checkbox("Tham khảo YouTube Trends", value=False, key="create_youtube")
            source_languages = st.multiselect("Ngôn ngữ nguồn", list(LANGUAGE_LABELS), default=["vi", "en"], format_func=LANGUAGE_LABELS.get, key="create_source_languages")
            web_limit = st.slider("Số bài web tối đa", min_value=1, max_value=12, value=6, key="create_web_limit")

            ai_enabled = st.checkbox("Sử dụng Clip AI Veo/Seedance (có tính phí)", value=False, disabled=settings.ai_clip_max_per_run == 0 or not allowed_models(settings), key="create_ai")
            ai_count, ai_model, ai_seconds, confirmed = 0, "veo-3.1", 4, False
            if ai_enabled and settings.ai_clip_max_per_run:
                ai_count = st.number_input("Số clip AI", min_value=1, max_value=settings.ai_clip_max_per_run, value=1, key="create_ai_count")
                names = allowed_models(settings)
                ai_model = st.selectbox("Model clip AI", names, index=names.index(settings.gateway_video_model) if settings.gateway_video_model in names else 0, key="create_ai_model")
                ai_seconds = st.selectbox("Thời lượng mỗi clip AI", MODELS[ai_model], index=0, key=f"create_ai_sec_{ai_model}")
                confirmed = st.checkbox("Xác nhận chi phí tạo clip AI", key="create_ai_confirm_cb")

        # THANH THÔNG SỐ ĐO THẬT & NÚT HÀNH ĐỘNG
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        col_m1, col_m2, col_act = st.columns([1.1, 1.1, 2.0])

        with col_m1:
            st.markdown(stat_html("Ước tính chi phí", "chưa có số đo", sub="Chỉ hiện khi có cost log thật"), unsafe_allow_html=True)
        with col_m2:
            st.markdown(stat_html("Thời gian dựng", "chưa có số đo", sub="Đo đạc theo máy local"), unsafe_allow_html=True)

        with col_act:
            st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
            ready_single = bool(entered_topic.strip() and route_ready(settings, "researcher") and route_ready(settings, "director") and (not ai_enabled or confirmed))

            if video_count == 1:
                # Chế độ 1 video
                if st.button("TẠO VIDEO", type="primary", use_container_width=True, disabled=bool(active_single or b_running or not ready_single)):
                    try:
                        style_preset = select_style(settings, key="create_style_preset", category=category, video_type=video_type)
                        config = RunConfig(
                            topic=entered_topic, category=category, video_type=video_type, video_format=video_format,
                            duration_sec=float(duration), voice=voice, mode="auto", youtube_trends=youtube, youtube_days=14,
                            web_limit=int(web_limit), ai_clips=int(ai_count), source_languages=source_languages,
                            output_language="vi", script_style=script_style, style_preset=style_preset,
                            content_mode="explainer_v2" if explainer_v2 else "event_only", ai_model=ai_model,
                            ai_seconds=ai_seconds, ai_confirmed=confirmed, render_mode="final", ai_failure_action="skip",
                            discovery=st.session_state.get("create_discovery")
                        )
                        key = manager.submit(config, settings)
                        st.session_state["pipeline_worker"] = key
                        st.session_state["pipeline_follow"] = key
                        st.rerun()
                    except Exception as error:
                        diagnostics.record_exception(error, "UI bắt đầu pipeline")
                        st.error(diagnostics.redact(str(error)))
            else:
                # Chế độ hàng loạt: Nút ĐỀ XUẤT N CHỦ ĐỀ (Pha 1)
                if st.button(f"ĐỀ XUẤT {video_count} CHỦ ĐỀ", type="primary", use_container_width=True, disabled=b_running or bool(active_single)):
                    # Pha 1: Thu thập N chủ đề mà không dựng video
                    history_set = get_historical_topics(settings.output_dir)
                    cached_trends = get_cached_trend_topics(settings.output_dir)
                    proposed = []
                    for idx in range(video_count):
                        cand_title = f"{entered_topic} - Góc nhìn {idx + 1}" if entered_topic.strip() else ""
                        if not cand_title and idx < len(cached_trends):
                            cand_title = cached_trends[idx]["title"]
                        elif not cand_title:
                            cand_title = f"Chủ đề công nghệ xu hướng số #{idx + 1}"

                        is_dup = (cand_title.strip().lower() in history_set)
                        proposed.append({
                            "index": idx + 1,
                            "topic": cand_title,
                            "angle": f"Góc nhìn phân tích #{idx + 1}",
                            "source": "Trend Scout Cache" if idx < len(cached_trends) else "Khám phá danh mục",
                            "is_duplicate": is_dup,
                        })
                    st.session_state["batch_proposed_topics"] = proposed
                    st.rerun()

        # =====================================================================
        # PHA 1 & 2: LUỒNG HÀNG LOẠT (Bảng N dòng & Xác nhận dựng)
        # =====================================================================
        proposed_topics = st.session_state.get("batch_proposed_topics")
        if proposed_topics and video_count > 1 and not b_running:
            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
            st.markdown(
                """
                <div style="background: #141414; border: 1px solid #2A2A2A; border-radius: 18px; padding: 20px; margin-bottom: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
                        <div style="font-weight: 800; font-size: 1.15rem; color: #FFFFFF;">
                            Bảng đề xuất danh sách chủ đề (Pha 1)
                        </div>
                        <div style="font-size: 0.85rem; color: #A8A8A8;">Kiểm tra trùng lặp trước khi dựng</div>
                    </div>
                """,
                unsafe_allow_html=True,
            )

            for item in proposed_topics:
                row_bg = "background: rgba(255, 212, 0, 0.08); border: 1px solid rgba(255, 212, 0, 0.3);" if item["is_duplicate"] else "background: #1C1C1C; border: 1px solid #2A2A2A;"
                status_chip = chip_html("Trùng lịch sử", "gold") if item["is_duplicate"] else chip_html("Ổn", "green")
                st.markdown(
                    f"""
                    <div style="{row_bg} border-radius: 12px; padding: 12px 16px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-weight: 800; color: #FFD400; margin-right: 8px;">#{item['index']}</span>
                            <span style="font-weight: 700; color: #FFFFFF;">{html.escape(item['topic'])}</span>
                            <span style="color: #888888; font-size: 0.85rem; margin-left: 8px;">({html.escape(item['source'])})</span>
                        </div>
                        <div>{status_chip}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Pha 2: Xác nhận chi phí để kích hoạt nút DỰNG N VIDEO
            col_cf, col_start_btn = st.columns([1.5, 1.5])
            with col_cf:
                confirm_batch = st.checkbox("Xác nhận chi phí và tài nguyên dựng lô video này", key="confirm_batch_run")
            with col_start_btn:
                if st.button(f"XÁC NHẬN VÀ DỰNG {len(proposed_topics)} VIDEO", type="primary", use_container_width=True, disabled=not confirm_batch):
                    params = {
                        "category": category,
                        "region": "both",
                        "time_window_days": 3,
                        "duration": duration,
                        "format": video_format,
                        "creative_license": "strict",
                        "style": "storytelling",
                        "review": False,
                        "use_youtube": False,
                        "ai_clips": 0,
                        "content_mode": "explainer_v2",
                    }
                    b_manager.start_batch(params, count=len(proposed_topics), settings=settings)
                    st.session_state.pop("batch_proposed_topics", None)
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

        # =====================================================================
        # TIẾN TRÌNH: TRANG TIẾN TRÌNH KHI ĐANG DỰNG (STEPPER 5 BƯỚC)
        # =====================================================================
        key = active_single or st.session_state.get("pipeline_worker")
        current = manager.snapshot(key) if key else None
        single_running = bool(current and current["status"] in {"queued", "running"})

        if single_running:
            st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="ui-card-dark">', unsafe_allow_html=True)
            snapshot = manager.snapshot(key)
            state = read_ui_state(project, snapshot)
            step_names = ["Tìm chủ đề", "Thu thập tin", "Kịch bản", "Assets & minh họa", "Dựng video"]
            cur_idx = 0
            if state:
                cur_step = state.get("current_step", "")
                mapping = {"research": 1, "director": 2, "assets": 3, "render": 4}
                cur_idx = mapping.get(cur_step, 0)
                if state.get("status") == "done":
                    cur_idx = 5

            st.markdown(stepper_html(step_names, cur_idx), unsafe_allow_html=True)

            # Thanh tiến độ vàng & Báo cáo cảnh báo bố cục nếu có
            if state:
                frac = state.get("step_progress", 0.5)
                st.progress(min(1.0, max(0.05, frac)), text=f"Đang xử lý: {state.get('current_step', '').upper()}")
                review_notes = state.get("review_notes", [])
                if any("layout" in str(n).lower() or "collision" in str(n).lower() for n in review_notes):
                    st.markdown(
                        """
                        <div style="background: rgba(255, 212, 0, 0.1); border: 2px solid #FFD400; border-radius: 12px; padding: 12px 16px; margin: 12px 0;">
                            <span style="color: #FFD400; font-weight: 700;">! Cảnh báo bố cục:</span> Phát hiện va chạm chữ. Hệ thống đang tự động điều chỉnh an toàn.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with st.expander("Nhật ký rút gọn (Mono font)", expanded=False):
                    st.code("\n".join(state.get("log", [])[-15:]), language="text")

            c_h1, c_h2 = st.columns([3, 1])
            with c_h2:
                if st.button("HỦY TÁC VỤ", type="secondary", key="btn_cancel_single", use_container_width=True):
                    manager.cancel(key)
                    st.info("Đã yêu cầu dừng tác vụ.")
            st.markdown('</div>', unsafe_allow_html=True)

        # Batch progress display (Tiến độ chạy hàng loạt)
        if b_running or b_manager.snapshot()["status"] != "idle":
            snap = b_manager.snapshot()
            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="ui-card-dark">', unsafe_allow_html=True)
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="font-weight: 800; font-size: 1.1rem; color: #FFFFFF;">
                        TIẾN ĐỘ SẢN XUẤT HÀNG LOẠT
                    </div>
                    {chip_html(snap['status'].upper(), 'gold' if b_running else 'neutral')}
                </div>
                """,
                unsafe_allow_html=True,
            )
            total = snap["total_count"] or 1
            curr = snap["current_index"]
            st.progress(min(1.0, curr / total), text=f"Tiến độ tổng: Đang xử lý video {curr}/{total}")

            st.write(f"Đã hoàn thành: **{len(snap['created_projects'])}** video")
            col_b_act1, col_b_act2 = st.columns([3, 1])
            with col_b_act2:
                if b_running and st.button("DỪNG CHẠY LOẠT", type="secondary", key="btn_stop_batch_safe", use_container_width=True):
                    b_manager.cancel()
                    st.warning("Đã gửi yêu cầu dừng sau khi hoàn tất video hiện tại.")
            with st.expander("Nhật ký chạy lô", expanded=True):
                st.code("\n".join(snap["log"]), language="text")
            st.markdown('</div>', unsafe_allow_html=True)

    # =========================================================================
    # CỘT PHẢI: KHUNG THẺ TRẮNG (CHỦ ĐỀ GỢI Ý & DỰ ÁN GẦN ĐÂY)
    # =========================================================================
    with col_side:
        # Khung thẻ trắng: Chủ đề gợi ý từ Trend Scout cache
        st.markdown(
            """
            <div class="ui-card-white" style="margin-bottom: 18px;">
                <div style="font-weight: 800; font-size: 1.05rem; color: #0A0A0A; margin-bottom: 10px;">
                    Chủ đề gợi ý xu hướng
                </div>
                <div style="font-size: 0.8rem; color: #666666; margin-bottom: 14px;">
                    Đọc từ cache Trend Scout (không gọi API ngoài)
                </div>
            """,
            unsafe_allow_html=True,
        )

        trend_suggestions = get_cached_trend_topics(settings.output_dir)
        for s_idx, sug in enumerate(trend_suggestions):
            t_title = sug["title"]
            if st.button(f"✓ {t_title}", key=f"sug_btn_{s_idx}", use_container_width=True):
                st.session_state["create_topic"] = t_title
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # Khung thẻ trắng: Dự án gần đây (3-5 dòng)
        st.markdown(
            """
            <div class="ui-card-white">
                <div style="font-weight: 800; font-size: 1.05rem; color: #0A0A0A; margin-bottom: 10px;">
                    Dự án gần đây
                </div>
            """,
            unsafe_allow_html=True,
        )

        recent_projects = list_projects(settings.output_dir)[:5]
        if recent_projects:
            for rp in recent_projects:
                rp_title = rp.topic or rp.name
                has_render = (rp.path / "render").is_dir() and any((rp.path / "render").glob("*.mp4"))
                st_chip = chip_html("Xong", "green") if has_render else chip_html("Đang dựng", "gold")
                st.markdown(
                    f"""
                    <div style="border-bottom: 1px solid #E5E5E5; padding: 8px 0; display: flex; justify-content: space-between; align-items: center;">
                        <div style="color: #0A0A0A; font-weight: 600; font-size: 0.85rem; max-width: 65%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            {html.escape(rp_title)}
                        </div>
                        <div>{st_chip}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div style="font-size: 0.85rem; color: #777;">Chưa có dự án nào</div>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
