"""Topic cards, RSS settings and handoff to the existing create-video form."""
from datetime import datetime
import streamlit as st
import yaml
from config.categories import load_categories,save_categories
from pipeline.discovery_jobs import DiscoveryJobs
from pipeline.discover import auto_pick,topic_config
from pipeline.topics_history import history_rows,already_made
from sources.topic_discovery import raw_suggestion
from utils.cache import cache_key
from app.views.create_video import pipeline_jobs

@st.cache_resource
def discovery_jobs(): return DiscoveryJobs()


def handoff(topic,category=None,suggestion=None):
    st.session_state["discovery_prefill"]={"topic":topic,"category":category,"suggestion":suggestion}
    st.session_state["pending_page"]="Tạo video"
    st.rerun()


def render(settings,project,topic,debug,diagnostics):
    st.title("Khám phá chủ đề")
    st.caption("RSS và tìm kiếm tin mới → chọn một sự kiện cụ thể → Research kiểm chứng nguồn. Không lấy metadata làm facts.")
    try: categories=load_categories()
    except Exception as error:
        st.error("Không đọc được config/categories.yaml: "+diagnostics.redact(str(error)))
        return
    with st.expander("Sửa danh mục, từ khóa và RSS"):
        source=yaml.safe_dump(categories.model_dump(mode="json"),allow_unicode=True,sort_keys=False)
        edited=st.text_area("Cấu hình YAML",value=source,height=280,key="discovery_categories_yaml")
        st.caption("enabled: false để tắt danh mục/RSS; region: vn hoặc global. Chỉ nhập URL RSS chính thức.")
        if st.button("Lưu cấu hình RSS"):
            try:
                save_categories(yaml.safe_load(edited));st.success("Đã lưu config/categories.yaml.");st.rerun()
            except Exception as error: st.error(diagnostics.redact(str(error)))
    enabled=[c.name for c in categories.categories if c.enabled]
    if not enabled: st.warning("Tất cả danh mục đã tắt. Bật lại trong cấu hình để tìm chủ đề.")
    else:
        with st.form("discover_topics"):
            category=st.selectbox("Danh mục",enabled,key="discover_category")
            region=st.selectbox("Khu vực",["vn","global","both"],index=2,format_func=lambda x:{"vn":"Việt Nam","global":"Quốc tế","both":"Cả hai"}[x])
            days=st.selectbox("Tin trong bao nhiêu ngày",[1,3,7],index=1)
            count=st.selectbox("Số gợi ý",[5,10])
            youtube=st.checkbox("Bổ sung YouTube trends",value=False)
            submitted=st.form_submit_button("Gợi ý chủ đề",type="primary")
        manager=discovery_jobs()
        if submitted:
            st.session_state["discovery_worker"]=manager.submit(settings,category=category,region=region,time_window_days=days,count=count,use_youtube=youtube)
        key=st.session_state.get("discovery_worker")
        snapshot=manager.snapshot(key) if key else None
        running=bool(snapshot and snapshot["status"]=="running")
        @st.fragment(run_every=1 if running else None)
        def panel():
            value=manager.snapshot(key) if key else None
            if not value: return
            if value["status"]=="running": st.info("Đang đọc RSS và gom nhóm tin…")
            elif value["status"]=="failed": st.error(value["error"])
            elif value.get("result") and st.session_state.get("discovery_loaded")!=key:
                st.session_state["discovery_result"]=value["result"]
                st.session_state["discovery_loaded"]=key
                st.rerun()
        panel()
    result=st.session_state.get("discovery_result")
    if result:
        with st.expander("Chẩn đoán từng nguồn RSS/tìm kiếm"):
            st.dataframe(result["sources"],hide_index=True)
            for warning in result["warnings"]: st.warning(diagnostics.redact(warning))
        if result.get("gemini_error"): st.warning("Gemini không khả dụng; các thẻ tin thô vẫn chọn được, Research sẽ kiểm chứng lại.")
        if not result["topics"]: st.info("Chưa có chủ đề mới phù hợp; đổi danh mục/khoảng ngày hoặc tự nhập chủ đề bên dưới.")
        rows=history_rows(settings.output_dir)
        selected=[]
        for index,suggestion in enumerate(result["topics"]):
            identity=result["generated_at"]+str(index)
            with st.container(border=True):
                title=st.text_input("Chủ đề đề xuất",value=suggestion["topic"],key="discover_title_"+identity,max_chars=220)
                made=already_made(title,rows,source_urls=suggestion["source_urls"])
                st.badge("Đã làm trong 14 ngày" if made else "Chưa làm",color="orange" if made else "green")
                st.write(suggestion["why_now"])
                st.write("Góc kể: "+suggestion["angle"])
                st.caption(f"Độ nóng {suggestion['score']}/10 · {suggestion['score_reason']}")
                for url in suggestion["source_urls"]: st.link_button("Nguồn: "+url,url)
                if st.checkbox("Chọn chủ đề",key="discover_select_"+identity,disabled=bool(made)):
                    selected.append({"topic":title,"category":result["category"],"suggestion":suggestion})
                if st.button("Tạo video từ chủ đề này",key="discover_create_"+identity,disabled=bool(made) or not title.strip()):
                    handoff(title,result["category"],suggestion)
        if selected and st.button("Đưa các chủ đề đã chọn vào hàng chờ"):
            st.session_state["discovery_queue"]=selected
            st.success(f"Đã lưu {len(selected)} chủ đề vào hàng chờ; mỗi lần tạo một video.")
        chosen=auto_pick(result,settings)
        manager=pipeline_jobs()
        if st.button("Tự chọn chủ đề tốt nhất và tạo video",type="primary",disabled=not chosen or bool(manager.active())):
            config=topic_config(chosen,result["category"],review=True)
            key=manager.submit(config,settings)
            st.session_state["pipeline_worker"]=key;st.session_state["pipeline_follow"]=key
            st.session_state["create_mode"]="review"
            handoff(config.topic,result["category"],chosen)
        if result.get("excluded_history"):
            with st.expander("Các chủ đề đã làm — bỏ khỏi đề xuất"):
                for entry in result["excluded_history"]: st.write("Đã làm: "+entry["topic"])
        with st.expander("Danh sách tin thô"):
            st.dataframe(result["raw_news"],hide_index=True,column_config={"url":st.column_config.LinkColumn("Nguồn")})
            if result["raw_news"]:
                item=st.selectbox("Chọn tin thô",result["raw_news"],format_func=lambda r:r["title"])
                if st.button("Dùng tiêu đề tin thô"):
                    group=next((g for g in result["groups"] if any(a["url"]==item["url"] for a in g["articles"])),None)
                    if group is None:
                        group={"id":cache_key(item["url"])[:16],"articles":[item],"source_count":1,"youtube_views":0,"youtube_videos":0}
                    category=next((c for c in categories.categories if c.name==result["category"]),categories.categories[0])
                    suggested=raw_suggestion(group,category,datetime.fromisoformat(result["generated_at"]),7)
                    handoff(item["title"],result["category"],suggested.model_dump(mode="json"))
    queue=st.session_state.get("discovery_queue",[])
    if queue:
        with st.expander("Hàng chờ chủ đề đã chọn",expanded=True):
            item=st.selectbox("Chọn chủ đề trong hàng chờ",queue,format_func=lambda x:x["topic"])
            if st.button("Mở form cho chủ đề trong hàng chờ"): handoff(item["topic"],item["category"],item["suggestion"])
    manual=st.text_input("Tự nhập chủ đề",key="discovery_manual",max_chars=500)
    if st.button("Dùng chủ đề tự nhập",disabled=not manual.strip()): handoff(manual.strip())
