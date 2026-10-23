"""Transient Gemini resilience; all SDK calls and sleeps are mocked."""
import json
from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from google.genai import errors
from pydantic import SecretStr
from config.settings import Settings,get_settings
from providers.llm_gemini import GeminiProvider,GeminiTransientError,GeminiRequestError,transient_gemini
from providers.gemini_resilience import compact_prompt
from providers.research_payload import ResearchFactsResponse


def failure(code=504):
    return errors.APIError(code,{"error":{"code":code,"status":"DEADLINE_EXCEEDED" if code==504 else "UNAVAILABLE","message":"fixture-secret; temporary"}})


@pytest.fixture
def sdk(tmp_path,monkeypatch):
    client=Mock()
    constructor=Mock(return_value=client)
    monkeypatch.setattr("providers.llm_gemini.genai.Client",constructor)
    sleep=Mock();monkeypatch.setattr("providers.llm_gemini.time.sleep",sleep)
    monkeypatch.setattr("providers.llm_gemini.random.uniform",lambda a,b:0)
    settings=Settings(root_dir=tmp_path,gemini_model="primary",gemini_api_key=SecretStr("fixture-secret"),gemini_fallback_model="backup")
    provider=GeminiProvider(settings)
    provider.progress=Mock()
    return provider,client,sleep,constructor


def success():
    return SimpleNamespace(text="{}",candidates=[],prompt_feedback=None)


def large_prompt():
    return "Never invent facts.\nINPUT_DATA_JSON:\n"+json.dumps({
        "style_profile":{"reusable_rules":["A short useful rule"]*20,"reference_texts":["must not copy "*2000],"scene_patterns":[{"description":"extra "*1000}]*15},
        "facts":[{"id":i,"fact_vi":f"Verified detail {i}","source_review":{"unused":"metadata "*100}} for i in range(1,31)],
        "outline":{"scenes":[{"fact_ids":[29,30]}]},
        "sources":[{"url":f"https://example.com/{i}","text":"real source paragraph "*3000} for i in range(8)]})


def test_504_twice_then_success_reports_progress_and_each_attempt(sdk):
    provider,client,sleep,constructor=sdk
    client.models.generate_content.side_effect=[failure(),failure(),success()]
    provider.request_observer=Mock()
    assert provider.generate_json(large_prompt(),ResearchFactsResponse)=="{}"
    assert client.models.generate_content.call_count==3 and provider.request_observer.call_count==3
    assert [c.args[0] for c in sleep.call_args_list]==[3,6]
    assert any("Gemini quá tải (504), thử lại lần 1/5 sau 3.0 giây" in c.args[0] for c in provider.progress.call_args_list)
    log=provider.diagnostics.path.read_text(encoding="utf-8")
    assert all(f"attempt={i}, code=" in log for i in (1,2,3))
    assert "elapsed_sec=" in log and "prompt_chars=" in log and "fixture-secret" not in log
    assert constructor.call_args.kwargs["http_options"].timeout==120000


def test_repeated_504_compacts_then_falls_back_with_one_shared_budget(sdk):
    provider,client,sleep,_=sdk
    client.models.generate_content.side_effect=[failure()]*6
    prompt=large_prompt()
    with pytest.raises(GeminiTransientError,match="6 lần gọi"):
        provider.generate_json(prompt,ResearchFactsResponse)
    calls=client.models.generate_content.call_args_list
    assert len(calls)==6
    assert [c.kwargs["model"] for c in calls]==["primary"]*3+["backup"]*3
    assert len(calls[2].kwargs["contents"])<len(calls[1].kwargs["contents"])
    assert calls[2].kwargs["contents"]==calls[3].kwargs["contents"]
    assert [c.args[0] for c in sleep.call_args_list]==[3,6,12,24,48]
    assert "Gemini fallback" in provider.diagnostics.path.read_text(encoding="utf-8")


def test_compaction_preserves_referenced_ids_and_limits_sources():
    original=large_prompt();limited=compact_prompt(original)
    data=json.loads(limited.split("\nINPUT_DATA_JSON:\n")[1])
    assert limited.startswith("Never invent facts.")
    assert len(data["facts"])==12 and {29,30}.issubset({r["id"] for r in data["facts"]})
    assert sum(len(s["text"]) for s in data["sources"])<=12000
    assert len(data["style_profile"]["reusable_rules"])<=6
    assert "reference_texts" not in limited and "source_review" not in limited
    assert compact_prompt("do not truncate instructions"*1000)=="do not truncate instructions"*1000


@pytest.mark.parametrize("code",[400,401,403,404])
def test_permanent_errors_never_retry_or_fallback(sdk,code):
    from providers.llm_base import ProviderError
    provider,client,sleep,_=sdk
    client.models.generate_content.side_effect=failure(code)
    with pytest.raises(ProviderError): provider.generate_json("prompt",ResearchFactsResponse)
    client.models.generate_content.assert_called_once();sleep.assert_not_called()


@pytest.mark.parametrize("error",[failure(429),failure(500),failure(502),failure(503),failure(504),TimeoutError("late"),httpx.ReadTimeout("late"),RuntimeError("DEADLINE_EXCEEDED"),RuntimeError("UNAVAILABLE")])
def test_retryable_codes_statuses_and_timeouts(sdk,error):
    provider,client,sleep,_=sdk
    assert transient_gemini(error)
    client.models.generate_content.side_effect=[error,success()]
    assert provider.generate_json("prompt",ResearchFactsResponse)=="{}"
    assert client.models.generate_content.call_count==2 and sleep.call_count==1


def test_gemini_configuration_is_independent_of_generic_timeout(tmp_path):
    env=tmp_path/"test.env"
    env.write_text("REQUEST_TIMEOUT_SEC=30\nGEMINI_TIMEOUT_SEC=145\nGEMINI_FALLBACK_MODEL=backup\n",encoding="utf-8")
    settings=get_settings(env)
    assert settings.request_timeout_sec==30 and settings.gemini_timeout_sec==145 and settings.gemini_fallback_model=="backup"
