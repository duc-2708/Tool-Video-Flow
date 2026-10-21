"""Shared editor. Widget drafts survive reruns; generation requires a click."""
import streamlit as st
from agents.video_prompt_writer import generate_for_shot,fallback_prompt
from pipeline.video_prompts import save_shot_prompt


def prompt_editor(settings,project,scene_id,shot_index,saved_prompt,topic,diagnostics,*,prefix):
    key = f"{prefix}_prompt_{project.name}_{scene_id}_{shot_index}"
    pending = st.session_state.pop(key+"_pending",None)
    if pending is not None:
        st.session_state[key] = pending
    draft = st.text_area(f"AI prompt · cảnh {scene_id} / shot {shot_index}",
        value=saved_prompt or fallback_prompt(topic),key=key,height=100)
    simpler = st.checkbox("Đơn giản hơn",key=key+"_simple")
    ready = bool(settings.gemini_api_key.get_secret_value().strip() and (settings.gemini_director_model.strip() or settings.gemini_model.strip()))
    if st.button("Viết lại prompt",key=key+"_rewrite",disabled=not ready):
        try:
            with st.spinner("Đang viết prompt ngắn; chưa tạo video…"):
                st.session_state[key+"_pending"] = generate_for_shot(project,scene_id,shot_index,settings,simpler=simpler)
            st.rerun()
        except Exception as error:
            diagnostics.record_exception(error,"UI viết lại video prompt")
            st.error(diagnostics.redact(str(error)))
    if st.button("Lưu prompt cho shot",key=key+"_save"):
        try:
            save_shot_prompt(project,scene_id,shot_index,draft)
            st.success("Đã lưu prompt; chỉ áp dụng cho job mới, không sửa hay gửi lại job đã gửi.")
        except Exception as error:
            diagnostics.record_exception(error,"UI lưu video prompt")
            st.error(diagnostics.redact(str(error)))
    return draft,key
