"""Regression tests for CTA event claim detection and 3-step auto-repair."""
import pytest
from pathlib import Path

from schemas.research_brief import ResearchBrief, Fact
from schemas.explainer import ScriptSentence
from schemas.edit_plan import EditPlan, Scene, Shot
from agents.explainer_guard import (
    is_cta_event_claim,
    repair_cta_sentences,
    sentence_issues,
)
from agents.validation_rules import run_rules, RuleViolation
from agents.director import validate_plan, DirectorRequest


@pytest.fixture
def sample_brief():
    return ResearchBrief(
        topic="Vụ kiện bản quyền âm nhạc AI",
        language="vi",
        angle_candidates=[{"angle": "Tranh chấp bản quyền AI", "why": "Nóng bỏng"}],
        trends=[],
        hooks=["Vụ kiện đòi bồi thường 1 tỷ USD"],
        audience_questions=[],
        keywords=["Round Hill Music", "Anthropic", "bản quyền", "AI"],
        risks=[],
        facts=[
            Fact(
                fact_vi="Round Hill Music đã nộp hai đơn kiện đòi bồi thường 1 tỷ USD.",
                claim="Round Hill Music đã nộp hai đơn kiện đòi bồi thường 1 tỷ USD.",
                source_name="Reuters",
                source_url="https://reuters.com/music-ai-lawsuit",
                confidence="high",
            ),
            Fact(
                fact_vi="Luật sở hữu trí tuệ chính thức có hiệu lực từ tháng 4 năm 2026 tại Việt Nam.",
                claim="Luật sở hữu trí tuệ chính thức có hiệu lực từ tháng 4 năm 2026 tại Việt Nam.",
                source_name="VnExpress",
                source_url="https://vnexpress.net/luat-shtt-2026",
                confidence="high",
            ),
        ],
    )


def _make_plan(cta_sentences: list[ScriptSentence]) -> EditPlan:
    scene1 = Scene(
        id=1,
        role="hook",
        narration="Âm nhạc và trí tuệ nhân tạo đang bước vào một cuộc chiến pháp lý căng thẳng.",
        sentences=[
            ScriptSentence(
                text="Âm nhạc và trí tuệ nhân tạo đang bước vào một cuộc chiến pháp lý căng thẳng.",
                type="explain",
                fact_ids=[],
            )
        ],
        shots=[Shot(type="stock_video", query="music", duration_sec=4.0, planning_duration=True, effect="zoom_in", text_overlay=None)],
        fact_ids=[],
    )
    cta_narration = " ".join(s.text for s in cta_sentences)
    scene2 = Scene(
        id=2,
        role="cta",
        narration=cta_narration,
        sentences=cta_sentences,
        shots=[Shot(type="stock_video", query="outro", duration_sec=4.0, planning_duration=True, effect="none", text_overlay=None)],
        fact_ids=[fid for s in cta_sentences for fid in s.fact_ids],
    )
    return EditPlan(
        title="Tranh chấp bản quyền AI",
        format="tiktok",
        voice="vi-VN-HoaiMyNeural",
        music={"mood": "calm", "volume": 0.08},
        scenes=[scene1, scene2],
        content_mode="explainer_v2",
        content_timed=True,
    )


def test_cta_pure_question_and_invitation_exempt(sample_brief):
    """Pure questions and comment invitations must never be flagged as event claims."""
    # Pure question with 'đã' in relative clause
    assert (
        is_cta_event_claim(
            "Liệu các mô hình trí tuệ nhân tạo có phải trả tiền cho từng giai điệu đã học không?",
            sample_brief,
        )
        is False
    )

    # General invitation with count
    assert (
        is_cta_event_claim(
            "Bạn nghĩ sao về điều này? Hãy để lại 1 bình luận bên dưới nhé!",
            sample_brief,
        )
        is False
    )

    # Pure channel follow call
    assert (
        is_cta_event_claim(
            "Đừng quên bấm theo dõi kênh để cập nhật tin công nghệ mới nhất!",
            sample_brief,
        )
        is False
    )

    # Question with perspective
    assert (
        is_cta_event_claim(
            "Theo bạn thì liệu công nghệ này có thực sự hữu ích không?",
            sample_brief,
        )
        is False
    )


def test_cta_with_fact_match_relabels_to_event(sample_brief):
    """CTA with empirical fact assertion matches brief fact -> splits into event + cta question."""
    plan = _make_plan([
        ScriptSentence(
            text="Round Hill Music đã nộp hai đơn kiện đòi 1 tỷ USD, bạn nghĩ sao?",
            type="cta",
            fact_ids=[],
        )
    ])

    # Issues initially detected
    issues = sentence_issues(plan, sample_brief)
    assert any("CTA không được chứa khẳng định sự kiện" in msg for _, msg in issues)

    # Run repair
    repaired = repair_cta_sentences(plan, sample_brief)
    assert len(repaired) == 1
    assert "khớp fact" in repaired[0][1]

    # Verify split sentences in scene 2
    sentences = plan.scenes[1].sentences
    assert len(sentences) == 2
    assert sentences[0].type == "event"
    assert sentences[0].fact_ids == [1]
    assert sentences[1].type == "cta"

    # Re-check issues -> clean!
    assert len(sentence_issues(plan, sample_brief)) == 0


def test_cta_with_opinion_relabels_to_opinion(sample_brief):
    """CTA with general opinion assertion -> relabels assertion to opinion, keeps cta question."""
    plan = _make_plan([
        ScriptSentence(
            text="Theo mình thì các mô hình AI trong tương lai sẽ phải chia sẻ doanh thu cho nghệ sĩ.",
            type="cta",
            fact_ids=[],
        )
    ])

    repaired = repair_cta_sentences(plan, sample_brief)
    assert len(repaired) == 1

    sentences = plan.scenes[1].sentences
    assert any(s.type == "opinion" for s in sentences)
    assert any(s.type == "cta" for s in sentences)

    # Re-check issues -> clean!
    assert len(sentence_issues(plan, sample_brief)) == 0


def test_cta_with_ungrounded_assertion_cuts_assertion(sample_brief):
    """CTA with ungrounded assertion -> cuts assertion, keeps pure cta question, does not halt."""
    plan = _make_plan([
        ScriptSentence(
            text="Hacker X vừa hack 999 bài hát từ bảo tàng âm nhạc bí mật, bạn có tin không?",
            type="cta",
            fact_ids=[],
        )
    ])

    repaired = repair_cta_sentences(plan, sample_brief)
    assert len(repaired) == 1
    assert "Cắt bỏ khẳng định không có căn cứ" in repaired[0][1]

    sentences = plan.scenes[1].sentences
    assert len(sentences) >= 1
    assert sentences[-1].type == "cta"
    assert "Hacker X" not in sentences[-1].text
    assert "999" not in sentences[-1].text

    # Re-check issues -> clean!
    assert len(sentence_issues(plan, sample_brief)) == 0


def test_validation_rules_auto_repairs_cta_without_exception(sample_brief):
    """Integration test: validate_plan auto-repairs CTA event claims via Group 2 repair without raising RuleViolation."""
    plan = _make_plan([
        ScriptSentence(
            text="Luật sở hữu trí tuệ chính thức có hiệu lực từ tháng 4 năm 2026 tại Việt Nam.",
            type="cta",
            fact_ids=[],
        ),
        ScriptSentence(
            text="Liệu các mô hình trí tuệ nhân tạo có phải trả tiền cho từng giai điệu đã học không?",
            type="cta",
            fact_ids=[],
        ),
    ])

    request = DirectorRequest(video_type="news", video_format="tiktok", duration_sec=30)
    repaired_plan = validate_plan(plan, sample_brief, request, check_style=False, allow_merge=False)
    assert repaired_plan is not None
    # Scene 2 sentence 1 should be converted to event with fact_ids=[2]
    assert repaired_plan.scenes[1].sentences[0].type == "event"
    assert repaired_plan.scenes[1].sentences[0].fact_ids == [2]
    # Sentence 2 should remain cta
    assert repaired_plan.scenes[1].sentences[1].type == "cta"
