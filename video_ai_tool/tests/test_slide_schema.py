"""Tests for SlideScript and SlideItem pydantic schemas."""
import pytest
from pydantic import ValidationError

from schemas.slide_script import (
    SlideScript,
    SlideItem,
    SourceRef,
    EmphasisItem,
    wrap_text_greedy,
)


def test_wrap_text_greedy_basic():
    text = "AI sẽ thay đổi thế giới mới"
    # Wrap at 14 chars per line
    lines = wrap_text_greedy(text, max_chars_per_line=14, max_lines=3)
    assert len(lines) <= 3
    for l in lines:
        assert len(l) <= 14
    # All words in lines should match original words
    assert " ".join(lines) == text


def test_wrap_text_greedy_overflow_respects_max_lines():
    long_text = "Một hai ba bốn năm sáu bảy tám chín mười mười một mười hai mười ba"
    lines = wrap_text_greedy(long_text, max_chars_per_line=10, max_lines=2)
    assert len(lines) == 2
    for l in lines:
        assert len(l) <= 10


def test_slide_item_slot_limits_clamped():
    # Overly long headline & pill
    long_title = "Tiêu đề siêu dài vượt quá ba dòng mười bốn ký tự cần phải được tự động cắt gọn gàng tại ranh giới từ"
    long_pill = "Đây là một cái pill quá dài vượt quá hai mươi tám ký tự cho phép"
    
    item = SlideItem(
        id="slide_1",
        layout="lg_source_headline",
        sentence_ids=[1],
        slots={
            "title": long_title,
            "pill": long_pill,
            "items": [
                "Ý 1 ngắn",
                "Ý 2 dài lê thê hơn bốn mươi ký tự chắc chắn sẽ bị cắt bớt một chút",
                "Ý 3",
                "Ý 4",
                "Ý 5 thừa ra sẽ bị bỏ",
            ],
            "left": {"title": "Một tiêu đề bên trái rất dài cần cắt tại ranh giới từ"},
        },
    )
    # Check slots clamped
    slots = item.slots
    assert len(slots["pill"]) <= 28
    assert len(slots["items"]) <= 4
    for it in slots["items"]:
        assert len(it) <= 40
    # Left side clamped
    assert len(slots["left"]["title"]) <= 28


def test_slide_item_layout_validation():
    # Valid layout (normalizes legacy lg_stat_hero to kit_stat)
    item = SlideItem(
        id="slide_1",
        layout="lg_stat_hero",
        sentence_ids=[1, 2],
        slots={"value": 85, "unit": "%"},
    )
    assert item.layout == "kit_stat"

    # Invalid layout should fail
    with pytest.raises(ValidationError):
        SlideItem(
            id="slide_invalid",
            layout="unknown_layout",  # type: ignore
            sentence_ids=[1],
        )


def test_slide_script_serialization():
    s_ref = SourceRef(url="https://vnexpress.net/thoi-su", domain="vnexpress.net", image_kind="card")
    emp = EmphasisItem(phrase="trí tuệ nhân tạo", kind="term", start_sec=0.5, end_sec=1.5)
    
    slide = SlideItem(
        id="slide_1",
        layout="lg_source_headline",
        sentence_ids=[1],
        slots={"title": "Đột phá mới"},
        source_ref=s_ref,
        emphasis=[emp],
        t_start=0.0,
        t_end=5.5,
        duration=5.5,
        narration="Đây là đột phá mới về trí tuệ nhân tạo.",
    )
    script = SlideScript(
        topic="Công nghệ AI",
        total_duration=5.5,
        slides=[slide],
        repair_notes=["Test note"],
    )
    data = script.model_dump(mode="json")
    assert data["topic"] == "Công nghệ AI"
    assert len(data["slides"]) == 1
    assert data["slides"][0]["layout"] == "kit_title"
    assert data["slides"][0]["source_ref"]["domain"] == "vnexpress.net"
    assert data["slides"][0]["emphasis"][0]["phrase"] == "trí tuệ nhân tạo"
