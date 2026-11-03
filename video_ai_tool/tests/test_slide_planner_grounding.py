"""Tests for Slide Planner Agent and Code Grounding Verification."""
import json
import pytest

from agents.slide_planner import plan_slides
from editor.motion.light_glass_slots import create_heuristic_slide_script
from editor.motion.slide_grounding import verify_and_ground_slides
from schemas.slide_script import SlideScript, SlideItem, EmphasisItem


class MockLLMClient:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def text(self, prompt: str) -> str:
        return self.response_text


@pytest.fixture
def sample_sentences():
    return [
        {"id": 1, "text": "Việt Nam chính thức công bố chiến lược phát triển AI mới.", "start": 0.0, "end": 4.5},
        {"id": 2, "text": "Mục tiêu đạt tốc độ tăng trưởng 35% trong năm 2026.", "start": 4.5, "end": 9.2},
        {"id": 3, "text": "Hệ thống bao gồm ba tính năng cốt lõi vượt trội.", "start": 9.2, "end": 14.0},
        {"id": 4, "text": "Hiệu suất xử lý nhanh hơn 40% so với phương pháp cũ.", "start": 14.0, "end": 19.5},
        {"id": 5, "text": "Các chuyên gia đánh giá đây là bước ngoặt quan trọng.", "start": 19.5, "end": 24.8},
        {"id": 6, "text": "Hãy theo dõi kênh để cập nhật tin tức công nghệ mỗi ngày.", "start": 24.8, "end": 30.0},
    ]


@pytest.fixture
def sample_brief():
    return {
        "topic": "Chiến lược AI Việt Nam",
        "facts": [
            {
                "claim": "Mục tiêu đạt tốc độ tăng trưởng 35% trong năm 2026",
                "source_name": "VnExpress",
                "source_url": "https://vnexpress.net/thoi-su/chien-luoc-ai",
                "confidence": "high",
                "evidence_quote": "tăng trưởng 35%",
            }
        ],
        "key_numbers": [{"text": "35% tăng trưởng", "fact_ids": [1]}],
    }


def test_heuristic_slide_script_coverage_and_anti_repeat(sample_sentences, sample_brief):
    script = create_heuristic_slide_script(
        sentences=sample_sentences,
        brief=sample_brief,
        total_duration=30.0,
    )
    # Target slides for 30s ~ 5 slides
    assert 5 <= len(script.slides) <= 10
    # First slide must be kit_title (or legacy lg_source_headline)
    assert script.slides[0].layout in ("kit_title", "lg_source_headline")
    # Last slide must be kit_outro (or legacy lg_cta_profile)
    assert script.slides[-1].layout in ("kit_outro", "lg_cta_profile")
    # No two adjacent layouts identical
    for i in range(len(script.slides) - 1):
        assert script.slides[i].layout != script.slides[i + 1].layout
    # 100% of sentences covered
    all_sids = [sid for s in script.slides for sid in s.sentence_ids]
    assert sorted(all_sids) == [1, 2, 3, 4, 5, 6]


def test_grounding_downgrades_fabricated_number(sample_sentences, sample_brief):
    # Construct a slide script with a fabricated number 9999%
    fabricated_slide = SlideItem(
        id="slide_2",
        layout="lg_stat_hero",
        sentence_ids=[2],
        slots={"value": 9999, "unit": "%", "label": "Tăng trưởng ảo"},
        narration=sample_sentences[1]["text"],  # only has 35% and 2026
        t_start=4.5,
        t_end=9.2,
        duration=4.7,
    )
    script = SlideScript(
        topic="Test",
        total_duration=30.0,
        slides=[
            SlideItem(id="slide_1", layout="lg_source_headline", sentence_ids=[1], slots={"title": "Tin Mới"}, t_start=0.0, t_end=4.5, duration=4.5),
            fabricated_slide,
            SlideItem(id="slide_3", layout="lg_cta_profile", sentence_ids=[3, 4, 5, 6], slots={"channel_name": "AI"}, t_start=9.2, t_end=30.0, duration=20.8),
        ],
    )
    sentences_by_id = {s["id"]: s for s in sample_sentences}
    healed = verify_and_ground_slides(script, sentences_by_id, sample_brief)

    # Slide 2 must have been downgraded from kit_stat/lg_stat_hero to kit_title/lg_note_card
    assert healed.slides[1].layout in ("lg_note_card", "kit_title")
    # Repair notes must record the downgrade
    assert any("grounding_unverified_number" in note for note in healed.repair_notes)


def test_grounding_prunes_fabricated_emphasis(sample_sentences, sample_brief):
    slide = SlideItem(
        id="slide_1",
        layout="lg_source_headline",
        sentence_ids=[1],
        slots={"title": "Việt Nam công bố AI"},
        emphasis=[
            EmphasisItem(phrase="Việt Nam", kind="name"),  # Grounded (in sentence 1)
            EmphasisItem(phrase="Tàu vũ trụ NASA", kind="term"),  # Fabricated!
        ],
        narration=sample_sentences[0]["text"],
        t_start=0.0,
        t_end=4.5,
        duration=4.5,
    )
    script = SlideScript(topic="Test", total_duration=4.5, slides=[slide])
    sentences_by_id = {s["id"]: s for s in sample_sentences}
    healed = verify_and_ground_slides(script, sentences_by_id, sample_brief)

    # Only "Việt Nam" should survive
    surviving_phrases = [e.phrase for e in healed.slides[0].emphasis]
    assert "Việt Nam" in surviving_phrases
    assert "Tàu vũ trụ NASA" not in surviving_phrases


def test_grounding_heals_missing_headline(sample_sentences, sample_brief):
    # Slide 1 is lg_source_headline but slots has empty title
    slide = SlideItem(
        id="slide_1",
        layout="lg_source_headline",
        sentence_ids=[1],
        slots={"title": "", "pill": "TIN NÓNG"},
        narration=sample_sentences[0]["text"],
        t_start=0.0,
        t_end=4.5,
        duration=4.5,
    )
    script = SlideScript(topic="Test", total_duration=4.5, slides=[slide])
    sentences_by_id = {s["id"]: s for s in sample_sentences}
    healed = verify_and_ground_slides(script, sentences_by_id, sample_brief)

    # Headline must be non-empty and extracted from sentence 1
    new_title = healed.slides[0].slots.get("title")
    assert new_title
    assert "Việt Nam" in new_title


def test_plan_slides_with_mock_llm(sample_sentences, sample_brief):
    mock_payload = {
        "slides": [
            {
                "id": "slide_1",
                "layout": "lg_source_headline",
                "sentence_ids": [1],
                "slots": {"pill": "TIN NÓNG", "title": "Chiến lược AI", "text": "Việt Nam công bố chiến lược AI."},
                "emphasis": [{"phrase": "chiến lược AI", "kind": "term"}],
            },
            {
                "id": "slide_2",
                "layout": "lg_stat_hero",
                "sentence_ids": [2],
                "slots": {"value": 35, "unit": "%", "label": "Tăng trưởng"},
                "emphasis": [{"phrase": "35%", "kind": "number"}],
            },
            {
                "id": "slide_3",
                "layout": "lg_shot_features",
                "sentence_ids": [3],
                "slots": {"title": "Tính năng", "items": ["Tính năng cốt lõi"]},
            },
            {
                "id": "slide_4",
                "layout": "lg_vs_compare",
                "sentence_ids": [4],
                "slots": {"left": {"label": "CŨ", "text": "Phương pháp cũ"}, "right": {"label": "MỚI", "text": "Hiệu suất 40%"}},
            },
            {
                "id": "slide_5",
                "layout": "lg_cta_profile",
                "sentence_ids": [5, 6],
                "slots": {"channel_name": "TIN CÔNG NGHỆ"},
            },
        ]
    }
    mock_client = MockLLMClient(json.dumps(mock_payload))
    script = plan_slides(
        brief=sample_brief,
        sentences=sample_sentences,
        total_duration=30.0,
        llm_client=mock_client,
    )
    assert len(script.slides) == 5
    assert script.slides[0].layout in ("kit_title", "lg_source_headline")
    assert script.slides[1].layout in ("kit_stat", "lg_stat_hero")
    assert script.slides[-1].layout in ("kit_outro", "lg_cta_profile")


def test_plan_slides_fallback_on_llm_failure(sample_sentences, sample_brief):
    # LLM returns malformed garbage
    broken_client = MockLLMClient("not a valid json { broken")
    script = plan_slides(
        brief=sample_brief,
        sentences=sample_sentences,
        total_duration=30.0,
        llm_client=broken_client,
    )
    # Should seamlessly fall back to heuristic mapper
    assert len(script.slides) >= 5
    assert script.slides[0].layout == "lg_source_headline"
    assert script.slides[-1].layout == "lg_cta_profile"
    assert any("heuristic fallback" in note for note in script.repair_notes)
