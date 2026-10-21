# file: app/views/assets.py
"""UI Assets: tiến độ theo cảnh, nghe giọng, preview stock và tìm lại từng shot."""
from pathlib import Path
import streamlit as st
from app.ui_errors import error_details
from config.settings import Settings
from pipeline.assets import load_assets, refresh_shot, run_assets, safe_asset_path
from pipeline.stock_assets import allowed_media_url
from utils.diagnostics import Diagnostics


def report(error: BaseException, project: Path, diagnostics: Diagnostics) -> None:
    diagnostics.record_exception(error, "Streamlit Assets")
    message, trace = error_details(error, diagnostics)
    st.session_state["assets_error"] = {"project": project.name, "message": message, "trace": trace}


def show_error(project: Path, debug: bool) -> None:
    error = st.session_state.get("assets_error")
    if error and error["project"] == project.name:
        st.error(error["message"])
        if debug:
            with st.expander("Traceback Assets (đã che credentials)"):
                st.code(error["trace"], language="text")
        st.caption("Chi tiết: logs/assets_errors.log.")


def render(settings: Settings, project: Path | None, topic: str, debug: bool, diagnostics: Diagnostics) -> None:
    st.title("Assets")
    st.caption("Giọng đọc và b-roll theo từng cảnh. Không ghi đè Edit Plan gốc; chưa render video.")
    if project is None or not (project / "edit_plan.json").exists():
        st.info("Chọn project có edit_plan.json hoặc tạo kế hoạch tại trang Edit Plan trước.")
        return
    diagnostics = Diagnostics(settings.logs_dir, filename="assets_errors.log", secrets=diagnostics.secrets)
    plan_path = project / "edit_plan.json"
    notice = st.session_state.pop("assets_notice", None)
    if notice and notice["project"] == project.name:
        st.success(notice["message"])
    if not settings.pixabay_api_key.get_secret_value().strip():
        st.info("Chưa có PIXABAY_API_KEY. Có thể tiếp tục tạo giọng và dùng stock tùy chọn/nền màu fallback.")
    if st.button("Tạo Assets", type="primary"):
        st.session_state.pop("assets_error", None)
        progress = st.progress(0.0, text="Chuẩn bị Assets…")
        try:
            with st.spinner("Đang tạo audio và tìm b-roll…"):
                run_assets(plan_path, settings, progress=lambda done, total, message:
                           progress.progress(done / total, text=diagnostics.redact(message)))
            st.session_state["assets_notice"] = {"project": project.name, "message": "Đã lưu Assets, resolved plan và credits. Xem cảnh báo/fallback bên dưới."}
            st.rerun()
        except Exception as error:
            report(error, project, diagnostics)
        finally:
            progress.empty()
    show_error(project, debug)
    if not (project / "assets.json").exists():
        st.info("Chưa có Assets. Nhấn Tạo Assets để bắt đầu.")
        return
    try:
        original, resolved, manifest = load_assets(plan_path)
    except Exception as error:
        report(error, project, diagnostics)
        show_error(project, debug)
        return
    completed = sum(scene.audio_path is not None for scene in manifest.scenes)
    fallbacks = sum(shot.fallback for scene in manifest.scenes for shot in scene.shots)
    columns = st.columns(3)
    columns[0].metric("Audio đã tạo", f"{completed}/{len(manifest.scenes)} cảnh")
    columns[1].metric("Thời lượng resolved", f"{resolved.duration_sec:.2f} giây")
    columns[2].metric("Shot fallback", str(fallbacks))
    if manifest.status == "partial":
        st.warning("Một số cảnh chưa có audio. Nhấn Tạo Assets để thử lại; các audio/cache đã thành công được tái sử dụng.")
    for warning in manifest.warnings:
        st.warning(diagnostics.redact(warning))
    st.dataframe([{"Cảnh": scene.scene_id, "Audio (giây)": scene.audio_duration_sec,
                   "Trạng thái giọng": "Đã có" if scene.audio_path else "Cần thử lại",
                   "Số shot": len(scene.shots), "Fallback": sum(shot.fallback for shot in scene.shots)}
                  for scene in manifest.scenes], hide_index=True)
    selected = st.selectbox("Cảnh để nghe và xem b-roll", [scene.scene_id for scene in manifest.scenes],
                            format_func=lambda value: f"Cảnh {value}")
    scene_assets = next(scene for scene in manifest.scenes if scene.scene_id == selected)
    scene_plan = next(scene for scene in resolved.scenes if scene.id == selected)
    st.subheader(f"Cảnh {selected} · {scene_plan.role}")
    st.write(diagnostics.redact(scene_plan.narration))
    if scene_assets.audio_path:
        try:
            audio = safe_asset_path(project, scene_assets.audio_path)
            st.audio(str(audio), format="audio/mp3")
        except Exception as error:
            report(error, project, diagnostics)
            show_error(project, debug)
    elif scene_assets.audio_error:
        st.error(diagnostics.redact(scene_assets.audio_error))
    for asset in scene_assets.shots:
        shot = dict(enumerate(scene_plan.shots, 1)).get(asset.shot_id)
        if shot is None:
            st.warning(f"Không tìm thấy shot {asset.shot_id} trong cảnh {scene_plan.id}; hãy tạo lại Assets.")
            continue
        with st.expander(f"Shot {asset.shot_id} · {shot.duration_sec:.2f}s · {asset.media_type}" + (" · FALLBACK" if asset.fallback else ""), expanded=True):
            if asset.fallback:
                st.warning(diagnostics.redact(asset.fallback_reason or "Đã dùng tài nguyên fallback."))
            try:
                media = safe_asset_path(project, asset.path)
                if asset.media_type == "video":
                    st.video(str(media))
                else:
                    st.image(str(media), width=360)
            except Exception as error:
                report(error, project, diagnostics)
                show_error(project, debug)
            if asset.author:
                st.caption(diagnostics.redact(f"{asset.provider.title()} · Tác giả: {asset.author}"))
            else:
                st.caption("Nền màu và chữ tạo bằng code.")
            if asset.source_url and allowed_media_url(asset.source_url, asset.provider, source=True):
                st.link_button("Mở nguồn stock", diagnostics.redact(asset.source_url))
            with st.form(f"assets_shot_{project.name}_{selected}_{asset.shot_id}_{manifest.resolved_plan_hash[:10]}"):
                query = st.text_input("Từ khóa b-roll (2–4 từ tiếng Anh)", diagnostics.redact(asset.query))
                refresh = st.form_submit_button("Tìm lại clip cho shot này")
            if refresh:
                st.session_state.pop("assets_error", None)
                try:
                    with st.spinner(f"Đang tìm lại cảnh {selected}, shot {asset.shot_id}…"):
                        refresh_shot(plan_path, settings, selected, asset.shot_id, query)
                    st.session_state["assets_notice"] = {"project": project.name, "message": f"Đã cập nhật riêng cảnh {selected}, shot {asset.shot_id}. Audio và các shot khác được giữ nguyên."}
                    st.rerun()
                except Exception as error:
                    report(error, project, diagnostics)
                    st.rerun()
    if (project / "credits.txt").is_file() and not (project / "credits.txt").is_symlink():
        with st.expander("Credits đang dùng"):
            st.text(diagnostics.redact((project / "credits.txt").read_text(encoding="utf-8")))
