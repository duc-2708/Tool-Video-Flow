"""Tests for source web citation capture and fallback card generation."""
import json
from pathlib import Path
from PIL import Image

from tools.source_capture import (
    clean_domain,
    generate_fallback_source_card,
    capture_sources_for_brief,
)


def test_clean_domain():
    assert clean_domain("https://vnexpress.net/thoi-su/bai-viet.html") == "vnexpress.net"
    assert clean_domain("http://www.theguardian.com/world/news") == "theguardian.com"
    assert clean_domain(None) == "Nguồn tin tức"


def test_generate_fallback_source_card(tmp_path):
    output_png = tmp_path / "test_source_card.png"
    card_path = generate_fallback_source_card(
        domain="techcrunch.com",
        title="OpenAI ra mắt mô hình trí tuệ nhân tạo mới",
        date_str="02/11/2026",
        output_png=output_png,
    )
    assert card_path.is_file()
    assert output_png.stat().st_size > 1000

    # Verify image dimensions 1280x720
    with Image.open(card_path) as img:
        assert img.size == (1280, 720)
        assert img.format == "PNG"


def test_capture_sources_for_brief_offline_fallback(tmp_path):
    sample_brief = {
        "topic": "Trí tuệ nhân tạo",
        "facts": [
            {
                "claim": "Bước tiến công nghệ mới nhất trong năm 2026",
                "source_name": "VnExpress",
                "source_url": "https://invalid-offline-domain-test.local/news/123",
            }
        ]
    }
    results = capture_sources_for_brief(
        brief=sample_brief,
        output_dir=tmp_path,
        max_sources=1,
        timeout_sec=2,  # very short timeout to trigger fallback
    )
    assert len(results) == 1
    url = "https://invalid-offline-domain-test.local/news/123"
    meta = results[url]
    assert meta["domain"] == "invalid-offline-domain-test.local"
    assert meta["title"] == "Bước tiến công nghệ mới nhất trong năm 2026"
    assert meta["kind"] == "card"
    assert Path(meta["image_path"]).is_file()
