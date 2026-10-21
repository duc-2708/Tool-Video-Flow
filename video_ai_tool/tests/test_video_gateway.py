"""Veo/Seedance regressions: all gateway calls mocked, no paid generation."""
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock
import pytest
import requests
from pydantic import SecretStr,ValidationError
from imageio_ffmpeg import get_ffmpeg_exe
from config.settings import Settings,ROOT_DIR,get_settings
from providers.video_gateway import VideoGateway,VideoRequest,GatewayVideoError,AmbiguousSubmission
from pipeline.ai_video import create_job,resume_job,load_job
from pipeline.ai_video_jobs import AIVideoJobs


@pytest.fixture
def settings(tmp_path):
    return Settings(root_dir=tmp_path,gateway_api_key=SecretStr("fixture-private-gateway-key"),retry_attempts=2)


def response(data,code=200):
    value = Mock()
    value.status_code = code
    value.headers = {}
    value.json.return_value = data
    return value


def test_auth_models_and_exact_host(settings):
    session = Mock()
    session.request.return_value = response({"data":[{"id":"veo-3.1"},{"id":"seedance-2.5-30s"},{"id":"chat-model"}]})
    client = VideoGateway(settings,session=session)
    assert [m["id"] for m in client.models()] == ["veo-3.1","seedance-2.5-30s"]
    args,kwargs = session.request.call_args
    assert args == ("GET","https://api.buihuuthang.com/v1/models")
    assert kwargs["headers"]["Authorization"] == "Bearer fixture-private-gateway-key"
    assert kwargs["allow_redirects"] is False
    with pytest.raises(ValueError,match="GATEWAY_BASE_URL"):
        VideoGateway(settings.model_copy(update={"gateway_base_url":"https://example.com/v1"}),session=session)


@pytest.mark.parametrize("model,seconds,cost",[("veo-3.1",4,2500),("veo-3.1",8,2500),("seedance-2.5-30s",5,2800),("seedance-2.5-30s",30,9300)])
def test_video_payload_and_price(model,seconds,cost):
    request = VideoRequest(model=model,seconds=seconds,prompt="Một cảnh thử",format="youtube")
    assert request.payload()["aspect_ratio"] == "16:9"
    assert request.payload()["seconds"] == seconds
    assert request.estimated_cost_vnd == cost


@pytest.mark.parametrize("parameters",[{"model":"veo-3.1","seconds":5},{"model":"seedance-2.5-30s","seconds":4},{"model":"seedance-2.0-fast","seconds":5,"resolution":"1080p"}])
def test_invalid_duration_and_resolution_not_sent(parameters):
    with pytest.raises(ValidationError):
        VideoRequest(prompt="Fixture",**parameters)


def test_post_timeout_never_retries_and_redacts_key(settings):
    session = Mock()
    session.request.side_effect = requests.Timeout("Authorization: Bearer fixture-private-gateway-key")
    client = VideoGateway(settings,session=session)
    with pytest.raises(AmbiguousSubmission):
        client.create(VideoRequest(prompt="Fixture"))
    assert session.request.call_count == 1
    log = client.diagnostics.path.read_text(encoding="utf-8")
    assert "Traceback" in log and "fixture-private-gateway-key" not in log


def test_post_502_never_retries(settings):
    session = Mock()
    session.request.return_value = response({"error":{"message":"Upstream unavailable"}},502)
    with pytest.raises(AmbiguousSubmission):
        VideoGateway(settings,session=session).create(VideoRequest(prompt="Fixture"))
    assert session.request.call_count == 1


def test_poll_and_download_always_include_model(settings):
    session = Mock()
    session.request.return_value = response({"status":"queued"})
    client = VideoGateway(settings,session=session)
    client.status("video /123","veo-3.1")
    assert session.request.call_args.kwargs["params"] == {"model":"veo-3.1"}
    assert session.request.call_args.args[1].endswith("video%20%2F123")
    client.download("video123","veo-3.1")
    assert session.request.call_args.kwargs["params"]["model"] == "veo-3.1"
    assert session.request.call_args.kwargs["stream"] is True


def test_read_retry_only_for_transient_errors(settings,monkeypatch):
    monkeypatch.setattr("providers.video_gateway.time.sleep",lambda seconds:None)
    session = Mock()
    session.request.side_effect = [response({"error":{"message":"Try later"}},503),response({"data":[]})]
    assert VideoGateway(settings,session=session).models() == []
    assert session.request.call_count == 2


def test_missing_post_id_is_ambiguous(settings):
    session = Mock()
    session.request.return_value = response({"status":"queued"})
    with pytest.raises(AmbiguousSubmission):
        VideoGateway(settings,session=session).create(VideoRequest(prompt="Fixture"))
    assert session.request.call_count == 1


def test_unauthorized_response_redacts_original_message(settings):
    session = Mock()
    session.request.return_value = response({"error":{"message":"Bad fixture-private-gateway-key"}},401)
    with pytest.raises(GatewayVideoError) as caught:
        VideoGateway(settings,session=session).models()
    assert "401" in str(caught.value) and "fixture-private-gateway-key" not in str(caught.value)
    assert session.request.call_count == 1


def test_create_dedup_and_resume_real_mp4(settings,tmp_path):
    project = tmp_path/"project"
    project.mkdir()
    (project/"credits.txt").write_text("Existing credits",encoding="utf-8")
    fixture = tmp_path/"fixture.mp4"
    subprocess.run([get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","color=c=blue:s=96x160:d=0.5:r=30","-c:v","libx264",str(fixture)],capture_output=True,check=True,timeout=20)
    gateway = Mock()
    gateway.create.return_value = ({"id":"video_fixture","status":"queued"},"2500")
    gateway.status.return_value = {"id":"video_fixture","status":"completed","progress":100}
    download = Mock()
    download.headers = {"Content-Type":"video/mp4"}
    download.iter_content.return_value = [fixture.read_bytes()]
    gateway.download.return_value = download
    request = VideoRequest(prompt="Fixture clip")
    path = create_job(project,request,settings,gateway=gateway)
    assert create_job(project,request,settings,gateway=gateway) == path
    gateway.create.assert_called_once()
    result = resume_job(path,settings,gateway=gateway,poll_sec=0)
    assert (result["width"],result["height"]) == (96,160)
    assert result["actual_cost_vnd"] == "2500"
    assert (project/result["clip_path"]).is_file()
    assert "fixture-private-gateway-key" not in path.read_text(encoding="utf-8")
    assert (project/"credits.txt").read_text(encoding="utf-8") == "Existing credits"
    assert resume_job(path,settings,gateway=gateway)["clip_path"] == result["clip_path"]
    gateway.download.assert_called_once()
    gateway.status.assert_called_once_with("video_fixture","veo-3.1")


def test_ambiguous_submit_persists_and_cannot_charge_twice(settings,tmp_path):
    project = tmp_path/"project"
    project.mkdir()
    gateway = Mock()
    gateway.create.side_effect = AmbiguousSubmission("Mất phản hồi")
    request = VideoRequest(prompt="Fixture clip")
    for _ in range(2):
        with pytest.raises(AmbiguousSubmission):
            create_job(project,request,settings,gateway=gateway)
    gateway.create.assert_called_once()
    path = next((project/"ai_video").glob("*.json"))
    assert load_job(path)["status"] == "ambiguous"
    with pytest.raises(GatewayVideoError,match="remote ID"):
        resume_job(path,settings,gateway=gateway)
    gateway.status.assert_not_called()


def test_failed_job_keeps_original_error(settings,tmp_path):
    project = tmp_path/"project"
    project.mkdir()
    gateway = Mock()
    gateway.create.return_value = ({"id":"video123","status":"queued"},None)
    path = create_job(project,VideoRequest(prompt="Fixture"),settings,gateway=gateway)
    gateway.status.return_value = {"status":"failed","error":{"message":"Fixture upstream failed"}}
    with pytest.raises(GatewayVideoError,match="Fixture upstream failed"):
        resume_job(path,settings,gateway=gateway)
    assert load_job(path)["status"] == "failed"
    assert "Fixture upstream failed" in (settings.logs_dir/"gateway_video_errors.log").read_text(encoding="utf-8")
    gateway.download.assert_not_called()


def test_gateway_env_is_independent_and_secret(isolate_configuration,monkeypatch):
    isolate_configuration.write_text("GATEWAY_API_KEY=fixture-secret\nGATEWAY_VIDEO_MODEL=veo-3.1\n",encoding="utf-8")
    settings = get_settings()
    assert settings.gateway_api_key.get_secret_value() == "fixture-secret"
    assert "fixture-secret" not in repr(settings)


def test_background_worker_only_resumes_existing_job(settings,tmp_path,monkeypatch):
    create = Mock()
    resume = Mock(return_value={"clip_path":"clips/fixture.mp4"})
    monkeypatch.setattr("pipeline.ai_video_jobs.create_job",create)
    monkeypatch.setattr("pipeline.ai_video_jobs.resume_job",resume)
    manager = AIVideoJobs()
    path = tmp_path/"project/ai_video/fixture.json"
    key = manager.submit(path.parent.parent,None,settings,job_path=path)
    manager.executor.shutdown(wait=True)
    create.assert_not_called()
    resume.assert_called_once()
    assert manager.snapshot(key)["status"] == "completed"


def test_remote_id_is_first_persisted_update_and_write_retried(settings,tmp_path,monkeypatch):
    import pipeline.ai_video as module
    project = tmp_path/"project"
    project.mkdir()
    gateway = Mock()
    gateway.create.return_value = ({"id":"remote_durable","status":"processing"},"2500")
    original = module.save_job
    updates = []
    def save(path,data,diagnostics):
        updates.append(dict(data))
        if len(updates) == 2:
            raise PermissionError("fixture cannot persist first ID write")
        return original(path,data,diagnostics)
    monkeypatch.setattr(module,"save_job",save)
    monkeypatch.setattr(module.time,"sleep",lambda _:None)
    path = create_job(project,VideoRequest(prompt="Persist ID first"),settings,gateway=gateway)
    assert updates[0]["remote_id"] is None
    assert updates[1]["remote_id"] == updates[2]["remote_id"] == "remote_durable"
    assert updates[1]["actual_cost_vnd"] is None and updates[1]["status"] == "queued"
    assert load_job(path)["actual_cost_vnd"] == "2500"
    gateway.create.assert_called_once()
    gateway.status.assert_not_called()
    log = (settings.logs_dir/"gateway_video_errors.log").read_text(encoding="utf-8")
    assert "remote_durable" in log and "1/3" in log


def test_permanent_id_write_failure_exposes_id_without_second_post(settings,tmp_path,monkeypatch):
    import pipeline.ai_video as module
    project = tmp_path/"project"
    project.mkdir()
    gateway = Mock()
    gateway.create.return_value = ({"id":"remote_recover_me"},None)
    original = module.save_job
    def save(path,data,diagnostics):
        if data.get("remote_id"):
            raise PermissionError("fixture all ID writes fail")
        return original(path,data,diagnostics)
    monkeypatch.setattr(module,"save_job",save)
    monkeypatch.setattr(module.time,"sleep",lambda _:None)
    with pytest.raises(GatewayVideoError,match="remote_recover_me"):
        create_job(project,VideoRequest(prompt="Lost local write"),settings,gateway=gateway)
    gateway.create.assert_called_once()
    assert load_job(next((project/"ai_video").glob("*.json")))["status"] == "submitting"
    assert "remote_recover_me" in (settings.logs_dir/"gateway_video_errors.log").read_text(encoding="utf-8")


def test_explicit_id_resume_persists_before_get_without_post(settings,tmp_path):
    from pipeline.ai_video import save_job,diagnostics_for
    project = tmp_path/"project"
    project.mkdir()
    path = project/"ai_video/job.json"
    save_job(path,{"request":VideoRequest(prompt="Recover existing").model_dump(),"status":"ambiguous","remote_id":None},diagnostics_for(settings))
    gateway = Mock()
    def status(remote_id,model):
        assert load_job(path)["remote_id"] == "dashboard_id"
        return {"status":"failed","error":"fixture after recovery"}
    gateway.status.side_effect = status
    with pytest.raises(GatewayVideoError,match="fixture after recovery"):
        resume_job(path,settings,remote_id="dashboard_id",gateway=gateway)
    gateway.create.assert_not_called()
    gateway.status.assert_called_once_with("dashboard_id","veo-3.1")


def test_locked_logs_do_not_lose_recovery_id(settings,tmp_path,monkeypatch):
    import pipeline.ai_video as module
    job = {"request":VideoRequest(prompt="Locked logs").model_dump(),"remote_id":None}
    diagnostics = Mock()
    diagnostics.redact.side_effect = lambda text:text
    diagnostics.record_exception.side_effect = PermissionError("fixture locked log")
    save = Mock(side_effect=PermissionError("fixture locked state"))
    monkeypatch.setattr(module,"save_job",save)
    monkeypatch.setattr(module.time,"sleep",lambda _:None)
    with pytest.raises(GatewayVideoError,match="recover_even_without_log"):
        module.persist_remote_id(tmp_path/"job.json",job,"recover_even_without_log",diagnostics)
    assert save.call_count == 3 and diagnostics.record_exception.call_count == 3


def test_recreate_requires_confirmation_preserves_history_and_never_replaces_id(settings,tmp_path):
    from pipeline.ai_video import recreate_job
    project = tmp_path/"project"
    project.mkdir()
    gateway = Mock()
    request = VideoRequest(prompt="Explicit recreate")
    gateway.create.side_effect = AmbiguousSubmission("fixture response lost")
    with pytest.raises(AmbiguousSubmission):
        create_job(project,request,settings,gateway=gateway)
    path = next((project/"ai_video").glob("*.json"))
    with pytest.raises(GatewayVideoError,match="xác nhận"):
        recreate_job(path,settings,gateway=gateway)
    assert gateway.create.call_count == 1
    gateway.create.side_effect = None
    gateway.create.return_value = ({"id":"explicit_new_id"},None)
    assert recreate_job(path,settings,confirmed=True,gateway=gateway) == path
    job = load_job(path)
    assert job["remote_id"] == "explicit_new_id" and job["recreate_confirmed"]
    assert job["previous_attempts"][0]["status"] == "ambiguous"
    assert "chi phí" in job["cost_warning"]
    with pytest.raises(GatewayVideoError,match="đã có remote ID"):
        recreate_job(path,settings,confirmed=True,gateway=gateway)
    assert gateway.create.call_count == 2


@pytest.mark.parametrize("configured", ["veo-3.1,seedance-2.5-30s", '["veo-3.1", "seedance-2.5-30s"]'])
def test_allowed_models_from_explicit_env_file(tmp_path, configured):
    path = tmp_path / "gateway.env"
    path.write_text("GATEWAY_ALLOWED_MODELS=" + configured + "\n", encoding="utf-8")
    assert get_settings(path).gateway_allowed_models == ["veo-3.1", "seedance-2.5-30s"]


def test_disallowed_model_never_submits(settings):
    session = Mock()
    settings = settings.model_copy(update={"gateway_allowed_models": ["veo-3.1"]})
    with pytest.raises(GatewayVideoError, match="GATEWAY_ALLOWED_MODELS"):
        VideoGateway(settings, session=session).create(VideoRequest(model="seedance-2.5-30s", seconds=30, prompt="Fixture"))
    session.request.assert_not_called()


def test_old_model_name_is_rejected_clearly():
    with pytest.raises(ValidationError, match="không hợp lệ.*seedance-2.5-30s"):
        VideoRequest(model="seedance-2.5", seconds=30, prompt="Fixture")


def test_model_403_explains_permissions_and_preserves_redacted_original(settings):
    session = Mock()
    session.request.return_value = response({"error": {"message": "Model access denied fixture-private-gateway-key"}}, code=403)
    client = VideoGateway(settings, session=session)
    with pytest.raises(GatewayVideoError, match="HTTP 403.*chưa có quyền.*veo-3.1") as caught:
        client.create(VideoRequest(prompt="Fixture"))
    assert "Model access denied" in str(caught.value)
    assert "fixture-private-gateway-key" not in str(caught.value)
    assert session.request.call_count == 1


@pytest.mark.parametrize("dirty", [
    "Apple iPhone 17 shows a logo and text with Tim Cook, screen with text, brand subtitle",
    "Google Gemini OpenAI Elon Musk discusses a chart on a laptop",
    "Samsung Galaxy with readable text and Jensen Huang",
    "Một video về thương hiệu và người nổi tiếng",
])
def test_sanitizer_removes_names_and_returns_short_english_template(dirty):
    import re
    from agents.video_prompt_writer import sanitize_video_prompt
    clean = sanitize_video_prompt(dirty)
    assert clean.isascii() and len(clean.split()) <= 30
    assert "static camera" in clean and "cinematic" in clean
    assert not re.search(r"apple|iphone|google|gemini|openai|elon|tim|cook|samsung|galaxy|jensen|huang|logo|text|subtitle|brand|chart", clean, re.I)
    assert sanitize_video_prompt(clean) == clean


def test_generation_failed_retry_is_durable_exactly_once_and_logs_full_error(settings,tmp_path):
    from agents.video_prompt_writer import fallback_prompt
    gateway = Mock()
    gateway.create.side_effect = [({"id":"first_remote"},None),({"id":"second_remote"},None)]
    gateway.status.return_value = {"status":"failed","error":{"code":"generation_failed",
        "message":"Provider failed fixture-private-gateway-key","details":{"reason":"safety_or_upstream","nested":[1,2,3]}}}
    project = tmp_path/"retry_project"
    project.mkdir()
    path = create_job(project,VideoRequest(prompt="Apple MacBook showing Tim Cook and text logo"),settings,gateway=gateway)
    for _ in range(2):
        with pytest.raises(GatewayVideoError,match="không tạo thêm job"):
            resume_job(path,settings,gateway=gateway,poll_sec=0)
    assert gateway.create.call_count == 2
    gateway.download.assert_not_called()
    requests = [call.args[0] for call in gateway.create.call_args_list]
    assert requests[0].prompt != requests[1].prompt
    assert requests[1].prompt == fallback_prompt(requests[0].prompt,simpler=True)
    assert len(requests[1].prompt.split()) < len(requests[0].prompt.split())
    root = load_job(path)
    child = load_job(path.parent/root["generation_retry_path"])
    assert child["remote_id"] == "second_remote" and root["generation_retry_count"] == 1
    log = (settings.logs_dir/"gateway_video_errors.log").read_text(encoding="utf-8")
    assert "fixture-private-gateway-key" not in log
    for value in ["first_remote","second_remote","safety_or_upstream",'"nested": [1, 2, 3]', requests[0].prompt, '"aspect_ratio": "9:16"']:
        assert value in log


def test_http_error_logs_entire_gateway_response_redacted(settings):
    session = Mock()
    session.request.return_value = response({"error":{"code":"bad_request","message":"Rejected",
        "details":{"token":"fixture-private-gateway-key","extra":"unabridged details"}}},400)
    client = VideoGateway(settings,session=session)
    with pytest.raises(GatewayVideoError):
        client.create(VideoRequest(prompt="A sphere rests indoors, soft light, static camera, cinematic."))
    log = client.diagnostics.path.read_text(encoding="utf-8")
    assert "unabridged details" in log and '"http_status": 400' in log
    assert "fixture-private-gateway-key" not in log


@pytest.mark.parametrize("values", [
    {"gateway_video_model":"seedance-2.5"},
    {"gateway_video_model":"veo-3.1","ai_clip_seconds":5},
    {"gateway_video_model":"seedance-2.5-30s","ai_clip_seconds":4},
    {"ai_clip_max_per_run":21},
])
def test_invalid_gateway_defaults_fail_on_startup(values):
    with pytest.raises(ValidationError):
        Settings(**values)


def test_seedance_default_seconds_and_explicit_configuration():
    assert Settings(gateway_video_model="seedance-2.5-30s").ai_clip_seconds == 5
    assert Settings(gateway_video_model="veo-3.1",ai_clip_seconds=8,ai_clip_max_per_run=1).ai_clip_seconds == 8


def test_generation_retry_missing_intent_file_never_posts_again(settings,tmp_path):
    import pipeline.ai_video as module
    gateway = Mock()
    gateway.create.return_value = ({"id":"original"},None)
    gateway.status.return_value = {"status":"failed","error":{"code":"generation_failed"}}
    project = tmp_path/"intent_project"
    project.mkdir()
    path = create_job(project,VideoRequest(prompt="Original clip"),settings,gateway=gateway)
    job = load_job(path)
    job.update(generation_retry_count=1,generation_retry_path="missing.json")
    module.save_job(path,job,module.diagnostics_for(settings))
    with pytest.raises(AmbiguousSubmission,match="kiểm tra dashboard"):
        resume_job(path,settings,gateway=gateway)
    gateway.create.assert_called_once()


def test_generation_retry_success_uses_existing_child_on_resume(settings,tmp_path,monkeypatch):
    import pipeline.ai_video as module
    from providers.video_gateway import GenerationFailed
    gateway = Mock()
    gateway.create.side_effect = [({"id":"original"},None),({"id":"retry_success"},None)]
    project = tmp_path/"success_project"
    project.mkdir()
    path = create_job(project,VideoRequest(prompt="Apple MacBook"),settings,gateway=gateway)
    def once(candidate, settings, **kwargs):
        if candidate == path:
            raise GenerationFailed("generation_failed")
        return {**load_job(candidate),"clip_path":"clips/success.mp4","duration_sec":4}
    monkeypatch.setattr(module,"_resume_job_once",once)
    for _ in range(2):
        result = resume_job(path,settings,gateway=gateway)
        assert result["remote_id"] == "retry_success" and Path(result["effective_job_path"]).is_file()
    assert load_job(path)["generation_retry_completed"]
    assert gateway.create.call_count == 2
