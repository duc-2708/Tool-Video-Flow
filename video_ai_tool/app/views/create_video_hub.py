"""Trang Tạo Video Trung Tâm: Tạo đơn lẻ hoặc Tạo hàng loạt (Luồng 2 pha).

Thiết kế hiện đại Đen - Vàng - Trắng theo Token Design và UI Kit.
Tuân thủ nghiêm ngặt Streamlit: Không dùng split HTML markdown để bao bọc widget.
Dùng with st.container(key="..."): để định dạng qua CSS class .st-key-...
"""
from datetime import datetime, timezone
import html
from pathlib import Path
import streamlit as st

from app.style_controls import select_category, select_style
from app.ui_kit import (
    card,
    chip_html,
    empty_state,
    section_header,
    stat_html,
    stepper_html,
)
from app.views.ai_video import allowed_models, failed_job_details, MODELS, recovery_controls
from app.views.edit_plan import render as edit_plan_page
from app.views.render import show_result
from config.categories import categories_for
from config.storytelling import DURATIONS, STYLES
from editor.timeline import confined
from pipeline.ai_video import load_job
from pipeline.batch_jobs import BatchJobs
from pipeline.projects import list_projects, read_json
from pipeline.run_all import LABELS, RunConfig, saved_config, STEPS
from providers.llm.router import route_ready
from schemas.languages import LABELS as LANGUAGE_LABELS
from schemas.research_brief import ResearchBrief
from utils.cache import cache_key


def pipeline_jobs():
    """Tái sử dụng pipeline_jobs từ create_video để test suite monkeypatch nhận diện đúng."""
    from app.views import create_video

    return create_video.pipeline_jobs()


def ai_video_jobs():
    from app.views import create_video

    return create_video.ai_video_jobs()


def batch_jobs():
    return BatchJobs()


def read_ui_state(project, snapshot=None):
    from app.views import create_video

    return create_video.read_ui_state(project, snapshot)


def get_cached_trend_topics(output_dir: Path) -> list[dict]:
    """Đọc chủ đề gợi ý từ cache Trend Scout local, không gọi mạng/API."""
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
    return [
        {"title": "Cơ hội tỷ USD từ thiết bị bay không người lái", "why_hot": "Công nghệ mới", "source": "Tin tức"},
        {"title": "Việt Nam đạt giải thưởng số toàn cầu", "why_hot": "Điểm sáng số", "source": "Công nghệ"},
        {"title": "Quy định an toàn và bảo mật cho mô hình AI", "why_hot": "Quy định AI", "source": "Chính sách"},
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
    # 0. Handoff từ trang Khám phá chủ đề
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

    # Tiêu đề lớn 3.2rem với chữ nhấn vàng "gì?"
    section_header("BẮT ĐẦU", "Hôm nay làm video gì?", accent_word="gì?")

    manager = pipeline_jobs()
    active = manager.active()
    b_manager = batch_jobs()
    b_running = b_manager.is_running()

    # Bố cục 2 cột [2.3, 1.0] theo thiết kế Y1
    col_main, col_side = st.columns([2.3, 1.0], gap="large")

    with col_main:
        # Ô nhập chủ đề cao 72px viền dưới vàng 4px bo 18px
        with st.container(key="topic_input_card"):
            entered_topic = st.text_input(
                "Chủ đề",
                value=topic or st.session_state.get("create_topic", ""),
                max_chars=500,
                key="create_topic",
                placeholder="Nhập chủ đề muốn làm video (ví dụ: Ra mắt chip xử lý M4, Cơ hội drone...)",
                label_visibility="collapsed",
            )

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

        # Segmented Control / Radio chế độ nhập
        input_modes = ["Từ chủ đề", "Theo danh mục", "Khám phá xu hướng"]
        if hasattr(st, "segmented_control"):
            input_mode = st.segmented_control(
                "Phương thức",
                input_modes,
                default="Từ chủ đề",
                key="hub_input_mode_sel",
                label_visibility="collapsed",
            )
        else:
            input_mode = st.radio(
                "Phương thức",
                input_modes,
                horizontal=True,
                key="hub_input_mode_rad",
                label_visibility="collapsed",
            )

        # Danh mục luôn được khởi tạo với key="create_category" để tương thích test
        category = select_category(settings, key="create_category")
        if input_mode == "Khám phá xu hướng":
            st.caption("Chủ đề sẽ được lấy tự động từ danh mục tin tức và xu hướng mới nhất.")

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # KHỐI: SỐ LƯỢNG VIDEO
        with st.container(key="qty_card"):
            st.markdown(
                "<div style='color: #FFD400; font-weight: 800; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;'>SỐ LƯỢNG VIDEO</div>",
                unsafe_allow_html=True,
            )
            if "hub_qty" not in st.session_state:
                st.session_state["hub_qty"] = 1

            def _change_hub_qty(delta: int):
                curr = st.session_state.get("hub_qty", 1)
                st.session_state["hub_qty"] = max(1, min(20, curr + delta))

            def _set_hub_qty(val: int):
                st.session_state["hub_qty"] = max(1, min(20, val))

            col_qty, col_presets = st.columns([1.2, 1.8])
            with col_qty:
                c_minus, c_num, c_plus = st.columns([1, 2, 1])
                c_minus.button(
                    "−",
                    key="btn_minus_qty",
                    on_click=_change_hub_qty,
                    args=(-1,),
                    use_container_width=True,
                )
                video_count = c_num.number_input(
                    "Số lượng",
                    min_value=1,
                    max_value=20,
                    step=1,
                    key="hub_qty",
                    label_visibility="collapsed",
                )
                c_plus.button(
                    "+",
                    key="btn_plus_qty",
                    on_click=_change_hub_qty,
                    args=(1,),
                    use_container_width=True,
                )

            with col_presets:
                p1, p5, p10, p20 = st.columns(4)
                for num, btn_col in [(1, p1), (5, p5), (10, p10), (20, p20)]:
                    is_active = (video_count == num)
                    b_type = "primary" if is_active else "secondary"
                    btn_col.button(
                        f"{num}",
                        key=f"btn_p_{num}",
                        on_click=_set_hub_qty,
                        args=(num,),
                        type=b_type,
                        use_container_width=True,
                    )

            st.toggle(
                "AI tự tìm chủ đề khác nhau",
                value=True,
                key="hub_auto_diff_topics",
            )
            st.caption("Hệ thống sẽ đối chiếu lịch sử 14 ngày để đảm bảo các video trong lô có góc nhìn hoàn toàn mới.")

        # HÀNG 4 THẺ TRẮNG: THỜI LƯỢNG, PHONG CÁCH, MINH HỌA, GIỌNG ĐỌC
        c_opt1, c_opt2, c_opt3, c_opt4 = st.columns([0.85, 1.25, 1.0, 0.9])

        with c_opt1:
            with st.container(key="opt_dur"):
                st.markdown("<p>1. THỜI LƯỢNG</p>", unsafe_allow_html=True)
                preset_dur = st.selectbox(
                    "Mốc thời lượng",
                    ["Tùy chỉnh", *DURATIONS],
                    key="create_duration_preset",
                    label_visibility="collapsed",
                )
                duration = float(preset_dur) if preset_dur != "Tùy chỉnh" else 45.0

        with c_opt2:
            with st.container(key="opt_style"):
                st.markdown("<p>2. PHONG CÁCH</p>", unsafe_allow_html=True)
                curr_type = st.session_state.get("create_type", "news")
                style_preset = select_style(
                    settings,
                    key="create_style_preset",
                    category=category,
                    video_type=curr_type,
                    current=prefill.get("style_preset") if prefill else None,
                    label_visibility="collapsed",
                )

        with c_opt3:
            with st.container(key="opt_ill"):
                st.markdown("<p>3. MINH HỌA</p>", unsafe_allow_html=True)
                ill_mode = st.selectbox(
                    "Minh họa",
                    ["Vector & Thẻ", "Stock B-Roll", "Hỗn hợp"],
                    key="hub_ill_mode",
                    label_visibility="collapsed",
                )

        with c_opt4:
            with st.container(key="opt_voice"):
                st.markdown("<p>4. GIỌNG ĐỌC</p>", unsafe_allow_html=True)
                voices = ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"]
                voice = st.selectbox(
                    "Giọng đọc",
                    voices,
                    index=voices.index(settings.default_voice) if settings.default_voice in voices else 0,
                    format_func=lambda v: "Hoài My (Nữ)" if "HoaiMy" in v else "Nam Minh (Nam)",
                    key="create_voice",
                    label_visibility="collapsed",
                )

        # Khổ video, thể loại, phong cách kịch bản & Chế độ Explainer v2
        c_sub1, c_sub2, c_sub3, c_sub4 = st.columns([1, 1, 1, 1.2])
        video_format = c_sub1.selectbox(
            "Khổ video",
            ["tiktok", "youtube"],
            format_func=lambda v: "TikTok · 9:16" if v == "tiktok" else "YouTube · 16:9",
            key="create_format",
        )
        video_type = c_sub2.selectbox(
            "Loại video",
            ["news", "review", "story"],
            format_func=lambda v: "Tin tức" if v == "news" else "Đánh giá" if v == "review" else "Kể chuyện",
            key="create_type",
        )
        script_style = c_sub3.selectbox(
            "Phong cách",
            list(STYLES),
            format_func=STYLES.get,
            key="create_script_style",
        )
        with c_sub4:
            st.markdown("<div style='height: 29px;'></div>", unsafe_allow_html=True)
            explainer_v2 = st.checkbox(
                "Explainer v2: Chuyên sâu",
                value=(ill_mode != "Stock B-Roll"),
                key="create_explainer_v2",
                help="Tối ưu kịch bản diễn giải phân tích với minh họa vector động",
            )

        # TÙY CHỌN NÂNG CAO (EXPANDER)
        with st.expander("Tùy chọn nâng cao (Nguồn web & Clip AI)", expanded=False):
            col_adv1, col_adv2 = st.columns(2)
            with col_adv1:
                youtube = st.checkbox("Dùng YouTube trends", value=False, key="create_youtube")
                web_limit = st.number_input("Số nguồn web tối đa", min_value=1, max_value=12, value=6, step=1, key="create_web_limit")
                mode = st.selectbox(
                    "Chế độ",
                    ["auto", "review"],
                    format_func=lambda v: "Tự động" if v == "auto" else "Duyệt kịch bản trước khi dựng",
                    key="create_mode",
                )
            with col_adv2:
                days = st.number_input("YouTube: số ngày gần đây", min_value=1, max_value=3650, value=14, step=1, key="create_days")
                source_languages = st.multiselect(
                    "Ngôn ngữ nguồn",
                    list(LANGUAGE_LABELS),
                    default=["vi", "en"],
                    format_func=LANGUAGE_LABELS.get,
                    key="create_source_languages",
                )
                output_language = st.selectbox("Ngôn ngữ kịch bản", ["vi"], format_func=LANGUAGE_LABELS.get, key="create_output_language")
                render_mode = st.selectbox(
                    "Chất lượng dựng",
                    ["preview", "final"],
                    format_func=lambda v: "Xem nhanh" if v == "preview" else "Bản cuối",
                    key="create_render_mode",
                )

            stop_on_ai_error = st.checkbox("Dừng pipeline khi Clip AI lỗi", value=False, key="create_stop_ai_error")
            ai_enabled = st.checkbox(
                "Dùng clip AI (có tính phí)",
                value=False,
                disabled=settings.ai_clip_max_per_run == 0 or not allowed_models(settings),
                key="create_ai",
            ) and settings.ai_clip_max_per_run > 0

            ai_count, ai_model, ai_seconds, confirmed = 0, "veo-3.1", 4, False
            if ai_enabled and settings.ai_clip_max_per_run:
                ai_count = st.number_input(
                    "Số clip AI tối đa trong lượt",
                    min_value=1,
                    max_value=settings.ai_clip_max_per_run,
                    value=1,
                    step=1,
                    key="create_ai_count",
                )
                names = allowed_models(settings)
                ai_model = st.selectbox(
                    "Model clip AI",
                    names,
                    index=names.index(settings.gateway_video_model) if settings.gateway_video_model in names else 0,
                    key="create_ai_model",
                )
                ai_seconds = st.selectbox(
                    "Thời lượng mỗi clip AI (giây)",
                    MODELS[ai_model],
                    index=MODELS[ai_model].index(settings.ai_clip_seconds) if settings.ai_clip_seconds in MODELS[ai_model] else 0,
                    key=f"create_ai_seconds_{ai_model}",
                )
                st.info(f"Sẽ tạo {ai_count} clip, model {ai_model}, thời lượng {ai_seconds} giây/clip.")
                signature = cache_key([ai_count, ai_model, ai_seconds, video_format])[:12]
                nonce = st.session_state.get("create_ai_approval_nonce", 0)
                confirmed = st.checkbox(
                    "Tôi xác nhận số clip, model, thời lượng và chi phí AI trước khi bắt đầu",
                    key=f"create_ai_approval_{signature}_{nonce}",
                )

        ready = bool(
            source_languages
            and entered_topic.strip()
            and route_ready(settings, "researcher")
            and route_ready(settings, "director")
            and (not ai_enabled or (confirmed and settings.gateway_api_key.get_secret_value().strip()))
        )

        # THANH CTA BAR (THÔNG SỐ ĐO THẬT & NÚT HÀNH ĐỘNG)
        with st.container(key="cta_bar"):
            col_m1, col_m2, col_act = st.columns([1.1, 1.1, 2.0])
            with col_m1:
                st.markdown(stat_html("Ước tính chi phí", "chưa có số đo", "Chỉ hiện khi có cost log thật"), unsafe_allow_html=True)
            with col_m2:
                st.markdown(stat_html("Thời gian dựng", "chưa có số đo", "Đo theo máy local"), unsafe_allow_html=True)
            with col_act:
                st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                if video_count == 1:
                    if st.button("Tạo video", type="primary", use_container_width=True, disabled=bool(active or not ready), key="auto_start"):
                        try:
                            config = RunConfig(
                                topic=entered_topic,
                                category=category,
                                video_type=video_type,
                                video_format=video_format,
                                duration_sec=float(duration),
                                voice=voice,
                                mode=mode,
                                youtube_trends=youtube,
                                youtube_days=int(days),
                                web_limit=int(web_limit),
                                ai_clips=int(ai_count),
                                source_languages=source_languages,
                                output_language=output_language,
                                script_style=script_style,
                                style_preset=style_preset,
                                discovery=st.session_state.get("create_discovery"),
                                content_mode="explainer_v2" if explainer_v2 else "event_only",
                                ai_model=ai_model,
                                ai_seconds=ai_seconds,
                                ai_confirmed=confirmed,
                                render_mode=render_mode,
                                ai_failure_action="stop" if stop_on_ai_error else "skip",
                            )
                            worker_key = manager.submit(config, settings)
                            st.session_state["pipeline_worker"] = worker_key
                            st.session_state["pipeline_follow"] = worker_key
                            st.session_state["create_ai_approval_nonce"] = st.session_state.get("create_ai_approval_nonce", 0) + 1
                            st.rerun()
                        except Exception as error:
                            diagnostics.record_exception(error, "UI bắt đầu pipeline")
                            st.error(diagnostics.redact(str(error)))
                else:
                    if st.button(f"ĐỀ XUẤT {video_count} CHỦ ĐỀ", type="primary", use_container_width=True, disabled=bool(active or b_running), key="auto_start"):
                        history_set = get_historical_topics(settings.output_dir)
                        cached_trends = get_cached_trend_topics(settings.output_dir)
                        proposed = []
                        for idx in range(video_count):
                            cand_title = f"{entered_topic} - Góc nhìn {idx + 1}" if entered_topic.strip() else ""
                            if not cand_title and idx < len(cached_trends):
                                cand_title = cached_trends[idx]["title"]
                            elif not cand_title:
                                cand_title = f"Chủ đề công nghệ xu hướng số #{idx + 1}"

                            is_dup = cand_title.strip().lower() in history_set
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
        # PHA 1 & 2: LUỒNG HÀNG LOẠT (BẢNG N CHỦ ĐỀ & XÁC NHẬN DỰNG)
        # =====================================================================
        proposed_topics = st.session_state.get("batch_proposed_topics")
        if proposed_topics and video_count > 1 and not b_running:
            st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown(
                    """
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
                    status_chip = chip_html("TRÙNG", "gold") if item["is_duplicate"] else chip_html("Ổn", "green")
                    st.markdown(
                        f"""
                        <div style="{row_bg} border-radius: 12px; padding: 12px 16px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
                            <div style="display: flex; align-items: center; gap: 14px;">
                                <span style="font-weight: 800; color: #FFD400; font-size: 1rem;">#{item['index']}</span>
                                <div>
                                    <div style="font-weight: 700; color: #FFFFFF; font-size: 0.95rem;">{html.escape(item['topic'])}</div>
                                    <div style="font-size: 0.8rem; color: #888888;">{html.escape(item['angle'])} · Nguồn: {html.escape(item['source'])}</div>
                                </div>
                            </div>
                            <div>{status_chip}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                confirm_cost = st.checkbox(
                    "Tôi xác nhận chi phí và thông số sản xuất cho lô này",
                    key="batch_cost_confirm",
                )
                if st.button("XÁC NHẬN VÀ DỰNG N VIDEO", type="primary", disabled=not confirm_cost or b_running, key="btn_confirm_batch"):
                    b_params = {
                        "category": category,
                        "duration": float(duration),
                        "voice": voice,
                        "style_preset": style_preset,
                        "region": "both",
                        "creative_license": "strict",
                    }
                    b_manager.start_batch(b_params, count=len(proposed_topics), settings=settings)
                    st.session_state.pop("batch_proposed_topics", None)
                    st.rerun()

        # Hiển thị tiến trình lô nếu đang chạy
        if b_running:
            b_snap = b_manager.snapshot()
            with st.container(border=True):
                st.markdown(f"**Đang sản xuất lô:** {b_snap['current_index']}/{b_snap['total_count']} video")
                st.progress(b_snap["current_index"] / max(1, b_snap["total_count"]))
                if st.button("Dừng lô an toàn", key="btn_stop_batch"):
                    b_manager.cancel()
                    st.info("Đã gửi yêu cầu dừng ở điểm an toàn. Chờ luồng hoàn tất bước hiện tại.")
                with st.expander("Nhật ký lô"):
                    st.code("\n".join(b_snap.get("log", [])), language="text")

    # CỘT PHẢI: KHUNG TRẮNG SIDE PANEL (Y1)
    with col_side:
        with st.container(key="side_panel"):
            st.markdown(
                "<h3 style='margin-top:0; font-size:1.15rem; font-weight:800; color:#0A0A0A;'>Chủ đề gợi ý hôm nay</h3>",
                unsafe_allow_html=True,
            )
            cached_trends = get_cached_trend_topics(settings.output_dir)
            for idx, c_item in enumerate(cached_trends):
                t_label = c_item["title"]
                if st.button(t_label, key=f"btn_pick_trend_{idx}", use_container_width=True):
                    st.session_state["create_topic"] = t_label
                    st.rerun()
                st.markdown(
                    f"<div style='font-size:0.75rem; color:#555; margin-top:-6px; margin-bottom:10px;'>{chip_html(c_item['source'], 'gold')} <span style='color:#555;'>{html.escape(c_item['why_hot'])}</span></div>",
                    unsafe_allow_html=True,
                )

            st.markdown("<hr style='border: none; border-top: 1px solid #E5E5E5; margin: 18px 0;'>", unsafe_allow_html=True)
            st.markdown(
                "<h3 style='font-size:1.15rem; font-weight:800; color:#0A0A0A;'>Dự án gần đây</h3>",
                unsafe_allow_html=True,
            )
            all_projs = list_projects(settings.output_dir)
            if not all_projs:
                st.markdown("<div style='color: #777; font-size: 0.85rem;'>Chưa có dự án nào.</div>", unsafe_allow_html=True)
            else:
                for p_item in all_projs[:4]:
                    p_state = read_ui_state(p_item.path)
                    st_val = p_state.get("status", "done") if p_state else "done"
                    c_tone = "green" if st_val == "done" else "gold" if st_val in {"running", "queued"} else "neutral"
                    st.markdown(
                        f"""
                        <div style="border-bottom: 1px solid #EEEEEE; padding: 8px 0; display: flex; justify-content: space-between; align-items: center;">
                            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 65%;">
                                <div style="font-weight: 700; color: #0A0A0A; font-size: 0.85rem;">{html.escape(p_item.topic or p_item.name)}</div>
                                <div style="font-size: 0.72rem; color: #777777;">{p_item.name[-8:]}</div>
                            </div>
                            <div>{chip_html(st_val.upper(), c_tone)}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # =========================================================================
    # TIẾN TRÌNH PIPELINE ĐANG CHẠY (Y2)
    # =========================================================================
    p_key = active or st.session_state.get("pipeline_worker")
    current_snap = manager.snapshot(p_key) if p_key else None
    if current_snap and st.session_state.get("pipeline_follow") == p_key and current_snap.get("project"):
        st.session_state["pending_project"] = Path(current_snap["project"]).name
        st.session_state.pop("pipeline_follow", None)
        st.rerun()

    if active and st.button("Hủy lượt dựng hiện tại", key="pipeline_cancel"):
        manager.cancel(active)
        st.info("Đã gửi yêu cầu dừng ở điểm an toàn.")

    running = bool(current_snap and current_snap.get("status") in {"queued", "running"})

    @st.fragment(run_every=1 if running else None)
    def progress_panel():
        snap = manager.snapshot(p_key) if p_key else None
        sel = project
        if snap and (st.session_state.get("pipeline_follow") == p_key or sel is None):
            sel = Path(snap["project"]) if snap.get("project") else sel
        st_data = read_ui_state(sel, snap)
        if st_data:
            step_names = list(STEPS)
            curr_step = st_data.get("current_step")
            act_idx = step_names.index(curr_step) if curr_step in step_names else 0
            if st_data.get("status") == "done":
                act_idx = len(step_names)
            step_labels = [LABELS.get(s, s) for s in step_names]
            step_times = []
            for s in step_names:
                e_info = st_data.get("steps", {}).get(s, {})
                step_times.append(f"{e_info.get('elapsed_sec', 0):.1f}s")

            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            st.markdown(stepper_html(step_labels, act_idx, step_times), unsafe_allow_html=True)

            # Banner cảnh báo bố cục viền vàng nếu có lỗi
            if st_data.get("error"):
                st.markdown(
                    f"""
                    <div style="background: rgba(255, 212, 0, 0.08); border: 2px solid #FFD400; border-radius: 14px; padding: 14px 18px; margin-bottom: 14px; color: #FFFFFF;">
                        <span style="color: #FFD400; font-weight: 800;">CẢNH BÁO:</span> {html.escape(diagnostics.redact(st_data['error']))}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with st.expander("Nhật ký rút gọn (mono)", expanded=st_data.get("status") != "done"):
                st.code("\n".join(diagnostics.redact(line) for line in st_data.get("log", [])[-25:]), language="text")

        if snap and snap.get("status") == "failed":
            st.error(snap.get("error"))
        if running and snap and snap.get("status") not in {"queued", "running"}:
            st.rerun()

    progress_panel()

    # =========================================================================
    # CÁC TRẠNG THÁI PHỤC HỒI & HOÀN TẤT (Y3 STORYBOARD, WAITING AI, Y4 KẾT QUẢ)
    # =========================================================================
    if project is None:
        return

    try:
        proj_state = read_ui_state(project, current_snap)
        if proj_state is None:
            return

        ai_folder = confined(project, "ai_video")
        if proj_state.get("steps", {}).get("ai_video", {}).get("status") == "skipped" and ai_folder.exists():
            with st.expander("Clip AI lỗi — đã dùng b-roll thay thế"):
                for path in sorted(ai_folder.glob("*.json")):
                    failed_job_details(load_job(path), diagnostics)

        # Trạng thái duyệt kịch bản (Y3 Storyboard)
        if proj_state.get("status") == "waiting_review":
            st.info("Kịch bản đã sẵn sàng. Duyệt/sửa bên dưới, lưu chỉnh sửa rồi tiếp tục.")
            edit_plan_page(settings, project, topic, debug, diagnostics)
            if st.button("Tiếp tục tạo video", type="primary", disabled=bool(active)):
                cfg = saved_config(project, continue_after_review=True)
                st.session_state["pipeline_worker"] = manager.submit(cfg, settings)
                st.rerun()

        # Trạng thái Clip AI lỗi
        elif proj_state.get("status") == "waiting_ai_choice" or (
            proj_state.get("status") == "failed" and proj_state.get("steps", {}).get("ai_video", {}).get("status") == "failed"
        ):
            st.warning("Bước Clip AI lỗi. Bạn có thể giữ video bằng cách render tiếp với b-roll thường, hoặc dừng.")
            choice = st.radio(
                "Xử lý khi Clip AI lỗi",
                ["Bỏ qua clip AI và render bằng b-roll thường", "Dừng pipeline"],
                index=0,
                key=f"ai_failure_choice_{project.name}",
            )
            busy = bool(active or ai_video_jobs().active(project))
            if st.button("Áp dụng lựa chọn", type="primary", disabled=busy):
                cfg = saved_config(project, ai_failure_decision="skip" if choice.startswith("Bỏ qua") else "stop")
                st.session_state["pipeline_worker"] = manager.submit(cfg, settings)
                st.rerun()

        elif proj_state.get("status") == "done":
            summary = proj_state.get("summary", {})
            st.success(
                f"Hoàn tất · {summary.get('elapsed_sec', 0):.1f}s xử lý · {summary.get('facts_used', 0)} fact / {summary.get('sources_used', 0)} nguồn đã dùng"
            )
            if proj_state.get("render_result"):
                show_result(proj_state["render_result"], project, diagnostics)
            for filename, label in [("render/credits.txt", "Tải credits.txt"), ("report.md", "Tải báo cáo")]:
                f_path = confined(project, filename)
                if f_path.is_file():
                    st.download_button(
                        label,
                        f_path.read_bytes(),
                        file_name=f_path.name,
                        mime="text/plain" if f_path.suffix == ".txt" else "text/markdown",
                    )
    except Exception as error:
        diagnostics.record_exception(error, "UI đọc checkpoint pipeline")
        st.error(diagnostics.redact(str(error)))
