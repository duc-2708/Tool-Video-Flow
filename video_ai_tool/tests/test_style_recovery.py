"""Mocked uploads/SDK; raw repair must never silently spend another video request."""
import io
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from google.genai import types
from pipeline.style_learner import analyze_one,analyze_batch,VideoStyleProvider,estimate_batch,digest_file
from pipeline.style_raw import raw_path,RawResponse,StyleRawError
from tests.test_style_learner import style_settings,observed
from utils.json_response import parse_json_object
from utils.style_rate_limit import reserve_style_request,estimated_video_tokens
from utils.atomic_io import write_text_atomic


@pytest.mark.parametrize("raw",[
    '```json\n{"message":"Xin chào", "items":[1,2]}\n```',
    'Đây là kết quả: {"message":"Xin chào", "items":[1,2]} kết thúc.',
    '{"message":"Xin chào", "items":[1,2,],}',
    "{'message':'Xin chào', 'items':[1,2]}",
    '{“message”:“Xin chào”, “items”:[1,2]}',
    json.dumps({"message":'Dấu { trong chuỗi } và “nháy”',"items":[1,2]},ensure_ascii=False),
])
def test_json_fences_prefix_trailing_comma_and_simple_quotes(raw):
    result=parse_json_object(raw)
    assert result["items"]==[1,2] and "message" in result


def test_parser_preserves_content_and_rejects_executable_or_truncated_input():
    text='Từ “đặc biệt”, dấu phẩy ,} và dấu { ngoặc }'
    assert parse_json_object("```json\n"+json.dumps({"text":text},ensure_ascii=False)+"\n```")["text"]==text
    with pytest.raises(ValueError):
        parse_json_object('{"x": "incomplete')
    with pytest.raises(ValueError):
        parse_json_object("{'x': __import__('os').getcwd()}")


def test_upload_unicode_quotes_hash_uses_only_ascii_name_and_sdk_headers(style_settings,monkeypatch):
    from google.genai._extra_utils import prepare_resumable_upload
    path=style_settings.root_dir/'assets/reference_videos/Tin thực sự “mới” #tin.mp4'
    path.write_bytes(b"mock bytes")
    llm=Mock();llm.generate_media_json.return_value="```json\n"+observed().model_dump_json()+"\n```"
    def upload(*,file,config):
        assert isinstance(file,io.IOBase) and file.name.isascii()
        assert file.name==digest_file(path)+".mp4" and config.display_name==file.name
        assert file.read()==b"mock bytes"
        file.seek(0)
        options,_,_=prepare_resumable_upload(file,user_mime_type="video/mp4")
        assert "X-Goog-Upload-File-Name" not in options.headers
        assert all(v.isascii() for v in options.headers.values())
        return SimpleNamespace(name="files/safe",uri="https://example.com/safe",state=SimpleNamespace(name="ACTIVE"))
    llm.client.files.upload.side_effect=upload
    monkeypatch.setattr("pipeline.style_learner.GeminiProvider",lambda settings:llm)
    provider=VideoStyleProvider(style_settings)
    assert provider.analyze(path,"prompt",lambda m:None).scenes
    llm.client.files.delete.assert_called_once_with(name="files/safe")


def test_raw_saved_before_pydantic_error_and_rerun_does_not_create_provider(style_settings,monkeypatch):
    folder=style_settings.root_dir/"assets/reference_videos/tin-tuc";folder.mkdir()
    path=folder/"Bản tin.mp4";path.write_bytes(b"video bytes")
    # Broken end_sec is now repairable. No valid scenes remains a real hard error.
    bad=observed().model_dump();bad["scenes"]=[]
    raw="```json\n"+json.dumps(bad,ensure_ascii=False)+"\n```"
    provider=Mock();provider.analyze.return_value=raw
    result=analyze_batch(style_settings,["tin-tuc/Bản tin.mp4"],provider=provider)
    target=raw_path(style_settings,"tin tức",digest_file(path))
    assert target.read_text(encoding="utf-8")==raw
    assert result[0]["status"]=="failed" and "ít nhất 1 cảnh hợp lệ" in result[0]["validation_fields"][0]["message"]
    constructor=Mock(side_effect=AssertionError("Never bill for a local raw retry"))
    monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",constructor)
    with pytest.raises(StyleRawError,match="ít nhất 1 cảnh hợp lệ"):
        analyze_one(style_settings,"tin-tuc/Bản tin.mp4")
    constructor.assert_not_called()
    write_text_atomic(target,"```json\n"+observed().model_dump_json()+"\n```")
    result=analyze_one(style_settings,"tin-tuc/Bản tin.mp4",from_raw=True)
    assert result["status"]=="cached" and result["analysis"]["scenes"]
    constructor.assert_not_called()
    assert estimate_batch(style_settings,["tin-tuc/Bản tin.mp4"])["estimated_input_tokens"]==0


def test_new_raw_before_parse_and_delete_uploaded_file_on_invalid_output(style_settings,monkeypatch):
    llm=Mock();llm.client.files.upload.return_value=SimpleNamespace(name="files/mock",uri="https://example.com/mock",state=SimpleNamespace(name="ACTIVE"))
    raw='```json\n{"broken":\n```';llm.generate_media_json.return_value=raw
    monkeypatch.setattr("pipeline.style_learner.GeminiProvider",lambda settings:llm)
    file=style_settings.root_dir/"assets/reference_videos/a.mp4"
    provider=VideoStyleProvider(style_settings)
    original=RawResponse.parse
    def parse(store):
        assert store.path.read_text(encoding="utf-8")==raw
        return original(store)
    monkeypatch.setattr(RawResponse,"parse",parse)
    with pytest.raises(StyleRawError):
        provider.analyze(file,"prompt",lambda m:None)
    llm.client.files.delete.assert_called_once_with(name="files/mock")
    assert llm.generate_media_json.call_count==2  # one compact retry for truncated JSON


def test_sdk_observer_saves_even_truncated_output_before_output_error(style_settings,monkeypatch):
    from providers.llm_gemini import GeminiProvider,GeminiOutputError
    from schemas.style import StyleAnalysis
    from pipeline.style_learner import style_diagnostics
    client=Mock()
    client.models.generate_content.return_value=types.GenerateContentResponse(candidates=[types.Candidate(
        finish_reason="MAX_TOKENS",content=types.Content(parts=[types.Part(text='{"scenes": [')]))])
    monkeypatch.setattr("providers.llm_gemini.genai.Client",lambda **kw:client)
    provider=GeminiProvider(style_settings)
    store=RawResponse(raw_path(style_settings,"tin-tuc","a"*64),{},style_diagnostics(style_settings))
    provider.response_observer=store.save
    with pytest.raises(GeminiOutputError):
        provider.generate_media_json("prompt",types.Part.from_uri(file_uri="https://example.com/file",mime_type="video/mp4"),StyleAnalysis)
    assert store.path.read_text(encoding="utf-8")=='{"scenes": ['
    assert store.metadata()["status"]["finish_reasons"]==["MAX_TOKENS"]


def test_media_config_low_fps_and_json_schema_are_sent(style_settings,monkeypatch):
    client=Mock()
    client.files.upload.return_value=SimpleNamespace(name="files/mock",uri="https://example.com/mock",state=SimpleNamespace(name="ACTIVE"))
    client.models.generate_content.return_value=SimpleNamespace(candidates=[],prompt_feedback=None,text=observed().model_dump_json())
    monkeypatch.setattr("providers.llm_gemini.genai.Client",lambda **kw:client)
    provider=VideoStyleProvider(style_settings)
    provider.analyze(style_settings.root_dir/"assets/reference_videos/a.mp4","prompt",lambda m:None)
    call=client.models.generate_content.call_args.kwargs
    assert call["config"].response_mime_type=="application/json" and call["config"].response_json_schema
    assert call["config"].media_resolution==types.MediaResolution.MEDIA_RESOLUTION_LOW
    assert call["contents"][0].video_metadata.fps==.5


def test_missing_optional_observations_get_defaults_without_inventing_scene_times():
    from schemas.style import StyleAnalysis
    data=observed().model_dump()
    for key in ("narration_style","visual_style","captions","audio","cta_ending","strengths","weaknesses"):
        data.pop(key)
    for scene in data["scenes"]:
        for key in ("visual_types","camera_effects","overlays","sfx","music","transition_to_next"):
            scene.pop(key)
    result=StyleAnalysis.model_validate(data)
    assert result.scenes[0].music=="Không rõ" and result.scenes[0].overlays==[]
    assert result.narration_style.voice_emotion=="Không rõ" and result.cta_ending.has_cta is None
    assert result.scenes[0].start_sec==data["scenes"][0]["start_sec"]


def test_raw_only_missing_file_never_calls_gemini(style_settings,monkeypatch):
    constructor=Mock();monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",constructor)
    with pytest.raises(ValueError,match="Chưa có bản thô"):
        analyze_one(style_settings,"a.mp4",from_raw=True)
    constructor.assert_not_called()


def test_rolling_minute_rpm_tpm_interval_reservations(style_settings):
    settings=style_settings.model_copy(update={"style_rpm_limit":2,"style_tpm_limit":1000,"style_request_interval_sec":3})
    current=[100.];waits=[]
    def sleep(seconds):
        waits.append(seconds);current[0]+=seconds
    for tokens in (600,400,500):
        reserve_style_request(settings,tokens,clock=lambda:current[0],sleep=sleep)
    assert current[0]>=160 and waits and all(0<s<=5 for s in waits)
    before=current[0]
    with pytest.raises(ValueError,match="vượt STYLE_TPM_LIMIT"):
        reserve_style_request(settings,1001,clock=lambda:current[0],sleep=sleep)
    assert current[0]==before
    assert estimated_video_tokens(style_settings,650)<650*150


def test_raw_redacts_keys_and_preserves_previous_paid_response(style_settings):
    from pipeline.style_learner import style_diagnostics
    store=RawResponse(raw_path(style_settings,"tin-tuc","b"*64),{},style_diagnostics(style_settings))
    store.save('raw fixture-style-secret')
    assert "fixture-style-secret" not in store.path.read_text(encoding="utf-8")
    store.save("second response")
    archives=list(store.path.parent.glob("b*.raw.txt"))
    assert len(archives)==2


def test_media_400_does_not_retry_and_keeps_low_resolution(style_settings,monkeypatch):
    from google.genai import errors
    from providers.llm_gemini import GeminiProvider,GeminiRequestError
    from schemas.style import StyleAnalysis
    client=Mock();client.models.generate_content.side_effect=[errors.ClientError(400,{"error":{"message":"response schema rejected"}}),
        SimpleNamespace(candidates=[],prompt_feedback=None,text='```json\n'+observed().model_dump_json()+'\n```')]
    monkeypatch.setattr("providers.llm_gemini.genai.Client",lambda **kw:client)
    provider=GeminiProvider(style_settings);provider.media_resolution="low"
    with pytest.raises(GeminiRequestError):
        provider.generate_media_json("prompt",types.Part.from_uri(file_uri="https://example.com/file",mime_type="video/mp4"),StyleAnalysis)
    config=client.models.generate_content.call_args.kwargs["config"]
    assert config.response_json_schema and config.response_mime_type=="application/json"
    assert config.media_resolution==types.MediaResolution.MEDIA_RESOLUTION_LOW
    assert client.models.generate_content.call_count==1


def test_raw_parse_works_without_key_or_model_and_bad_optional_metadata(style_settings,monkeypatch):
    path=style_settings.root_dir/"assets/reference_videos/a.mp4"
    raw=raw_path(style_settings,None,digest_file(path))
    raw.parent.mkdir(parents=True,exist_ok=True)
    raw.write_text(observed().model_dump_json(),encoding="utf-8")
    raw.with_suffix(".meta.json").write_text("broken",encoding="utf-8")
    from pydantic import SecretStr
    offline=style_settings.model_copy(update={"gemini_api_key":SecretStr(""),"gemini_model":"","gemini_style_model":""})
    constructor=Mock(side_effect=AssertionError("No paid call"));monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",constructor)
    assert analyze_one(offline,"a.mp4",from_raw=True)["analysis"]["scene_count"]==3
    constructor.assert_not_called()


def test_cli_from_raw_only_does_not_upload(style_settings,monkeypatch):
    from pipeline.style_learner import main
    path=style_settings.root_dir/"assets/reference_videos/a.mp4"
    target=raw_path(style_settings,None,digest_file(path));target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text("```json\n"+observed().model_dump_json()+"\n```",encoding="utf-8")
    monkeypatch.setattr("pipeline.style_learner.get_settings",lambda:style_settings)
    monkeypatch.setattr("sys.argv",["style_learner","--videos","a.mp4","--from-raw"])
    constructor=Mock(side_effect=AssertionError("No upload"));monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",constructor)
    assert main()==0
    constructor.assert_not_called()


def test_raw_repair_ui_dispatches_offline_job_without_key(style_settings,monkeypatch):
    from pydantic import SecretStr
    from streamlit.testing.v1 import AppTest
    from config.settings import ROOT_DIR
    folder=style_settings.root_dir/"assets/reference_videos/tin-tuc";folder.mkdir()
    path=folder/"Thực sự #tin.mp4";path.write_bytes(b"news video")
    target=raw_path(style_settings,"tin-tuc",digest_file(path));target.parent.mkdir(parents=True,exist_ok=True)
    bad=observed().model_dump();bad["scenes"][0]["end_sec"]="wrong"
    target.write_text(json.dumps(bad,ensure_ascii=False),encoding="utf-8")
    offline=style_settings.model_copy(update={"gemini_api_key":SecretStr(""),"gemini_model":""})
    monkeypatch.setattr("config.settings.get_settings",lambda:offline)
    manager=Mock();manager.active.return_value=None;manager.snapshot.return_value=None;manager.submit_analysis.return_value="raw-worker"
    monkeypatch.setattr("app.views.style_samples.style_jobs",lambda:manager)
    at=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=30).run()
    at.sidebar.radio[0].set_value("Phong cách mẫu").run()
    at.session_state["style_category_tabs"]="tin tức";at.run()
    assert not at.exception
    button=next(b for b in at.button if b.label=="Sửa lại từ bản thô")
    assert not button.disabled
    button.click().run()
    assert not at.exception and manager.submit_analysis.call_args.kwargs=={"from_raw":True}


def test_existing_paid_v2_json_cache_does_not_reupload_after_media_settings_added(style_settings):
    from pipeline.style_learner import analysis_inputs,storage
    from tests.test_style_learner import record
    from utils.cache import cache_key
    from utils.atomic_io import write_json_atomic
    path,info,notes,prompt,identity=analysis_inputs(style_settings,"a.mp4")
    identity["prompt_hash"]=cache_key(prompt)
    cached=record();cached=cached.model_copy(update=identity)
    write_json_atomic(storage(style_settings)/".cache"/(cache_key(identity)+".json"),cached.model_dump(mode="json"))
    provider=Mock()
    assert estimate_batch(style_settings,["a.mp4"])["estimated_input_tokens"]==0
    assert analyze_one(style_settings,"a.mp4",provider=provider)["status"]=="cached"
    provider.analyze.assert_not_called()


def test_windows_console_reconfigures_ascii_streams_to_utf8(monkeypatch):
    from utils.console import configure_console
    output=io.BytesIO();errors=io.BytesIO()
    stdout=io.TextIOWrapper(output,encoding="ascii");stderr=io.TextIOWrapper(errors,encoding="ascii")
    monkeypatch.setattr("sys.stdout",stdout);monkeypatch.setattr("sys.stderr",stderr)
    configure_console()
    stdout.write("Tin thực sự “mới” #tin");stderr.write("Lỗi tiếng Việt")
    stdout.flush();stderr.flush()
    assert "thực sự" in output.getvalue().decode("utf-8")
    assert "tiếng Việt" in errors.getvalue().decode("utf-8")
