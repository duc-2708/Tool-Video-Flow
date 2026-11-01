"""Kho video đã làm: Xem lại, phát video MP4, tải về và xem chi tiết dự án."""
from pathlib import Path
import streamlit as st

from config.settings import get_settings
from pipeline.projects import list_projects, read_json


def render(settings, project, topic, debug, diagnostics):
    st.markdown("""
        <div class="main-card">
            <h2 style="margin: 0; color: #ffd60a; font-weight: 800; font-size: 1.8rem;">
                🎞️ Kho Video Đã Tạo
            </h2>
            <p style="margin: 4px 0 0 0; color: #a1a1aa; font-size: 0.95rem;">
                Toàn bộ video MP4 đã được render hoàn chỉnh. Bạn có thể xem trực tiếp, kiểm tra thông số hoặc tải file về máy.
            </p>
        </div>
    """, unsafe_allow_html=True)

    projects = list_projects(settings.output_dir)
    video_items = []

    for p in projects:
        render_dir = p.path / "render"
        if render_dir.is_dir():
            mp4s = list(render_dir.glob("*.mp4"))
            if mp4s:
                mp4_file = mp4s[0]
                brief_topic = ""
                if (p.path / "brief.json").is_file():
                    try:
                        b = read_json(p.path / "brief.json")
                        brief_topic = b.get("topic", "")
                    except Exception:
                        pass

                video_items.append({
                    "project_name": p.name,
                    "project_path": p.path,
                    "topic": brief_topic or p.topic,
                    "file_path": mp4_file,
                    "filename": mp4_file.name,
                    "size_mb": round(mp4_file.stat().st_size / (1024 * 1024), 2),
                    "mtime": mp4_file.stat().st_mtime
                })

    # Sắp xếp mới nhất lên đầu
    video_items.sort(key=lambda x: x["mtime"], reverse=True)

    if not video_items:
        st.info("Hiện chưa có video nào được render hoàn tất trong thư mục output/. Hãy tạo video đầu tiên!")
        return

    # Bộ lọc & Thống kê
    col_stat1, col_stat2, col_search = st.columns([1, 1, 2])
    col_stat1.metric("Tổng số video", len(video_items))
    total_size = round(sum(v["size_mb"] for v in video_items), 1)
    col_stat2.metric("Tổng dung lượng", f"{total_size} MB")
    search_query = col_search.text_input("🔍 Tìm kiếm theo chủ đề / tên file", value="", key="search_gallery")

    filtered = video_items
    if search_query.strip():
        q = search_query.strip().lower()
        filtered = [v for v in video_items if q in v["topic"].lower() or q in v["filename"].lower()]

    st.write(f"Hiển thị **{len(filtered)}** video:")

    # Hiển thị dạng lưới 2 cột
    cols = st.columns(2)
    for idx, item in enumerate(filtered):
        c = cols[idx % 2]
        with c:
            with st.container():
                st.markdown(f"""
                    <div style="background: #141417; border: 1px solid #27272a; border-radius: 12px; padding: 14px; margin-bottom: 18px;">
                        <div style="color: #ffd60a; font-weight: 700; font-size: 1.05rem; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                            {item['topic']}
                        </div>
                        <div style="color: #71717a; font-size: 0.8rem; margin-bottom: 10px;">
                            📁 {item['filename']} · ⚖️ {item['size_mb']} MB
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                try:
                    video_bytes = item["file_path"].read_bytes()
                    st.video(video_bytes)
                except Exception as e:
                    st.error(f"Không thể phát video: {e}")

                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    st.download_button(
                        label="⬇️ Tải Video MP4",
                        data=video_bytes,
                        file_name=item["filename"],
                        mime="video/mp4",
                        key=f"dl_{item['project_name']}_{idx}",
                        use_container_width=True
                    )
                with bcol2:
                    if st.button("🔎 Mở Project", key=f"sel_{item['project_name']}_{idx}", use_container_width=True):
                        st.session_state["project_choice"] = item["project_name"]
                        st.session_state["ui_page"] = "Render"
                        st.rerun()
