# file: app/views/edit_plan.py
"""Trang Director/Edit Plan: tạo, sửa lời đọc/query và lưu có kiểm tra."""
import json
from pathlib import Path
import streamlit as st
from app.style_controls import select_style
from agents.director import run_director, save_edit_plan, review_notes_for
from app.ui_errors import error_details
from config.settings import Settings
from pipeline.projects import read_json
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from utils.cache import cache_key
from utils.diagnostics import Diagnostics
from app.ai_prompt_controls import prompt_editor
from config.storytelling import DURATIONS,STYLES
from agents.story_style import data_advice
from agents.director_story import rewrite_script


def report_error(error: BaseException, diagnostics: Diagnostics, project: Path) -> None:
    diagnostics.record_exception(error, "Streamlit Director")
    message, trace = error_details(error, diagnostics)
    st.session_state["director_error"] = {"project": project.name, "message": message, "trace": trace}


def render(settings: Settings, project: Path | None, topic: str, debug: bool, diagnostics: Diagnostics) -> None:
    st.title("Edit Plan")
    st.caption("Director → kế hoạch JSON. Chưa tạo audio, tải media hoặc render video.")
    if project is None or not (project / "brief.json").exists():
        st.info("Chọn project đã có brief.json hoặc chạy Research trước khi tạo Edit Plan.")
        return
    diagnostics = Diagnostics(settings.logs_dir, filename="director_errors.log", secrets=diagnostics.secrets)
    scope = project.name
    notice = st.session_state.get("director_notice")
    if notice and notice["project"] == scope:
        st.success(notice["message"])
        del st.session_state["director_notice"]
    existing = None
    if (project / "edit_plan.json").exists():
        try:
            existing = EditPlan.model_validate(read_json(project / "edit_plan.json"))
        except Exception as error:
            report_error(error, diagnostics, project)
    brief_data = read_json(project/"brief.json")
    if existing:
        for warning in existing.review_notes:
            st.warning(diagnostics.redact(warning))
    if len(brief_data.get("facts",[]))<8:
        st.warning("dữ liệu mỏng")
    draft_path = project/"edit_plan.draft.json"
    if draft_path.exists() and read_json(draft_path).get("status") != "resolved":
        draft = read_json(draft_path)
        st.warning("Có bản nháp Director chưa đạt kiểm tra; cần sửa và đối chiếu trước khi dùng.")
        for warning in draft.get("warnings",[]):
            st.warning(diagnostics.redact(str(warning)))
        if draft.get("validation_errors"):
            st.dataframe(draft["validation_errors"],hide_index=True,width="stretch")
        if st.checkbox("Sửa bản nháp",value=existing is None,key=f"director_draft_{scope}"):
            try:
                existing = EditPlan.model_validate(draft.get("plan"))
            except Exception:
                raw_draft = st.text_area("JSON bản nháp cần sửa",value=json.dumps(draft.get("plan"),ensure_ascii=False,indent=2),height=350)
                if st.button("Kiểm tra và lưu bản nháp"):
                    try:
                        save_edit_plan(project/"brief.json",json.loads(raw_draft),settings)
                        st.success("Đã kiểm tra và lưu Edit Plan.")
                    except Exception as error:
                        report_error(error,diagnostics,project)
                        st.error(diagnostics.redact(str(error)))
    kinds, formats = ["news", "review", "story"], ["tiktok", "youtube"]
    model_ready = bool(settings.gemini_api_key.get_secret_value().strip() and
                       (settings.gemini_director_model.strip() or settings.gemini_model.strip()))
    with st.form(f"director_generate_{scope}"):
        video_type = st.selectbox("Loại video", kinds, index=kinds.index(existing.video_type) if existing and existing.video_type in kinds else 1)
        video_format = st.selectbox("Khổ video", formats, index=formats.index(existing.format) if existing else 0,
                                    format_func=lambda value: "TikTok · 9:16" if value == "tiktok" else "YouTube · 16:9")
        preset = st.selectbox("Mốc thời lượng",["Tùy chỉnh",*DURATIONS],key=f"director_duration_preset_{scope}")
        style_preset=select_style(settings,key=f"director_style_preset_{scope}",current=existing.style_preset if existing else None)
        selected_style = st.selectbox("Phong cách",list(STYLES),format_func=STYLES.get,index=list(STYLES).index(existing.script_style) if existing and existing.script_style else 0)
        duration = st.number_input("Độ dài yêu cầu (giây)", min_value=6.0, max_value=600.0,
                                  value=float(existing.target_duration_sec or 45) if existing else 45.0, step=1.0)
        duration = float(preset) if preset != "Tùy chỉnh" else duration
        advice = data_advice(ResearchBrief.model_validate(brief_data),duration)
        if advice["thin"]:
            st.warning(advice["warning"]+f"; đề xuất {advice['suggested_duration']:g} giây.")
        output_language = st.selectbox("Ngôn ngữ kịch bản",["vi"],format_func=lambda value:"Tiếng Việt")
        ai_clip_limit = st.number_input("Số shot chuẩn bị clip AI",min_value=0,max_value=max(0,settings.ai_clip_max_per_run),value=0,step=1)
        generate = st.form_submit_button("Tạo Edit Plan", type="primary", disabled=not model_ready)
    if generate:
        st.session_state.pop("director_error", None)
        status = st.empty()
        try:
            with st.spinner("Director đang viết và kiểm tra căn cứ…"):
                run_director(project / "brief.json", settings, video_type=video_type, video_format=video_format,
                             duration_sec=float(duration),script_style=selected_style,style_preset=style_preset,output_language=output_language,ai_clip_limit=int(ai_clip_limit), progress=lambda text: status.info(diagnostics.redact(text)))
            st.session_state["director_notice"] = {"project": scope, "message": "Đã tạo và kiểm tra Edit Plan."}
            st.rerun()
        except Exception as error:
            status.empty()
            report_error(error, diagnostics, project)
    saved_error = st.session_state.get("director_error")
    if saved_error and saved_error["project"] == scope:
        st.error(saved_error["message"])
        if debug:
            with st.expander("Traceback Director (đã che credentials)"):
                st.code(saved_error["trace"], language="text")
        st.caption("Chi tiết: logs/director_errors.log. Kế hoạch thành công trước đó được giữ lại nếu lượt mới lỗi.")
    if existing is None:
        st.info("Chưa có Edit Plan hợp lệ. Tạo kế hoạch bằng form phía trên.")
        return
    data = json.loads(diagnostics.redact(existing.model_dump_json()))
    target = existing.target_duration_sec
    st.subheader(diagnostics.redact(existing.title))
    if existing.validation_events:
        with st.expander("Tự sửa và cảnh báo theo luật",expanded=True):
            st.dataframe([e.model_dump(mode="json") for e in existing.validation_events],hide_index=True,width="stretch")
    st.metric("Tổng thời lượng kế hoạch", f"{existing.duration_sec:.1f} giây",
              delta=f"{existing.duration_sec - target:+.1f} giây so với yêu cầu" if target else None, delta_color="off")
    st.caption(f"Yêu cầu đã lưu: {target:.1f}s · cho phép ±10%" if target else "Kế hoạch cũ chưa có thời lượng yêu cầu; hãy tạo lại.")
    word_count = sum(len(s.narration.split()) for s in existing.scenes)
    st.caption(f"Lời đọc: {word_count} từ · {word_count/existing.duration_sec:.2f} từ/giây · mục tiêu 2.4–2.8")
    st.caption("Thời lượng hiện tại tính theo shot; sẽ căn lại theo audio thật ở Giai đoạn 4.")
    revision = cache_key(data)[:12]
    role_labels = {"hook": "Mở đầu", "body": "Nội dung", "transition": "Chuyển ý", "cta": "Kết video"}
    try:
        brief = ResearchBrief.model_validate(read_json(project / "brief.json"))
    except Exception as error:
        report_error(error, diagnostics, project)
        st.error("Không đọc được brief để đối chiếu nguồn của cảnh. Hãy kiểm tra brief.json.")
        return
    rewrite_style = st.selectbox("Giọng khi viết lại",list(STYLES),format_func=STYLES.get,
        index=list(STYLES).index(existing.script_style) if existing.script_style else 0,key=f"rewrite_style_{scope}")
    if st.button(f"Viết lại toàn bộ với giọng {STYLES[rewrite_style]}",disabled=not model_ready,key=f"rewrite_all_{scope}"):
        try:
            with st.spinner("Đang viết lại, giữ nguyên fact_ids…"):
                rewrite_script(project/"brief.json",settings,style=rewrite_style)
            st.rerun()
        except Exception as error: report_error(error,diagnostics,project)
    rewrite_scene = st.selectbox("Chọn cảnh để viết lại",[s.id for s in existing.scenes],key=f"rewrite_scene_{scope}")
    if st.button("Viết lại cảnh này",disabled=not model_ready,key=f"rewrite_one_{scope}"):
        try:
            with st.spinner("Đang sửa riêng cảnh đã chọn…"):
                rewrite_script(project/"brief.json",settings,style=rewrite_style,scene_id=rewrite_scene)
            st.rerun()
        except Exception as error: report_error(error,diagnostics,project)
    if existing.story_outline:
        with st.expander("Dàn ý và câu hỏi xuyên suốt"):
            st.write(existing.story_outline.open_loop)
            st.caption("Giải đáp: "+existing.story_outline.payoff)
            for point in existing.story_outline.main_points: st.write(f"{point.idea} · fact_ids={point.fact_ids}")
    with st.form(f"director_edit_{scope}_{revision}"):
        if existing.render_style:
            with st.expander("Chỉnh mặc định dựng từ phong cách mẫu"):
                style=data["render_style"];captions=style["captions"]
                captions["enabled"]=st.checkbox("Bật phụ đề",value=captions["enabled"],key=f"style_caps_{scope}_{revision}")
                modes=["word","phrase","sentence"]
                captions["mode"]=st.selectbox("Nhóm phụ đề",modes,index=modes.index(captions["mode"]),key=f"style_capmode_{scope}_{revision}")
                captions["font_scale"]=st.number_input("Cỡ chữ / chiều rộng",min_value=.03,max_value=.10,value=float(captions["font_scale"]),step=.001,key=f"style_font_{scope}_{revision}")
                for field,label in [("color","Màu chữ"),("highlight_color","Màu từ đang đọc"),("stroke_color","Màu viền")]:
                    captions[field]=st.color_picker(label,value=captions[field],key=f"style_{field}_{scope}_{revision}")
                positions=["lower","center","top"]
                captions["position"]=st.selectbox("Vị trí phụ đề",positions,index=positions.index(captions["position"]),key=f"style_position_{scope}_{revision}")
                data["music"]["volume"]=st.slider("Âm lượng nhạc nền",0.,.35,float(data["music"]["volume"]),.01,key=f"style_music_{scope}_{revision}")
                style["ducking"]=st.checkbox("Hạ nhạc khi có lời đọc",value=style["ducking"],key=f"style_duck_{scope}_{revision}")
        for scene in data["scenes"]:
            with st.expander(f"Cảnh {scene['id']} · {role_labels[scene['role']]} · {sum(s['duration_sec'] for s in scene['shots']):.1f}s",
                             expanded=scene["role"] == "hook"):
                st.caption("Vai trò: " + scene["role"] + " · Fact tham chiếu: " + (", ".join(map(str, scene["fact_ids"])) or "CTA không nêu fact"))
                for fact_id in scene["fact_ids"]:
                    if 1<=fact_id<=len(brief.facts):
                        fact = brief.facts[fact_id-1]
                        st.write(f"Fact #{fact_id}: {fact.fact_vi or fact.claim}")
                scene["narration"] = st.text_area("Lời đọc", value=scene["narration"],
                    key=f"narration_{scope}_{revision}_{scene['id']}")
                if scene.get("pronunciation_hint"):
                    st.caption("Gợi ý phát âm (ghi chú biên tập): "+scene["pronunciation_hint"])
                rows = [{field: shot[field] for field in ("type", "query", "duration_sec", "effect", "text_overlay")} for shot in scene["shots"]]
                edited = st.data_editor(rows, hide_index=True, num_rows="fixed",
                    disabled=["type", "duration_sec"],
                    column_config={"type": "Loại shot", "query": st.column_config.TextColumn("Từ khóa b-roll (sửa tại đây)", required=True),
                                   "duration_sec": "Giây", "effect": "Hiệu ứng", "text_overlay": "Chữ trên hình"},
                    key=f"shots_{scope}_{revision}_{scene['id']}")
                for shot, row in zip(scene["shots"], edited):
                    shot["query"] = row["query"]
                    shot["effect"] = row["effect"]
                    shot["text_overlay"] = row["text_overlay"]
                st.caption(f"Chuyển cảnh: {scene['transition_out']} · SFX: {scene['sfx']} · Pattern interrupt: {'Có' if scene['pattern_interrupt'] else 'Không'}")
                st.markdown("**Ghi chú kiểm chứng · chỉ dành cho biên tập**")
                try:
                    notes = review_notes_for(scene["fact_ids"], brief)
                    for warning in (scene.get("review_notes") or {}).get("warnings",[]):
                        st.warning(warning)
                    if any(fact.source_count == 1 for fact in notes.facts):
                        st.badge("1 nguồn", color="orange")
                    st.caption(f"Fact IDs: {notes.fact_ids} · Số nguồn trong cảnh: {notes.source_count} · Confidence: {notes.confidence or 'Không áp dụng'}")
                    rows = [{"fact_id": fact.fact_id, "source_count": fact.source_count, "confidence": fact.confidence,
                             "source_name": source.name, "source_url": str(source.url)} for fact in notes.facts for source in fact.sources]
                    if rows:
                        st.dataframe(rows, hide_index=True, column_config={"fact_id": "Fact ID", "source_count": "Số nguồn của fact",
                            "confidence": "Confidence", "source_name": "Nguồn", "source_url": st.column_config.LinkColumn("URL nguồn", display_text="Mở nguồn")})
                    else:
                        st.caption("Cảnh không nêu fact; không có nguồn cần đối chiếu.")
                except ValueError as error:
                    st.warning(diagnostics.redact(str(error)))
        st.caption("Lưu sẽ validate lại schema, thời lượng và căn cứ bằng model Director. Có thể dùng quota API; chưa tạo audio/render.")
        save = st.form_submit_button("Lưu chỉnh sửa", disabled=not model_ready)
    if save:
        st.session_state.pop("director_error", None)
        try:
            with st.spinner("Đang kiểm tra nội dung chỉnh sửa và lưu…"):
                save_edit_plan(project / "brief.json", data, settings)
            st.session_state["director_notice"] = {"project": scope, "message": "Đã kiểm tra và lưu chỉnh sửa vào edit_plan.json."}
            st.rerun()
        except Exception as error:
            report_error(error, diagnostics, project)
            st.rerun()
    ai_slots = [(scene,index,shot) for scene in existing.scenes for index,shot in enumerate(scene.shots,1) if shot.type == "ai_video"]
    if ai_slots:
        st.subheader("Prompt clip AI · sửa trước khi tạo")
        st.caption("Một câu tiếng Anh, tối đa 30 từ; không chữ/thương hiệu/người thật. Viết lại chỉ dùng Gemini, chưa gọi API tạo clip.")
        for scene,index,shot in ai_slots:
            with st.expander(f"Prompt cảnh {scene.id} / shot {index}"):
                prompt_editor(settings,project,scene.id,index,shot.ai_prompt,existing.title,diagnostics,prefix="edit_plan")
    with st.expander("JSON đã lưu"):
        raw = diagnostics.redact(existing.model_dump_json(indent=2))
        st.code(raw, language="json")
        st.download_button("Tải edit_plan.json", raw.encode("utf-8"), file_name="edit_plan.json",
                           mime="application/json", on_click="ignore")
