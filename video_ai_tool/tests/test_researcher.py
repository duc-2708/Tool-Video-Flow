# file: tests/test_researcher.py
"""Kiểm thử Researcher offline; không đọc .env và không dùng API thật."""
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from agents.researcher import ResearchError, create_brief, run_research, validate_grounding
from config.settings import ROOT_DIR, Settings
from providers.llm_base import LLMProvider
from schemas.research_brief import ResearchBrief, SearchQuery
from schemas.source import SourceDocument
from utils.cache import JsonCache
from utils.diagnostics import Diagnostics


@pytest.fixture
def source() -> SourceDocument:
    return SourceDocument(title="Fixture", url="https://example.com/article", source_name="example.com",
        platform="web", content_kind="article", text="Dữ liệu này chỉ là ví dụ phục vụ kiểm thử phần mềm.",
        retrieved_at="2026-10-20T00:00:00Z")


def fake_queries(*args):
    return [SearchQuery(source_lang="vi",query="fixture query one",region="vn-vi"),SearchQuery(source_lang="en",query="video editing basics",region="us-en")]


def response_data(source: SourceDocument) -> dict:
    return {"topic": "Dựng video", "language": "vi", "angle_candidates": [{"angle": "Quy trình", "why": "Dễ hiểu"}],
        "facts": [{"claim": claim, "fact_vi": claim, "source_name": "AI tự đặt tên", "source_url": str(source.url),
                   "confidence": "high", "evidence_quote": quote} for claim, quote in [
                       ("Đây là fixture ví dụ.", "Dữ liệu này chỉ là ví dụ"),
                       ("Ví dụ phục vụ kiểm thử.", "ví dụ phục vụ kiểm thử"),
                       ("Nội dung đề cập kiểm thử phần mềm.", "phục vụ kiểm thử phần mềm.")]],
        "trends": [], "hooks": ["Quy trình nào phù hợp?"], "audience_questions": [], "keywords": ["video"], "risks": []}


class FakeLLM(LLMProvider):
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0
        self.prompts = []

    @property
    def model_name(self) -> str:
        return "offline-fixture"

    def generate_json(self, prompt: str, schema: type) -> str:
        self.prompts.append(prompt)
        value = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return value


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # Prompt thật; mọi credentials và cache là fixture, không nạp .env.
    return Settings(root_dir=tmp_path, retry_attempts=2)


def test_retry_invalid_json_and_cache(source: SourceDocument, settings: Settings) -> None:
    (settings.root_dir / "prompts").mkdir()
    (settings.prompts_dir / "researcher.txt").write_text((ROOT_DIR / "prompts/researcher.txt").read_text(encoding="utf-8"), encoding="utf-8")
    llm = FakeLLM(["not json", json.dumps(response_data(source))])
    cache = JsonCache(settings.cache_dir)
    brief = create_brief("Dựng video", [source], llm, settings, cache)
    assert llm.calls == 2
    assert brief.facts[0].source_name == "example.com"
    assert brief.facts[0].confidence == "medium"
    assert create_brief("Dựng video", [source], llm, settings, cache) == brief
    assert llm.calls == 2


@pytest.mark.parametrize("change", ["url", "quote", "social_fact", "topic", "trend_platform"])
def test_reject_invented_evidence(source: SourceDocument, change: str, settings: Settings) -> None:
    data = response_data(source)
    if change == "url":
        data["facts"][0]["source_url"] = "https://invented.example/fact"
    elif change == "quote":
        data["facts"][0]["evidence_quote"] = "Thông tin này không hề có trong tài liệu"
    elif change == "social_fact":
        source.platform, source.content_kind = "youtube", "social_signal"
    elif change == "topic":
        data["topic"] = "Chủ đề khác"
    else:
        data["trends"] = [{"signal": "Ví dụ", "platform": "youtube", "evidence_url": str(source.url)}]
    if change in {"url","quote"}:
        result=validate_grounding(ResearchBrief.model_validate(data), "Dựng video", [source], diagnostics=Diagnostics(settings.logs_dir))
        assert len(result.facts)==2 and all(str(f.source_url)==str(source.url) and f.evidence_quote in source.text for f in result.facts)
    else:
        with pytest.raises(ValueError if change in {"topic", "trend_platform"} else ResearchError):
            validate_grounding(ResearchBrief.model_validate(data), "Dựng video", [source], diagnostics=Diagnostics(settings.logs_dir))


def test_snippet_fact_always_low(source: SourceDocument, settings: Settings) -> None:
    source.content_kind = "snippet"
    brief = validate_grounding(ResearchBrief.model_validate(response_data(source)), "Dựng video", [source], diagnostics=Diagnostics(settings.logs_dir))
    assert brief.facts[0].confidence == "low"


def test_empty_sources_does_not_call_llm(settings: Settings) -> None:
    llm = FakeLLM(["{}"])
    with pytest.raises(ResearchError):
        create_brief("Dựng video", [], llm, settings, JsonCache(settings.cache_dir))
    assert llm.calls == 0


def test_retry_exhaustion(source: SourceDocument, settings: Settings) -> None:
    settings.prompts_dir.mkdir()
    (settings.prompts_dir / "researcher.txt").write_text("Fixture prompt", encoding="utf-8")
    llm = FakeLLM(["{}"])
    with pytest.raises(ResearchError):
        create_brief("Dựng video", [source], llm, settings, JsonCache(settings.cache_dir))
    assert llm.calls == 2


def test_pipeline_writes_artifacts_without_real_api(source: SourceDocument, settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    import agents.researcher as module
    settings = settings.model_copy(update={"gemini_api_key": __import__("pydantic").SecretStr("fixture-only"), "gemini_model": "fixture"})
    settings.prompts_dir.mkdir()
    (settings.prompts_dir / "researcher.txt").write_text("Fixture prompt", encoding="utf-8")
    monkeypatch.setattr(module.WebSearch, "collect", lambda *a: ([source], []))
    monkeypatch.setattr(module, "generate_queries", fake_queries)
    llm = FakeLLM([json.dumps(response_data(source))])
    llm.close = Mock()
    monkeypatch.setattr(module, "GeminiProvider", lambda s: llm)
    path = run_research("Dựng video", settings, use_youtube=False, progress=lambda message: None)
    assert path.exists() and (path.parent / "sources.json").exists()
    assert ResearchBrief.model_validate_json(path.read_text(encoding="utf-8")).facts
    llm.close.assert_called_once()


def prepare_prompt(settings):
    settings.prompts_dir.mkdir(exist_ok=True)
    (settings.prompts_dir / "researcher.txt").write_text((ROOT_DIR / "prompts/researcher.txt").read_text(encoding="utf-8"), encoding="utf-8")


def fact_for(source, quote):
    return {"claim": "Dữ liệu kiểm thử có nguồn.", "source_name": "Fixture", "source_url": str(source.url),
            "confidence": "medium", "fact_vi": "Dữ liệu kiểm thử có nguồn.", "evidence_quote": quote}


def test_filter_and_trim_individual_facts(source, settings):
    # 41 short words: first 25 fit the 200-character limit. Preserve whitespace
    # from the original quote instead of inventing a replacement sentence.
    long_quote = " \n ".join([f"từ{i}" for i in range(41)])
    source.text += " " + long_quote
    data = response_data(source)
    data["facts"] += [fact_for(source, long_quote), fact_for(source, "Câu này hoàn toàn không tồn tại trong nguồn.")]
    original = ResearchBrief.model_validate(data)
    warnings, report = [], {}
    diagnostics = Diagnostics(settings.logs_dir)
    result = validate_grounding(original, "Dựng video", [source], warnings=warnings, report=report, diagnostics=diagnostics)
    assert len(result.facts) == 4
    assert len(result.facts[-1].evidence_quote.split()) == 25
    assert result.facts[-1].evidence_quote in source.text
    assert result.facts[-1].evidence_quote == long_quote[:long_quote.index("từ25")].rstrip()
    assert len(original.facts) == 5 and len(original.facts[3].evidence_quote.split()) == 41
    assert report["returned"] == 5 and report["kept"] == 4 and report["discarded"] == 1 and report["trimmed"] == 1
    assert any("fact #5" in item and "không tìm thấy" in item for item in warnings)
    assert any("fact #4" in item and "41 từ" in item for item in warnings)
    log = diagnostics.path.read_text(encoding="utf-8")
    assert "loại fact #5" in log and "không tìm thấy nguyên văn" in log


def test_unknown_url_dropped_without_failing_valid_brief(source, settings):
    data = response_data(source)
    extra = fact_for(source, "Dữ liệu này chỉ là ví dụ")
    extra["source_url"] = "https://unknown.example/article"
    data["facts"].append(extra)
    warnings = []
    result = validate_grounding(ResearchBrief.model_validate(data), "Dựng video", [source], warnings=warnings, diagnostics=Diagnostics(settings.logs_dir))
    assert len(result.facts) == 3
    assert "source_url không thuộc" in warnings[0]


def test_quote_typography_and_whitespace_normalized(source, settings):
    source.text += ' Nguồn nói: “Dựng   video\n cho người mới”.'
    data = response_data(source)
    quote = 'Nguồn nói: "Dựng video cho người mới".'
    data["facts"].append(fact_for(source, quote))
    result = validate_grounding(ResearchBrief.model_validate(data), "Dựng video", [source], diagnostics=Diagnostics(settings.logs_dir))
    assert len(result.facts) == 4 and result.facts[-1].evidence_quote == quote


def test_fabricated_suffix_cannot_be_hidden_by_trimming(source, settings):
    source.text += " " + " ".join([f"từ{i}" for i in range(30)])
    data = response_data(source)
    data["facts"].append(fact_for(source, " ".join([f"từ{i}" for i in range(25)]) + " phần đuôi bịa không có thật"))
    warnings, report = [], {}
    result = validate_grounding(ResearchBrief.model_validate(data), "Dựng video", [source], warnings=warnings, report=report, diagnostics=Diagnostics(settings.logs_dir))
    assert len(result.facts) == 3 and report["trimmed"] == 0 and report["discarded"] == 1
    assert "quote dài" in warnings[0] and "không tìm thấy" in warnings[0]


def test_under_three_facts_reports_exact_counts(source, settings):
    data = response_data(source)
    data["facts"][2]["evidence_quote"] = "Bằng chứng này không có trong tài liệu."
    report, warnings = {}, []
    brief=validate_grounding(ResearchBrief.model_validate(data), "Dựng video", [source], report=report, warnings=warnings, diagnostics=Diagnostics(settings.logs_dir))
    assert len(brief.facts)==2 and report["kept"]==2 and report["discarded"]==1
    assert warnings and "fact #3" in warnings[0]


def test_retry_includes_specific_fact_reason(source, settings):
    prepare_prompt(settings)
    invalid = response_data(source)
    for fact in invalid["facts"]: fact["evidence_quote"] = " ".join(["bịa"]*41)
    llm = FakeLLM([json.dumps(invalid), json.dumps(response_data(source))])
    brief = create_brief("Dựng video", [source], llm, settings, JsonCache(settings.cache_dir))
    assert len(brief.facts) == 3 and llm.calls == 2
    assert "fact #3" in llm.prompts[1] and "quote dài 41 từ" in llm.prompts[1]
    assert "không tìm thấy nguyên văn" in llm.prompts[1] and "tối đa 25 từ" in llm.prompts[1]
    assert "KHÔNG DỊCH" in llm.prompts[0] and "KHÔNG VIẾT LẠI" in llm.prompts[0]


def test_filter_success_no_retry_and_cache_keeps_original_counts(source, settings):
    prepare_prompt(settings)
    data = response_data(source)
    data["facts"].append(fact_for(source, "Đây là bằng chứng giả không có thật."))
    llm = FakeLLM([json.dumps(data)])
    report = {}
    cache = JsonCache(settings.cache_dir)
    brief = create_brief("Dựng video", [source], llm, settings, cache, grounding_report=report)
    assert len(brief.facts) == 3 and llm.calls == 1 and report["discarded"] == 1
    report.clear()
    cached = create_brief("Dựng video", [source], llm, settings, cache, grounding_report=report)
    assert cached == brief and llm.calls == 1
    assert report["returned"] == 4 and report["kept"] == 3 and report["discarded"] == 1


def test_retry_exhaustion_keeps_exact_grounding_error(source, settings):
    prepare_prompt(settings)
    data = response_data(source)
    data["facts"] = data["facts"][:2]
    for fact in data["facts"]: fact["evidence_quote"]="Bằng chứng bịa không có trong nguồn."
    llm = FakeLLM([json.dumps(data)])
    with pytest.raises(ResearchError, match="chỉ có 0 fact hợp lệ trên 2 fact Gemini trả về"):
        create_brief("Dựng video", [source], llm, settings, JsonCache(settings.cache_dir))
    assert llm.calls == settings.retry_attempts


def test_run_writes_fact_statistics_and_warnings(source, settings, monkeypatch):
    import agents.researcher as module
    settings = settings.model_copy(update={"gemini_api_key": __import__("pydantic").SecretStr("fixture-only"), "gemini_model": "fixture"})
    prepare_prompt(settings)
    monkeypatch.setattr(module.WebSearch, "collect", lambda *args: ([source], []))
    monkeypatch.setattr(module, "generate_queries", fake_queries)
    data = response_data(source)
    data["facts"].append(fact_for(source, "Một đoạn không tồn tại trong nguồn này."))
    llm = FakeLLM([json.dumps(data)])
    llm.close = Mock()
    monkeypatch.setattr(module, "GeminiProvider", lambda s: llm)
    path = run_research("Dựng video", settings, use_youtube=False, progress=lambda message: None)
    source_data = json.loads((path.parent/"sources.json").read_text(encoding="utf-8"))
    assert source_data["grounding"]["kept"] == 3 and source_data["grounding"]["discarded"] == 1
    assert any("fact #4" in notice for notice in source_data["warnings"])
