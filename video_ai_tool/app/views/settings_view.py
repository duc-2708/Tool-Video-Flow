"""Trang Cài đặt API Token & Mô hình AI cho người dùng."""
from pathlib import Path
import streamlit as st

from config.settings import get_settings


def update_env_file(root_dir: Path, key: str, value: str):
    """Cập nhật giá trị an toàn vào file .env trong thư mục gốc app."""
    env_path = root_dir / ".env"
    lines = []
    found = False

    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def render(settings, project, topic, debug, diagnostics):
    st.markdown("""
        <div class="main-card">
            <h2 style="margin: 0; color: #ffd60a; font-weight: 800; font-size: 1.8rem;">
                ⚙️ Cài Đặt Token & Cấu Hình AI
            </h2>
            <p style="margin: 4px 0 0 0; color: #a1a1aa; font-size: 0.95rem;">
                Nhập API Key / Token để kết nối tới các dịch vụ AI. Giá trị được lưu an toàn trực tiếp vào file <code>.env</code> local của bạn.
            </p>
        </div>
    """, unsafe_allow_html=True)

    root_dir = settings.root_dir

    # 1. Google Gemini AI Token
    with st.container():
        st.subheader("1. Google Gemini API (Bắt buộc cho Research & Script & Visual)")
        curr_gemini = settings.gemini_api_key.get_secret_value()
        gemini_status = "🟢 Đã kết nối" if curr_gemini.strip() else "🔴 Chưa có token"
        st.caption(f"Trạng thái hiện tại: **{gemini_status}**")

        new_gemini = st.text_input(
            "Gemini API Key",
            value=curr_gemini if not curr_gemini else "••••••••••••••••••••••••",
            type="password",
            help="Lấy tại Google AI Studio (https://aistudio.google.com/)",
            key="cfg_gemini_key"
        )

        col_m1, col_m2 = st.columns(2)
        gemini_model = col_m1.text_input(
            "Gemini Model chính (GEMINI_MODEL)",
            value=settings.gemini_model or "gemini-2.5-flash",
            help="Ví dụ: gemini-2.5-flash, gemini-3-flash-preview",
            key="cfg_gemini_model"
        )
        gemini_director = col_m2.text_input(
            "Model Director kịch bản (GEMINI_DIRECTOR_MODEL)",
            value=settings.gemini_director_model or "gemini-2.5-pro",
            help="Ví dụ: gemini-2.5-pro, gemini-2.5-flash",
            key="cfg_gemini_director"
        )

    st.divider()

    # 2. OpenAI & Gateway Video (Tùy chọn)
    with st.container():
        st.subheader("2. AI Video Gateway & OpenAI (Tùy chọn)")
        curr_gateway = settings.gateway_api_key.get_secret_value()
        gateway_status = "🟢 Đã có key" if curr_gateway.strip() else "⚪ Chưa cấu hình"
        st.caption(f"Trạng thái Gateway: **{gateway_status}**")

        new_gateway = st.text_input(
            "Gateway API Key (Veo/Seedance Video AI)",
            value=curr_gateway if not curr_gateway else "••••••••••••••••••••••••",
            type="password",
            key="cfg_gateway_key"
        )

        curr_openai = settings.openai_api_key.get_secret_value()
        new_openai = st.text_input(
            "OpenAI API Key (Tùy chọn cho fallback LLM)",
            value=curr_openai if not curr_openai else "••••••••••••••••••••••••",
            type="password",
            key="cfg_openai_key"
        )

    st.divider()

    # 3. Stock Media & YouTube (Tùy chọn)
    with st.container():
        st.subheader("3. Media Stock & YouTube API (Tùy chọn)")
        c1, c2 = st.columns(2)
        curr_pexels = settings.pexels_api_key.get_secret_value()
        new_pexels = c1.text_input(
            "Pexels API Key",
            value=curr_pexels if not curr_pexels else "••••••••••••••••••••••••",
            type="password",
            key="cfg_pexels_key"
        )

        curr_pixabay = settings.pixabay_api_key.get_secret_value()
        new_pixabay = c2.text_input(
            "Pixabay API Key",
            value=curr_pixabay if not curr_pixabay else "••••••••••••••••••••••••",
            type="password",
            key="cfg_pixabay_key"
        )

        curr_yt = settings.youtube_api_key.get_secret_value()
        new_yt = st.text_input(
            "YouTube Data API Key",
            value=curr_yt if not curr_yt else "••••••••••••••••••••••••",
            type="password",
            key="cfg_yt_key"
        )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Lưu Cấu Hình Vào .env", type="primary", use_container_width=True):
        updated_count = 0

        # Update gemini if changed from mask
        if new_gemini and new_gemini != "••••••••••••••••••••••••":
            update_env_file(root_dir, "GEMINI_API_KEY", new_gemini.strip())
            updated_count += 1
        if gemini_model.strip():
            update_env_file(root_dir, "GEMINI_MODEL", gemini_model.strip())
            updated_count += 1
        if gemini_director.strip():
            update_env_file(root_dir, "GEMINI_DIRECTOR_MODEL", gemini_director.strip())
            updated_count += 1

        if new_gateway and new_gateway != "••••••••••••••••••••••••":
            update_env_file(root_dir, "GATEWAY_API_KEY", new_gateway.strip())
            updated_count += 1
        if new_openai and new_openai != "••••••••••••••••••••••••":
            update_env_file(root_dir, "OPENAI_API_KEY", new_openai.strip())
            updated_count += 1
        if new_pexels and new_pexels != "••••••••••••••••••••••••":
            update_env_file(root_dir, "PEXELS_API_KEY", new_pexels.strip())
            updated_count += 1
        if new_pixabay and new_pixabay != "••••••••••••••••••••••••":
            update_env_file(root_dir, "PIXABAY_API_KEY", new_pixabay.strip())
            updated_count += 1
        if new_yt and new_yt != "••••••••••••••••••••••••":
            update_env_file(root_dir, "YOUTUBE_API_KEY", new_yt.strip())
            updated_count += 1

        st.success(f"✅ Đã lưu cấu hình thành công! Hãy khởi động lại hoặc tải lại trang.")
        st.session_state["settings_updated"] = True
        st.rerun()
