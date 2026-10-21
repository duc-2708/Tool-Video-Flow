# file: app/views/research.py
"""Trang Research mỏng, gọi trực tiếp hàm dùng chung với CLI."""
from pathlib import Path
import json
import streamlit as st
from agents.researcher import run_research
from app.ui_errors import error_details
from config.settings import Settings
from pipeline.projects import create_project, load_brief, read_json
from utils.diagnostics import Diagnostics
from schemas.languages import LABELS
from sources.web_search import search_summary


def display_error(message: str, trace: str, debug: bool) -> None:
    st.error(message)
    if debug:
        with st.expander("Traceback (đã che credentials)"):
            st.code(trace, language="text")
    st.caption("Chi tiết đã lưu vào logs/researcher_errors.log.")


def show_error(error: BaseException, diagnostics: Diagnostics, debug: bool) -> None:
    diagnostics.record_exception(error, "Streamlit Research")
    message, trace = error_details(error, diagnostics)
    display_error(message, trace, debug)


def render(settings: Settings, project: Path | None, topic: str, debug: bool, diagnostics: Diagnostics) -> None:
    st.title("Research")
    st.caption("Thu thập nguồn → Research Brief. Tiếp theo: Edit Plan → Assets. Render sẽ được thêm ở giai đoạn sau.")
    scope = project.name if project else "new"
    with st.form(f"research_form_{scope}"):
        entered_topic = st.text_input("Chủ đề", value=topic, max_chars=500, key=f"research_topic_{scope}",
                                     placeholder="Ví dụ: trong dựng video cho người mới")
        enable_youtube = st.checkbox("Bật YouTube trends", value=False)
        source_languages = st.multiselect("Ngôn ngữ nguồn",list(LABELS),default=["vi","en"],format_func=LABELS.get)
        output_language = st.selectbox("Ngôn ngữ kịch bản",["vi"],format_func=LABELS.get)
        web_limit = st.number_input("Số nguồn web tối đa", min_value=1, max_value=12, value=6, step=1)
        youtube_days = st.number_input("YouTube trends: số ngày gần đây", min_value=1, max_value=3650, value=14, step=1)
        vietnamese = st.checkbox("Ưu tiên video tiếng Việt", value=True)
        submitted = st.form_submit_button("Chạy Researcher", type="primary",
                                          disabled=not bool(settings.gemini_api_key.get_secret_value().strip() and settings.gemini_model.strip()))
    if submitted:
        st.session_state.pop("research_error", None)
        if not entered_topic.strip():
            st.warning("Hãy nhập chủ đề trước khi chạy.")
        else:
            destination = project
            progress = st.empty()
            try:
                # Kiểm tra key trước khi tạo thư mục; không tạo project rỗng vì thiếu cấu hình.
                settings.require_key("gemini")
                settings.require_gemini_model()
                destination = destination or create_project(settings.output_dir, entered_topic)
                with st.spinner("Researcher đang xử lý…"):
                    result = run_research(entered_topic, settings, web_limit=int(web_limit),
                        use_youtube=enable_youtube, youtube_days=int(youtube_days), youtube_vietnamese=vietnamese, output_dir=destination,
                        source_languages=source_languages,output_language=output_language,
                        progress=lambda message: progress.info(diagnostics.redact(message)), debug=False)
                st.session_state["pending_project"] = result.parent.name
                st.session_state["research_notice"] = "Researcher hoàn tất. Brief và nguồn đối chiếu đã được lưu."
                st.rerun()
            except Exception as error:
                progress.empty()
                if destination is not None:
                    diagnostics.record_exception(error, "Streamlit Research run failed")
                    message, trace = error_details(error, diagnostics)
                    st.session_state["research_error"] = {"project": destination.name, "message": message, "trace": trace}
                    st.session_state["pending_project"] = destination.name
                    st.rerun()
                show_error(error, diagnostics, debug)
    previous_error = st.session_state.get("research_error")
    if previous_error and project and previous_error["project"] == project.name:
        display_error(previous_error["message"], previous_error["trace"], debug)
    if project is None:
        st.info("Nhập chủ đề và chạy Researcher để tạo project mới, hoặc chọn project có sẵn ở sidebar.")
        return
    st.caption("Project: " + diagnostics.redact(project.name))
    try:
        report = read_json(project/"sources.json").get("search_diagnostics")
        if report:
            st.info(search_summary(report))
            with st.expander("Chẩn đoán từng truy vấn và URL"):
                for query in report.get("queries",[]):
                    st.write(query["query"])
                    st.caption(f"Tìm được {query['found']}, giữ {query.get('kept',0)}, loại {query.get('discarded',0)}")
                    st.dataframe(query.get("decisions",[]),hide_index=True)
    except (OSError,ValueError):
        pass
    if not (project / "brief.json").exists():
        st.info("Project chưa có brief.json. Chạy Researcher bằng form phía trên.")
        return
    try:
        brief = load_brief(project)
        # Sanitize cả artifact khi hiển thị/tải; không bao giờ đưa Settings/SecretStr vào widget.
        brief_data = json.loads(diagnostics.redact(brief.model_dump_json()))
    except Exception as error:
        show_error(error, diagnostics, debug)
        return
    overview, sources_tab, raw_tab = st.tabs(["Research Brief", "Nguồn đối chiếu", "JSON thô"])
    with overview:
        st.subheader(brief_data["topic"])
        if len(brief.facts)<8:
            st.warning("dữ liệu mỏng, kịch bản sẽ ít chi tiết")
        source_rows = []
        try:
            source_rows = read_json(project/"sources.json").get("sources",[])
        except (OSError,ValueError):
            pass
        st.metric("Số nguồn bài viết",len(source_rows))
        if source_rows:
            st.dataframe([{"source_name":row.get("source_name"),"content_length":len(row.get("text","")),
                "published_at":row.get("published_at"),"url":row.get("url")} for row in source_rows],hide_index=True,
                column_config={"source_name":"Nguồn","content_length":"Ký tự bài viết","published_at":"Ngày đăng","url":st.column_config.LinkColumn("Bài viết")})
        for field,label in [("key_numbers","Số liệu chính"),("timeline","Dòng thời gian"),("why_it_matters","Vì sao đáng quan tâm"),
                ("counterpoints","Ý kiến trái chiều"),("glossary","Thuật ngữ")]:
            if brief_data.get(field):
                st.markdown("### "+label)
                st.dataframe(brief_data[field],hide_index=True,column_config={"text":"Chi tiết","fact_ids":"Fact đối chiếu"})
        if brief_data.get("story_angles"):
            st.markdown("### Góc kể chi tiết")
            st.dataframe(brief_data["story_angles"],hide_index=True)
        grounding = {}
        try:
            source_report = read_json(project / "sources.json").get("grounding", {})
            fields = ("returned", "kept", "discarded", "trimmed")
            if (isinstance(source_report, dict) and all(type(source_report.get(key)) is int and source_report[key] >= 0 for key in fields)
                    and source_report["kept"] == len(brief_data["facts"])
                    and source_report["returned"] == source_report["kept"] + source_report["discarded"]
                    and source_report["trimmed"] <= source_report["kept"]):
                grounding = source_report
        except (OSError, ValueError):
            # Older projects can have brief.json without source statistics.
            pass
        kept, discarded, trimmed = st.columns(3)
        kept.metric("Fact giữ lại", len(brief_data["facts"]))
        discarded.metric("Fact bị loại", grounding.get("discarded", "—"))
        trimmed.metric("Quote được rút gọn", grounding.get("trimmed", "—"))
        if grounding:
            st.caption(f"Đối chiếu brief đã lưu: {grounding['returned']} fact Gemini trả về. Lý do loại/rút gọn nằm trong Rủi ro và lưu ý và tab Nguồn đối chiếu.")
        else:
            st.caption("Project cũ chưa có thống kê fact bị loại; chạy Researcher lại để cập nhật.")
        st.markdown("### Dữ kiện và nguồn")
        if brief_data["facts"]:
            st.dataframe([{key: fact.get(key) for key in ("fact_vi","evidence_quote","source_lang","source_name","published_at","confidence","source_url")} | {"fact_vi":fact.get("fact_vi") or fact["claim"]} for fact in brief_data["facts"]],
                hide_index=True, column_config={"claim": st.column_config.TextColumn("Thông tin", width="large"),
                    "fact_vi":st.column_config.TextColumn("Dữ kiện tiếng Việt",width="large"),"evidence_quote":st.column_config.TextColumn("Quote nguyên văn",width="large"),
                    "source_lang":"Ngôn ngữ gốc","source_name":"Tên báo","published_at":"Ngày đăng",
                    "confidence": st.column_config.TextColumn("Độ tin cậy"),
                    "source_url": st.column_config.LinkColumn("Nguồn", display_text="Mở nguồn")})
        else:
            st.warning("Chưa có fact đủ dẫn chứng. Không dùng tín hiệu xã hội như sự thật chắc chắn.")
        with st.expander("Truy vấn tìm kiếm đã dùng"):
            if brief_data.get("search_queries"):
                st.dataframe(brief_data["search_queries"],hide_index=True)
            else:
                st.caption("Project cũ chưa có nhật ký truy vấn; chạy Research lại để cập nhật.")
        st.markdown("### Góc tiếp cận")
        st.dataframe(brief_data["angle_candidates"], hide_index=True,
                     column_config={"angle": "Góc tiếp cận", "why": "Lý do"})
        for label, field in [("Hooks", "hooks"), ("Câu hỏi của người xem", "audience_questions"),
                             ("Từ khóa", "keywords"), ("Rủi ro và lưu ý", "risks")]:
            st.markdown(f"### {label}")
            if not brief_data[field]:
                st.caption("Chưa có dữ liệu.")
            for item in brief_data[field]:
                st.write("• " + item)
        if brief_data["trends"]:
            st.markdown("### Tín hiệu quan sát")
            st.dataframe(brief_data["trends"], hide_index=True,
                column_config={"evidence_url": st.column_config.LinkColumn("Nguồn", display_text="Mở nguồn")})
        st.markdown("### YouTube trends · tín hiệu nội dung")
        st.caption("Video nhiều lượt xem trong kết quả tìm kiếm ở cửa sổ đã chọn; không chứng minh tốc độ lan truyền hay tính đúng của nội dung. Facts chỉ dựa trên nguồn web.")
        signals = brief_data.get("trend_signals", [])
        if signals:
            st.dataframe([{field: signal.get(field) for field in ("title", "channel", "views", "likes", "comments", "published_at", "url")} for signal in signals],
                hide_index=True, column_config={"title": "Tiêu đề", "channel": "Kênh", "views": st.column_config.NumberColumn("Lượt xem", format="localized"),
                    "likes": "Like", "comments": "Bình luận", "published_at": "Ngày đăng", "url": st.column_config.LinkColumn("Video", display_text="Mở YouTube")})
            with st.expander("Hashtag và bình luận API chính thức"):
                for signal in signals:
                    st.write(signal["title"])
                    st.caption(" ".join(signal.get("hashtags", [])))
                    for comment in signal.get("top_comments", []):
                        st.text(comment)
        else:
            st.caption("Chưa có tín hiệu YouTube. Bật YouTube trends khi chạy Research; thiếu key hoặc hết quota sẽ tự bỏ qua.")
        insights = brief_data.get("trend_insights", {})
        for name, label in [("hook_patterns", "Mẫu hook"), ("keywords", "Từ khóa từ tín hiệu"),
                            ("common_questions", "Câu hỏi thường gặp"), ("angles", "Góc khai thác từ tín hiệu")]:
            values = insights.get(name, [])
            if values:
                st.markdown("**" + label + "**")
                for insight in values:
                    st.write(insight["text"])
                    st.caption("Lý do: " + insight["reason"])
                    for url in insight["evidence_urls"]:
                        st.link_button("Video đối chiếu tín hiệu", url)
    with sources_tab:
        if not (project / "sources.json").exists():
            st.info("Project chưa có sources.json.")
        else:
            try:
                data = read_json(project / "sources.json")
                st.json(json.loads(diagnostics.redact(json.dumps(data, ensure_ascii=False))), expanded=1)
            except Exception as error:
                show_error(error, diagnostics, debug)
    with raw_tab:
        raw = json.dumps(brief_data, ensure_ascii=False, indent=2)
        st.code(raw, language="json")
        st.download_button("Tải brief.json", data=raw.encode("utf-8"), file_name="brief.json",
                           mime="application/json", on_click="ignore")
