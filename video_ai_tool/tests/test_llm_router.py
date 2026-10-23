"""Multi-provider text routing. Real SDK shapes, all calls/sleeps mocked."""
import ast
import builtins
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import openai
import httpx2
import pytest
from pydantic import BaseModel, SecretStr
from config.settings import Settings, ROOT_DIR, get_settings
from providers.llm.base import AuthError, BadRequestError, ConfigurationError, OutputError, RateLimitError, TimeoutError, TransientError
from providers.llm.router import Router, RoutedProvider, provider_for_step, route_ready, add_provider_notes
from providers.llm.openai_client import OpenAIClient, response_format
from providers.llm.gemini_client import GeminiClient
from utils.diagnostics import Diagnostics


class Example(BaseModel):
    text: str


@pytest.fixture
def settings(tmp_path):
    return Settings(root_dir=tmp_path,openai_api_key=SecretStr("fixture-openai-secret"),openai_model="openai-test",
        gemini_api_key=SecretStr("fixture-gemini-secret"),gemini_model="gemini-test")


def response(text='{"text":"ok"}', **kwargs):
    return SimpleNamespace(output_text=text,output=[],status="completed",**kwargs)


def api_error(code):
    request=httpx2.Request("POST","https://api.openai.com/v1/responses")
    return openai.APIStatusError("fixture-openai-secret API failure",response=httpx2.Response(code,request=request),body={"error":{"message":"fixture-openai-secret"}})


@pytest.fixture
def sdk(settings,monkeypatch):
    client=OpenAIClient(settings)
    sdk=Mock();sdk.responses.create.return_value=response()
    monkeypatch.setattr(client,"_client",lambda:sdk)
    monkeypatch.setattr(client.limiter,"acquire",Mock())
    sleep=Mock();monkeypatch.setattr("providers.llm.openai_client.time.sleep",sleep)
    monkeypatch.setattr("providers.llm.openai_client.random.uniform",lambda a,b:0)
    return client,sdk,sleep


def test_blank_and_missing_optional_settings_never_break_loading(tmp_path):
    env=tmp_path/"empty.env"
    env.write_text("OPENAI_API_KEY=\nOPENAI_MODEL=\nOPENAI_DIRECTOR_MODEL=\nOPENAI_TIMEOUT_SEC=\nOPENAI_RPM_LIMIT=\nOPENAI_MAX_RETRIES=\nLLM_PROVIDER_RESEARCHER=\nLLM_PROVIDER_DIRECTOR=\nLLM_PROVIDER_TREND=\nLLM_FALLBACK_PROVIDER=\n",encoding="utf-8")
    cfg=get_settings(env)
    assert cfg.openai_timeout_sec==120 and cfg.openai_rpm_limit==20 and cfg.openai_max_retries==3
    assert cfg.llm_provider_researcher=="gemini" and cfg.llm_fallback_provider==""
    assert not route_ready(cfg,"researcher")
    with pytest.raises(ConfigurationError,match="GEMINI_API_KEY"):
        provider_for_step(cfg,"researcher")


@pytest.mark.parametrize("field",["openai_timeout_sec","openai_rpm_limit","openai_max_retries"])
@pytest.mark.parametrize("value",["not-a-number",-1,float("inf"),None,""])
def test_optional_invalid_numbers_default_with_safe_variable_name(field,value):
    cfg=Settings(**{field:value})
    assert getattr(cfg,field)==getattr(Settings(),field)
    if value not in (None,""):
        assert field.upper() in " ".join(cfg.llm_configuration_warnings)
        assert "not-a-number" not in " ".join(cfg.llm_configuration_warnings)


def test_unknown_provider_disables_route_without_crashing_config(settings):
    cfg=Settings(root_dir=settings.root_dir,llm_provider_director="mystery-provider",openai_api_key=SecretStr("not-printed"))
    assert not route_ready(cfg,"director")
    with pytest.raises(ConfigurationError,match="LLM_PROVIDER_DIRECTOR"):
        provider_for_step(cfg,"director")
    assert "mystery-provider" not in " ".join(cfg.llm_configuration_warnings)


@pytest.mark.parametrize("step",["researcher","director","trend"])
def test_provider_selection_per_step_and_director_model(settings,step):
    cfg=settings.model_copy(update={"llm_provider_"+step:"openai","openai_director_model":"director-test"})
    provider=provider_for_step(cfg,step)
    assert provider.router.primary=="openai"
    assert provider.model_name=="openai:"+("director-test" if step=="director" else "openai-test")
    assert cfg.gemini_model=="gemini-test"


@pytest.mark.parametrize("failure",[RateLimitError("limit",code=429),TimeoutError("late",code=504),TransientError("down",code=503)])
def test_router_fallback_once_for_transient_only(settings,failure):
    primary=Mock();backup=Mock()
    primary.generate_json.side_effect=failure
    backup.generate_json.return_value={"text":"recovered"}
    cfg=settings.model_copy(update={"llm_fallback_provider":"openai"})
    router=Router(cfg,"director",clients={"gemini":primary,"openai":backup})
    assert router.generate_json("same prompt",schema=Example)=={"text":"recovered"}
    primary.generate_json.assert_called_once();backup.generate_json.assert_called_once()
    assert primary.generate_json.call_args==backup.generate_json.call_args
    assert router.warnings and "một lần" in router.warnings[0]


@pytest.mark.parametrize("failure",[AuthError("bad key",code=401),BadRequestError("bad schema",code=400),OutputError("bad JSON",retryable=True),ValueError("JSON")])
def test_permanent_or_output_error_does_not_switch(settings,failure):
    primary=Mock();backup=Mock();primary.generate_json.side_effect=failure
    router=Router(settings.model_copy(update={"llm_fallback_provider":"openai"}),"researcher",clients={"gemini":primary,"openai":backup})
    with pytest.raises(type(failure)): router.generate_json("same",schema=Example)
    backup.generate_json.assert_not_called()


def test_both_providers_fail_does_not_bounce_or_enable_unconfigured_fallback(settings):
    a=Mock();b=Mock();a.generate_json.side_effect=TransientError("down");b.generate_json.side_effect=TransientError("down")
    router=Router(settings.model_copy(update={"llm_fallback_provider":"openai"}),"trend",clients={"gemini":a,"openai":b})
    with pytest.raises(TransientError): router.generate_json("p",schema=Example)
    assert a.generate_json.call_count==b.generate_json.call_count==1
    router=Router(settings,"trend",clients={"gemini":a,"openai":b})
    with pytest.raises(TransientError): router.generate_json("p",schema=Example)
    assert b.generate_json.call_count==1


def test_disabled_primary_can_use_explicit_configured_fallback(settings):
    cfg=settings.model_copy(update={"gemini_api_key":SecretStr(""),"llm_fallback_provider":"openai"})
    backup=Mock();backup.generate_json.return_value={"text":"ok"}
    router=Router(cfg,"researcher",clients={"openai":backup})
    assert route_ready(cfg,"researcher") and router.generate_json("p")=={"text":"ok"}
    assert "thiếu GEMINI_API_KEY" in router.warnings[0]


def test_no_style_media_route_and_learner_stays_gemini(settings):
    with pytest.raises(ConfigurationError,match="Style Learner"):
        Router(settings,"style")
    text=(ROOT_DIR/"pipeline/style_learner.py").read_text(encoding="utf-8")
    assert "GeminiProvider(" in text and "provider_for_step" not in text and "openai" not in text


def test_responses_parameters_and_parsed_json(sdk):
    client,raw,_=sdk
    raw.responses.create.return_value=response('prefix ```json\n{"text":"xin chào",}\n``` suffix')
    assert client.generate_json("Original user prompt",system="sys",schema=Example,max_output_tokens=1200,timeout=77)=={"text":"xin chào"}
    kwargs=raw.responses.create.call_args.kwargs
    assert kwargs["input"]=="Original user prompt" and kwargs["max_output_tokens"]==1200 and kwargs["timeout"]==77
    assert kwargs["store"] is False and "temperature" not in kwargs
    assert kwargs["text"]["format"]["type"]=="json_schema" and kwargs["text"]["format"]["strict"] is True
    assert kwargs["instructions"].startswith("sys\n")


def test_free_mapping_schema_uses_json_mode_without_changing_local_schema(sdk):
    class Mapping(BaseModel):
        values: dict[str,str]
    original=Mapping.model_json_schema()
    fmt,manual=response_format(Mapping)
    assert fmt=={"type":"json_object"} and manual==original and Mapping.model_json_schema()==original
    client,raw,_=sdk
    raw.responses.create.return_value=response('{"values":{"x":"y"}}')
    assert client.generate_json("p",schema=Mapping)=={"values":{"x":"y"}}
    assert "JSON schema" in raw.responses.create.call_args.kwargs["instructions"]


def test_real_edit_plan_strict_wire_uses_supported_formats_without_mutating_schema():
    from schemas.edit_plan import EditPlan
    original=EditPlan.model_json_schema()
    wire,_=response_format(EditPlan)
    def check(node):
        if isinstance(node,dict):
            assert node.get("format")!="uri"
            for value in node.values(): check(value)
        elif isinstance(node,list):
            for value in node: check(value)
    check(wire)
    assert original==EditPlan.model_json_schema() and wire["schema"]["properties"]["format"]


@pytest.mark.parametrize("code",[429,500,502,503,504])
def test_openai_retry_backoff_and_rpm_every_attempt(sdk,code):
    client,raw,sleep=sdk
    client.request_observer=Mock()
    raw.responses.create.side_effect=[api_error(code),api_error(code),response()]
    assert client.generate_json("p",schema=Example)=={"text":"ok"}
    assert [c.args[0] for c in sleep.call_args_list]==[3,6]
    assert client.limiter.acquire.call_count==3 and client.request_observer.call_count==3
    assert "fixture-openai-secret" not in client.diagnostics.path.read_text(encoding="utf-8")


@pytest.mark.parametrize("code,error_type",[(400,BadRequestError),(401,AuthError),(403,AuthError),(404,BadRequestError)])
def test_openai_permanent_errors_not_retried(sdk,code,error_type):
    client,raw,sleep=sdk;raw.responses.create.side_effect=api_error(code)
    with pytest.raises(error_type): client.generate_json("p",schema=Example)
    raw.responses.create.assert_called_once();sleep.assert_not_called()


def test_openai_timeout_exhaustion_is_normalized_and_bounded(sdk):
    client,raw,sleep=sdk
    raw.responses.create.side_effect=openai.APITimeoutError(request=httpx2.Request("POST","https://api.openai.com/v1/responses"))
    with pytest.raises(TimeoutError): client.generate_text("p")
    assert raw.responses.create.call_count==4 and sleep.call_count==3


def test_sdk_constructor_disables_hidden_retry_and_does_not_use_gateway(settings,monkeypatch):
    import logging
    constructor=Mock(return_value=Mock())
    monkeypatch.setattr("openai.OpenAI",constructor)
    original_import=builtins.__import__
    def import_with_sdk_debug(name,*args,**kwargs):
        module=original_import(name,*args,**kwargs)
        if name=="openai": logging.getLogger("openai").setLevel(logging.DEBUG)
        return module
    client=OpenAIClient(settings)
    with monkeypatch.context() as scoped:
        scoped.setattr(builtins,"__import__",import_with_sdk_debug)
        client._client()
    assert logging.getLogger("openai").level==logging.WARNING
    args=constructor.call_args.kwargs
    assert args["max_retries"]==0 and args["timeout"]==120 and args["base_url"]=="https://api.openai.com/v1"
    client.close();constructor.return_value.close.assert_called_once()


@pytest.mark.parametrize("case",["empty","refusal","truncated"])
def test_incomplete_refusal_empty_not_returned_as_good_json(sdk,case):
    client,raw,_=sdk
    result=response("" if case=="empty" else '{"text":"partial')
    if case=="refusal": result.output=[SimpleNamespace(content=[SimpleNamespace(type="refusal")])]
    if case=="truncated": result.status="incomplete";result.incomplete_details=SimpleNamespace(reason="max_output_tokens")
    raw.responses.create.return_value=result
    with pytest.raises(OutputError) as caught: client.generate_json("p",schema=Example)
    assert caught.value.retryable==(case!="refusal")


def test_generate_text_is_plain_and_honors_temperature(sdk):
    client,raw,_=sdk;raw.responses.create.return_value=response("plain answer")
    assert client.generate_text("p",system="sys",temperature=.4)=="plain answer"
    assert raw.responses.create.call_args.kwargs["temperature"]==.4 and "text" not in raw.responses.create.call_args.kwargs


def test_gemini_adapter_preserves_network_retry_and_json_recovery(settings,monkeypatch):
    from google.genai import errors
    raw=Mock();constructor=Mock(return_value=raw)
    monkeypatch.setattr("providers.llm_gemini.genai.Client",constructor)
    monkeypatch.setattr("providers.llm_gemini.time.sleep",Mock())
    failure=errors.APIError(504,{"error":{"message":"late","code":504}})
    raw.models.generate_content.side_effect=[failure,failure,SimpleNamespace(text='```json\n{"text":"ok"}\n```',candidates=[],prompt_feedback=None)]
    client=GeminiClient(settings,diagnostics=Diagnostics(settings.logs_dir))
    client.request_observer=Mock()
    assert client.generate_json("p",schema=Example,timeout=50,max_output_tokens=1000)=={"text":"ok"}
    assert raw.models.generate_content.call_count==3 and client.request_observer.call_count==3
    assert constructor.call_args.kwargs["http_options"].timeout==50000


def test_facade_keeps_research_brief_schema_and_fallback_notes(settings):
    from schemas.research_brief import ResearchBrief
    from tests.test_director import fixture_plan
    from schemas.edit_plan import EditPlan
    provider=RoutedProvider(settings,"researcher")
    provider.router.generate_json=Mock(return_value={"topic":"t","facts":[{"fact_vi":"Một fact tiếng Việt.","evidence_quote":"Nguyên văn đủ dài.","source_url":"https://example.com/a"}],
        "angle_candidates":[{"angle":"góc","why":"vì"}],"hooks":["h"],"audience_questions":[],"keywords":["k"],"risks":[]})
    brief=ResearchBrief.model_validate_json(provider.generate_json("p",ResearchBrief))
    assert brief.language=="vi" and brief.facts[0].claim==brief.facts[0].fact_vi
    provider.router.warnings=["LLM dự phòng openai."]
    add_provider_notes(brief,provider)
    plan=EditPlan.model_validate(fixture_plan());add_provider_notes(plan,provider)
    assert "LLM dự phòng openai." in brief.risks and "LLM dự phòng openai." in plan.review_notes


def test_research_openai_only_has_no_gemini_requirement(settings,monkeypatch):
    from agents.researcher import run_research
    from tests.test_researcher import response_data,fake_queries
    from schemas.source import SourceDocument
    cfg=settings.model_copy(update={"gemini_api_key":SecretStr(""),"gemini_model":"","llm_provider_researcher":"openai"})
    source=SourceDocument(title="Fixture",url="https://example.com/article",source_name="example.com",platform="web",content_kind="article",
        text="Dữ liệu này chỉ là ví dụ phục vụ kiểm thử phần mềm.",retrieved_at="2026-10-20T00:00:00Z")
    cfg.prompts_dir.mkdir();(cfg.prompts_dir/"researcher.txt").write_text("Keep facts grounded.",encoding="utf-8")
    raw=Mock();raw.responses.create.return_value=response(json.dumps(response_data(source),ensure_ascii=False))
    monkeypatch.setattr(OpenAIClient,"_client",lambda self:raw)
    monkeypatch.setattr("agents.researcher.generate_queries",fake_queries)
    monkeypatch.setattr("agents.researcher.WebSearch.collect",lambda *a:([source],[]))
    path=run_research("Dựng video",cfg,use_youtube=False,progress=lambda m:None)
    assert path.exists() and json.loads(path.read_text(encoding="utf-8"))["facts"]
    assert raw.responses.create.call_args.kwargs["model"]=="openai-test"


def test_target_agents_have_no_direct_google_or_gemini_provider_import():
    for relative in ("agents/researcher.py","agents/director.py","pipeline/auto_category.py","pipeline/trend_scout.py","sources/topic_discovery.py"):
        tree=ast.parse((ROOT_DIR/relative).read_text(encoding="utf-8"))
        imports=[node for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom))]
        assert not any(isinstance(node,ast.ImportFrom) and (node.module or "").startswith(("google","providers.llm_gemini")) for node in imports)


def test_ui_openai_only_enables_text_pipeline_but_not_style(settings,monkeypatch):
    from streamlit.testing.v1 import AppTest
    cfg=settings.model_copy(update={"gemini_api_key":SecretStr(""),"gemini_model":"", "llm_provider_researcher":"openai","llm_provider_director":"openai","llm_provider_trend":"openai"})
    monkeypatch.setattr("config.settings.get_settings",lambda:cfg)
    app=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=30).run()
    assert not app.exception and not app.button(key="auto_start").disabled
    app.sidebar.radio[0].set_value("Research").run()
    assert not next(b for b in app.button if b.label=="Chạy Researcher").disabled
    assert any("chỉ Gemini" in c.value for c in app.sidebar.caption)
