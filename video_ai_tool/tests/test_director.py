# file: tests/test_director.py
"""Director: duration, grounding, retry, cache và lưu an toàn; không gọi mạng."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from pydantic import SecretStr
from agents.director import (DirectorError, DirectorRequest, brief_hash, create_edit_plan,
    director_diagnostics, run_director, save_edit_plan, validate_plan, timing_blueprint, review_notes_for)
from config.settings import ROOT_DIR, Settings
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from utils.cache import JsonCache, write_json


def fixture_brief() -> ResearchBrief:
    return ResearchBrief(topic="Dựng video", language="vi", angle_candidates=[{"angle": "Quy trình", "why": "Dễ hiểu"}],
        facts=[{"claim": "Có thể cắt và ghép video.", "source_name": "Fixture", "source_url": "https://example.com",
                "confidence": "medium"}], trends=[], hooks=["Bắt đầu từ đâu?"], audience_questions=[], keywords=["video"], risks=[])


def fixture_plan() -> dict:
    scenes = []
    for index in range(1, 9):
        is_cta = index == 8
        shot = {"type": "stock_video", "query": "video editing", "duration_sec": 3.0,
                "effect": "zoom_in", "text_overlay": None}
        scenes.append({"id": index, "role": "hook" if index == 1 else "cta" if is_cta else "body",
            "narration": "Bạn muốn tìm hiểu bước nào?" if is_cta else "Bạn có thể cắt và ghép video.",
            "shots": [deepcopy(shot)] if index == 1 else [deepcopy(shot), deepcopy(shot)],
            "transition_out": "cut", "sfx": "pop", "pattern_interrupt": index >= 3,
            "fact_ids": [] if is_cta else [1]})
    return {"title": "Dựng video", "format": "tiktok", "voice": "vi-VN-HoaiMyNeural",
            "music": {"mood": "calm", "volume": 0.1}, "scenes": scenes}


class FakeDirector:
    model_name = "director-fixture"
    def __init__(self, plans: list[dict | str], audits: list[dict] | None = None) -> None:
        self.plans, self.audits = plans, audits or [{"approved": True, "issues": []}]
        self.plan_calls = 0
        self.audit_calls = 0
        self.prompts = []
        self.close = Mock()

    def generate_json(self, prompt: str, schema: type) -> str:
        self.prompts.append((schema, prompt))
        if schema is EditPlan or schema.__name__ == "SceneRepairs":
            value = self.plans[min(self.plan_calls, len(self.plans) - 1)]
            self.plan_calls += 1
            if schema.__name__ == "SceneRepairs" and isinstance(value,dict):
                value = {"scenes":value["scenes"]}
        else:
            value = self.audits[min(self.audit_calls, len(self.audits) - 1)]
            self.audit_calls += 1
        return value if isinstance(value, str) else json.dumps(value)


@pytest.fixture
def director_settings(tmp_path: Path) -> Settings:
    (tmp_path / "prompts").mkdir()
    for name in ("director_common.txt", "director_review.txt", "director_news.txt", "director_story.txt", "director_audit.txt"):
        (tmp_path / "prompts" / name).write_text((ROOT_DIR / "prompts" / name).read_text(encoding="utf-8"), encoding="utf-8")
    return Settings(root_dir=tmp_path, gemini_api_key=SecretStr("fixture-only"), gemini_model="research-fixture", retry_attempts=2)


def test_director_model_fallback_and_override() -> None:
    assert Settings(gemini_model="research").require_director_model() == "research"
    assert Settings(gemini_model="research", gemini_director_model="  director  ").require_director_model() == "director"
    assert Settings(gemini_director_model="director").require_director_model() == "director"


def test_retry_json_validate_and_cache(director_settings: Settings) -> None:
    provider = FakeDirector(["bad json", fixture_plan()])
    request = DirectorRequest(script_style=None,video_type="review", video_format="tiktok", duration_sec=45.0)
    cache = JsonCache(director_settings.cache_dir)
    plan = create_edit_plan(fixture_brief(), request, provider, director_settings, cache,
                            director_diagnostics(director_settings), progress=lambda m: None)
    assert plan.duration_sec == 45 and plan.target_duration_sec == 45 and plan.brief_hash
    assert provider.plan_calls == 2 and provider.audit_calls == 1
    create_edit_plan(fixture_brief(), request, provider, director_settings, cache,
                     director_diagnostics(director_settings), progress=lambda m: None)
    assert provider.plan_calls == 2 and provider.audit_calls == 1


@pytest.mark.parametrize("change", ["duration", "unknown_fact", "banned", "format", "interrupt", "stale"])
def test_reject_invalid_plan(change: str) -> None:
    data, brief = fixture_plan(), fixture_brief()
    if change == "duration":
        data["scenes"].pop()
        data["scenes"][-1]["role"] = "cta"
    elif change == "unknown_fact":
        data["scenes"][0]["fact_ids"] = [2]
    elif change == "banned":
        data["scenes"][0]["narration"] = "Chưa xác minh: có thể cắt và ghép video."
    elif change == "invented_number":
        data["scenes"][1]["narration"] = "Bạn kiếm 100 triệu mỗi tháng."
    elif change == "format":
        data["format"] = "youtube"
    elif change == "interrupt":
        for scene in data["scenes"]:
            scene["pattern_interrupt"] = False
    else:
        data["brief_hash"] = "old"
    request=DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45.0)
    if change=="unknown_fact":
        with pytest.raises(ValueError,match="fact_id"): validate_plan(EditPlan.model_validate(data),brief,request)
    else:
        result=validate_plan(EditPlan.model_validate(data),brief,request)
        assert result.validation_events


def test_audit_rejects_unsupported_semantics_then_retries(director_settings: Settings) -> None:
    wrong = fixture_plan()
    wrong["scenes"][1]["narration"] = "Đây là phần mềm tốt nhất."
    provider = FakeDirector([wrong, fixture_plan()], [{"approved": False, "issues": ["Cảnh 2 không có căn cứ so sánh."]}, {"approved": True, "issues": []}])
    result = create_edit_plan(fixture_brief(), DirectorRequest(script_style=None,video_type="review", video_format="tiktok", duration_sec=45.0),
        provider, director_settings, JsonCache(director_settings.cache_dir), director_diagnostics(director_settings), lambda m: None)
    assert result and provider.plan_calls == 2 and provider.audit_calls == 2


def test_pipeline_and_save_revalidate_and_keep_existing_on_failure(director_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    import agents.director as module
    path = director_settings.output_dir / "fixture" / "brief.json"
    write_json(path, fixture_brief().model_dump(mode="json"))
    provider = FakeDirector([fixture_plan()])
    monkeypatch.setattr(module, "director_provider", lambda *args: provider)
    result = run_director(path, director_settings, progress=lambda m: None,script_style=None)
    assert result.name == "edit_plan.json" and provider.close.call_count == 1
    data = json.loads(result.read_text(encoding="utf-8"))
    data["scenes"][1]["narration"] = "Cắt video rồi ghép video."
    save_edit_plan(path, data, director_settings)
    previous = result.read_bytes()
    data["scenes"][1]["narration"] = "Tăng thu nhập 999 triệu."
    provider.audits = [{"approved":False,"issues":["Cảnh 2 không có căn cứ thu nhập."]}]
    with pytest.raises(ValueError):
        save_edit_plan(path, data, director_settings)
    assert result.read_bytes() == previous


def test_no_usable_facts_and_exhaustion(director_settings: Settings) -> None:
    provider = FakeDirector(["invalid"])
    request = DirectorRequest(script_style=None,video_type="review", video_format="tiktok", duration_sec=45.0)
    brief = fixture_brief()
    brief.facts = []
    with pytest.raises(DirectorError):
        create_edit_plan(brief, request, provider, director_settings, JsonCache(director_settings.cache_dir), director_diagnostics(director_settings))
    assert provider.plan_calls == 0
    with pytest.raises(DirectorError):
        create_edit_plan(fixture_brief(), request, provider, director_settings, JsonCache(director_settings.cache_dir), director_diagnostics(director_settings), lambda m: None)
    assert provider.plan_calls == 2


@pytest.mark.parametrize("duration", [6, 7, 9, 10, 15, 45, 59.7, 60, 600])
def test_timing_blueprint(duration: float) -> None:
    schedule = timing_blueprint(duration)
    assert abs(sum(sum(scene["shot_durations_sec"]) for scene in schedule) - duration) < 0.0001
    assert all(1.5 <= value <= 4 for scene in schedule for value in scene["shot_durations_sec"])
    assert schedule[0]["role"] == "hook" and schedule[-1]["role"] == "cta"


def test_low_confidence_uses_attribution_without_uncertainty_warning() -> None:
    brief = fixture_brief()
    brief.facts[0].confidence = "low"
    data = fixture_plan()
    for scene in data["scenes"]:
        if scene["fact_ids"]:
            scene["narration"] = "Có thể cắt và ghép video."
    plan = validate_plan(EditPlan.model_validate(data), brief,
                         DirectorRequest(script_style=None,video_type="review", video_format="tiktok", duration_sec=45.0))
    assert plan.scenes[0].narration == "Theo example.com, Có thể cắt và ghép video."
    assert plan.scenes[0].review_notes.confidence == "low"


def test_review_notes_replace_labels_but_still_reject_invented_numbers() -> None:
    brief = fixture_brief()
    brief.facts[0].confidence = "low"
    data = fixture_plan()
    data["scenes"][1]["shots"][0]["text_overlay"] = "Cắt ghép video"
    plan = EditPlan.model_validate(data)
    request = DirectorRequest(script_style=None,video_type="review", video_format="tiktok", duration_sec=45.0)
    validate_plan(plan, brief, request)
    assert plan.scenes[0].narration.startswith("Theo example.com,")
    assert plan.scenes[1].shots[0].text_overlay == "Cắt ghép video"
    assert plan.scenes[0].review_notes.source_count == 1
    assert plan.scenes[0].review_notes.facts[0].sources[0].name == "example.com"
    assert str(plan.scenes[0].review_notes.facts[0].sources[0].url) == "https://example.com/"
    plan.scenes[1].narration += " Earn 999 million."
    with pytest.raises(ValueError,match="grounding_numbers"):
        validate_plan(plan,brief,request)


def test_director_provider_selects_model_without_changing_researcher(director_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    import agents.director as module
    settings = director_settings.model_copy(update={"gemini_director_model": "separate-director"})
    provider=module.director_provider(settings, director_diagnostics(settings))
    assert provider.router.primary=="gemini" and provider.model_name=="separate-director"
    assert settings.gemini_model == "research-fixture"


@pytest.mark.parametrize("phrase", ["Chưa xác minh", "CHƯA KIỂM CHỨNG", "cần xác minh", "Theo thông tin sơ bộ chưa kiểm chứng", "chưa được xác minh", "Chưa\nkiểm chứng"])
@pytest.mark.parametrize("field", ["narration", "text_overlay", "on_screen_text"])
def test_forbidden_phrases_rejected_in_all_video_text(phrase, field):
    data = fixture_plan()
    if field == "narration":
        data["scenes"][1][field] = phrase+": cắt ghép video."
    else:
        shot = data["scenes"][1]["shots"][0]
        if field == "on_screen_text":
            shot.pop("text_overlay")
        shot[field] = phrase+": Cắt ghép"
    plan=validate_plan(EditPlan.model_validate(data),fixture_brief(),DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45.))
    from agents.director import FORBIDDEN_EDITORIAL
    import re
    assert not any(re.search(FORBIDDEN_EDITORIAL,s.narration+" "+" ".join(x.text_overlay or "" for x in s.shots),re.I) for s in plan.scenes)
    assert any(e.rule_id=="forbidden_editorial" and e.action=="fixed" for e in plan.validation_events)


def test_director_regenerates_banned_copy_and_keeps_review_sources(director_settings):
    invalid = fixture_plan()
    invalid["scenes"][1]["narration"] = "Theo thông tin sơ bộ chưa kiểm chứng, có thể cắt ghép video."
    invalid["scenes"][1]["shots"][0]["text_overlay"] = "Chưa xác minh"
    brief = fixture_brief()
    brief.facts[0].confidence = "low"
    provider = FakeDirector([invalid, fixture_plan()])
    result = create_edit_plan(brief, DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45.),provider,
        director_settings,JsonCache(director_settings.cache_dir),director_diagnostics(director_settings),lambda m:None)
    assert provider.plan_calls == 1 and provider.audit_calls == 1
    for scene in result.scenes:
        visible = scene.narration+" "+" ".join(shot.text_overlay or "" for shot in scene.shots)
        assert not any(phrase in visible.casefold() for phrase in ["chưa xác minh","chưa kiểm chứng","cần xác minh"])
    notes = result.scenes[1].review_notes
    assert notes.fact_ids == [1] and notes.source_count == 1 and notes.confidence == "low"
    assert str(notes.facts[0].sources[0].url) == str(brief.facts[0].source_url)
    assert not any(schema.__name__=="SceneRepairs" for schema,_ in provider.prompts)
    # A second pass through validation cannot duplicate the attribution.
    validate_plan(result,brief,DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45.))
    assert result.scenes[1].narration.count("Theo example.com,") == 1


def test_same_fact_two_domains_speaks_directly_with_full_review_sources():
    brief = fixture_brief()
    other = brief.facts[0].model_copy(update={"source_url": __import__("pydantic").HttpUrl("https://second.example/news")})
    brief.facts.append(other)
    plan = validate_plan(EditPlan.model_validate(fixture_plan()), brief, DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45.))
    assert not plan.scenes[0].narration.startswith("Theo ")
    notes = plan.scenes[0].review_notes
    assert notes.source_count == 2 and set(notes.fact_ids)<= {1,2}
    assert {source.name for source in notes.facts[0].sources} == {"example.com","second.example"}
    assert {source.fact_id for source in notes.facts[0].sources} == {1,2}


def test_two_urls_same_domain_still_one_source():
    from pydantic import HttpUrl
    brief = fixture_brief()
    brief.facts.append(brief.facts[0].model_copy(update={"source_url":HttpUrl("https://www.example.com/another")}))
    notes = review_notes_for([1],brief)
    assert notes.source_count == 1 and len(notes.facts[0].sources) == 2


def test_different_claims_not_conflated_as_two_sources():
    from pydantic import HttpUrl
    brief = fixture_brief()
    brief.facts.append(brief.facts[0].model_copy(update={"claim":"Có thể thay đổi tốc độ video.","source_url":HttpUrl("https://second.example/news")}))
    notes = review_notes_for([1,2],brief)
    assert notes.source_count == 2 and all(fact.source_count == 1 for fact in notes.facts)
    data = fixture_plan()
    data["scenes"][1]["fact_ids"] = [1,2]
    plan=validate_plan(EditPlan.model_validate(data),brief,DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45.))
    assert any(e.rule_id=="attribution" and e.action=="fixed" for e in plan.validation_events)
    assert all(f.source_count==1 for f in review_notes_for([1,2],brief).facts)


def test_review_notes_forgery_recomputed_and_domain_digits_not_claim_numbers():
    from pydantic import HttpUrl
    brief = fixture_brief()
    brief.facts[0].source_url = HttpUrl("https://9to5mac.com/news")
    plan = validate_plan(EditPlan.model_validate(fixture_plan()),brief,DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45.))
    assert plan.scenes[0].narration.startswith("Theo 9to5mac.com,")
    plan.scenes[0].review_notes.source_count = 999
    validate_plan(plan,brief,DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45.))
    assert plan.scenes[0].review_notes.source_count == 1
    assert plan.scenes[-1].review_notes.source_count == 0 and plan.scenes[-1].review_notes.confidence is None


def test_overlay_short_and_alias_serializes_to_renderer_field():
    data = fixture_plan()
    shot = data["scenes"][0]["shots"][0]
    shot.pop("text_overlay")
    shot["on_screen_text"] = "Cắt ghép video"
    plan = EditPlan.model_validate(data)
    assert plan.model_dump()["scenes"][0]["shots"][0]["text_overlay"] == "Cắt ghép video"
    assert "review_notes" not in plan.model_dump()["scenes"][0]
    plan.scenes[1].shots[0].text_overlay = " ".join(["video"]*13)
    validate_plan(plan,fixture_brief(),DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45.))
    assert any(e.rule_id=="overlay_style" and e.group==3 for e in plan.validation_events)


def test_director_uses_trend_insights_for_style_not_new_facts(director_settings):
    from schemas.research_brief import TrendInsights
    from tests.test_youtube_trends import insight_fixture
    brief = fixture_brief()
    brief.trend_insights = TrendInsights.model_validate(insight_fixture())
    provider = FakeDirector([fixture_plan()])
    request = DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45.)
    plan = create_edit_plan(brief,request,provider,director_settings,JsonCache(director_settings.cache_dir),director_diagnostics(director_settings),lambda message:None)
    prompt = next(prompt for schema,prompt in provider.prompts if schema is EditPlan)
    assert '"trend_insights"' in prompt and "Mở bằng câu hỏi bắt đầu từ đâu" in prompt
    assert "Không dùng trend_insights" in prompt
    plan.scenes[1].narration = "Video này đã có 999999 lượt xem."
    with pytest.raises(ValueError,match="grounding_numbers"):
        validate_plan(plan,brief,request)


@pytest.mark.parametrize("duration,allowed", [(40.5, True), (49.5, True), (40.49, False), (49.51, False)])
def test_duration_tolerance_boundaries(duration: float, allowed: bool) -> None:
    data = fixture_plan()
    for scene in data["scenes"][1:]:
        for shot in scene["shots"]:
            shot["duration_sec"] = (duration - 3) / 14
    plan = EditPlan.model_validate(data)
    if allowed:
        plan.validate_target_duration(45.0)
    else:
        plan.validate_target_duration(45.0)
        assert plan.duration_sec==pytest.approx(45.0)
