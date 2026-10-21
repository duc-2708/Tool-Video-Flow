"""Prompt validation/generation and edited drafts: no live LLM/video calls."""
import json
from unittest.mock import Mock
import pytest
from pydantic import SecretStr
from streamlit.testing.v1 import AppTest
from agents.video_prompt_writer import validate_ai_prompt,write_video_prompt,fallback_prompt,fill_plan_prompts,VideoPrompt
from config.settings import ROOT_DIR,Settings
from schemas.edit_plan import EditPlan,Shot
from pipeline.projects import create_project,read_json
from pipeline.assets import source_hash
from pipeline.video_prompts import save_shot_prompt
from pipeline.ai_video import create_job,resume_job,load_job
from providers.video_gateway import VideoRequest,GatewayVideoError
from utils.cache import write_json
from utils.diagnostics import Diagnostics
from tests.test_director import fixture_plan,fixture_brief
from tests.test_run_all import stages

SAFE = "A ceramic cup rests on a wooden table in soft warm light, static camera, cinematic."
MANUAL = "A plain stone rests on a wooden desk in soft warm light, static camera, cinematic."


def test_short_safe_single_sentence_and_configuration_stays_separate():
    assert validate_ai_prompt(SAFE) == SAFE
    request = VideoRequest(prompt=SAFE,model="veo-3.1",seconds=4,format="tiktok")
    assert request.payload()["seconds"] == 4 and request.payload()["aspect_ratio"] == "9:16"
    assert "4" not in request.prompt and "9:16" not in request.prompt


@pytest.mark.parametrize("bad",[
    SAFE+" No text.", SAFE.replace("cup","cup with a logo"),SAFE.replace("cup","chart"),
    SAFE.replace("cup","Elon Musk"),SAFE.replace("cup","unknownbrand"),
    SAFE.replace("rests","rests and rotates"),SAFE.replace("static camera","static camera, slow pan"),
    SAFE.replace("cup","subtitle"), SAFE.replace("cup","screen"), SAFE.replace("cup","weapon"),
    "A cup rests. A stone rotates on a table in warm light, static camera, cinematic.",
    SAFE.replace("wooden table","wooden table " + "plain "*30),
])
def test_unsafe_or_complex_prompts_are_blocked(bad):
    with pytest.raises(ValueError):
        validate_ai_prompt(bad)


def test_bad_prompt_is_regenerated_then_safe_result_used(tmp_path):
    provider = Mock()
    provider.generate_json.side_effect = [json.dumps({"ai_prompt":SAFE+" No text."}),json.dumps({"ai_prompt":SAFE})]
    result = write_video_prompt({"topic":"Video editing","narration":"Dựng video."},provider,Diagnostics(tmp_path))
    assert result == SAFE and provider.generate_json.call_count == 2
    assert provider.generate_json.call_args.args[1] is VideoPrompt
    assert "RETRY" in provider.generate_json.call_args.args[0]


def test_three_invalid_attempts_use_safe_topic_fallback(tmp_path):
    provider = Mock()
    provider.generate_json.return_value = json.dumps({"ai_prompt":"A celebrity reads a brand name on a screen."})
    result = write_video_prompt({"topic":"video editing"},provider,Diagnostics(tmp_path))
    assert provider.generate_json.call_count == 3
    assert result == fallback_prompt("video editing")
    assert validate_ai_prompt(result) == result
    assert "dự phòng" in (tmp_path/"researcher_errors.log").read_text(encoding="utf-8")


def test_simpler_prompt_uses_static_camera_and_less_words(tmp_path):
    provider = Mock()
    provider.generate_json.return_value = json.dumps({"ai_prompt":SAFE.replace("static camera","slow pan")})
    result = write_video_prompt({"topic":"food"},provider,Diagnostics(tmp_path),simpler=True)
    assert len(result.split()) <= 22 and "static camera" in result
    assert validate_ai_prompt(result,simpler=True) == result
    assert provider.generate_json.call_count == 3


def test_fill_ai_shots_preserves_valid_manual_prompt_and_source_alias(tmp_path):
    plan = EditPlan.model_validate(fixture_plan())
    plan.scenes[0].shots[0].type = "ai_video"
    plan.scenes[0].shots[0].ai_prompt = MANUAL
    plan.scenes[1].shots[0].type = "ai_video"
    provider = Mock()
    provider.generate_json.return_value = json.dumps({"ai_prompt":SAFE})
    fill_plan_prompts(plan,fixture_brief(),provider,Diagnostics(tmp_path))
    assert plan.scenes[0].shots[0].ai_prompt == MANUAL
    assert plan.scenes[1].shots[0].ai_prompt == SAFE
    provider.generate_json.assert_called_once()
    data = plan.scenes[0].shots[0].model_dump()
    data["source"] = data.pop("type")
    assert Shot.model_validate(data).type == "ai_video"


def test_prompt_only_save_preserves_asset_hash_and_checkpoint(tmp_path):
    import hashlib
    plan = EditPlan.model_validate(fixture_plan())
    plan.scenes[0].shots[0].type = "ai_video"
    plan.scenes[0].shots[0].ai_prompt = SAFE
    path = tmp_path/"edit_plan.json"
    write_json(path,plan.model_dump(mode="json"))
    old_hash = source_hash(plan)
    write_json(tmp_path/"run_state.json",{"steps":{"director":{"artifacts":{"edit_plan.json":hashlib.sha256(path.read_bytes()).hexdigest()}},
        "ai_video":{"status":"pending"},"render":{"status":"pending"}}})
    save_shot_prompt(tmp_path,plan.scenes[0].id,1,MANUAL)
    saved = EditPlan.model_validate(read_json(path))
    assert saved.scenes[0].shots[0].ai_prompt == MANUAL and source_hash(saved) == old_hash
    assert read_json(tmp_path/"run_state.json")["steps"]["director"]["artifacts"]["edit_plan.json"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_timeout_suggests_simpler_prompt_without_paid_retry(tmp_path):
    settings = Settings(root_dir=tmp_path,gateway_api_key=SecretStr("fixture-only"))
    project = create_project(settings.output_dir,"Timeout prompt")
    gateway = Mock()
    gateway.create.return_value = ({"id":"already_paid_id"},None)
    path = create_job(project,VideoRequest(prompt=SAFE),settings,gateway=gateway)
    with pytest.raises(TimeoutError):
        resume_job(path,settings,gateway=gateway,wait_sec=0)
    job = load_job(path)
    assert job["remote_id"] == "already_paid_id"
    assert validate_ai_prompt(job["simpler_prompt_suggestion"],simpler=True)
    assert len(job["simpler_prompt_suggestion"].split()) < len(SAFE.split())
    assert "không tự gửi lại" in job["retry_notice"]
    gateway.create.assert_called_once()
    gateway.status.assert_not_called()


def test_changed_prompt_after_failure_cannot_silently_charge_again(stages,monkeypatch):
    from pipeline.run_all import run_all,RunConfig
    from pipeline.run_all_ai import prepare_ai_bundle
    settings,_,_,_ = stages
    config = RunConfig(topic="Safe prompt ledger",ai_clips=1,ai_confirmed=True)
    project = run_all(config,settings=settings,stop_after="assets")
    create = Mock(side_effect=TimeoutError("fixture paid POST timeout"))
    monkeypatch.setattr("pipeline.run_all_ai.create_job",create)
    diagnostics = Diagnostics(settings.logs_dir)
    with pytest.raises(TimeoutError):
        prepare_ai_bundle(project,config,settings,lambda *args:None,lambda:None,diagnostics)
    data = read_json(project/"edit_plan.json")
    for scene in data["scenes"]:
        for shot in scene["shots"]:
            shot["ai_prompt"] = MANUAL
    write_json(project/"edit_plan.json",data)
    with pytest.raises(GatewayVideoError,match="Prompt đã đổi"):
        prepare_ai_bundle(project,config,settings,lambda *args:None,lambda:None,diagnostics)
    create.assert_called_once()


@pytest.mark.parametrize("page",["AI Video","Edit Plan"])
def test_manual_ui_prompt_survives_rerun_and_is_saved(tmp_path,monkeypatch,page):
    settings = Settings(root_dir=tmp_path,gateway_api_key=SecretStr("fixture-ui-private"))
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    project = create_project(settings.output_dir,"Prompt editor")
    plan = EditPlan.model_validate(fixture_plan())
    plan.scenes[0].shots[0].type = "ai_video"
    plan.scenes[0].shots[0].ai_prompt = SAFE
    write_json(project/"edit_plan.json",plan.model_dump(mode="json"))
    write_json(project/"brief.json",fixture_brief().model_dump(mode="json"))
    manager = Mock()
    manager.active.return_value = None
    manager.submit.return_value = "fixture-worker"
    manager.snapshot.return_value = {"status":"completed","progress":1.,"message":"Fixture"}
    monkeypatch.setattr("app.views.ai_video.ai_video_jobs",lambda:manager)
    app = AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=25).run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception
    textarea = next(widget for widget in app.text_area if widget.label.startswith("AI prompt"))
    textarea.set_value(MANUAL).run()
    next(widget for widget in app.checkbox if widget.label == "Đơn giản hơn").check().run()
    assert next(widget for widget in app.text_area if widget.label.startswith("AI prompt")).value == MANUAL
    next(button for button in app.button if button.label == "Lưu prompt cho shot").click().run()
    assert not app.exception
    assert read_json(project/"edit_plan.json")["scenes"][0]["shots"][0]["ai_prompt"] == MANUAL
    if page == "AI Video":
        next(button for button in app.button if button.label.startswith("Tạo 1 clip")).click().run()
        assert not app.exception
        assert manager.submit.call_args.args[1].prompt == MANUAL
