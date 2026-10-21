"""Long article detail extraction and word budgets, all providers mocked."""
import json
from unittest.mock import Mock
import pytest
from agents.researcher import create_brief,ResearchError,validate_grounding
from agents.director import validate_plan,DirectorRequest
from agents.script_depth import speech_budget
from config.settings import ROOT_DIR,Settings
from schemas.source import SourceDocument
from schemas.research_brief import ResearchBrief
from schemas.edit_plan import EditPlan
from sources.web_search import article_excerpt,WebSearch
from tests.test_researcher import response_data,FakeLLM
from tests.test_director import fixture_plan
from utils.cache import JsonCache
from utils.diagnostics import Diagnostics


def deep_fixture():
    sentences = [f"Công ty công bố sản phẩm phiên bản {index} với giá {index*100} đô la trong tháng này." for index in range(1,13)]
    source = SourceDocument(title="Sản phẩm",url="https://example.com/news/product-launch",source_name="example.com",platform="web",
        content_kind="article",retrieved_at="2026-10-21",published_at="2026-10-21",text="\n\n".join(sentences))
    data = response_data(source)
    data["facts"] = [{"claim":sentence,"fact_vi":sentence,"evidence_quote":sentence,"confidence":"medium",
        "source_name":source.source_name,"source_url":str(source.url)} for sentence in sentences]
    data.update(research_depth="deep",story_angles=[{"angle":name,"why":"So sánh giá sản phẩm có căn cứ."} for name in ["Giá","Phiên bản","Sản phẩm"]],
        key_numbers=[{"text":"Phiên bản 1 giá 100 đô la.","fact_ids":[1]}],timeline=[],counterpoints=[],glossary=[],
        why_it_matters=[{"text":"Người xem có thể đối chiếu các mức giá đã công bố.","fact_ids":[1,2]}])
    return source,data


def detailed_plan(brief):
    plan = EditPlan.model_validate(fixture_plan())
    for scene in plan.scenes:
        scene.fact_ids = [1,2] if scene.role == "body" else [1] if scene.role != "cta" else []
        scene.narration = ("Phiên bản 1 giá 100 đô la, phiên bản 2 giá 200 đô la." if scene.role == "body"
            else "Phiên bản 1 giá 100 đô la." if scene.role == "hook"
            else "Bạn muốn đối chiếu phiên bản nào trước khi lựa chọn?")
    return plan


def test_long_source_generates_twelve_grounded_facts_and_details(tmp_path):
    source,data = deep_fixture()
    settings = Settings(root_dir=tmp_path)
    settings.prompts_dir.mkdir()
    (settings.prompts_dir/"researcher.txt").write_text((ROOT_DIR/"prompts/researcher.txt").read_text(encoding="utf-8"),encoding="utf-8")
    llm = FakeLLM([json.dumps(data,ensure_ascii=False)])
    brief = create_brief(data["topic"],[source],llm,settings,JsonCache(settings.cache_dir))
    assert len(brief.facts) == 12 and brief.research_depth == "deep"
    assert brief.key_numbers[0].fact_ids == [1]
    assert source.model_dump()["content_length"] == len(source.text)
    plan = validate_plan(detailed_plan(brief),brief,DirectorRequest(video_type="review",video_format="tiktok",duration_sec=45))
    assert all(len(scene.fact_ids)>=2 for scene in plan.scenes if scene.role == "body")
    count = sum(len(scene.narration.split()) for scene in plan.scenes)
    assert count>0 and plan.validation_events  # Repeated evidence is merged; word budget is advisory.
    assert "100" in " ".join(scene.narration for scene in plan.scenes)


@pytest.mark.parametrize("error",["facts","words","vague"])
def test_detailed_script_rejects_shallow_body_or_wrong_word_budget(tmp_path,error):
    source,data = deep_fixture()
    brief = validate_grounding(ResearchBrief.model_validate(data),data["topic"],[source],diagnostics=Diagnostics(tmp_path))
    plan = detailed_plan(brief)
    body = next(scene for scene in plan.scenes if scene.role == "body")
    if error == "facts":
        body.fact_ids = [1]
    elif error == "words":
        for scene in plan.scenes:
            scene.narration = "Sản phẩm."
    else:
        body.narration += " Nhiều người quan tâm."
    if error == "facts":
        validate_plan(plan,brief,DirectorRequest(video_type="review",video_format="tiktok",duration_sec=45))
        assert body.fact_ids==[1]
    elif error=="words":
        validate_plan(plan,brief,DirectorRequest(video_type="review",video_format="tiktok",duration_sec=45))
        assert plan.scenes[0].review_notes.warnings
    else:
        validate_plan(plan,brief,DirectorRequest(video_type="review",video_format="tiktok",duration_sec=45))
        assert any(e.rule_id=="cliches" and e.group==3 for e in plan.validation_events)


def test_short_sources_and_category_pages_discarded(tmp_path,monkeypatch):
    search = WebSearch(Settings(root_dir=tmp_path),JsonCache(tmp_path/"cache"))
    monkeypatch.setattr(search,"_search",lambda *args:[{"href":"https://example.com/category/tech"},
        {"href":"https://example.com/news/short"},{"href":"https://example.com/news/full","date":"2026-10-21"}])
    monkeypatch.setattr(search,"_article",lambda url:("a"*100 if url.endswith("short") else "Full paragraph. "*80,url,"2026-10-21"))
    docs,warnings = search.collect("fixture")
    assert len(docs) == 1 and docs[0].content_length>=500
    assert any("quá ngắn" in notice for notice in warnings)
    assert any("chuyên mục" in notice for notice in warnings)


def test_paragraph_cap_does_not_split_source():
    paragraphs = ["A"*2900,"B"*2900,"C"*2900]
    assert article_excerpt("\n\n".join(paragraphs)) == "\n\n".join(paragraphs[:2])
    assert len(article_excerpt("\n\n".join(paragraphs)))<=8000


def test_derived_details_referencing_filtered_facts_are_removed(tmp_path):
    source,data = deep_fixture()
    data["facts"][0]["evidence_quote"] = "Câu hoàn toàn không có trong bài nguồn này."
    brief = validate_grounding(ResearchBrief.model_validate(data),data["topic"],[source],diagnostics=Diagnostics(tmp_path))
    assert len(brief.facts) == 11 and not brief.key_numbers and not brief.why_it_matters


def test_full_articles_with_three_facts_continue_with_warning(tmp_path):
    source,data = deep_fixture()
    data["facts"] = data["facts"][:3]
    settings = Settings(root_dir=tmp_path,retry_attempts=2)
    settings.prompts_dir.mkdir()
    (settings.prompts_dir/"researcher.txt").write_text("Fixture deep prompt",encoding="utf-8")
    llm = FakeLLM([json.dumps(data,ensure_ascii=False)])
    brief = create_brief(data["topic"],[source],llm,settings,JsonCache(settings.cache_dir))
    assert len(brief.facts) == 3 and llm.calls == 1
    assert any("kịch bản" in warning for warning in brief.risks)
