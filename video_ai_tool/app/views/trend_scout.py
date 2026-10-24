"""Trend metadata UI; selected topics always return to verified Research."""
import streamlit as st
from config.categories import categories_for
from config.trends import load_trends
from db.repository import Repository
from pipeline.trend_scout_jobs import TrendScoutJobs
from app.views.discover import handoff


@st.cache_resource
def scout_jobs():
    return TrendScoutJobs()


def render(settings, project, topic, debug, diagnostics):
    st.title("Trend Scout")
    st.caption("Chỉ học tín hiệu xu hướng từ metadata. Không tải video, không lấy transcript. Researcher sẽ kiểm chứng bằng bài viết gốc.")
    try:
        cfg = load_trends(settings)
        categories = [c.name for c in categories_for(settings).categories if c.enabled]
        usage = Repository.for_settings(settings).trend_usage()
    except Exception as error:
        st.error(diagnostics.redact(str(error)))
        return
    st.metric("ScrapeCreators: lượt HTTP dự trù hôm nay (UTC)", f"{usage['requests']} / {cfg.TREND_DAILY_CREDIT_LIMIT}")
    st.caption(f"Credit API báo: {usage['reported_credits'] or 0:g} từ {usage['reported_calls']} phản hồi. Lỗi/timeout vẫn tính lượt dự trù; đây không phải số dư dashboard.")
    if not cfg.enabled:
        st.info("Trend Scout đang tắt. Đặt enabled: true trong config/trends.yaml để bật; tắt giữ luồng RSS/news cũ.")
    with st.expander("Nguồn và điều kiện"):
        for name, active in cfg.providers.items():
            available = name not in {"weibo", "bilibili"}
            if name == "scrapecreators_tiktok": available = bool(settings.scrapecreators_api_key.get_secret_value().strip())
            if name == "youtube_trending": available = bool(settings.youtube_api_key.get_secret_value().strip())
            st.write(f"{name}: {'bật' if cfg.enabled and active and available else 'bỏ qua/tắt'}")
        st.caption("Weibo/Bilibili: CHƯA XÁC NHẬN endpoint công khai ổn định. Region TikTok là proxy, không bảo đảm nguồn gốc video.")
    if categories:
        with st.form("trend_scan"):
            category = st.selectbox("Danh mục", categories, key="trend_category")
            region = st.selectbox("Khu vực", ["vn", "global", "both"], key="trend_region")
            count = st.selectbox("Số chủ đề", [5, 10], key="trend_count")
            submitted = st.form_submit_button("Quét xu hướng", type="primary", disabled=not cfg.enabled)
        manager = scout_jobs()
        if submitted:
            st.session_state["trend_worker"] = manager.submit(settings, category=category, region=region, count=count)
        key = st.session_state.get("trend_worker")
        snapshot = manager.snapshot(key) if key else None
        running = bool(snapshot and snapshot["status"] == "running")

        @st.fragment(run_every=1 if running else None)
        def panel():
            value = manager.snapshot(key) if key else None
            if not value: return
            if value["status"] == "running":
                st.info("Đang quét metadata và gom nhóm chủ đề…")
            elif value["status"] == "failed":
                st.error(value["error"])
            elif st.session_state.get("trend_loaded") != key:
                st.session_state["trend_result"] = value["result"]
                st.session_state["trend_loaded"] = key
                st.rerun()
        panel()
    result = st.session_state.get("trend_result")
    if result:
        for warning in result["warnings"]:
            st.warning(diagnostics.redact(warning))
        rows = []
        platforms = {r["url"]: r["platform"] for r in result["items"]}
        for row in result["trend_topics"]:
            rows.append({"Chủ đề": row["topic_title_vi"], "Điểm tổng": row["score_total"], "Độ nóng": row["score_hot"],
                "Hợp danh mục": row["score_fit_category"], "Khán giả VN": row["score_vietnam_audience"],
                "Nền tảng": ", ".join(sorted({platforms.get(u, "metadata") for u in row["sources"]})), "Nguồn": row["sources"][0]})
        st.dataframe(rows, hide_index=True, column_config={"Nguồn": st.column_config.LinkColumn("Nguồn tín hiệu")})
        for index, (row, suggestion) in enumerate(zip(result["trend_topics"], result["topics"])):
            with st.container(border=True):
                title = st.text_input("Chủ đề", value=row["topic_title_vi"], max_chars=220, key=f"trend_title_{result['generated_at']}_{index}")
                st.write(row["why_hot"])
                st.write("Góc kể: "+" · ".join(row["angle_suggestions"]))
                for url in row["sources"]:
                    st.link_button("Tín hiệu: "+platforms.get(url, "nguồn"), url)
                if st.button("Dùng chủ đề này", key=f"trend_use_{index}", disabled=not title.strip()):
                    updated = {**suggestion, "topic": title.strip()}
                    handoff(title.strip(), result["category"], updated)
        if not rows:
            st.info("Chưa có chủ đề mới phù hợp. Có thể tự nhập ý tưởng bên dưới.")
        with st.expander("Chẩn đoán nguồn / lịch sử đã làm"):
            st.json({"sources": result["sources"], "excluded_history": result["excluded_history"]})
    with st.form("trend_inspiration"):
        manual = st.text_area("Nhập chủ đề cảm hứng", max_chars=500, key="trend_manual", placeholder="Tên chủ đề hoặc mô tả ngắn video bạn đã thấy")
        use = st.form_submit_button("Đưa thẳng vào Researcher")
    if use:
        if manual.strip():
            st.session_state["pending_research_topic"] = manual.strip()
            st.session_state["pending_page"] = "Research"
            st.rerun()
        else:
            st.warning("Nhập chủ đề trước khi tiếp tục.")
