"""Motion Gallery UI view for Streamlit: preview, test and override animation recipes."""
from pathlib import Path
import streamlit as st

GALLERY_DIR = Path(__file__).resolve().parents[2] / "output/motion_gallery"
THUMBS_DIR = GALLERY_DIR / "thumbs"


def render(settings, project, topic, debug, diagnostics):
    st.header("Phòng thử hiệu ứng (Motion Gallery)")
    st.caption("Xem trước và kiểm định 14 công thức hoạt họa, biến thể và chú thích chuyển động 4b theo thời gian thực.")

    contact_sheet = GALLERY_DIR / "contact_sheet.png"
    if contact_sheet.is_file():
        st.subheader("Bảng mẫu tổng quan (Contact Sheet)")
        st.image(str(contact_sheet), caption="Khung hình đại diện của toàn bộ các công thức hoạt họa tại t=2.0s", use_container_width=True)

    st.divider()

    # List rendered MP4 clips
    clips = sorted(GALLERY_DIR.glob("*.mp4"))
    if not clips:
        st.info("Chưa có clip nào được kết xuất trong Phòng thử hiệu ứng. Hãy chạy lệnh: `python tools/motion_gallery.py` để kết xuất toàn bộ.")
        return

    clip_names = [c.stem for c in clips]
    selected_name = st.selectbox("Chọn công thức hoạt họa để xem chi tiết", clip_names)

    selected_clip = GALLERY_DIR / f"{selected_name}.mp4"
    selected_thumb = THUMBS_DIR / f"{selected_name}.jpg"

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader(f"Video Xem thử: {selected_name}")
        st.video(str(selected_clip))
        st.download_button("Tải video MP4", selected_clip.read_bytes(), file_name=selected_clip.name, mime="video/mp4")

    with col2:
        st.subheader("Thông tin kỹ thuật")
        st.markdown(f"""
        - **Tên công thức**: `{selected_name}`
        - **Kích thước mẫu**: 540x960 (scale 0.5), 24 fps
        - **Thời lượng**: 3.5 giây
        - **Cơ chế chuyển động**: Pure deterministic seek (anime.js / Mulberry32 / SVG)
        - **Độ sâu 3D & Parallax**: 3 lớp độc lập (background, content, foreground/annotations)
        - **An toàn giao diện**: Phủ $\ge 60\%$ ngang, $\ge 35\%$ dọc, cỡ chữ $\ge 38$px
        """)

        if selected_thumb.is_file():
            st.image(str(selected_thumb), caption=f"Khung hình tại t=2.0s ({selected_name})", width=280)
