"""Unit and regression tests for Vietnamese accent validation and repair."""
from copy import deepcopy
import pytest
from utils.vietnamese_accent import (
    is_unaccented_vietnamese,
    has_vietnamese_accent,
    restore_known_accents,
    audit_plan_accents,
    count_accent_chars,
)
from schemas.edit_plan import EditPlan, Scene, Shot
from schemas.research_brief import ResearchBrief
from agents.validation_rules import run_rules, RuleViolation


def test_accent_detection_positive():
    # Sentences with diacritics should not be flagged as unaccented
    assert not is_unaccented_vietnamese("tương tự như việc kiểm tra từng viên gạch")[0]
    assert not is_unaccented_vietnamese("mô hình gợi ý")[0]
    assert not is_unaccented_vietnamese("thẩm định khác")[0]
    assert not is_unaccented_vietnamese("tri thức cơ bản")[0]
    assert not is_unaccented_vietnamese("OpenAI công bố loạt phát kiến khoa học nhờ AI")[0]
    assert not is_unaccented_vietnamese("Hello world this is a pure english test phrase")[0]


def test_accent_detection_negative():
    # Unaccented Vietnamese sentences / phrases should be flagged
    assert is_unaccented_vietnamese("May moc co the xu ly luong du lieu khong lo de tim ra quy luyet an giau.")[0]
    assert is_unaccented_vietnamese("Tuong tu nhu viec kiem tra tung vien gach xay nha")[0]
    assert is_unaccented_vietnamese("trieu thuc co ban")[0]
    assert is_unaccented_vietnamese("khoa hoc trong tuong lai")[0]
    assert is_unaccented_vietnamese("tham dinh khac khe")[0]
    assert is_unaccented_vietnamese("mo hinh goi y")[0]


def test_restore_known_accents():
    raw = "May moc co the xu ly luong du lieu khong lo de tim ra quy luyet an giau."
    restored = restore_known_accents(raw)
    assert "máy móc" in restored.lower()
    assert "quy luật ẩn giấu" in restored.lower()
    assert "dữ liệu khổng lồ" in restored.lower()

    exact_1 = restore_known_accents("tuong tu nhu viec")
    assert exact_1 == "tương tự như việc"

    exact_2 = restore_known_accents("mo hinh goi y")
    assert exact_2 == "mô hình gợi ý"

    exact_3 = restore_known_accents("tham dinh khac khe")
    assert exact_3 == "thẩm định khắt khe"


def test_audit_plan_accents():
    scenes = [
        Scene(
            id=1,
            role="hook",
            narration="Mình thử nhìn chuyện này từ cơ chế phía sau.",
            shots=[
                Shot(
                    type="stock_video",
                    query="science",
                    duration_sec=3.0,
                    effect="zoom_in",
                    text_overlay=None,
                    card_text="Ý tưởng mới",
                )
            ]
        ),
        Scene(
            id=2,
            role="body",
            narration="May moc co the xu ly luong du lieu khong lo de tim ra quy luyet an giau.",
            shots=[
                Shot(
                    type="stock_video",
                    query="computer",
                    duration_sec=3.0,
                    effect="zoom_in",
                    text_overlay=None,
                    card_text="Xu ly du lieu khong lo",
                )
            ]
        )
    ]
    plan = EditPlan(
        title="AI giải mã toán học",
        format="tiktok",
        voice="vi-VN-HoaiMyNeural",
        music={"mood": "calm", "volume": 0.1},
        scenes=scenes
    )
    violations = audit_plan_accents(plan)
    assert len(violations) > 0
    assert any("Cảnh 2" in v for v in violations)


def test_validation_rule_group_1_repair():
    brief = ResearchBrief(
        topic="Dựng video",
        language="vi",
        angle_candidates=[{"angle": "Quy trình", "why": "Dễ hiểu"}],
        facts=[{
            "claim": "Có thể cắt và ghép video.",
            "source_name": "Fixture",
            "source_url": "https://example.com",
            "confidence": "medium"
        }],
        trends=[],
        hooks=["Bắt đầu từ đâu?"],
        audience_questions=[],
        keywords=["video"],
        risks=[]
    )
    # Plan with known unaccented text that can be auto-repaired
    scene = Scene(
        id=1,
        role="hook",
        fact_ids=[1],
        narration="trieu thuc co ban giup may moc phan tich du lieu.",
        shots=[
            Shot(
                type="stock_video",
                query="tech",
                duration_sec=3.0,
                effect="zoom_in",
                text_overlay=None,
                card_text="trieu thuc co ban"
            )
        ]
    )
    scene2 = Scene(
        id=2,
        role="cta",
        narration="Bạn có thể kiểm tra kết quả ngay.",
        shots=[
            Shot(
                type="stock_video",
                query="tech",
                duration_sec=3.0,
                effect="zoom_in",
                text_overlay=None,
                card_text="Kiểm tra ngay"
            )
        ]
    )
    plan = EditPlan(
        title="AI giải mã toán học",
        format="tiktok",
        voice="vi-VN-HoaiMyNeural",
        music={"mood": "calm", "volume": 0.1},
        scenes=[scene, scene2]
    )
    
    # Run validation rules with auto repair
    events = run_rules(plan, brief, check_style=False)
    # The rule should repair "trieu thuc co ban" into "tri thức cơ bản"
    assert "tri thức cơ bản" in plan.scenes[0].narration.lower()
