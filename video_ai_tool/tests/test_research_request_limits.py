"""Budget, compact wire schema, original 400 and exactly one safe fallback."""
import json
from unittest.mock import Mock
import pytest
from pydantic import SecretStr
from google.genai import errors
from providers.llm_gemini import GeminiProvider,GeminiRequestError
from providers.research_payload import bounded_sources,ResearchFactsResponse,ResearchDetailsResponse,compact_facts_json,reduced_request_prompt
from schemas.research_brief import ResearchBrief
from config.settings import Settings
from app.ui_errors import error_details
from utils.diagnostics import Diagnostics
from agents.researcher import create_brief,enrich_brief_details
from utils.cache import JsonCache
from tests.test_deep_research import deep_fixture
from tests.test_researcher import FakeLLM


def test_source_budget_shared_and_immutable():
    rows = [{"text":"First paragraph. "*600+"\n\n"+"Second paragraph. "*600,"url":f"https://example.com/{index}","transcript":"do not send"} for index in range(8)]
    before = json.dumps(rows)
    limited = bounded_sources(rows)
    assert sum(len(row["text"]) for row in limited)<=40000
    assert all(len(row["text"])<=5000 for row in limited)
    assert all(row["text"] and row["text"] in rows[index]["text"] for index,row in enumerate(limited))
    assert json.dumps(rows) == before
    assert all("transcript" not in row for row in limited)


def test_reduced_schema_has_no_optional_union_or_dynamic_dict():
    schema = json.dumps(ResearchFactsResponse.model_json_schema())
    assert len(schema)<len(json.dumps(ResearchBrief.model_json_schema()))/3
    assert all(key not in schema for key in ["anyOf","additionalProperties","TrendSignal","pronunciation_hint"])
    assert set(ResearchFactsResponse.model_fields) == {"topic","facts","angle_candidates","hooks","audience_questions","keywords","risks"}
    source,data = deep_fixture()
    payload = {key:data[key] for key in ResearchFactsResponse.model_fields}
    payload["facts"] = [{key:fact[key] for key in ["fact_vi","evidence_quote","source_url"]} for fact in data["facts"]]
    brief = ResearchBrief.model_validate_json(compact_facts_json(json.dumps(payload)))
    assert len(brief.facts) == 12 and brief.facts[0].claim == brief.facts[0].fact_vi


def provider_fixture(tmp_path,monkeypatch):
    client = Mock()
    monkeypatch.setattr("providers.llm_gemini.genai.Client",lambda **kwargs:client)
    provider = GeminiProvider(Settings(root_dir=tmp_path,gemini_api_key=SecretStr("fixture-secret-marker"),gemini_model="fixture",retry_attempts=3))
    return provider,client


def error400(message):
    return errors.ClientError(400,{"error":{"code":400,"status":"INVALID_ARGUMENT","message":message}})


def test_400_original_message_redacted_in_log_ui_and_only_one_retry(tmp_path,monkeypatch):
    provider,client = provider_fixture(tmp_path,monkeypatch)
    message = 'Unknown name "additional_properties"; fixture-secret-marker '+"detail "*300
    client.models.generate_content.side_effect = error400(message)
    with pytest.raises(GeminiRequestError) as caught:
        provider.generate_json("test prompt",ResearchBrief)
    assert client.models.generate_content.call_count == 2
    summary,_ = error_details(caught.value,provider.diagnostics)
    assert "INVALID_ARGUMENT" in summary and 'Unknown name "additional_properties"' in summary
    assert "fixture-secret-marker" not in summary and message.split("fixture-secret-marker")[1] in summary
    log = provider.diagnostics.path.read_text(encoding="utf-8")
    assert "INVALID_ARGUMENT" in log and "fixture-secret-marker" not in log
    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.response_json_schema is None and config.response_mime_type is None
    assert config.max_output_tokens is None and config.temperature is None and config.thinking_config is None


def test_one_reduced_attempt_can_succeed_and_reuses_compatible_mode(tmp_path,monkeypatch):
    provider,client = provider_fixture(tmp_path,monkeypatch)
    response = Mock(text="{}",candidates=[])
    client.models.generate_content.side_effect = [error400("Unsupported max_output_tokens"),response,response]
    prompt = "Research instructions\nINPUT_DATA_JSON:\n"+json.dumps({"sources":[{"text":"paragraph "*8000} for _ in range(8)]})
    assert provider.generate_json(prompt,ResearchBrief) == "{}"
    sent = client.models.generate_content.call_args.kwargs["contents"]
    payload = json.loads(sent.split("\nINPUT_DATA_JSON:\n")[1])
    assert sum(len(row["text"]) for row in payload["sources"])<=12000
    assert provider.generate_json("another task",ResearchBrief) == "{}"
    assert client.models.generate_content.call_count == 3
    assert client.models.generate_content.call_args.kwargs["config"].response_json_schema is None


def test_researcher_always_caps_sources_before_call(tmp_path):
    source,data = deep_fixture()
    sources = [source.model_copy(update={"text":source.text+"\n\n"+"Extra paragraph. "*8000}) for _ in range(8)]
    settings = Settings(root_dir=tmp_path)
    settings.prompts_dir.mkdir()
    (settings.prompts_dir/"researcher.txt").write_text("Fixture prompt",encoding="utf-8")
    provider = FakeLLM([json.dumps(data)])
    brief = create_brief(data["topic"],sources,provider,settings,JsonCache(settings.cache_dir))
    assert len(brief.facts) == 12
    payload = json.loads(provider.prompts[0].split("\nINPUT_DATA_JSON:\n")[1])
    assert sum(len(row["text"]) for row in payload["sources"])<=40000


def test_second_pass_only_receives_grounded_facts_and_filters_invalid_ids(tmp_path):
    _,data = deep_fixture()
    brief = ResearchBrief.model_validate(data)
    brief.story_angles = []
    provider = Mock()
    provider.generate_json.return_value = json.dumps({"story_angles":[{"angle":"Giá","why":"So sánh giá đã công bố"}],
        "key_numbers":[{"text":"100 đô la","fact_ids":[1]},{"text":"Invented","fact_ids":[999]}],
        "timeline":[],"why_it_matters":[],"counterpoints":[],"glossary":[]})
    enrich_brief_details(brief,provider,Diagnostics(tmp_path))
    assert provider.generate_json.call_args.args[1] is ResearchDetailsResponse
    prompt = provider.generate_json.call_args.args[0]
    assert "evidence_quote" not in prompt and "source_url" not in prompt
    assert len(brief.key_numbers) == 1 and brief.key_numbers[0].fact_ids == [1]
