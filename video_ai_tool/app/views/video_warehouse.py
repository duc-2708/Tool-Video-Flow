"""Kho video đã làm: Xem lại, phát video MP4, tải về và quản lý phân trang tối ưu RAM."""
from datetime import datetime
import html
from pathlib import Path
import subprocess
import streamlit as st

from app.ui_kit import chip_html, section_header, stat_html
from pipeline.projects import list_projects, read_json


def ensure_thumbnail(mp4_path: Path) -> Path | None:
    """Tạo cache thumbnail 1 giây đầu bằng ffmpeg mà không nạp video vào RAM."""
    thumb_path = mp4_path.parent / "thumb.jpg"
    if thumb_path.is_file():
        return thumb_path
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        subprocess.run(
            [
                get_ffmpeg_exe(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                "00:00:01",
                "-i",
                str(mp4_path),
                "-vframes",
                "1",
                "-q:v",
                "2",
                "-y",
                str(thumb_path),
            ],
            check=True,
            timeout=10,
        )
        if thumb_path.is_file():
            return thumb_path
    except Exception:
        pass
    return None


if hasattr(st, "dialog"):
    @st.dialog("Phát video hoàn chỉnh")
    def video_player_dialog(video_path: Path, title: str):
        st.write(f"**{title}**")
        st.video(str(video_path))


def render(settings, project, topic, debug, diagnostics):
    section_header("THƯ VIỆN", "Kho video đã sản xuất", accent_word="sản xuất")

    projects = list_projects(settings.output_dir)
    video_items = []

    for p in projects:
        render_dir = p.path / "render"
        has_mp4 = False
        if render_dir.is_dir():
            mp4s = sorted(render_dir.glob("*.mp4"))
            if mp4s:
                has_mp4 = True
                mp4_file = mp4s[0]
                brief_topic = ""
                if (p.path / "brief.json").is_file():
                    try:
                        b = read_json(p.path / "brief.json")
                        brief_topic = b.get("topic", "")
                    except Exception:
                        pass

                quality_score = None
                report_file = render_dir / "report.json"
                if report_file.is_file():
                    try:
                        rep = read_json(report_file)
                        quality_score = rep.get("quality_score") or rep.get("overall_score")
                    except Exception:
                        pass

                video_items.append({
                    "project_name": p.name,
                    "project_path": p.path,
                    "topic": brief_topic or p.topic,
                    "file_path": mp4_file,
                    "filename": mp4_file.name,
                    "size_mb": round(mp4_file.stat().st_size / (1024 * 1024), 2),
                    "mtime": mp4_file.stat().st_mtime,
                    "status": "Xong",
                    "score": quality_score,
                })

        if not has_mp4:
            run_state = p.path / "run_state.json"
            status = "Đang dựng"
            if run_state.is_file():
                try:
                    s_data = read_json(run_state)
                    if s_data.get("status") in {"error", "failed"}:
                        status = "Lỗi"
                except Exception:
                    pass
            video_items.append({
                "project_name": p.name,
                "project_path": p.path,
                "topic": p.topic or p.name,
                "file_path": None,
                "filename": "Chưa có MP4",
                "size_mb": 0.0,
                "mtime": p.path.stat().st_mtime,
                "status": status,
                "score": None,
            })

    if not video_items:
        st.info("Hiện chưa có dự án nào trong thư mục output/. Hãy tạo video đầu tiên!")
        return

    # Bộ lọc & Thống kê
    c_st1, c_st2, c_search, c_filter, c_sort = st.columns([1, 1, 2, 1.2, 1.2])
    total_completed = len([v for v in video_items if v["status"] == "Xong"])
    c_st1.metric("Video hoàn thành", total_completed)
    total_size = round(sum(v["size_mb"] for v in video_items), 1)
    c_st2.metric("Tổng dung lượng", f"{total_size} MB")

    search_query = c_search.text_input("Tìm kiếm chủ đề / tên file", value="", key="search_warehouse", placeholder="Nhập từ khóa...")
    status_filter = c_filter.selectbox("Trạng thái", ["Tất cả", "Xong", "Đang dựng", "Lỗi"], key="filter_status_warehouse")
    sort_by = c_sort.selectbox("Sắp xếp", ["Mới nhất", "Cũ nhất", "Dung lượng lớn", "Điểm cao"], key="sort_warehouse")

    # Lọc danh sách
    filtered = video_items
    if search_query.strip():
        q = search_query.strip().lower()
        filtered = [v for v in filtered if q in v["topic"].lower() or q in v["filename"].lower()]

    if status_filter != "Tất cả":
        filtered = [v for v in filtered if v["status"] == status_filter]

    # Sắp xếp danh sách
    if sort_by == "Mới nhất":
        filtered.sort(key=lambda x: x["mtime"], reverse=True)
    elif sort_by == "Cũ nhất":
        filtered.sort(key=lambda x: x["mtime"])
    elif sort_by == "Dung lượng lớn":
        filtered.sort(key=lambda x: x["size_mb"], reverse=True)
    elif sort_by == "Điểm cao":
        filtered.sort(key=lambda x: (x["score"] or 0), reverse=True)

    st.markdown(f"<div style='color: #888888; font-size: 0.9rem; margin-bottom: 12px;'>Tìm thấy <b>{len(filtered)}</b> mục</div>", unsafe_allow_html=True)

    # PHÂN TRANG (8 video / trang)
    PAGE_SIZE = 8
    total_pages = max(1, (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE)
    curr_page = st.session_state.get("warehouse_page", 1)
    if curr_page > total_pages:
        curr_page = 1

    start_idx = (curr_page - 1) * PAGE_SIZE
    end_idx = min(len(filtered), start_idx + PAGE_SIZE)
    page_items = filtered[start_idx:end_idx]

    # LƯỚI 4 CỘT THẺ TRẮNG
    cols = st.columns(4)
    for idx, item in enumerate(page_items):
        col = cols[idx % 4]
        with col:
            t_chip = "green" if item["status"] == "Xong" else "gold" if item["status"] == "Đang dựng" else "red"
            date_str = datetime.fromtimestamp(item["mtime"]).strftime("%d/%m/%Y")
            topic_escaped = html.escape(item["topic"])
            filename_escaped = html.escape(item["filename"])

            # Thẻ trắng bo tròn 18px
            st.markdown(
                f"""
                <div class="ui-card-white" style="margin-bottom: 18px; display: flex; flex-direction: column; justify-content: space-between; min-height: 280px;">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <span style="font-size: 0.75rem; color: #666666;">{date_str}</span>
                            {chip_html(item['status'], t_chip)}
                        </div>
                        <div style="font-weight: 800; font-size: 0.95rem; color: #0A0A0A; line-height: 1.3; margin-bottom: 6px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;" title="{topic_escaped}">
                            {topic_escaped}
                        </div>
                        <div style="font-size: 0.75rem; color: #555555; margin-bottom: 12px;">
                            {filename_escaped} · {item['size_mb']} MB
                        </div>
                    </div>
                """,
                unsafe_allow_html=True,
            )

            # Lazy thumbnail
            if item["file_path"] and item["file_path"].is_file():
                thumb = ensure_thumbnail(item["file_path"])
                if thumb and thumb.is_file():
                    st.image(str(thumb), use_container_width=True)
                else:
                    st.markdown(
                        """
                        <div style="width: 100%; height: 120px; background: #EAEAEA; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #888888; font-size: 0.85rem; font-weight: 600; margin-bottom: 10px;">
                            9:16 MP4
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    if st.button("Phát", key=f"play_{item['project_name']}_{idx}", use_container_width=True):
                        if hasattr(st, "dialog"):
                            video_player_dialog(item["file_path"], item["topic"])
                        else:
                            st.video(str(item["file_path"]))

                with btn_c2:
                    try:
                        # Lazy read bytes khi người dùng tải
                        with open(item["file_path"], "rb") as f:
                            st.download_button(
                                label="Tải",
                                data=f.read(),
                                file_name=item["filename"],
                                mime="video/mp4",
                                key=f"dl_{item['project_name']}_{idx}",
                                use_container_width=True,
                            )
                    except Exception:
                        st.caption("Lỗi đọc file")
            else:
                st.markdown(
                    """
                    <div style="width: 100%; height: 120px; background: #F0F0F0; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #999999; font-size: 0.8rem; margin-bottom: 10px;">
                        Chưa xuất MP4
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            if st.button("Mở dự án", key=f"open_prj_{item['project_name']}_{idx}", use_container_width=True):
                st.session_state["project_choice"] = item["project_name"]
                st.session_state["ui_page"] = "Render"
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    # Thanh điều hướng phân trang
    if total_pages > 1:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        col_p1, col_p2, col_p3 = st.columns([2, 3, 2])
        with col_p2:
            p_prev, p_info, p_next = st.columns([1, 2, 1])
            if p_prev.button("Trang trước", disabled=(curr_page <= 1), use_container_width=True):
                st.session_state["warehouse_page"] = curr_page - 1
                st.rerun()
            p_info.markdown(f"<div style='text-align: center; line-height: 40px; color: #FFFFFF; font-weight: 700;'>Trang {curr_page} / {total_pages}</div>", unsafe_allow_html=True)
            if p_next.button("Trang sau", disabled=(curr_page >= total_pages), use_container_width=True):
                st.session_state["warehouse_page"] = curr_page + 1
                st.rerun()
