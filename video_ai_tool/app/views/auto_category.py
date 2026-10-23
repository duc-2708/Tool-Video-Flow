"""One button: category -> discover -> existing verified video pipeline."""
from pathlib import Path
import streamlit as st
from app.style_controls import select_style
from config.categories import categories_for
from config.storytelling import DURATIONS,STYLES
from pipeline.auto_category_jobs import AutoCategoryJobs
from pipeline.projects import read_json
from app.views.edit_plan import render as edit_page
from app.views.render import show_result
from providers.video_gateway import VideoRequest

@st.cache_resource
def auto_jobs(): return AutoCategoryJobs()


def render(settings,project,topic,debug,diagnostics):
    st.title("Tạo video theo danh mục")
    st.caption("Khám phá chủ đề → Tìm thông tin → Kịch bản → Asset → Render. Ít dữ liệu sẽ tự rút thời lượng; không thêm sự kiện để kéo dài.")
    try: categories=[c.name for c in categories_for(settings).categories if c.enabled]
    except Exception as error: st.error(diagnostics.redact(str(error)));return
    if not categories: st.warning("Bật ít nhất một danh mục trong config/categories.yaml.");return
    manager=auto_jobs();active=manager.active()
    category=st.selectbox("Danh mục",categories,key="auto_category")
    left,right=st.columns(2)
    region=left.selectbox("Khu vực",["vn","global","both"],index=2,key="auto_region")
    days=right.selectbox("Khoảng ngày",[1,3,7],index=1,key="auto_days")
    duration=left.selectbox("Thời lượng mong muốn (giây)",DURATIONS,index=1,key="auto_duration")
    format_name=right.selectbox("Tỉ lệ",["tiktok","youtube"],format_func=lambda v:"TikTok · 9:16" if v=="tiktok" else "YouTube · 16:9",key="auto_format")
    style_preset=select_style(settings,key="auto_style_preset",category=category)
    style=left.selectbox("Phong cách",list(STYLES),format_func=STYLES.get,key="auto_style")
    explainer_v2=st.checkbox("Explainer v2: giảng giải chuyên sâu",value=False,key="auto_explainer_v2")
    creative=right.selectbox("Mức sáng tạo",["strict","balanced","story"],key="auto_creative")
    st.caption("Mức sáng tạo chỉ đổi cách kể; số liệu, sự kiện và khẳng định luôn phải có fact làm căn cứ.")
    mode=st.radio("Chế độ chạy",["Tự động hoàn toàn","Dừng để duyệt kịch bản"],key="auto_mode")
    youtube=st.checkbox("Bật YouTube trends",value=False,key="auto_youtube")
    ai=st.checkbox("Bật clip AI (có tính phí)",value=False,disabled=settings.ai_clip_max_per_run==0,key="auto_ai")
    count=0;confirmed=False
    if ai:
        count=st.number_input("Số clip AI tối đa",min_value=1,max_value=settings.ai_clip_max_per_run,value=1,key="auto_ai_count")
        quote=VideoRequest(model=settings.gateway_video_model,seconds=settings.ai_clip_seconds,prompt="Estimate")
        st.info(f"Sẽ tạo tối đa {count} clip, model {settings.gateway_video_model}, {settings.ai_clip_seconds}s/clip. Tham khảo {quote.estimated_cost_vnd*count:,} VNĐ; generation_failed có thể phát sinh một job thử lại/clip.")
        confirmed=st.checkbox("Tôi xác nhận chi phí trước khi bắt đầu",key=f"auto_ai_confirm_{count}_{settings.gateway_video_model}_{settings.ai_clip_seconds}_{st.session_state.get('auto_ai_nonce',0)}")
    params=dict(category=category,region=region,time_window_days=days,duration=duration,format=format_name,creative_license=creative,
        style=style,style_preset=style_preset,review=mode!="Tự động hoàn toàn",use_youtube=youtube,ai_clips=int(count),ai_confirmed=confirmed,content_mode="explainer_v2" if explainer_v2 else "event_only")
    ready=bool(settings.gemini_api_key.get_secret_value().strip() and settings.gemini_model.strip() and
        (not ai or confirmed and settings.gateway_api_key.get_secret_value().strip()))
    if st.button("Tạo video",type="primary",width="stretch",disabled=bool(active) or not ready,key="auto_start"):
        st.session_state["auto_worker"]=manager.submit_auto(params,settings)
        st.session_state["auto_ai_nonce"]=st.session_state.get("auto_ai_nonce",0)+1
        st.rerun()
    key=active or st.session_state.get("auto_worker")
    snapshot=manager.snapshot(key) if key else None
    running=bool(snapshot and snapshot["status"] in {"queued","running"})
    if running and st.button("Hủy",key="auto_cancel"): manager.cancel(key);st.info("Sẽ dừng ở điểm an toàn; không gửi thêm bước mới.")
    @st.fragment(run_every=1 if running else None)
    def panel():
        value=manager.snapshot(key) if key else None
        if not value: return
        state=value.get("state")
        if state:
            meta=state.get("auto_category",{})
            st.write("Chủ đề: "+(meta.get("selected_topic") or "Đang chọn…"))
            st.caption(meta.get("selection_reason") or "")
            for step,label in [("discovery","Khám phá chủ đề"),("research","Tìm thông tin"),("director","Kịch bản"),("assets","Asset"),("render","Render")]:
                entry=state["steps"][step]
                fraction=1. if entry["status"] in {"done","skipped"} else state.get("step_progress",0.) if state.get("current_step")==step else 0.
                st.progress(fraction,text=f"{label} · {entry['status']} · {entry['elapsed_sec']:.1f}s")
            with st.expander("Nhật ký ngắn / nguồn đang đọc",expanded=running): st.text("\n".join(state.get("log",[])[-15:]))
        if value.get("error"): st.error(value["error"])
        if debug and value.get("traceback"):
            with st.expander("Traceback đã che key"): st.code(value["traceback"])
        if running and value["status"] not in {"queued","running"}: st.rerun()
    panel()
    current=Path(snapshot["project"]) if snapshot and snapshot.get("project") else project
    if current is None or not (current/"run_state.json").exists(): return
    try:
        state=read_json(current/"run_state.json",allow_stale=True)
        if "auto_category" not in state: return
        if state["status"]=="waiting_review":
            st.info("Đang chờ duyệt kịch bản. Lưu chỉnh sửa rồi bấm Tiếp tục.")
            edit_page(settings,current,topic,debug,diagnostics)
        if state["status"]!="done" and not running:
            if st.button("Tiếp tục",type="primary",key="auto_resume"):
                st.session_state["auto_worker"]=manager.submit_auto({},settings,resume=current);st.rerun()
        if state["status"]=="done":
            meta=state["auto_category"];summary=state.get("summary",{})
            st.success("Đã hoàn tất: "+meta["selected_topic"])
            st.caption(f"{summary.get('facts',0)} fact · {summary.get('sources_used',0)} nguồn · nội dung có hỗ trợ AI")
            show_result(state["render_result"],current,diagnostics)
            for entry in state["steps"].values():
                for warning in entry.get("warnings",[]): st.warning(warning)
            report=current/"report.md"
            if report.exists(): st.download_button("Tải báo cáo",report.read_bytes(),file_name="report.md")
            if st.button("Tạo video khác trong danh mục này",disabled=bool(active) or not ready):
                params["category"]=meta["config"]["category"]
                st.session_state["auto_worker"]=manager.submit_auto(params,settings)
                st.session_state["auto_ai_nonce"]=st.session_state.get("auto_ai_nonce",0)+1
                st.rerun()
    except Exception as error:
        diagnostics.record_exception(error,"UI danh mục tự động");st.error(diagnostics.redact(str(error)))
