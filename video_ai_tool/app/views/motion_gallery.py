"""Motion Gallery UI view for Streamlit: Motion Kit v2 visual components and demo showcase."""
from pathlib import Path
import streamlit as st

KIT_DEMO_DIR = Path(__file__).resolve().parents[2] / "output/kit_demo"


def render(settings, project, topic, debug, diagnostics):
    st.header("Phòng thử hiệu ứng — Motion Kit v2")
    st.caption("Khám phá hệ thống đồ họa Motion Kit v2: seek-based deterministic, bảng màu thanh lịch, typography sắc nét và chuyển cảnh liền mạch.")

    tab_demo, tab_components = st.tabs(["Video Demo & Kiểm Định (Audit)", "Thư Viện Thành Phần Kit v2"])

    with tab_demo:
        _render_demo_tab()

    with tab_components:
        _render_components_tab()


def _render_demo_tab():
    st.subheader("Video Trình Diễn Tổng Hợp (Demo ~30s)")
    demo_video = KIT_DEMO_DIR / "kit_demo.mp4"
    contact_sheet = KIT_DEMO_DIR / "contact_sheet.jpg"
    audit_json = KIT_DEMO_DIR / "audit_result.json"

    if demo_video.is_file():
        col1, col2 = st.columns([1, 1])
        with col1:
            st.video(str(demo_video))
            st.download_button("Tải video Demo MP4", demo_video.read_bytes(), file_name="kit_demo.mp4", mime="video/mp4", key="btn_down_kit_demo")
        with col2:
            st.markdown("""
            **Các phân cảnh trong video Demo Motion Kit v2:**
            1. `kit_title`: Tiêu đề lớn & pill nhận diện mở đầu
            2. `kit_stat`: Con số tăng trưởng 128 tỷ USD (đếm đơn điệu trong 1.2s)
            3. `kit_chart_bar`: Biểu đồ cột so sánh thị phần công nghệ
            4. `kit_chart_line`: Biểu đồ đường vẽ mượt tiến trình theo năm
            5. `kit_photo`: Ảnh tư liệu điện ảnh (Ken Burns 1.00 -> 1.03) kèm chú thích
            6. `kit_list`: Danh sách 3 điểm nhấn công nghệ nổi bật
            7. `kit_quote`: Trích dẫn nhận định chuyên gia phân tích
            8. `kit_outro`: Kêu gọi theo dõi và nhận diện kênh
            """)
            if contact_sheet.is_file():
                st.image(str(contact_sheet), caption="Bảng ghép khung hình 0.5s/khung (Contact Sheet)", use_container_width=True)

        if audit_json.is_file():
            st.divider()
            st.subheader("Kết Quả Kiểm Định Chất Lượng (Quality Audit)")
            import json
            try:
                audit_data = json.loads(audit_json.read_text(encoding="utf-8"))
                st.json(audit_data)
            except Exception:
                pass
    else:
        st.info("Chưa có video demo được kết xuất. Bạn có thể kết xuất video test bằng lệnh: `python tools/render_kit_demo.py`.")


def _render_components_tab():
    st.subheader("Danh Mục Thành Phần Motion Kit v2 (`kit_*`)")
    st.markdown("""
    Toàn bộ chuyển động trong Motion Kit v2 là hàm thuần theo thời gian $t$, xác định và tái lập 100%:
    - **Nền**: `#F6F7FB`, thẻ trắng `#FFFFFF` bo góc mềm viền `#E5E7EB` bóng nhẹ.
    - **Chữ**: `#0F172A`, điểm nhấn xanh `#2563EB`, tím `#7C3AED`, tăng `#059669`, giảm `#DC2626`.
    - **Khung cố định**: Brand chip top-left, Source pill bottom-center, 2 blob mờ trôi chậm chu kỳ $\\ge 20$s.
    """)

    components = [
        {
            "id": "kit_title",
            "name": "1. kit_title (Tiêu đề lớn & Câu phụ)",
            "desc": "Tiêu đề 96-132px đậm (tối đa 3 dòng x 14 ký tự), phụ đề >= 48px, pill và thumbnail tùy chọn.",
        },
        {
            "id": "kit_stat",
            "name": "2. kit_stat (Số liệu lớn đếm đơn điệu)",
            "desc": "Con số chủ đạo đếm tăng một chiều trong <= 1.2s rồi giữ nguyên, đơn vị và delta tăng/giảm.",
        },
        {
            "id": "kit_chart_bar",
            "name": "3. kit_chart_bar (Biểu đồ cột động)",
            "desc": "Vẽ dần các cột trong 0.9s từ dữ liệu thật, nhãn và giá trị gắn trực tiếp trên cột.",
        },
        {
            "id": "kit_chart_line",
            "name": "4. kit_chart_line (Biểu đồ đường động)",
            "desc": "Đường nối spline vẽ dần qua các mốc thời gian trong 0.9s, các điểm chốt phát sáng.",
        },
        {
            "id": "kit_chart_donut",
            "name": "5. kit_chart_donut (Biểu đồ tròn phân bổ)",
            "desc": "Vòng cung phân bổ tỷ lệ phần trăm vẽ dần trong 0.9s kèm bảng chú giải bên phải.",
        },
        {
            "id": "kit_photo",
            "name": "6. kit_photo (Ảnh tư liệu / Chân dung)",
            "desc": "Thẻ ảnh 910x1000 bo góc 28px, zoom Ken Burns nhẹ nhàng 1.00 -> 1.03, chú thích tên và nguồn.",
        },
        {
            "id": "kit_list",
            "name": "7. kit_list (Danh sách điểm nhấn)",
            "desc": "Tối đa 4 ý ngắn gọn, hiện lần lượt so le trong 0.7s đầu với chữ >= 44px sắc nét.",
        },
        {
            "id": "kit_compare",
            "name": "8. kit_compare (Bảng đối chiếu 2 vế)",
            "desc": "2 cột so sánh trực quan (mỗi bên <= 2 dòng) với thẻ nhấn mạnh kết quả vượt trội.",
        },
        {
            "id": "kit_quote",
            "name": "9. kit_quote (Trích dẫn chuyên gia)",
            "desc": "Dấu ngoặc kép phong cách editorial, câu nói tâm đắc, tên nhân vật và tổ chức/vai trò.",
        },
        {
            "id": "kit_timeline",
            "name": "10. kit_timeline (Tiến trình mốc sự kiện)",
            "desc": "Dòng thời gian tối đa 5 mốc quan trọng với các nút điểm liên kết mượt mà.",
        },
        {
            "id": "kit_outro",
            "name": "11. kit_outro (Thẻ kết & Kêu gọi theo dõi)",
            "desc": "Avatar thương hiệu, tên kênh, nút kêu gọi đăng ký và thông điệp kết video.",
        },
    ]

    for comp in components:
        with st.expander(comp["name"]):
            st.markdown(comp["desc"])
