"""Category scan source management, preview and explicit Gemini cost approval."""
import streamlit as st
from config.categories import resolve_category
from db.repository import Repository
from pipeline.scan_jobs import ScanJobs
from pipeline.scan_sources import add_source, estimate_selection, retry_candidates
from sources.youtube_resolver import YouTubeCatalog, resolve_source
from utils.cache import cache_key
from utils.atomic_io import read_json_atomic


@st.cache_resource
def scan_jobs():
    return ScanJobs()


def show_worker(settings, category, diagnostics):
    manager=scan_jobs()
    key=st.session_state.get("style_scan_worker_"+category)
    snapshot=manager.snapshot(key) if key else None
    running=bool(snapshot and snapshot["status"] in {"queued","running"})
    @st.fragment(run_every=1 if running else None)
    def panel():
        current=manager.snapshot(key) if key else None
        if not current:
            return
        st.info(current["message"])
        if current["error"]:
            st.error(current["error"])
        applied_key="style_scan_applied_"+category
        if current["status"] in {"finished","failed"} and st.session_state.get(applied_key)!=key:
            st.session_state[applied_key]=key
            if current["status"]=="finished":
                if current["kind"]=="scan":
                    st.session_state["style_scan_preview_"+category]=current["result"]
                else:
                    st.session_state.pop("style_scan_preview_"+category,None)
                    st.session_state["style_scan_outcome_"+category]=current["result"]
            st.rerun(scope="app")
    panel()


def render(settings, category, diagnostics):
    category=resolve_category(settings,category).category_id
    st.subheader("Nguồn quét YouTube")
    st.caption("Chỉ học phong cách, không sao chép nội dung. Chỉ gọi API chính thức; không tải video hoặc transcript.")
    repo=Repository.for_settings(settings)
    api=YouTubeCatalog(settings)
    try:
        quota=api.quota()
        st.caption(f"Quota YouTube hôm nay (ước lượng, ngày Pacific): {quota['estimated_units']}/{settings.youtube_daily_quota} đơn vị · Search: {quota['search_calls']} · Lượt gọi Gemini Style hôm nay (UTC): {repo.daily_calls('gemini_style')}")
    except (OSError,ValueError) as error:
        st.warning("Không đọc được quota: "+diagnostics.redact(str(error)))
    manager=scan_jobs();active=manager.active()
    with st.form("scan_add_form_"+category):
        kind=st.radio("Loại nguồn",["channel","keyword"],format_func=lambda v:"Kênh/link YouTube" if v=="channel" else "Từ khóa",horizontal=True)
        value=st.text_input("Link video/kênh/playlist YouTube, @handle, tên kênh hoặc từ khóa",key="scan_value_"+category)
        submitted=st.form_submit_button("Thêm nguồn",disabled=bool(active))
    if submitted:
        try:
            with st.spinner("Phân giải bằng YouTube Data API…"):
                result=resolve_source(value,api,kind=kind)
            if result.get("notice"):
                st.info(result["notice"])
            if not result["choices"]:
                st.warning("Không tìm thấy kênh phù hợp.")
            elif result["requires_selection"]:
                st.session_state["scan_choices_"+category]=result["choices"]
            else:
                add_source(settings,category,result["choices"][0])
                st.session_state.pop("scan_choices_"+category,None)
                st.success("Đã thêm nguồn; chưa gọi Gemini.")
        except Exception as error:
            diagnostics.record_exception(error,"Thêm nguồn YouTube")
            st.error(diagnostics.redact(str(error)))
    choices=st.session_state.get("scan_choices_"+category)
    if choices:
        labels={c["value"]:c["label"]+" · "+c["value"] for c in choices}
        selected=st.selectbox("Chọn đúng kênh (không tự chọn kết quả)",[None,*labels],format_func=lambda v:labels.get(v,"Chọn kênh…"),key="scan_channel_choice_"+category+cache_key(choices))
        if st.button("Xác nhận kênh đã chọn",disabled=not selected,key="scan_confirm_channel_"+category):
            add_source(settings,category,next(c for c in choices if c["value"]==selected))
            st.session_state.pop("scan_choices_"+category,None)
            st.rerun()
    sources=repo.sources(category)
    maximum=st.number_input("Số video mới tối đa mỗi lần quét",min_value=1,max_value=min(settings.scan_max_new_videos,settings.style_max_videos_per_run),value=min(settings.scan_max_new_videos,settings.style_max_videos_per_run),key="scan_max_"+category)
    mode=st.selectbox("Loại video cần học",["all","shorts","regular"],format_func=lambda v:{"all":"Tất cả","shorts":"Video ngắn ≤180s (ước lượng Shorts)","regular":"Video dài >180s"}[v],key="scan_mode_"+category)
    if mode!="all":
        st.info("Data API công khai không có cờ Shorts chính xác. Bộ lọc này dùng thời lượng; nếu chọn video dài, tăng SCAN_MAX_VIDEO_SEC trên 180.")
    order=st.selectbox("Thứ tự tìm từ khóa",["date","viewCount"],format_func=lambda v:"Mới nhất" if v=="date" else "Lượt xem cao",key="scan_order_"+category)
    def start(source_id=None):
        st.session_state["style_scan_worker_"+category]=manager.submit_scan(settings,category,source_id=source_id,maximum=int(maximum),mode=mode,order=order)
        st.rerun()
    if st.button("Quét tất cả nguồn của danh mục",disabled=bool(active) or not any(s["active"] for s in sources),key="scan_all_"+category):
        start()
    all_learned=repo.videos(category)
    for source in sources:
        with st.expander(f"#{source['id']} · {source['label']}"):
            thumbnail=source["thumbnail_url"]
            if thumbnail.startswith("https://"):
                st.image(thumbnail,width=60)
            if source["source_url"]:
                st.link_button("Mở kênh YouTube",source["source_url"])
            count=sum(r["status"]=="done" and not r["permanent_skip"] for r in repo.videos(category,source["id"]))
            st.write(f"Đã học: {count} video · Quét lần cuối: {source['last_scanned_at'] or 'Chưa quét'}")
            enabled=st.checkbox("Bật nguồn",value=bool(source["active"]),key="scan_active_"+str(source["id"]))
            if enabled!=bool(source["active"]):
                repo.activate(source["id"],enabled);st.rerun()
            if st.button("Quét nguồn này",disabled=bool(active) or not enabled,key="scan_one_"+str(source["id"])):
                start(source["id"])
    show_worker(settings,category,diagnostics)
    plan=st.session_state.get("style_scan_preview_"+category)
    if plan:
        st.write("Video mới sẽ học — quét chưa gọi Gemini")
        for warning in plan.get("warnings",[]):
            st.warning(warning)
        if plan["videos"]:
            st.dataframe([{"ID":r["video_id"],"tiêu đề":r["title"],"giây":r["duration_sec"],"ngày":r["published_at"],"trạng thái":r["decision"],"lý do":r["reason"]} for r in plan["videos"]],hide_index=True,width="stretch")
        selected=[];revision=cache_key(plan)
        for row in plan["videos"]:
            if row["decision"]=="ready":
                if st.checkbox("Học: "+row["title"],value=True,key="scan_pick_"+revision+row["video_id"]):
                    selected.append(row)
                if st.button("Bỏ qua mãi mãi",key="scan_preview_skip_"+category+row["video_id"],disabled=bool(active)):
                    from pipeline.scan_sources import video_fields
                    repo.save_video(category,row.get("platform","youtube"),row["video_id"],status="skipped",force=True,
                        source_ids=row.get("source_ids",[]),**video_fields(row),permanent_skip=1,error="Người dùng chọn bỏ qua mãi mãi.")
                    row.update(decision="skipped",reason="Người dùng chọn bỏ qua mãi mãi.")
                    st.session_state["style_scan_preview_"+category]=plan
                    from pipeline.category_style import rebuild_category
                    rebuild_category(settings,category)
                    st.rerun()
        if selected:
            try:
                estimate=estimate_selection(settings,selected,category)
                st.write(f"{estimate['videos']} video · {estimate['duration_sec']:g}s · ~{estimate['estimated_input_tokens']:,} token đầu vào + ~{estimate['estimated_output_tokens']:,} token đầu ra. Giá thực tế tùy model/gói.")
                consent=st.checkbox("Tôi xác nhận gọi Gemini để học các URL đã chọn; có thể phát sinh chi phí",key="scan_consent_"+cache_key([revision,selected]))
                ready=bool(consent and not active and settings.gemini_api_key.get_secret_value().strip() and (settings.gemini_style_model.strip() or settings.gemini_model.strip()))
                if st.button("Xác nhận học video đã chọn",disabled=not ready,key="scan_learn_"+category,type="primary"):
                    st.session_state["style_scan_worker_"+category]=manager.submit_learning(settings,category,selected)
                    st.rerun()
            except (OSError,ValueError) as error:
                st.error(diagnostics.redact(str(error)))
        elif not plan["videos"]:
            st.info("Không có video mới phù hợp.")
    outcome=st.session_state.get("style_scan_outcome_"+category)
    if outcome:
        for result in outcome["results"]:
            (st.error if result["error"] else st.success)(result["filename"]+": "+(result["error"] or result["status"]))
        for warning in outcome["warnings"]:
            st.warning(warning)
    st.write("Video đã ghi nhận")
    options={None:"Tất cả nguồn",**{s["id"]:s["label"] for s in sources}}
    source_filter=st.selectbox("Lọc nguồn",list(options),format_func=options.get,key="scan_filter_"+category)
    learned=repo.videos(category,source_filter) if source_filter else all_learned
    failed=retry_candidates(settings,category,source_id=source_filter)[:int(maximum)]
    if st.button("Thử lại video lỗi",disabled=not failed or bool(active),key="scan_retry_"+category):
        st.session_state["style_scan_preview_"+category]={"videos":failed,"warnings":[],"created_at":"retry"}
        st.rerun()
    for row in learned:
        with st.expander(row["title"]+" · "+row["platform"]+" · "+row["status"]):
            st.write(row["url"])
            if row["error"]:
                st.warning(diagnostics.redact(row["error"]))
            if st.button("Xem phân tích",key="scan_view_"+str(row["id"]),disabled=not row["analysis_path"]):
                try:
                    from pipeline.scan_sources import analysis_path
                    if row["platform"]=="youtube":
                        path=analysis_path(settings,category,row["video_id"])
                    else:
                        from pipeline.style_library import record_path
                        path=record_path(settings,row["url"])
                    st.json(read_json_atomic(path))
                except (OSError,ValueError) as error:
                    st.error(diagnostics.redact(str(error)))
            if st.button("Học lại",key="scan_relearn_"+str(row["id"]),disabled=bool(active) or bool(row["permanent_skip"])):
                retry=retry_candidates(settings,category,video_id=row["video_id"],platform=row["platform"],relearn=True)
                st.session_state["style_scan_preview_"+category]={"videos":retry,"warnings":["Học lại có thể tốn phí; bản phân tích đang dùng chỉ được thay khi có kết quả mới hợp lệ."],"created_at":"relearn"}
                st.rerun()
            if st.button("Bỏ qua mãi mãi",key="scan_skip_"+str(row["id"]),disabled=bool(active) or bool(row["permanent_skip"])):
                repo.skip_forever(category,row["platform"],row["video_id"])
                from pipeline.category_style import rebuild_category
                rebuild_category(settings,category)
                st.rerun()
