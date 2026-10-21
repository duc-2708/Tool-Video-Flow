"""Observe references, review analyses, select a subset and edit reusable rules."""
import json
from pathlib import Path
import streamlit as st
from pipeline.style_learner import reference_dir, storage, estimate_batch
from pipeline.style_profile import build_profile, save_profile, list_profiles
from pipeline.style_jobs import StyleJobs
from schemas.style import AnalysisRecord, StyleProfile
from utils.cache import cache_key


@st.cache_resource
def style_jobs():
    return StyleJobs()


def render(settings, project, topic, debug, diagnostics):
    st.title("Phong cách mẫu")
    st.caption("Học cấu trúc, giọng kể và nhịp; nội dung video mới vẫn chỉ dựa trên brief.")
    st.info("Bỏ .mp4 vào assets/reference_videos/. Ghi chú tùy chọn: file .txt cùng tên. Video được upload để phân tích rồi yêu cầu xóa khỏi Gemini; không đưa hình/âm thanh mẫu vào video xuất.")
    folder = reference_dir(settings)
    names = sorted(p.name for p in folder.iterdir() if p.suffix.lower() == ".mp4" and p.is_file() and p.resolve().parent == folder)
    st.caption("Model phân tích: " + diagnostics.redact(settings.gemini_style_model.strip() or settings.gemini_model or "Chưa cấu hình"))
    manager = style_jobs()
    active = manager.active()
    scope = st.radio("Phạm vi phân tích", ["Chọn video", "Tất cả video"], horizontal=True)
    selected = names if scope == "Tất cả video" else st.multiselect("Video cần phân tích", names, default=names[:settings.style_max_videos_per_run])
    estimate = None
    if selected:
        try:
            estimate = estimate_batch(settings, selected)
            st.write(f"{estimate['videos']} video · {estimate['total_duration_sec']:g}s · {estimate['new_videos']} video chưa có cache")
            st.write(f"Ước lượng ~{estimate['estimated_input_tokens']:,} token đầu vào + ~{estimate['estimated_output_tokens']:,} token đầu ra. Giá thực tế phụ thuộc model/gói; đây không phải số token tính phí chính xác.")
            st.dataframe(estimate["items"], hide_index=True, width="stretch")
        except Exception as error:
            st.error(diagnostics.redact(str(error)))
    signature = cache_key([selected, estimate, settings.gemini_style_model, settings.gemini_model])
    confirm = st.checkbox("Tôi đồng ý upload các video đã chọn và dùng quota Gemini theo ước lượng", key="style_consent_"+signature)
    ready = bool(estimate and confirm and not active and (settings.gemini_style_model.strip() or settings.gemini_model.strip()) and settings.gemini_api_key.get_secret_value().strip())
    if st.button("Phân tích tất cả" if scope == "Tất cả video" else "Phân tích video đã chọn", disabled=not ready, type="primary"):
        st.session_state["style_worker"] = manager.submit_analysis(selected, settings)
        st.rerun()
    # Single-file selection uses exactly the same estimate/consent workflow.
    st.caption("Để phân tích riêng một file, chọn duy nhất video đó; chọn nhiều file để phân tích cả lô (tối đa theo cấu hình).")
    worker = active or st.session_state.get("style_worker")
    snapshot = manager.snapshot(worker) if worker else None
    running = bool(snapshot and snapshot["status"] in {"queued", "running"})

    @st.fragment(run_every=1 if running else None)
    def progress_panel():
        current = manager.snapshot(worker) if worker else None
        if not current:
            return
        st.info(current["message"])
        if current.get("error"):
            st.error(current["error"])
        for result in current["results"]:
            for warning in result.get("warnings", []):
                st.warning(warning)
            if result.get("error"):
                st.error(result["filename"]+": "+result["error"])
            else:
                st.success(result["filename"]+": "+result["status"])
        if running and current["status"] not in {"queued", "running"}:
            st.rerun(scope="app")

    progress_panel()
    analyzed = []
    for name in names:
        path = storage(settings) / f"{Path(name).stem}.json"
        status_path = path.with_name(path.stem + ".status.json")
        if status_path.exists():
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
                if status.get("error"):
                    st.warning(name+": "+status["error"])
                for warning in status.get("warnings", []):
                    st.warning(name+": "+warning)
            except (OSError, ValueError):
                pass
        if not path.exists():
            continue
        try:
            record = AnalysisRecord.model_validate_json(path.read_text(encoding="utf-8"))
            analyzed.append(name)
            with st.expander(name + " · Đã phân tích"):
                st.write("Hook:", record.analysis.hook.model_dump())
                st.dataframe([s.model_dump() for s in record.analysis.structure], hide_index=True)
                st.write("Nhịp:", record.analysis.pacing.model_dump())
                for rule in record.analysis.reusable_rules:
                    st.write("• " + rule)
                st.json(record.analysis.model_dump(mode="json"))
        except Exception as error:
            st.warning(name + ": " + diagnostics.redact(str(error)))
    st.subheader("Tổng hợp thành preset")
    chosen = st.multiselect("Video đưa vào preset", analyzed, default=analyzed)
    name = st.text_input("Tên preset", value="Phong cách của tôi")
    if st.button("Tổng hợp thành preset", disabled=not chosen or not name.strip()):
        try:
            st.session_state["style_profile_preview"] = build_profile(settings, name, chosen).model_dump(mode="json")
        except Exception as error:
            st.error(diagnostics.redact(str(error)))
    existing = list_profiles(settings)
    if existing:
        picked = st.selectbox("Preset đã lưu", [p.slug for p in existing], format_func=lambda v: next(p.name for p in existing if p.slug == v))
        if st.button("Mở preset để sửa quy tắc"):
            st.session_state["style_profile_preview"] = next(p.model_dump(mode="json") for p in existing if p.slug == picked)
    preview = st.session_state.get("style_profile_preview")
    if preview:
        profile = StyleProfile.model_validate(preview)
        st.write("Preset:", profile.name)
        rules = st.text_area("Quy tắc tái sử dụng (mỗi dòng một quy tắc)", value="\n".join(profile.reusable_rules), height=220, key="style_rules_"+profile.slug)
        with st.expander("Thông số preset"):
            st.json(profile.model_dump(mode="json", exclude={"reference_texts"}))
        if st.button("Lưu preset", type="primary"):
            try:
                profile.reusable_rules = list(dict.fromkeys(line.strip() for line in rules.splitlines() if line.strip()))
                if not profile.reusable_rules:
                    raise ValueError("Cần ít nhất một quy tắc tái sử dụng.")
                path = save_profile(settings, profile)
                st.session_state["style_profile_preview"] = profile.model_dump(mode="json")
                st.success("Đã lưu preset: " + path.name)
            except Exception as error:
                st.error(diagnostics.redact(str(error)))
