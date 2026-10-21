# file: tests/test_schemas.py
"""Kiểm tra ranh giới dữ liệu không tin cậy do AI sinh."""
from copy import deepcopy
import json
import pytest
from pydantic import ValidationError
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief


@pytest.fixture
def plan_data() -> dict:
    shot = {"type": "stock_video", "query": "video editing", "duration_sec": 3.0,
            "effect": "zoom_in", "text_overlay": None}
    return {"title": "Ví dụ kiểm tra schema", "format": "tiktok", "voice": "vi-VN-HoaiMyNeural",
            "music": {"mood": "calm", "volume": 0.1}, "scenes": [
                {"id": 1, "role": "hook", "narration": "Bạn đang dựng video như thế nào?",
                 "shots": [deepcopy(shot)], "transition_out": "cut", "sfx": "pop"},
                {"id": 2, "role": "cta", "narration": "Hãy chia sẻ cách bạn đang làm.",
                 "shots": [deepcopy(shot)], "transition_out": "fade", "sfx": "none"}]}


@pytest.fixture
def brief_data() -> dict:
    return {"topic": "Dựng video", "language": "vi",
            "angle_candidates": [{"angle": "Quy trình", "why": "Làm rõ từng bước"}],
            "facts": [{"claim": "Dữ liệu giả lập chỉ dùng kiểm thử", "source_name": "Example",
                       "source_url": "https://example.com/test", "confidence": "low"}],
            "trends": [], "hooks": ["Bắt đầu từ đâu?"], "audience_questions": [],
            "keywords": ["editing"], "risks": ["Fixture không phải nghiên cứu thực tế"]}


def test_brief_json_roundtrip(brief_data: dict) -> None:
    brief = ResearchBrief.model_validate_json(json.dumps(brief_data))
    assert ResearchBrief.model_validate_json(brief.model_dump_json()) == brief


@pytest.mark.parametrize("url", ["", "not-a-url", "file:///secret", "ftp://example.com"])
def test_brief_requires_http_source(brief_data: dict, url: str) -> None:
    brief_data["facts"][0]["source_url"] = url
    with pytest.raises(ValidationError):
        ResearchBrief.model_validate(brief_data)


def test_source_required(brief_data: dict) -> None:
    del brief_data["facts"][0]["source_url"]
    with pytest.raises(ValidationError):
        ResearchBrief.model_validate(brief_data)


def test_unknown_field_rejected(plan_data: dict) -> None:
    plan_data["python_code"] = "print('không được thực thi')"
    with pytest.raises(ValidationError):
        EditPlan.model_validate(plan_data)


@pytest.mark.parametrize("duration", [1.49, 4.01, float("nan"), float("inf"), "3"])
def test_invalid_shot_duration(plan_data: dict, duration: object) -> None:
    plan_data["scenes"][1]["shots"][0]["duration_sec"] = duration
    plan=EditPlan.model_validate(plan_data)
    assert 1.5<=plan.scenes[1].shots[0].duration_sec<=4


@pytest.mark.parametrize("change", ["duplicate_id", "missing_hook", "long_hook", "missing_cta"])
def test_scene_structure(plan_data: dict, change: str) -> None:
    if change == "duplicate_id":
        plan_data["scenes"][1]["id"] = 1
    elif change == "missing_hook":
        plan_data["scenes"][0]["role"] = "body"
    elif change == "long_hook":
        plan_data["scenes"][0]["shots"][0]["duration_sec"] = 4.0
    else:
        plan_data["scenes"][-1]["role"] = "body"
    plan=EditPlan.model_validate(plan_data)
    assert len({s.id for s in plan.scenes})==len(plan.scenes)
    assert plan.scenes[0].role=="hook" and plan.scenes[0].duration_sec<=3
    assert plan.scenes[-1].role=="cta" and plan.validation_events


def test_target_duration_and_json_roundtrip(plan_data: dict) -> None:
    plan = EditPlan.model_validate_json(json.dumps(plan_data))
    plan.validate_target_duration(6)
    plan.validate_target_duration(45)
    assert plan.duration_sec==pytest.approx(45)
    with pytest.raises(ValueError):
        plan.validate_target_duration(float("nan"))
    assert EditPlan.model_validate_json(plan.model_dump_json()) == plan
