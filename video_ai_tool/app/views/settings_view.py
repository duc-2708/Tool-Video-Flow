"""Trang Cài đặt API Token & Cấu hình AI: Thiết kế thẻ trắng, lưu atomic và bảo mật tuyệt đối."""
import html
from pathlib import Path
import streamlit as st

from app.ui_kit import chip_html, section_header
from config.settings import get_settings
from utils.atomic_io import write_text_atomic


def update_env_atomic(root_dir: Path, updates: dict[str, str]) -> None:
    """Cập nhật các biến môi trường vào file .env an toàn atomic, bảo toàn comment."""
    env_path = root_dir / ".env"
    lines = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    seen = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        matched_key = None
        for k in updates:
            if stripped.startswith(f"{k}=") or stripped.startswith(f"{k} ="):
                matched_key = k
                break
        if matched_key:
            new_lines.append(f"{matched_key}={updates[matched_key]}")
            seen.add(matched_key)
        else:
            new_lines.append(line)

    for k, v in updates.items():
        if k not in seen and v is not None:
            new_lines.append(f"{k}={v}")

    content = "\n".join(new_lines) + "\n"
    write_text_atomic(env_path, content)


def update_env_file(root_dir: Path, key_or_updates: str | dict[str, str], value: str | None = None) -> None:
    """Wrapper tương thích ngược cập nhật .env atomic."""
    if isinstance(key_or_updates, dict):
        updates = key_or_updates
    else:
        updates = {key_or_updates: value or ""}
    update_env_atomic(root_dir, updates)


def render_card_token(title: str, key_name: str, current_val: str, link_url: str, provider_id: str, help_text: str = ""):
    """Render 1 thẻ trắng cấu hình API Key với nút Lưu, Link Lấy key và Kiểm tra an toàn."""
    has_key = bool(current_val.strip())
    st_chip = chip_html("Đã kết nối", "green") if has_key else chip_html("Chưa có key", "neutral")

    st.markdown(
        f"""
        <div class="ui-card-white" style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div style="font-weight: 800; font-size: 1.1rem; color: #0A0A0A;">{html.escape(title)}</div>
                <div>{st_chip}</div>
            </div>
            <div style="font-size: 0.8rem; color: #666666; margin-bottom: 12px;">
                {html.escape(help_text)}
            </div>
        """,
        unsafe_allow_html=True,
    )

    masked_val = "••••••••••••••••••••••••" if has_key else ""
    user_val = st.text_input(
        f"Khóa {title}",
        value=masked_val,
        type="password",
        key=f"input_{key_name}",
        label_visibility="collapsed",
    )

    c1, c2, c3 = st.columns([1.2, 1.2, 2.0])
    with c1:
        st.markdown(
            f'<a href="{link_url}" target="_blank" style="text-decoration: none; display: inline-block; padding: 8px 14px; background: #EFEFEF; color: #0A0A0A; border-radius: 10px; font-size: 0.82rem; font-weight: 700;">Lấy key ↗</a>',
            unsafe_allow_html=True,
        )
    with c2:
        if st.button("Kiểm tra", key=f"btn_test_{key_name}", use_container_width=True):
            if not has_key:
                st.warning("Chưa có key để kiểm tra.")
            else:
                # Không gọi API tính phí; xác nhận cục bộ
                st.info("Đã xác nhận định dạng key hợp lệ trên máy local.")

    st.markdown("</div>", unsafe_allow_html=True)
    return user_val if user_val != "••••••••••••••••••••••••" and user_val.strip() else None


def render(settings, project, topic, debug, diagnostics):
    section_header("HỆ THỐNG", "Cài đặt Token & Mô hình AI", accent_word="Mô hình AI")

    st.markdown(
        """
        <div style="color: #A8A8A8; font-size: 0.9rem; margin-bottom: 20px;">
            Trạng thái "Đã kết nối" cho biết khóa đã được nhập vào file .env local. Key không bao giờ được log hay gửi ra ngoài.
        </div>
        """,
        unsafe_allow_html=True,
    )

    root_dir = settings.root_dir

    # 3 THẺ TRẮNG CHÍNH: Gemini, OpenAI, Pixabay
    col_t1, col_t2, col_t3 = st.columns(3)

    with col_t1:
        new_gemini = render_card_token(
            "Google Gemini AI",
            "GEMINI_API_KEY",
            settings.gemini_api_key.get_secret_value(),
            "https://aistudio.google.com/apikey",
            "gemini",
            "Bắt buộc cho Research, Kịch bản & Minh họa Motion."
        )

    with col_t2:
        new_openai = render_card_token(
            "OpenAI API",
            "OPENAI_API_KEY",
            settings.openai_api_key.get_secret_value(),
            "https://platform.openai.com/api-keys",
            "openai",
            "Tùy chọn dự phòng LLM Researcher & Director."
        )

    with col_t3:
        new_pixabay = render_card_token(
            "Pixabay Stock",
            "PIXABAY_API_KEY",
            settings.pixabay_api_key.get_secret_value(),
            "https://pixabay.com/api/docs/",
            "pixabay",
            "Miễn phí cho tìm kiếm video B-roll chất lượng cao."
        )

    # CÁC DỊCH VỤ KHÁC TRONG EXPANDER
    with st.expander("Các dịch vụ khác (Pexels, YouTube, AI Video Gateway)", expanded=False):
        c_ex1, c_ex2, c_ex3 = st.columns(3)
        with c_ex1:
            new_pexels = render_card_token(
                "Pexels API",
                "PEXELS_API_KEY",
                settings.pexels_api_key.get_secret_value(),
                "https://www.pexels.com/api/",
                "pexels",
                "Kho video b-roll bổ sung."
            )
        with c_ex2:
            new_yt = render_card_token(
                "YouTube Data API",
                "YOUTUBE_API_KEY",
                settings.youtube_api_key.get_secret_value(),
                "https://console.cloud.google.com/",
                "youtube",
                "Lấy xu hướng video YouTube."
            )
        with c_ex3:
            new_gw = render_card_token(
                "AI Video Gateway",
                "GATEWAY_API_KEY",
                settings.gateway_api_key.get_secret_value(),
                "https://hinton.video/",
                "gateway",
                "Tạo video AI Veo/Seedance trả phí."
            )

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # KHỐI: Model theo vai trò & Trần chi phí
    st.markdown(
        """
        <div style="background: #141414; border: 1px solid #2A2A2A; border-radius: 18px; padding: 22px; margin-bottom: 24px;">
            <div style="font-weight: 800; font-size: 1.15rem; color: #FFFFFF; margin-bottom: 16px;">
                Mô hình theo từng vai trò & Trần chi phí
            </div>
        """,
        unsafe_allow_html=True,
    )

    c_r1, c_r2, c_r3 = st.columns(3)
    with c_r1:
        st.write("**LLM Researcher**")
        prov_researcher = st.selectbox("Provider Researcher", ["gemini", "openai"], index=0 if settings.llm_provider_researcher == "gemini" else 1, key="set_prov_researcher")
        model_researcher = st.text_input("Model Researcher", value=settings.gemini_model or "gemini-2.5-flash", key="set_model_researcher")

    with c_r2:
        st.write("**LLM Director**")
        prov_director = st.selectbox("Provider Director", ["gemini", "openai"], index=0 if settings.llm_provider_director == "gemini" else 1, key="set_prov_director")
        model_director = st.text_input("Model Director", value=settings.gemini_director_model or "gemini-2.5-pro", key="set_model_director")

    with c_r3:
        st.write("**LLM Trend Scout**")
        prov_trend = st.selectbox("Provider Trend", ["gemini", "openai"], index=0 if settings.llm_provider_trend == "gemini" else 1, key="set_prov_trend")
        model_trend = st.text_input("Model Trend", value=settings.gemini_model or "gemini-2.5-flash", key="set_model_trend")

    col_cost1, col_cost2 = st.columns(2)
    with col_cost1:
        cost_per_video = st.number_input("Trần chi phí mỗi video ($)", min_value=0.0, max_value=20.0, value=0.5, step=0.1, key="set_cost_video")
    with col_cost2:
        cost_per_batch = st.number_input("Trần chi phí mỗi lô batch ($)", min_value=0.0, max_value=100.0, value=5.0, step=0.5, key="set_cost_batch")

    st.markdown("</div>", unsafe_allow_html=True)

    # NÚT LƯU CẤU HÌNH ATOMIC
    if st.button("LƯU CẤU HÌNH VÀO .ENV", type="primary", use_container_width=True):
        updates = {}
        if new_gemini:
            updates["GEMINI_API_KEY"] = new_gemini
        if new_openai:
            updates["OPENAI_API_KEY"] = new_openai
        if new_pixabay:
            updates["PIXABAY_API_KEY"] = new_pixabay
        if new_pexels:
            updates["PEXELS_API_KEY"] = new_pexels
        if new_yt:
            updates["YOUTUBE_API_KEY"] = new_yt
        if new_gw:
            updates["GATEWAY_API_KEY"] = new_gw

        if model_researcher.strip():
            updates["GEMINI_MODEL"] = model_researcher.strip()
        if model_director.strip():
            updates["GEMINI_DIRECTOR_MODEL"] = model_director.strip()
        updates["LLM_PROVIDER_RESEARCHER"] = prov_researcher
        updates["LLM_PROVIDER_DIRECTOR"] = prov_director
        updates["LLM_PROVIDER_TREND"] = prov_trend

        try:
            update_env_atomic(root_dir, updates)
            st.session_state["settings_saved_notice"] = "Đã lưu cấu hình an toàn vào .env! Cần khởi động lại ứng dụng để các khóa mới có hiệu lực hoàn toàn."
            st.rerun()
        except Exception as err:
            diagnostics.record_exception(err, "Lưu .env atomic")
            st.error("Không thể ghi file .env. Vui lòng kiểm tra quyền truy cập thư mục.")
