"""Render page: background worker, periodic progress, playback and download."""
import html
from pathlib import Path
import streamlit as st
from app.ui_kit import chip_html, section_header, stat_html
from editor.jobs import RenderJobs
from editor.timeline import confined
from pipeline.projects import read_json


@st.cache_resource
def render_jobs():
    return RenderJobs()


def show_result(result, project, diagnostics):
    root = confined(project, "render")
    path = confined(root, Path(result["filename"]).name)
    if not path.is_file():
        st.warning("File MP4 chưa có hoặc đã được di chuyển.")
        return

    # Trích xuất dữ liệu thực tế từ quality_report & brief
    qc = result.get("quality_summary") or {}
    report_data = {}
    if result.get("quality_report"):
        try:
            report_data = read_json(confined(project, Path(result["quality_report"]).name))
        except Exception:
            report_data = {}
    elif (project / "quality_report.json").is_file():
        try:
            report_data = read_json(project / "quality_report.json")
        except Exception:
            report_data = {}

    # 1. Điểm kiểm tra (chỉ hiện khi có dữ liệu thật)
    score_display = "chưa có"
    if "score" in report_data:
        score_display = f"{report_data['score']}/100"
    elif "warning_count" in qc:
        score_display = f"{max(0, 100 - qc['warning_count'] * 10)}/100"

    # 2. % Thời lượng có hình chuyển động (chỉ hiện khi có số liệu thật)
    motion_display = "chưa có"
    cov = qc.get("illustration_coverage_percent") or report_data.get("illustration_coverage_percent")
    if cov is not None:
        motion_display = f"{float(cov):.1f}%"

    # 3. Dữ kiện có nguồn (từ brief.json thật)
    facts_display = "chưa có"
    brief_facts = []
    if (project / "brief.json").is_file():
        try:
            b_info = read_json(project / "brief.json")
            brief_facts = b_info.get("facts", [])
            sourced = len([f for f in brief_facts if f.get("sources") or f.get("source_count", 0) > 0])
            if brief_facts:
                facts_display = f"{sourced}/{len(brief_facts)}"
        except Exception:
            pass

    # Bố cục 2 cột: Trái Video 9:16 + Nút tải/mở, Phải: Metric + Checklist
    col_vid, col_details = st.columns([1.1, 1.9])

    with col_vid:
        st.video(str(path))
        st.download_button(
            "Tải MP4",
            data=path.read_bytes(),
            file_name=path.name,
            mime="video/mp4",
            key=f"download_{path.name}",
            type="primary",
            use_container_width=True,
        )
        c_open, c_rerender = st.columns(2)
        with c_open:
            if st.button("Mở project", key=f"open_proj_{path.name}", use_container_width=True):
                st.session_state["project_choice"] = project.name
                st.session_state["pending_page"] = "Edit Plan"
                st.rerun()
        with c_rerender:
            if st.button("Dựng lại", key=f"rerender_{path.name}", use_container_width=True):
                st.info("Chuyển tới cấu hình để dựng lại.")
                st.session_state["pending_page"] = "Render"
                st.rerun()

        st.caption(
            f"{result['duration_sec']:.2f}s · {result['width']}×{result['height']} · {result['fps']} fps · {path.stat().st_size/1024**2:.2f} MB · Dựng trong {result['render_seconds']:.1f}s"
        )

    with col_details:
        # Ba ô số liệu đo thật
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(stat_html("Điểm kiểm tra", score_display, sub="Chất lượng hoạt họa"), unsafe_allow_html=True)
        with m2:
            st.markdown(stat_html("% Chuyển động", motion_display, sub="Độ phủ minh họa"), unsafe_allow_html=True)
        with m3:
            st.markdown(stat_html("Dữ kiện có nguồn", facts_display, sub="Đối chiếu brief.json"), unsafe_allow_html=True)

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # Checklist ✓ / ! / ✕ từ quality_report / layout_report
        st.markdown('<div class="ui-card-dark" style="padding: 14px 18px; margin-bottom: 12px;">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 0.85rem; font-weight: 800; color: #FFD400; text-transform: uppercase; margin-bottom: 8px;">Tiêu chuẩn kiểm định</div>', unsafe_allow_html=True)

        # 1. Bố cục
        lr_path = project / "layout_report.json"
        if lr_path.is_file():
            try:
                lr_data = read_json(lr_path)
                if lr_data.get("overall_all_passed", True):
                    st.markdown("<div style='color: #4CAF50; font-weight: 600; margin: 4px 0;'>✓ Bố cục: Toàn bộ khung hình đạt chuẩn khoảng an toàn</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='color: #FF5252; font-weight: 600; margin: 4px 0;'>✕ Bố cục: Phát hiện lỗi va chạm hoặc tràn viền sau kiểm định</div>", unsafe_allow_html=True)
            except Exception:
                st.markdown("<div style='color: #FFD400; font-weight: 600; margin: 4px 0;'>! Bố cục: Chưa phân tích được layout_report</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='color: #A8A8A8; font-weight: 600; margin: 4px 0;'>! Bố cục: Không có layout_report.json</div>", unsafe_allow_html=True)

        # 2. Minh họa chuyển động
        if cov is not None:
            if float(cov) >= 85:
                st.markdown(f"<div style='color: #4CAF50; font-weight: 600; margin: 4px 0;'>✓ Minh họa: Đạt độ phủ hoạt họa {float(cov):.1f}% (mục tiêu &gt;= 85%)</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='color: #FFD400; font-weight: 600; margin: 4px 0;'>! Minh họa: Độ phủ hoạt họa {float(cov):.1f}% dưới 85% (có fallback)</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='color: #A8A8A8; font-weight: 600; margin: 4px 0;'>! Minh họa: Chưa có số liệu độ phủ</div>", unsafe_allow_html=True)

        # 3. Dữ kiện nguồn
        if brief_facts:
            st.markdown(f"<div style='color: #4CAF50; font-weight: 600; margin: 4px 0;'>✓ Nguồn tin: Đã đối chiếu {facts_display} sự kiện với nguồn xác thực</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='color: #A8A8A8; font-weight: 600; margin: 4px 0;'>! Nguồn tin: Chưa có thông tin đối chiếu nguồn</div>", unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # Bảng chi phí theo bước chỉ khi có dữ liệu thật
        cost_file = project / "cost_log.json"
        if not cost_file.is_file():
            cost_file = project / "costs.json"
        if cost_file.is_file():
            try:
                cost_data = read_json(cost_file)
                if cost_data:
                    with st.expander("Bảng chi phí theo bước (Dữ liệu đo thật)", expanded=False):
                        if isinstance(cost_data, list):
                            st.dataframe(cost_data, hide_index=True, use_container_width=True)
                        elif isinstance(cost_data, dict):
                            st.json(cost_data)
            except Exception:
                pass

    # Visual Bible expander
    bible_file = project / "visual_bible.json"
    bible_status_file = project / "visual_bible_status.json"
    if bible_file.is_file():
        try:
            b_data = read_json(bible_file)
            b_status = read_json(bible_status_file) if bible_status_file.is_file() else {}
            if b_status.get("fallback_used"):
                st.warning(f"! Visual Bible: Đang dùng quy tắc dự phòng ({b_status.get('reason', '')})")
            with st.expander("Kế hoạch hình ảnh tổng thể (Visual Bible)"):
                worlds_txt = "; ".join(f"{w.get('kind')} ({w.get('reason')})" for w in b_data.get("worlds", []))
                actors_txt = "; ".join(f"{a.get('type')} ({a.get('role')})" for a in b_data.get("persistent_actors", []))
                chaps_txt = " · ".join(f"{ch.get('kicker')}: {ch.get('title')}" for ch in b_data.get("structure", {}).get("chapters", []))
                st.markdown(f"- **Thế giới:** {html.escape(worlds_txt)}")
                st.markdown(f"- **Vật thể xuyên suốt:** {html.escape(actors_txt)}")
                st.markdown(f"- **Cấu trúc:** {html.escape(chaps_txt)}")
                pm = b_data.get("progress_metaphor", {})
                if pm.get("type") != "none":
                    st.markdown(f"- **Tiến độ ẩn dụ:** `{html.escape(pm.get('type', ''))}` ({html.escape(', '.join(pm.get('items', [])))})")
        except Exception:
            pass

    if report_data:
        with st.expander("Báo cáo chất lượng hình ảnh chi tiết"):
            if report_data.get("fallbacks"):
                st.warning("Danh sách cảnh fallback:")
                for fb in report_data["fallbacks"]:
                    st.write(f"- Cảnh {fb.get('scene_id')}: {fb.get('reason')}")
            st.json(report_data)

    sheet = confined(project / "review_frames", Path(result.get("contact_sheet") or "contact_sheet.png").name)
    if sheet.is_file() and result.get("motion_enabled"):
        with st.expander("Khung hình kiểm tra và ghi chú Motion"):
            st.image(str(sheet))
            for note in result.get("review_notes", []):
                st.write(diagnostics.redact(note))
    if result.get("warnings"):
        with st.expander("Các shot dùng fallback / cảnh báo"):
            for warning in result["warnings"]:
                st.write(diagnostics.redact(warning))
    st.caption("Phụ đề dùng timing từ nếu có sidecar hợp lệ; nếu chưa có thì ước lượng theo số ký tự, chưa phải căn chỉnh giọng nói chính xác.")


def render(settings, project, topic, debug, diagnostics):
    section_header("XỬ LÝ", "Render Video", accent_word="Video")
    st.caption("Dựng video từ Assets đã chuẩn bị. Mọi kết quả nằm trong render/; các đầu vào được giữ nguyên.")
    if settings.motion_enabled:
        st.info(f"Motion graphics bật · {settings.motion_fps} fps · scale {settings.motion_scale:g}. Thiếu Playwright/Chromium sẽ dùng đồ họa Pillow. Tiến độ chụp cảnh kèm thời gian còn lại ước tính.")
    if project is None:
        st.info("Chọn một project đã tạo Assets.")
        return
    plan = project / "edit_plan.resolved.json"
    if not plan.is_file():
        st.info("Hãy tạo Assets trước để có edit_plan.resolved.json và audio.")
        return
    manager = render_jobs()
    state_key = f"render_job_{project.name}"
    active = manager.active(project)
    from editor.motion.theme import theme_names
    motion = st.toggle("Bật Motion", value=settings.motion_enabled, disabled=bool(active))
    mascot = st.toggle("Bật mascot hình khối riêng", value=settings.mascot_enabled, disabled=bool(active))
    scenes_on = st.toggle("Bật cảnh minh họa hoạt họa", value=settings.motion_scenes_enabled, disabled=bool(active) or not motion)
    fps = st.selectbox("FPS Motion bản nháp", [24, 30], index=0 if settings.motion_fps == 24 else 1, disabled=bool(active))
    themes = ["auto", *theme_names(settings.root_dir)]
    theme = st.selectbox("Theme Motion", themes, index=themes.index(settings.motion_theme) if settings.motion_theme in themes else 0, disabled=bool(active))
    settings = settings.model_copy(update={"motion_enabled": motion, "mascot_enabled": mascot, "motion_theme": theme, "motion_scenes_enabled": scenes_on, "motion_fps": fps})
    ai_on = st.toggle("Clip AI làm nền (có phí)", value=bool(settings.ai_clips_per_video), disabled=bool(active) or not motion)
    ai_count = 0
    ai_confirmed = False
    if ai_on and motion:
        from pipeline.controlled_ai import estimate
        from pipeline.ai_budget import remaining
        from schemas.assets import ResolvedEditPlan
        try:
            data = ResolvedEditPlan.model_validate(read_json(plan))
            info = estimate(data, settings, count=max(1, settings.ai_clips_per_video))
            ai_count = info["count"]
            st.caption(f"Sẽ dùng tối đa {ai_count} clip hook/cao trào · {info['model']} · {info['seconds']}s · ngân sách còn {remaining(settings)} lượt POST hôm nay.")
            st.warning(f"Tham khảo {info['estimated_vnd_per_job']:,}đ/job; tối đa {info['estimated_vnd_max_with_retry']:,}đ nếu generation_failed phải thử lại. Giá thực xem dashboard. Không retry POST khi timeout/thiếu ID.")
            ai_confirmed = st.checkbox("Tôi xác nhận số clip, model, thời lượng và chi phí dự kiến", disabled=bool(active))
            if not settings.gateway_api_key.get_secret_value().strip():
                ai_confirmed = False
                st.info("Thiếu GATEWAY_API_KEY; dùng gradient hoặc điền key bằng editor.")
        except (OSError, ValueError) as error:
            st.warning(diagnostics.redact(str(error)))
    settings = settings.model_copy(update={"ai_clips_per_video": ai_count if ai_on else 0})
    try:
        scene_ids = [scene["id"] for scene in read_json(plan)["scenes"]]
    except (OSError, ValueError, KeyError):
        scene_ids = []
    if scene_ids:
        with st.expander("Xem trước / render lại một cảnh"):
            scene_id = st.selectbox("Cảnh", scene_ids)
            a, b = st.columns(2)
            preview_settings = settings.model_copy(update={"motion_scale": 0.5})
            if a.button("Xem trước cảnh", disabled=bool(active)):
                st.session_state[state_key] = manager.submit(plan, "preview", preview_settings, diagnostics.secrets, scene_id=scene_id)
                st.rerun()
            if b.button("Render lại chỉ cảnh này", disabled=bool(active)):
                st.session_state[state_key] = manager.submit(plan, "preview", preview_settings, diagnostics.secrets, scene_id=scene_id, force_scene=scene_id)
                st.rerun()
    left, right = st.columns(2)
    for column, label, mode in [(left, "Render xem nhanh", "preview"), (right, "Render bản cuối", "final")]:
        if column.button(label, disabled=bool(active) or bool(ai_count and not ai_confirmed), width="stretch"):
            options = {"ai_background_count": ai_count, "ai_confirmed": True} if ai_count else {}
            st.session_state[state_key] = manager.submit(plan, mode, settings, diagnostics.secrets, **options)
            st.rerun()
    job_id = st.session_state.get(state_key) or active
    job = manager.snapshot(job_id) if job_id else None
    running = bool(job and job["status"] in {"queued", "running"})

    @st.fragment(run_every=1 if running else None)
    def progress_panel():
        current = manager.snapshot(job_id) if job_id else None
        if not current:
            return
        st.progress(current["progress"], text=current["message"])
        if current["status"] == "failed":
            st.error("Render thất bại: " + current["error"])
            if debug:
                with st.expander("Traceback gốc (đã che thông tin nhạy cảm)"):
                    st.code(current["traceback"], language="text")
        elif current["status"] == "complete":
            st.success("Render hoàn tất. Có thể xem và tải MP4 bên dưới.")
            if current.get("result", {}).get("scene_id") is not None:
                show_result(current["result"], project, diagnostics)
        if running and current["status"] in {"complete", "failed"}:
            st.rerun()

    progress_panel()
    for mode, label in [("preview", "Bản xem nhanh"), ("final", "Bản cuối")]:
        report_path = project / "render" / f"{mode}.json"
        if report_path.is_file():
            try:
                result = read_json(confined(project / "render", f"{mode}.json"))
                st.subheader(label)
                show_result(result, project, diagnostics)
            except Exception as error:
                diagnostics.record_exception(error, "Đọc kết quả Render trên UI")
                st.error("Không đọc được kết quả Render: " + diagnostics.redact(str(error)))
