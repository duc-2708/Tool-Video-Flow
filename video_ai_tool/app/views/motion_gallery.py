"""Motion Gallery UI view for Streamlit: preview, test and override animation recipes."""
from pathlib import Path
import streamlit as st

GALLERY_DIR = Path(__file__).resolve().parents[2] / "output/motion_gallery"
THUMBS_DIR = GALLERY_DIR / "thumbs"
LG_DEMO_DIR = Path(__file__).resolve().parents[2] / "output/light_glass_demo"


def render(settings, project, topic, debug, diagnostics):
    st.header("Phòng thử hiệu ứng (Motion Gallery)")
    st.caption("Xem trước và kiểm định các công thức hoạt họa, biến thể và chú thích chuyển động.")

    tab_standard, tab_light_glass = st.tabs(["Hiệu ứng Tiêu chuẩn (Engine 4b)", "Phong cách Light Glass (Pastel)"])

    with tab_standard:
        _render_standard_gallery()

    with tab_light_glass:
        _render_light_glass_gallery()


def _render_standard_gallery():
    contact_sheet = GALLERY_DIR / "contact_sheet.png"
    if contact_sheet.is_file():
        st.subheader("Bảng mẫu tổng quan (Contact Sheet)")
        st.image(str(contact_sheet), caption="Khung hình đại diện của toàn bộ các công thức hoạt họa tại t=2.0s", use_container_width=True)

    st.divider()

    clips = sorted(GALLERY_DIR.glob("*.mp4"))
    if not clips:
        st.info("Chưa có clip nào được kết xuất trong Phòng thử hiệu ứng tiêu chuẩn. Hãy chạy lệnh: `python tools/motion_gallery.py` để kết xuất toàn bộ.")
        return

    clip_names = [c.stem for c in clips]
    selected_name = st.selectbox("Chọn công thức hoạt họa để xem chi tiết", clip_names, key="standard_recipe_select")

    selected_clip = GALLERY_DIR / f"{selected_name}.mp4"
    selected_thumb = THUMBS_DIR / f"{selected_name}.jpg"

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader(f"Video Xem thử: {selected_name}")
        st.video(str(selected_clip))
        st.download_button("Tải video MP4", selected_clip.read_bytes(), file_name=selected_clip.name, mime="video/mp4", key="btn_down_std")

    with col2:
        st.subheader("Thông tin kỹ thuật")
        st.markdown(f"""
        - **Tên công thức**: `{selected_name}`
        - **Kích thước mẫu**: 540x960 (scale 0.5), 24 fps
        - **Thời lượng**: 3.5 giây
        - **Cơ chế chuyển động**: Pure deterministic seek (anime.js / Mulberry32 / SVG)
        - **Độ sâu 3D & Parallax**: 3 lớp độc lập (background, content, foreground/annotations)
        - **An toàn giao diện**: Phủ $\\ge 60\\%$ ngang, $\\ge 35\\%$ dọc, cỡ chữ $\\ge 38$px
        """)

        if selected_thumb.is_file():
            st.image(str(selected_thumb), caption=f"Khung hình tại t=2.0s ({selected_name})", width=280)


def _render_light_glass_gallery():
    st.subheader("Phong cách Light Glass (Pastel)")
    st.markdown("""
    Phong cách giao diện sáng, tối giản, sang trọng cho video tin công nghệ 9:16 (1080x1920) @ 30fps.
    - **Nền**: `#f4f5f8` với 2 blob mờ trôi chậm (chu kỳ 12s) + lưới chấm 28px (opacity 6%).
    - **Thương hiệu**: Nhận diện thương hiệu cố định trên top (`y=70px`), pill nguồn tin tức ở đáy (`y=1770px`).
    - **Khung thẻ**: Nền trắng bo góc 36px, đổ bóng mượt chuẩn Apple/Linear, chuyển động easing `cubic-bezier(.22, 1, .36, 1)`.
    - **Font**: Typography Inter offline tải tự động, không phụ thuộc Google Fonts / CDN bên ngoài.
    """)

    # Demo video preview if exists
    demo_video = LG_DEMO_DIR / "light_glass_demo.mp4"
    demo_contact_sheet = LG_DEMO_DIR / "contact_sheet.png"

    if demo_video.is_file():
        st.subheader("Video Trình diễn Tổng hợp (Demo 6 Shots)")
        col_v1, col_v2 = st.columns([1, 1])
        with col_v1:
            st.video(str(demo_video))
            st.download_button("Tải video Demo MP4", demo_video.read_bytes(), file_name="light_glass_demo.mp4", mime="video/mp4", key="btn_down_lg")
        with col_v2:
            st.markdown("""
            **Kịch bản bản tin mẫu (38s - 6 shots):**
            1. `lg_source_headline`: Tiêu đề & nguồn tin công nghệ (mở đầu)
            2. `lg_stat_hero`: Con số thống kê 78% hiệu năng (đếm số mượt)
            3. `lg_shot_features`: Danh sách 3 tính năng đột phá mới
            4. `lg_vs_compare`: Bảng so sánh 2 thế hệ vi xử lý
            5. `lg_note_card`: Nhận định chuyên gia công nghệ
            6. `lg_cta_profile`: Kêu gọi theo dõi & nhận diện kênh
            """)
            if demo_contact_sheet.is_file():
                st.image(str(demo_contact_sheet), caption="Bảng ghép 6 khung hình giữa các shot (Contact Sheet)", use_container_width=True)
    else:
        st.info("Chưa có video demo được kết xuất. Bạn có thể kết xuất video test bằng lệnh: `python tools/render_light_glass_demo.py`.")

    st.divider()
    st.subheader("Danh mục 6 Công thức Hoạt họa Light Glass")

    lg_recipes_info = [
        {
            "id": "lg_source_headline",
            "name": "1. lg_source_headline (Tiêu đề & Nguồn tin)",
            "role": "Shot mở đầu",
            "desc": "Header nguồn tin báo + Headline chữ lớn Inter 900 68px + badge/tóm tắt 3 dòng.",
            "sample_data": {
                "source": "TECH INSIGHT · MẪU",
                "title": "KIẾN TRÚC VI XỬ LÝ MỚI ĐẠT HIỆU NĂNG VƯỢT TRỘI",
                "highlight": ["HIỆU NĂNG", "VƯỢT TRỘI"],
                "text": "Kiến trúc chip thế hệ mới vừa được công bố với quy trình đóng gói tiên tiến.",
                "note": "Ghi chú: Dữ liệu mẫu giả định dùng cho kiểm thử thiết kế."
            }
        },
        {
            "id": "lg_stat_hero",
            "name": "2. lg_stat_hero (Con số Thống kê Khổng lồ)",
            "role": "Shot số liệu",
            "desc": "Con số 140px nổi bật, đếm mượt từ 0 đến giá trị đích trong 0.8s, đúng giá trị lời đọc.",
            "sample_data": {
                "label": "TĂNG TRƯỞNG HIỆU SUẤT XỬ LÝ AI",
                "value": 78,
                "unit": "%",
                "number_text": "78%",
                "text": "Tốc độ xử lý tác vụ trí tuệ nhân tạo tăng vọt so với thế hệ tiền nhiệm.",
                "note": "Ghi chú: Dữ liệu mẫu giả định dùng cho kiểm thử thiết kế."
            }
        },
        {
            "id": "lg_shot_features",
            "name": "3. lg_shot_features (Danh sách Điểm Nổi bật)",
            "role": "Shot tính năng",
            "desc": "2-4 hàng tính năng với icon tròn pastel, xuất hiện so-le (stagger 0.08s), trượt êm.",
            "sample_data": {
                "title": "3 CẢI TIẾN TRỌNG TÂM",
                "items": [
                    "Băng thông bộ nhớ hợp nhất mở rộng gấp đôi",
                    "Khả năng tiết kiệm điện năng giảm nhiệt lượng 35%",
                    "Tương thích hoàn toàn mọi framework AI hiện hành"
                ],
                "note": "Ghi chú: Dữ liệu mẫu giả định dùng cho kiểm thử thiết kế."
            }
        },
        {
            "id": "lg_vs_compare",
            "name": "4. lg_vs_compare (Bảng So sánh 2 Đối tượng)",
            "role": "Shot so sánh",
            "desc": "2 cột song song (cũ/đối thủ vs mới/nổi bật), badge tương ứng và gạch đầu dòng đối chiếu.",
            "sample_data": {
                "title": "SO SÁNH THẾ HỆ TIỀN NHIỆM VÀ MỚI",
                "bars": [
                    {"label": "Thế hệ cũ: 14 lõi hiệu năng, tiêu thụ 65W", "value": 45},
                    {"label": "Thế hệ mới: 24 lõi xử lý, tiêu thụ chỉ 38W", "value": 85}
                ],
                "note": "Ghi chú: Dữ liệu mẫu giả định dùng cho kiểm thử thiết kế."
            }
        },
        {
            "id": "lg_note_card",
            "name": "5. lg_note_card (Nhận định & Phân tích)",
            "role": "Shot phân tích",
            "desc": "Thẻ ghi chú với dấu ngoặc kép to mờ mờ, font Inter 600 sang trọng và phần chân thẻ tác giả.",
            "sample_data": {
                "label": "GHI CHÚ CHUYÊN GIA",
                "text": "Bước chuyển dịch kiến trúc này mở ra chu kỳ nâng cấp thiết bị mạnh mẽ nhất trong nửa thập kỷ qua.",
                "author": "Chuyên gia phân tích phần cứng · Mẫu",
                "note": "Ghi chú: Dữ liệu mẫu giả định dùng cho kiểm thử thiết kế."
            }
        },
        {
            "id": "lg_cta_profile",
            "name": "6. lg_cta_profile (Kêu gọi Hành động & Kênh)",
            "role": "Shot kết thúc",
            "desc": "Khung hồ sơ thương hiệu lớn, logo, tên kênh, handle, nút Follow giả lập viên thuốc nổi bật.",
            "sample_data": {
                "text": "BẤM THEO DÕI ĐỂ CẬP NHẬT TIN CÔNG NGHỆ MỚI NHẤT MỖI NGÀY",
                "channel_name": "TIN CÔNG NGHỆ",
                "channel_handle": "@tincongnghe_ai",
                "note": "Ghi chú: Dữ liệu mẫu giả định dùng cho kiểm thử thiết kế."
            }
        }
    ]

    for rec in lg_recipes_info:
        with st.expander(f"**{rec['name']}** — *{rec['role']}*", expanded=False):
            st.write(rec['desc'])
            st.json(rec['sample_data'])
            thumb_file = LG_DEMO_DIR / f"shot_{rec['id']}_mid.png"
            alt_thumb = LG_DEMO_DIR / f"shot_{lg_recipes_info.index(rec)+1}_mid.png"
            if thumb_file.is_file():
                st.image(str(thumb_file), caption=f"Khung giữa ({rec['id']})", width=340)
            elif alt_thumb.is_file():
                st.image(str(alt_thumb), caption=f"Khung giữa ({rec['id']})", width=340)
