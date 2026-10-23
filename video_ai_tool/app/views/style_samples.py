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


def render_legacy(settings, project, topic, debug, diagnostics):
    st.title("Phong cách mẫu")
    st.caption("Học cấu trúc, giọng kể và nhịp; nội dung video mới vẫn chỉ dựa trên brief.")
    seconds=st.number_input("Giới hạn đoạn phân tích (giây)",min_value=1.,max_value=600.,value=float(settings.style_max_video_sec),key="style_max_sec_legacy")
    settings=settings.model_copy(update={"style_max_video_sec":seconds})
    st.caption("Chỉ phân tích từ giây 0 đến giới hạn này; video trên 600 giây được bỏ qua. Có bản thô thì chỉ parse tại máy.")
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
                st.success(result["filename"]+": "+result.get("status_label",result["status"]))
        if running and current["status"] not in {"queued", "running"}:
            st.rerun(scope="app")

    progress_panel()

    if estimate:
        from app.views.style_raw import render as render_raw_repair
        render_raw_repair(settings,estimate["items"],manager,active,"legacy",diagnostics)
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
                st.caption(f"{len(record.analysis.analysis_warnings)} cảnh báo phân tích")
                for warning in record.warnings:
                    st.warning(diagnostics.redact(warning))
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


def analysis_controls(settings,names,scope,diagnostics):
    seconds=st.number_input("Giới hạn đoạn phân tích (giây)",min_value=1.,max_value=600.,value=float(settings.style_max_video_sec),key="style_max_sec_"+scope)
    settings=settings.model_copy(update={"style_max_video_sec":seconds})
    st.caption("Video dài hơn giới hạn: chỉ phân tích đoạn đầu. Video trên 600 giây: bỏ qua. 400: thử tối đa 4 cấu hình thay thế; quota thực có thể cao hơn ước lượng. Có bản thô: không gọi lại Gemini.")
    manager=style_jobs()
    active=manager.active()
    mode=st.radio("Phạm vi phân tích",["Chọn video","Tất cả video"],horizontal=True,key="style_mode_"+scope)
    selected=names if mode=="Tất cả video" else st.multiselect("Video cần phân tích",names,default=names[:settings.style_max_videos_per_run],key="style_selected_"+scope)
    estimate=None
    if selected:
        try:
            estimate=estimate_batch(settings,selected)
            st.write(f"{estimate['videos']} video · {estimate['total_duration_sec']:g}s · {estimate['new_videos']} video chưa có cache")
            st.write(f"Ước lượng ~{estimate['estimated_input_tokens']:,} token đầu vào + ~{estimate['estimated_output_tokens']:,} token đầu ra; giá thực tế phụ thuộc model/gói.")
            st.dataframe(estimate["items"],hide_index=True,width="stretch")
        except Exception as error:
            st.error(diagnostics.redact(str(error)))
    consent=st.checkbox("Tôi đồng ý upload các video đã chọn và dùng quota Gemini theo ước lượng",key="style_confirm_"+scope+cache_key(estimate))
    ready=bool(estimate and consent and not active and settings.gemini_api_key.get_secret_value().strip() and (settings.gemini_style_model.strip() or settings.gemini_model.strip()))
    if st.button("Phân tích tất cả" if mode=="Tất cả video" else "Phân tích video đã chọn",disabled=not ready,type="primary",key="style_analyze_"+scope):
        st.session_state["style_worker"]=manager.submit_analysis(selected,settings)
        st.rerun()
    worker=active or st.session_state.get("style_worker")
    snapshot=manager.snapshot(worker) if worker else None
    running=bool(snapshot and snapshot["status"] in {"queued","running"})
    @st.fragment(run_every=1 if running else None)
    def progress_panel():
        current=manager.snapshot(worker) if worker else None
        if not current:
            return
        st.info(current["message"])
        if current.get("error"):
            st.error(current["error"])
        for result in current.get("results",[]):
            for warning in result.get("warnings",[]):
                st.warning(warning)
            if result.get("error"):
                st.error(result["filename"]+": "+result["error"])
            else:
                st.success(result["filename"]+": "+result.get("status_label",result["status"]))
        if running and current["status"] not in {"queued","running"}:
            st.rerun(scope="app")
    progress_panel()

    if estimate:
        from app.views.style_raw import render as render_raw_repair
        render_raw_repair(settings,estimate["items"],manager,active,scope,diagnostics)


def scene_table(analysis):
    return [{"start":s.start_sec,"end":s.end_sec,"mục đích":s.purpose,"tóm tắt lời đọc":s.narration_summary,
        "số từ":s.word_count,"từ/giây":s.words_per_sec,"số shot":s.shot_count,"giây/shot":s.average_shot_sec,
        "hình":", ".join(s.visual_types),"hiệu ứng":", ".join(s.camera_effects),"chuyển cảnh":s.transition_to_next.type if s.transition_to_next else "Không có",
        "câu nối":s.transition_to_next.connective_template if s.transition_to_next else ""} for s in analysis.scenes]


def category_panel(settings,category,project,diagnostics):
    from config.categories import categories_for
    from pipeline.style_library import list_videos,read_record,record_path,confirm_category,save_upload
    from pipeline.category_style import rebuild_category,save_category_edits,compare_plan
    from pipeline.projects import list_projects,read_json
    from schemas.edit_plan import EditPlan
    scope=category or "_unsorted"
    categories=categories_for(settings).categories
    if category:
        from app.views.style_sources import render as render_sources
        render_sources(settings,category,diagnostics)
    upload_key="style_upload_"+scope+str(st.session_state.get("style_upload_nonce",0))
    uploads=st.file_uploader("Thêm video .mp4",type=["mp4"],accept_multiple_files=True,max_upload_size=settings.style_max_file_mb,key=upload_key)
    if st.button("Thêm video",disabled=not uploads,key="style_add_"+scope):
        messages=[]
        for upload in uploads:
            try:
                messages.append(save_upload(settings,upload.name,upload.getvalue(),scope))
            except Exception as error:
                st.error(diagnostics.redact(upload.name+": "+str(error)))
        if messages:
            st.session_state["style_notice"]="Đã thêm: "+", ".join(messages)+". Chưa gọi Gemini."
            st.session_state["style_upload_nonce"]=st.session_state.get("style_upload_nonce",0)+1
            st.rerun()
    st.caption("Hoặc bỏ video vào assets/reference_videos/"+scope+"/. Giới hạn chi phí chỉ áp dụng khi bấm Phân tích.")
    names=list_videos(settings,scope)
    if not names:
        st.info("Chưa có video trong thư mục này.")
    profile=None
    profile_type=None
    if category:
        profile_type=st.selectbox("Hồ sơ theo loại video",[None,"news","review","story"],format_func=lambda v:v or "Chung cả danh mục",key="style_profile_type_"+scope)
        try:
            profile=rebuild_category(settings,category,video_type=profile_type)
            st.metric("Số video mẫu làm cơ sở",profile.video_count)
            st.caption("Độ tin cậy: "+profile.confidence_label)
            for warning in profile.warnings:
                st.info(diagnostics.redact(warning))
        except Exception as error:
            st.error(diagnostics.redact(str(error)))
    rows=[]
    records={}
    for name in names:
        try:
            record=read_record(settings,name)
            records[name]=record
            guess=record.analysis.category_guess
            row={"video":name,"trạng thái":"done (có cảnh báo)" if record.analysis.analysis_warnings else "Đã phân tích",
                "số cảnh báo":len(record.analysis.analysis_warnings),
                "gợi ý":guess.category_id if guess else "Chưa có","tin cậy":guess.confidence if guess else None}
        except (OSError,ValueError):
            row={"video":name,"trạng thái":"Chưa phân tích","gợi ý":"","tin cậy":None}
        status=record_path(settings,name,status=True)
        if status.exists():
            try:
                state=read_json(status)
                if state.get("error"):
                    row["trạng thái"]=state["error"]
            except (OSError,ValueError):
                pass
        rows.append(row)
    if rows:
        st.dataframe(rows,hide_index=True,width="stretch")
    analysis_controls(settings,names,scope,diagnostics)
    for name,record in records.items():
        with st.expander(name+" · Phân tích kịch bản/phân cảnh"):
            st.caption(f"{len(record.analysis.analysis_warnings)} cảnh báo phân tích")
            for warning in record.warnings:
                st.warning(diagnostics.redact(warning))
            if record.analysis.scenes:
                st.dataframe(scene_table(record.analysis),hide_index=True,width="stretch")
            else:
                st.info("Phân tích phiên bản cũ; bấm Phân tích để lấy scenes[] chi tiết.")
            st.write("Mạch kể: "+record.analysis.narrative_flow)
            st.write("Cụm nối:",record.analysis.connective_phrases)
            with st.expander("JSON phân tích"):
                st.json(record.analysis.model_dump(mode="json"))
            if category is None:
                ids=[c.category_id for c in categories]
                guess=record.analysis.category_guess
                guess_id=guess.category_id if guess and guess.category_id in ids else ids[0]
                names_by_id={c.category_id:c.name for c in categories}
                target=st.selectbox("Xác nhận/đổi danh mục",ids,index=ids.index(guess_id),format_func=names_by_id.get,key="style_guess_"+cache_key(name))
                if guess:
                    confidence=f"{guess.confidence:.0%}" if guess.confidence is not None else "chưa có độ tin cậy"
                    st.caption(f"Gemini gợi ý {guess.category_id} · {confidence}: {guess.reason}")
                if st.button("Xác nhận và chuyển file",key="style_move_"+cache_key(name)):
                    try:
                        moved=confirm_category(settings,name,target)
                        rebuild_category(settings,target)
                        st.session_state["style_notice"]="Đã chuyển video và ghi chú/phân tích: "+moved
                        st.rerun()
                    except Exception as error:
                        diagnostics.record_exception(error,"Xác nhận danh mục video mẫu")
                        st.error(diagnostics.redact(str(error)))
    if profile is None:
        return
    st.subheader("Hồ sơ tổng hợp của danh mục")
    if st.button("Tổng hợp lại",key="style_rebuild_"+scope):
        try:
            profile=rebuild_category(settings,category,force=True,video_type=profile_type)
            st.session_state["style_notice"]="Đã tổng hợp lại; các trường đã khóa được giữ nguyên."
            st.rerun()
        except Exception as error:
            st.error(diagnostics.redact(str(error)))
    st.dataframe([r.model_dump(mode="json") for r in profile.scene_pacing],hide_index=True,width="stretch")
    st.write("Khuôn mạch kể:",profile.narrative_flows)
    if profile.connective_frequencies:
        st.dataframe([f.model_dump() for f in profile.connective_frequencies],hide_index=True)
    revision=cache_key([profile.source_signature,profile.reusable_rules,profile.connective_phrases,profile.locked_fields])[:12]
    with st.form("category_rules_"+scope+str(profile_type)+revision):
        themes=["studio","paper"]
        visual_theme=st.selectbox("Theme đồ họa",themes,index=themes.index(profile.visual_theme) if profile.visual_theme in themes else 0)
        visual_templates=st.checkbox("Dùng mẫu đồ họa khi dựng",value=profile.visual_templates)
        progress_tracker=st.checkbox("Bật thanh tiến trình ý chính",value=profile.progress_tracker)
        progress_labels=st.text_input("Nhãn tiến trình (phân cách bằng dấu |)",value=" | ".join(profile.progress_labels))
        appearances=["classic","pill"]
        appearance=st.selectbox("Kiểu phụ đề đồ họa",appearances,index=appearances.index(profile.captions.appearance))
        rules=st.text_area("Quy tắc tái sử dụng (mỗi dòng một quy tắc)",value="\n".join(profile.reusable_rules),key="style_category_rules_"+scope+revision)
        phrases=st.text_area("Cụm nối (mỗi dòng một khuôn, tối đa 12)",value="\n".join(profile.connective_phrases),key="style_category_connectors_"+scope+revision)
        lock_rules=st.checkbox("Khóa quy tắc, không tổng hợp đè",value="reusable_rules" in profile.locked_fields)
        lock_phrases=st.checkbox("Khóa cụm nối, không tổng hợp đè",value="connective_phrases" in profile.locked_fields)
        saved=st.form_submit_button("Lưu quy tắc và khóa")
    if saved:
        try:
            locks=(["reusable_rules"] if lock_rules else [])+(["connective_phrases"] if lock_phrases else [])
            updated=save_category_edits(settings,category,reusable_rules=rules.splitlines(),connective_phrases=phrases.splitlines(),locked_fields=locks,video_type=profile_type)
            updated.visual_theme=visual_theme;updated.visual_templates=visual_templates;updated.progress_tracker=progress_tracker
            updated.progress_labels=[v.strip() for v in progress_labels.split("|") if v.strip()][:6]
            updated.captions.appearance=appearance
            from pipeline.category_style import profile_file
            from utils.atomic_io import write_json_atomic
            write_json_atomic(profile_file(settings,category,profile_type),updated.model_dump(mode="json"))
            st.session_state["style_notice"]="Đã lưu quy tắc/cụm nối và trạng thái khóa."
            st.rerun()
        except Exception as error:
            st.error(diagnostics.redact(str(error)))
    with st.expander("JSON hồ sơ"):
        st.json(profile.model_dump(mode="json",exclude={"reference_texts"}))
    candidates={p.name:p.path for p in list_projects(settings.output_dir) if (p.path/"edit_plan.json").is_file()}
    if candidates:
        chosen=st.selectbox("Project để so khớp",list(candidates),index=list(candidates).index(project.name) if project and project.name in candidates else 0,key="style_compare_"+scope)
        if st.button("So khớp kịch bản",key="style_compare_run_"+scope):
            try:
                plan=EditPlan.model_validate(read_json(candidates[chosen]/"edit_plan.json"))
                result=compare_plan(plan,profile)
                st.dataframe(result["summary"],hide_index=True)
                left,right=st.columns(2)
                left.write("Kịch bản mới");left.dataframe(result["scenes"],hide_index=True)
                right.write("Cấu trúc hồ sơ");right.dataframe(result["patterns"] or [s.model_dump() for s in profile.structure],hide_index=True)
                st.dataframe(result["phrases"],hide_index=True)
            except Exception as error:
                st.error(diagnostics.redact(str(error)))


def render(settings,project,topic,debug,diagnostics):
    from config.categories import categories_for
    from pipeline.style_library import list_videos
    st.title("Phong cách mẫu")
    st.caption("Video theo danh mục → phân tích kịch bản/phân cảnh → hồ sơ tự áp dụng. Nội dung mới vẫn chỉ dựa trên brief.")
    notice=st.session_state.pop("style_notice",None)
    if notice:
        st.success(diagnostics.redact(notice))
    try:
        categories=categories_for(settings).categories
    except Exception as error:
        st.error("Không đọc được danh mục: "+diagnostics.redact(str(error)))
        return
    labels=[c.name for c in categories]+["Chưa phân loại","Preset tự chọn"]
    default="Chưa phân loại" if list_videos(settings,"_unsorted") else labels[0]
    tabs=st.tabs(labels,default=default,key="style_category_tabs",on_change="rerun")
    for index,tab in enumerate(tabs):
        if not tab.open:
            continue
        with tab:
            if index==len(labels)-1:
                render_legacy(settings,project,topic,debug,diagnostics)
            else:
                category_panel(settings,categories[index].category_id if index<len(categories) else None,project,diagnostics)
