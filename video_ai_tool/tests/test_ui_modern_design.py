"""Unit tests for the Black-Gold-White modern Streamlit UI design tokens, ui_kit, XSS escaping, and AppTest."""
import html
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from config.settings import ROOT_DIR, Settings
from app.ui_kit import chip_html, stat_html, stepper_html, empty_state
from pipeline.projects import create_project


def test_theme_css_no_external_urls():
    """theme.css must not use external URLs, CDN links, or external @import."""
    css_path = ROOT_DIR / "app/theme.css"
    assert css_path.is_file(), "theme.css not found"
    content = css_path.read_text(encoding="utf-8")
    assert "http://" not in content.lower(), "External http:// URL found in theme.css"
    assert "https://" not in content.lower(), "External https:// URL found in theme.css"
    assert "@import" not in content.lower(), "@import found in theme.css"


def test_ui_kit_escapes_html():
    """All components in ui_kit must escape input text to prevent XSS injection."""
    malicious_text = "<script>alert('xss')</script>"
    safe_pattern = "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
    safe_alt_pattern = "&lt;script&gt;alert('xss')&lt;/script&gt;"

    # 1. chip_html
    c_html = chip_html(malicious_text, "gold")
    assert "<script>" not in c_html
    assert safe_pattern in c_html or safe_alt_pattern in c_html

    # 2. stat_html
    s_html = stat_html(malicious_text, "100%", sub=malicious_text)
    assert "<script>" not in s_html
    assert safe_pattern in s_html or safe_alt_pattern in s_html

    # 3. stepper_html
    st_html = stepper_html(["Step 1", malicious_text], active_index=1)
    assert "<script>" not in st_html
    assert safe_pattern in st_html or safe_alt_pattern in st_html


@pytest.mark.parametrize("page_name", [
    "Tạo video theo danh mục",
    "Tạo video",
    "Kho video đã làm",
    "Cài đặt Token & AI",
])
def test_apptest_pages_render_without_exception(tmp_path, monkeypatch, page_name):
    """Every major page rendered by AppTest should load without raising an unhandled exception."""
    settings = Settings(root_dir=tmp_path)
    monkeypatch.setattr("config.settings.get_settings", lambda: settings)

    proj = create_project(settings.output_dir, "UI Test Project")
    (proj / "brief.json").write_text('{"topic": "Test topic", "facts": []}', encoding="utf-8")

    app = AppTest.from_file(ROOT_DIR / "app/streamlit_app.py", default_timeout=45).run()
    assert not app.exception

    if page_name != "Tạo video theo danh mục":
        app.sidebar.radio[0].set_value(page_name).run()
        assert not app.exception, f"Exception occurred while rendering page: {page_name}"


def test_topic_with_script_tag_escaped(tmp_path, monkeypatch):
    """XSS injection attempt in topic should not create raw HTML script tags."""
    settings = Settings(root_dir=tmp_path)
    monkeypatch.setattr("config.settings.get_settings", lambda: settings)

    malicious_topic = "Tech News <script>alert(1)</script>"
    create_project(settings.output_dir, malicious_topic)

    app = AppTest.from_file(ROOT_DIR / "app/streamlit_app.py", default_timeout=45).run()
    app.sidebar.radio[0].set_value("Kho video đã làm").run()
    assert not app.exception

    # Assert no raw unescaped script tag is in markdown elements
    for md in app.markdown:
        assert "<script>alert(1)</script>" not in str(md.value)
