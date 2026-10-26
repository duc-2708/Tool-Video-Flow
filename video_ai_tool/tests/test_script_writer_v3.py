"""Tests for Script Writer v3 (Prompt A) and its validation / self-repair rules."""
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from config.settings import Settings
from schemas.research_brief import ResearchBrief, Fact
from schemas.explainer import KnowledgeNote
from agents.director import DirectorRequest
from schemas.script_v3 import (
    ScriptV3Response,
    ScriptV3Scene,
    ScriptV3Sentence,
    normalize_script_v3_payload,
)
from agents.script_writer import (
    render_script_prompt,
    check_and_repair_script,
    to_edit_plan,
    create_script_v3_plan,
)
from utils.diagnostics import Diagnostics


@pytest.fixture
def sample_brief():
    return ResearchBrief(
        topic="Nắng nóng kỷ lục tại châu Âu",
        language="vi",
        angle_candidates=[{"angle": "Cơ chế nhiệt đô thị", "why": "Dễ hiểu"}],
        trends=[],
        hooks=["Hơn 50.000 người tử vong"],
        audience_questions=[],
        keywords=["nắng nóng", "châu Âu"],
        risks=[],
        facts=[
            Fact(claim="50.000 người chết do nắng nóng", fact_vi="Hơn 50.000 người tử vong vì nắng nóng kỷ lục tại châu Âu năm nay.", source_name="vnexpress.net", source_url="https://vnexpress.net/1", confidence="high", published_at="2026-10-24"),
            Fact(claim="20% nhà có điều hòa", fact_vi="Chỉ khoảng 20% nhà ở tại châu Âu được lắp điều hòa.", source_name="reuters.com", source_url="https://reuters.com/2", confidence="high", published_at="2026-10-24"),
            Fact(claim="Châu Âu ấm nhanh gấp đôi", fact_vi="Châu Âu ấm lên nhanh gấp đôi mức trung bình toàn cầu.", source_name="who.int", source_url="https://who.int/3", confidence="medium", published_at="2026-10-24"),
        ],
        knowledge_notes=[
            KnowledgeNote(
                text="Nhiệt cực đoan làm hệ làm mát cơ thể quá tải giống như cỗ máy thiếu quạt tản nhiệt.",
                analogy="Cỗ máy thiếu quạt tản nhiệt",
                confidence="medium",
                source="kiến thức nền",
            )
        ],
    )


@pytest.fixture
def sample_request():
    return DirectorRequest(
        video_type="news",
        video_format="tiktok",
        duration_sec=60.0,
        category="công nghệ",
        content_mode="explainer_v2",
    )


class MockProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0
        self.prompts = []

    def generate_json(self, prompt, schema=None):
        self.call_count += 1
        self.prompts.append(prompt)
        if not self.responses:
            raise RuntimeError("Hết mock response")
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def test_render_script_prompt(sample_brief):
    template = "VAI TRÒ: {CATEGORY}; THỜI LƯỢNG: {SECONDS}s; TỪ: ~{N}; CẢNH: {S}.\nTƯ LIỆU:\n<<<DÁN CÁC FACT/BÀI VIẾT VÀO ĐÂY>>>"
    rendered = render_script_prompt(template, sample_brief, "công nghệ", 60.0)
    assert "VAI TRÒ: công nghệ" in rendered
    assert "THỜI LƯỢNG: 60s" in rendered
    assert "Fact 1" in rendered
    assert "50.000" in rendered
    assert "Cỗ máy thiếu quạt tản nhiệt" in rendered


def test_script_writer_v3_valid_json_to_edit_plan(sample_brief, sample_request, tmp_path):
    settings = Settings(root_dir=tmp_path, default_voice="vi-VN-HoaiMyNeural", script_v3_enabled=True)
    diagnostics = Diagnostics(tmp_path / "logs")

    valid_payload = {
        "title": "Bẫy nhiệt châu Âu và cỗ máy quá tải",
        "central_metaphor": "Cỗ máy sinh học thiếu quạt làm mát",
        "scenes": [
            {
                "scene_id": 1,
                "purpose": "hook",
                "sentences": [
                    {"text": "Hơn 50.000 người đã tử vong vì đợt nắng nóng kỷ lục năm nay.", "type": "event", "fact_ids": [1]}
                ],
                "visual_hint": "Biểu đồ cột đỏ tăng vọt"
            },
            {
                "scene_id": 2,
                "purpose": "explain",
                "sentences": [
                    {"text": "Cơ thể con người vận hành như cỗ máy, khi quá nóng mà không kịp tản nhiệt sẽ bị kẹt.", "type": "explain", "fact_ids": []}
                ],
                "visual_hint": "Bình nước chịu áp lực"
            },
            {
                "scene_id": 3,
                "purpose": "example",
                "sentences": [
                    {"text": "Chỉ khoảng 20% nhà ở tại châu Âu có điều hòa.", "type": "event", "fact_ids": [2]},
                    {"text": "Thiết kế giữ ấm vô tình biến nhà cửa thành lò nhiệt mùa hè.", "type": "explain", "fact_ids": []}
                ],
                "visual_hint": "Mô hình căn hộ giữ nhiệt"
            },
            {
                "scene_id": 4,
                "purpose": "cta",
                "sentences": [
                    {"text": "Hạ tầng đô thị cần thay đổi khẩn cấp trước khi quá muộn.", "type": "opinion", "fact_ids": []},
                    {"text": "Theo bạn giải pháp nào là hiệu quả nhất lúc này?", "type": "cta", "fact_ids": []}
                ],
                "visual_hint": "Bình chọn tương tác"
            }
        ]
    }

    provider = MockProvider([valid_payload])
    plan = create_script_v3_plan(sample_brief, sample_request, provider, settings, diagnostics)

    assert plan is not None
    assert plan.title == "Bẫy nhiệt châu Âu và cỗ máy quá tải"
    assert len(plan.scenes) == 4
    assert plan.scenes[0].role == "hook"
    assert plan.scenes[-1].role == "cta"
    assert "50.000" in plan.scenes[0].narration
    assert any("Cỗ máy" in note for note in plan.review_notes)


def test_script_writer_v3_extra_keys_normalization():
    dirty_payload = {
        "title": "Tiêu đề chuẩn",
        "central_metaphor": "Cỗ máy tản nhiệt",
        "extra_llm_meta": "giá trị lạ cần bóc tách",
        "scenes": [
            {
                "scene_id": 1,
                "purpose": "hook",
                "unknown_scene_key": [1, 2, 3],
                "sentences": [
                    {
                        "text": "Câu sự kiện có số liệu.",
                        "type": "event",
                        "fact_ids": [1],
                        "extra_sentence_field": True
                    }
                ]
            }
        ]
    }

    normalized = normalize_script_v3_payload(dirty_payload)
    assert "extra_llm_meta" not in normalized
    assert "unknown_scene_key" not in normalized["scenes"][0]
    assert "extra_sentence_field" not in normalized["scenes"][0]["sentences"][0]

    # Validates cleanly via StrictModel
    parsed = ScriptV3Response.model_validate(normalized)
    assert parsed.title == "Tiêu đề chuẩn"
    assert any("[script_extra, nhóm 3]" in note for note in parsed.repair_notes)


def test_script_writer_v3_retry_on_corrupted_json(sample_brief, sample_request, tmp_path):
    settings = Settings(root_dir=tmp_path, retry_attempts=3, script_v3_enabled=True)
    diagnostics = Diagnostics(tmp_path / "logs")

    good_payload = {
        "title": "Kịch bản sau retry",
        "central_metaphor": "Cỗ máy làm mát",
        "scenes": [
            {
                "scene_id": 1,
                "purpose": "hook",
                "sentences": [{"text": "Hơn 50.000 người tử vong vì nắng nóng.", "type": "event", "fact_ids": [1]}]
            },
            {
                "scene_id": 2,
                "purpose": "cta",
                "sentences": [
                    {"text": "Đô thị cần thích ứng.", "type": "opinion", "fact_ids": []},
                    {"text": "Bạn nghĩ sao?", "type": "cta", "fact_ids": []}
                ]
            }
        ]
    }

    # First attempt raises ValueError (corrupted JSON), second attempt succeeds
    provider = MockProvider([ValueError("Invalid JSON syntax at byte 42"), good_payload])
    plan = create_script_v3_plan(sample_brief, sample_request, provider, settings, diagnostics)

    assert plan is not None
    assert provider.call_count == 2
    assert plan.title == "Kịch bản sau retry"


def test_script_writer_v3_self_repairs_hook_metaphor_and_cta(sample_brief, tmp_path):
    diagnostics = Diagnostics(tmp_path / "logs")

    # Script has:
    # 1. Boilerplate hook opening "Hôm nay mình sẽ nói về..."
    # 2. Empty central_metaphor
    # 3. Last scene missing question '?'
    # 4. Excessive hedging "có thể / có lẽ"
    # 5. Dangling sentence ending with "và"
    raw_script = ScriptV3Response(
        title="Tiêu đề thử nghiệm",
        central_metaphor="",  # Empty -> should auto-derive
        scenes=[
            ScriptV3Scene(
                scene_id=1,
                purpose="hook",
                sentences=[
                    ScriptV3Sentence(text="Hôm nay mình sẽ nói về hơn 50.000 người tử vong vì nắng nóng kỷ lục.", type="event", fact_ids=[1])
                ]
            ),
            ScriptV3Scene(
                scene_id=2,
                purpose="explain",
                sentences=[
                    ScriptV3Sentence(text="Có thể nhiệt độ cực đoan có lẽ làm cơ thể quá tải và", type="explain", fact_ids=[]),
                    ScriptV3Sentence(text="Dường như có thể các tế bào chịu áp lực lớn.", type="explain", fact_ids=[])
                ]
            ),
            ScriptV3Scene(
                scene_id=3,
                purpose="cta",
                sentences=[
                    ScriptV3Sentence(text="Hãy cùng hành động ngay hôm nay", type="cta", fact_ids=[])  # No '?'
                ]
            )
        ]
    )

    repaired = check_and_repair_script(raw_script, sample_brief, diagnostics)

    # 1. Boilerplate hook stripped
    assert not repaired.scenes[0].sentences[0].text.startswith("Hôm nay")
    assert "Hơn 50.000" in repaired.scenes[0].sentences[0].text

    # 2. Central metaphor derived from knowledge note
    assert "quạt tản nhiệt" in repaired.central_metaphor.lower() or "cỗ máy" in repaired.central_metaphor.lower()

    # 3. CTA question added
    assert any("?" in s.text for s in repaired.scenes[-1].sentences)

    # 4. Dangling "và" stripped
    assert not repaired.scenes[1].sentences[0].text.endswith(" và")
    assert not repaired.scenes[1].sentences[0].text.endswith(" và.")

    # 5. Repair notes recorded
    notes = repaired.repair_notes
    assert any("[hook, nhóm 2]" in n for n in notes)
    assert any("[metaphor, nhóm 2]" in n for n in notes)
    assert any("[cta, nhóm 2]" in n for n in notes)
    assert any("[syntax, nhóm 2]" in n for n in notes)


def test_script_writer_v3_fallback_to_director_on_fatal_error(sample_brief, sample_request, tmp_path, monkeypatch):
    from agents.director import create_edit_plan

    settings = Settings(root_dir=tmp_path, default_voice="vi-VN-HoaiMyNeural", script_v3_enabled=True, retry_attempts=2)
    diagnostics = Diagnostics(tmp_path / "logs")

    # Mock provider that always fails ScriptWriter v3
    failing_provider = MockProvider([RuntimeError("Fatal provider timeout"), RuntimeError("Fatal provider timeout")])

    mock_fallback_plan = MagicMock()
    mock_fallback_plan.title = "Fallback plan from legacy director"
    monkeypatch.setattr("agents.explainer_director.create_explainer_plan", lambda *args, **kwargs: mock_fallback_plan)

    plan = create_edit_plan(
        sample_brief,
        sample_request,
        failing_provider,
        settings,
        MagicMock(get=lambda *args: None, set=lambda *args: None),
        diagnostics,
    )
    assert plan is mock_fallback_plan
    # Check that diagnostic recorded fallback
    log_text = diagnostics.path.read_text(encoding="utf-8") if diagnostics.path.exists() else ""
    assert "Script Writer v3" in log_text


def test_script_writer_v3_event_grounding_no_false_positive_sentence_start(sample_brief):
    from agents.validation_rules import names_quotes, Context
    from schemas.edit_plan import EditPlan, Scene, Shot
    from schemas.explainer import ScriptSentence

    # Sentence starts with capitalized Vietnamese words like "Khoảng", "Hơn", "Đợt"
    scene1 = Scene(
        id=1,
        role="hook",
        narration="Hơn 50.000 người tử vong vì nắng nóng kỷ lục tại châu Âu.",
        sentences=[
            ScriptSentence(type="event", text="Hơn 50.000 người tử vong vì nắng nóng kỷ lục tại châu Âu.", fact_ids=[1])
        ],
        shots=[Shot(type="stock_video", query="heatwave", duration_sec=5.0, planning_duration=True, effect="zoom_in", text_overlay=None)],
        fact_ids=[1],
    )
    scene2 = Scene(
        id=2,
        role="cta",
        narration="Đô thị cần thay đổi ra sao? Hãy bình luận.",
        sentences=[
            ScriptSentence(type="cta", text="Đô thị cần thay đổi ra sao? Hãy bình luận.", fact_ids=[])
        ],
        shots=[Shot(type="stock_video", query="city", duration_sec=5.0, planning_duration=True, effect="zoom_in", text_overlay=None)],
        fact_ids=[],
    )
    plan = EditPlan(
        title="Test Grounding",
        format="tiktok",
        voice="vi-VN-HoaiMyNeural",
        music={"mood": "calm", "volume": 0.08},
        scenes=[scene1, scene2],
        content_mode="explainer_v2",
        content_timed=True,
    )
    ctx = Context(plan, sample_brief)
    issues = names_quotes(ctx)
    # Ensure "Hơn" is not falsely reported as an ungrounded proper name
    name_issues = [i for i in issues if "Tên riêng không có trong brief" in i.message]
    assert len(name_issues) == 0, f"Bị báo nhầm chữ đầu câu viết hoa thành tên riêng: {name_issues}"


def test_script_v3_disabled_runs_legacy_director(sample_brief, sample_request, tmp_path, monkeypatch):
    from agents.director import create_edit_plan

    settings = Settings(root_dir=tmp_path, default_voice="vi-VN-HoaiMyNeural", script_v3_enabled=False)
    diagnostics = Diagnostics(tmp_path / "logs")

    called_legacy = []
    mock_legacy_plan = MagicMock()
    mock_legacy_plan.title = "Legacy Director Plan"

    monkeypatch.setattr("agents.explainer_director.create_explainer_plan", lambda *args, **kwargs: (called_legacy.append(True), mock_legacy_plan)[1])

    plan = create_edit_plan(
        sample_brief,
        sample_request,
        MockProvider([]),
        settings,
        MagicMock(get=lambda *args: None, set=lambda *args: None),
        diagnostics,
    )
    assert plan is mock_legacy_plan
    assert len(called_legacy) == 1
