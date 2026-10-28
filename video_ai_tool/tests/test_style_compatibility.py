"""No Gemini requests: transport bisection, raw reuse and video scope policy."""
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from google.genai import errors
from config.settings import Settings
from pipeline.style_learner import VideoStyleProvider,analyze_one,analyze_batch,estimate_batch,inspect_video,main,digest_file,style_diagnostics
from pipeline.style_raw import RawResponse,raw_path,StyleRawError
from providers.style_schema import flat_style_schema,response_schema
from schemas.style import StyleAnalysis
from schemas.style_compact import CompactStyleAnalysis
from tests.test_style_learner import style_settings,observed


def invalid():
    return errors.ClientError(400,{"error":{"code":400,"status":"INVALID_ARGUMENT","message":"Request contains an invalid argument.",
        "details":[{"fieldViolations":[{"field":"media_resolution","description":"fixture-style-secret; unsupported parameter"}]}]}})


def response(seconds=30):
    return SimpleNamespace(candidates=[],prompt_feedback=None,text=json.dumps({"duration_sec":seconds,"scenes":[{"start_sec":0,"end_sec":seconds,"purpose":"giải thích"}]}))


def sdk(settings,monkeypatch,responses):
    client=Mock()
    client.files.upload.return_value=SimpleNamespace(name="files/mock",uri="https://example.com/file",state=SimpleNamespace(name="ACTIVE"))
    client.models.generate_content.side_effect=responses
    monkeypatch.setattr("providers.llm_gemini.genai.Client",lambda **kwargs:client)
    settings=settings.model_copy(update={"style_max_output_tokens":16000,"style_request_interval_sec":0,"style_rpm_limit":1000})
    return settings,client


@pytest.mark.parametrize("failures",[1,2,3,4])
def test_bisect_in_order_once_and_remembers_for_next_video_and_provider(style_settings,monkeypatch,failures):
    settings,client=sdk(style_settings,monkeypatch,[*[invalid() for _ in range(failures)],response(),response()])
    secret_file=settings.root_dir/".env";secret_file.write_text("GEMINI_API_KEY=fixture-style-secret\n",encoding="utf-8")
    before=secret_file.read_bytes()
    progress=[]
    result=analyze_one(settings,"a.mp4",progress=progress.append)
    assert result["status"]=="done"
    calls=client.models.generate_content.call_args_list
    assert len(calls)==failures+1
    assert calls[0].kwargs["config"].media_resolution is not None
    assert calls[1].kwargs["config"].media_resolution is None
    if failures>=2:
        assert calls[2].kwargs["config"].response_json_schema is None
        assert calls[2].kwargs["config"].response_mime_type=="application/json"
        assert "Schema tham khảo" in calls[2].kwargs["contents"][1]
    if failures>=3:
        assert calls[3].kwargs["config"].max_output_tokens==8192
        assert "CHẾ ĐỘ GỌN" in calls[3].kwargs["contents"][1]
    if failures==4:
        wire=calls[4].kwargs["config"].response_json_schema
        assert set(wire["properties"]["scenes"]["items"]["properties"])=={"start_sec","end_sec","purpose"}
    learned=calls[-1].kwargs["config"]
    (settings.root_dir/"assets/reference_videos/b.mp4").write_bytes(b"different sample")
    analyze_one(settings,"b.mp4")  # New VideoStyleProvider reads the disk cache.
    assert client.models.generate_content.call_count==failures+2
    config=client.models.generate_content.call_args.kwargs["config"]
    assert config.media_resolution==learned.media_resolution
    assert config.response_json_schema==learned.response_json_schema
    assert config.max_output_tokens==learned.max_output_tokens
    assert secret_file.read_bytes()==before
    suggestions=(settings.logs_dir/"style_compatibility.suggested.env").read_text(encoding="utf-8")
    assert "STYLE_MEDIA_RESOLUTION=none" in suggestions and "fixture-style-secret" not in suggestions
    assert f"STYLE_USE_RESPONSE_SCHEMA={str(config.response_json_schema is not None).lower()}" in suggestions
    log=(settings.logs_dir/"style_learner_errors.log").read_text(encoding="utf-8")
    for field in ("model","max_output_tokens","media_resolution","response_mime_type","schema_chars","has_response_schema","thinking_config","prompt_chars","size_bytes","format"):
        assert f'"{field}"' in log
    assert "fieldViolations" in log and "unsupported parameter" in log
    assert "fixture-style-secret" not in log+str(progress)
    client.files.delete.assert_called()


def test_all_400_attempts_are_bounded_and_file_is_cleaned(style_settings,monkeypatch):
    from providers.llm_gemini import GeminiRequestError
    settings,client=sdk(style_settings,monkeypatch,[invalid()]*5)
    with pytest.raises(GeminiRequestError,match="cấu hình/request"):
        analyze_one(settings,"a.mp4")
    assert client.models.generate_content.call_count==5
    client.files.delete.assert_called_once()
    assert not raw_path(settings,None,digest_file(settings.root_dir/"assets/reference_videos/a.mp4")).exists()


@pytest.mark.parametrize("model",[StyleAnalysis,CompactStyleAnalysis])
def test_media_wire_schema_is_flat_while_local_pydantic_is_flexible(model):
    schema=flat_style_schema(model)
    text=json.dumps(schema)
    assert not any(token in text for token in ("anyOf","oneOf","$ref","$defs","additionalProperties"))
    assert response_schema(model)==schema
    essential=flat_style_schema(model,essential=True)
    assert essential["properties"]["scenes"]["items"]["required"]==["start_sec","end_sec","purpose"]
    assert model.model_validate({"scenes":[{"start_sec":"0","end_sec":"3","purpose":"hook","transition_to_next":None}]}).scenes


def test_existing_raw_valid_or_truncated_never_generates_and_keeps_bytes(style_settings,monkeypatch):
    file=style_settings.root_dir/"assets/reference_videos/a.mp4"
    store=RawResponse(raw_path(style_settings,None,digest_file(file)),{},style_diagnostics(style_settings))
    store.save(observed().model_dump_json())
    original=store.path.read_bytes()
    constructor=Mock(side_effect=AssertionError("No Gemini for existing raw"))
    monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",constructor)
    assert analyze_one(style_settings,"a.mp4",force=False)["status"]=="cached"
    assert store.path.read_bytes()==original
    store.save('{"scenes": [',{"finish_reasons":["MAX_TOKENS"]})
    original=store.path.read_bytes()
    cache_dir = style_settings.root_dir / "assets/reference_videos/analysis/.cache"
    for c in cache_dir.glob("*.json"): c.unlink()
    with pytest.raises(StyleRawError): analyze_one(style_settings,"a.mp4",force=False)
    assert estimate_batch(style_settings,["a.mp4"])["estimated_input_tokens"]==0
    assert store.path.read_bytes()==original
    constructor.assert_not_called()


def test_force_relearn_bypasses_raw_and_calls_provider(style_settings,monkeypatch):
    file=style_settings.root_dir/"assets/reference_videos/a.mp4"
    store=RawResponse(raw_path(style_settings,None,digest_file(file)),{},style_diagnostics(style_settings))
    store.save(observed().model_dump_json())
    provider_mock=Mock()
    provider_mock.analyze.return_value=observed()
    provider_mock.use_existing_raw=True
    provider_mock.raw_store=None
    constructor=Mock(return_value=provider_mock)
    monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",constructor)
    result=analyze_one(style_settings,"a.mp4",force=True)
    assert result["status"]=="done"
    constructor.assert_called_once()
    provider_mock.analyze.assert_called_once()


def test_long_video_is_skipped_with_warning_and_no_upload(style_settings,monkeypatch):
    monkeypatch.setattr("pipeline.style_learner.inspect_video",inspect_video)
    monkeypatch.setattr("pipeline.style_learner.subprocess.run",lambda *a,**kw:SimpleNamespace(stderr=b"Duration: 00:35:43.98 Video: h264"))
    provider=Mock()
    estimate=estimate_batch(style_settings,["a.mp4"])
    assert estimate["items"][0]["skipped"] and estimate["estimated_input_tokens"]==0
    results=analyze_batch(style_settings,["a.mp4"],provider=provider)
    assert results[0]["status"]=="skipped" and "2143.98" in str(results[0]["warnings"])
    assert "600" in str(results[0]["warnings"])
    provider.analyze.assert_not_called()


def test_partial_video_uses_offsets_and_reduced_estimate(style_settings,monkeypatch):
    settings,client=sdk(style_settings,monkeypatch,[response(180)])
    monkeypatch.setattr("pipeline.style_learner.inspect_video",lambda path,s:{"duration_sec":300.,"size_bytes":path.stat().st_size})
    estimate=estimate_batch(settings,["a.mp4"])
    assert estimate["items"][0]["analysis_duration_sec"]==180
    assert "0–180s" in estimate["items"][0]["scope_warning"]
    result=analyze_one(settings,"a.mp4")
    media=client.models.generate_content.call_args.kwargs["contents"][0]
    assert media.video_metadata.start_offset=="0s" and media.video_metadata.end_offset=="180s"
    assert result["analysis"]["duration_sec"]==180 and any("0–180s" in w for w in result["warnings"])
    raw=raw_path(settings,None,digest_file(settings.root_dir/"assets/reference_videos/a.mp4"))
    assert json.loads(raw.with_suffix(".meta.json").read_text(encoding="utf-8"))["status"]["video"]["duration_sec"]==300


def test_cli_max_sec_changes_scope(style_settings,monkeypatch):
    settings,client=sdk(style_settings,monkeypatch,[response(60)])
    monkeypatch.setattr("pipeline.style_learner.inspect_video",lambda path,s:{"duration_sec":300.,"size_bytes":path.stat().st_size})
    monkeypatch.setattr("pipeline.style_learner.get_settings",lambda:settings)
    monkeypatch.setattr("sys.argv",["style_learner","--videos","a.mp4","--max-sec","60"])
    assert main()==0
    assert client.models.generate_content.call_args.kwargs["contents"][0].video_metadata.end_offset=="60s"
