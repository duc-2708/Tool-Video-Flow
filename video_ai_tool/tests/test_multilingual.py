"""Foreign evidence stays verbatim; Vietnamese facts drive the script. Offline."""
import json
from unittest.mock import Mock
import pytest
from pydantic import SecretStr
from agents.researcher import run_research,validate_grounding,ResearchError
from agents.search_queries import generate_queries,QueryPlan
from agents.director import director_facts,DirectorError,validate_plan,DirectorRequest
from config.settings import Settings,ROOT_DIR
from schemas.research_brief import ResearchBrief
from schemas.source import SourceDocument
from schemas.edit_plan import EditPlan
from sources.web_search import WebSearch,article_url
from utils.cache import JsonCache,write_json
from utils.diagnostics import Diagnostics
from utils.source_credits import source_credit_lines
from tests.test_researcher import response_data
from tests.test_director import fixture_plan


def english_source():
    return SourceDocument(title="Video editing workflow",url="https://www.reuters.com/technology/video-editing-workflow-2026-10-21/",
        source_name="Reuters",platform="web",source_lang="en",content_kind="article",published_at="2026-10-21",
        retrieved_at="2026-10-21T00:00:00Z",text="Editors can cut and join clips. A clear workflow helps beginners. Practice improves editing confidence.")


def english_brief(source):
    data = response_data(source)
    rows = [("Có thể cắt và ghép video.","Editors can cut and join clips."),
        ("Quy trình rõ ràng giúp người mới học dựng.","A clear workflow helps beginners."),
        ("Luyện tập giúp người dựng tự tin hơn.","Practice improves editing confidence.")]
    data["facts"] = [dict(claim="Unused English claim",fact_vi=vi,evidence_quote=quote,source_name="Reuters",
        source_url=str(source.url),confidence="medium",source_lang="en") for vi,quote in rows]
    return data


def test_english_quotes_grounded_and_fabricated_fact_filtered(tmp_path):
    source = english_source()
    data = english_brief(source)
    fake = dict(data["facts"][0],evidence_quote="This statement was never published by the source.")
    data["facts"].append(fake)
    warnings = []
    brief = validate_grounding(ResearchBrief.model_validate(data),data["topic"],[source],warnings=warnings,diagnostics=Diagnostics(tmp_path/"logs"))
    assert len(brief.facts) == 3 and "fact #4" in warnings[0]
    assert brief.facts[0].fact_vi == "Có thể cắt và ghép video."
    assert brief.facts[0].evidence_quote in source.text and brief.facts[0].source_lang == "en"
    assert brief.facts[0].published_at == "2026-10-21"
    assert brief.facts[0].claim == brief.facts[0].fact_vi


def test_translated_quote_and_missing_fact_vi_do_not_pass(tmp_path):
    source = english_source()
    data = english_brief(source)
    data["facts"][0]["evidence_quote"] = "Người dựng có thể cắt và ghép clip."
    data["facts"][1].pop("fact_vi")
    brief=validate_grounding(ResearchBrief.model_validate(data),data["topic"],[source],diagnostics=Diagnostics(tmp_path/"logs"))
    assert len(brief.facts)==1 and brief.facts[0].evidence_quote in source.text


def test_empty_vietnamese_fact_is_filtered_individually(tmp_path):
    source = english_source()
    data = english_brief(source)
    data["facts"].append(dict(data["facts"][0],fact_vi="  "))
    report = {}
    brief = validate_grounding(ResearchBrief.model_validate(data),data["topic"],[source],report=report,diagnostics=Diagnostics(tmp_path/"logs"))
    assert len(brief.facts) == 3 and report["discarded"] == 1
    assert "thiếu fact_vi" in report["warnings"][0]


def test_natural_queries_generated_for_every_language_and_cached(tmp_path):
    settings = Settings(root_dir=tmp_path)
    provider = Mock(model_name="offline")
    provider.generate_json.return_value = json.dumps({"languages":[
        {"source_lang":"vi","queries":["dựng video cho người mới","quy trình dựng video cơ bản"]},
        {"source_lang":"en","queries":["video editing workflow for beginners","how to start editing videos"]}]})
    cache = JsonCache(settings.cache_dir)
    queries = generate_queries("Dựng video",["vi","en"],provider,settings,cache,Diagnostics(settings.logs_dir))
    assert len(queries) == 4
    assert queries[2].source_lang == "en" and queries[2].region == "us-en"
    assert queries[2].query == "video editing workflow for beginners"
    assert generate_queries("Dựng video",["vi","en"],provider,settings,cache,Diagnostics(settings.logs_dir)) == queries
    provider.generate_json.assert_called_once()


def test_multilingual_research_end_to_end_mocked(tmp_path,monkeypatch):
    source = english_source()
    settings = Settings(root_dir=tmp_path,gemini_model="offline",gemini_api_key=SecretStr("fixture-private"))
    settings.prompts_dir.mkdir()
    (settings.prompts_dir/"researcher.txt").write_text((ROOT_DIR/"prompts/researcher.txt").read_text(encoding="utf-8"),encoding="utf-8")
    provider = Mock(model_name="offline")
    def generate(prompt,schema):
        if schema is QueryPlan:
            return json.dumps({"languages":[{"source_lang":"en","queries":["video editing workflow for beginners","learn video editing basics"]}]})
        assert schema is ResearchBrief and "Editors can cut and join clips." in prompt
        return json.dumps(english_brief(source),ensure_ascii=False)
    provider.generate_json.side_effect = generate
    monkeypatch.setattr("agents.researcher.provider_for_step",lambda *args,**kwargs:provider)
    collect = Mock(return_value=([source],[]))
    monkeypatch.setattr(WebSearch,"collect",collect)
    path = run_research("Dựng video",settings,source_languages=["en"],web_limit=3,use_youtube=False,progress=lambda _:None)
    brief = ResearchBrief.model_validate_json(path.read_text(encoding="utf-8"))
    assert brief.output_language == "vi" and brief.source_languages == ["en"]
    assert brief.search_queries[0].query == "video editing workflow for beginners"
    assert collect.call_args_list[0].args == ("video editing workflow for beginners",3,"en")
    assert collect.call_count == 4 and len(brief.search_queries) == 4
    assert any("dữ liệu" in warning.lower() for warning in brief.risks)
    assert brief.facts[0].evidence_quote == "Editors can cut and join clips."
    assert "Có thể cắt" in brief.facts[0].fact_vi
    provider.close.assert_called_once()


def test_director_only_receives_fact_vi_and_uses_publisher(tmp_path):
    source = english_source()
    brief = ResearchBrief.model_validate(english_brief(source))
    payload = director_facts(brief)
    assert payload[0]["fact_vi"] == "Có thể cắt và ghép video."
    assert "claim" not in payload[0] and "evidence_quote" not in payload[0]
    plan = validate_plan(EditPlan.model_validate(fixture_plan()),brief,DirectorRequest(video_type="review",video_format="tiktok",duration_sec=45))
    assert plan.scenes[0].narration.startswith("Theo Reuters, ")
    assert "chưa xác minh" not in plan.model_dump_json().lower()
    brief.facts[0].fact_vi = None
    with pytest.raises(DirectorError,match="thiếu fact_vi"):
        director_facts(brief)


@pytest.mark.parametrize("url,expected",[("https://example.com/",False),("https://example.com/news",False),
    ("https://example.com/category/ai",False),("https://example.com/news/ai-launch-2026",True)])
def test_filter_homepages_and_categories(url,expected):
    assert article_url(url) == expected


def test_ddgs_region_and_source_credits(tmp_path,monkeypatch):
    client = Mock()
    client.news.return_value = []
    monkeypatch.setattr("sources.web_search.DDGS",lambda **kwargs:client)
    search = WebSearch(Settings(root_dir=tmp_path),JsonCache(tmp_path/"cache"))
    search._search("영상 편집", "news", 3, "ko")
    assert client.news.call_args.kwargs["region"] == "kr-kr"
    source = english_source()
    write_json(tmp_path/"brief.json",english_brief(source))
    write_json(tmp_path/"sources.json",{"sources":[source.model_dump(mode="json")]})
    # Dates on source documents are retained even before fact grounding.
    lines = "\n".join(source_credit_lines(tmp_path))
    assert "Reuters" in lines and "ngôn ngữ gốc: en" in lines
    assert str(source.url) in lines and "2026-10-21" in lines
