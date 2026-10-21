import json
"""One-button UI and background worker tests with no paid/network calls."""
import pytest
from threading import Event
from unittest.mock import Mock
from pydantic import SecretStr
from streamlit.testing.v1 import AppTest
from config.settings import ROOT_DIR,Settings
from pipeline.projects import create_project
from pipeline.run_all import RunConfig,run_all,PipelineError
from pipeline.run_all_jobs import PipelineJobs
from tests.test_run_all import stages  # Reuse only the offline stage fixture.


def app():
    at=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=25).run()
    return at.sidebar.radio[0].set_value("Tạo video").run()


def setup_manager(monkeypatch):
    manager = Mock()
    manager.active.return_value = None
    manager.submit.return_value = "fixture-worker"
    manager.snapshot.return_value = {"status":"finished","project":None,"state":None,"message":"Fixture","error":None}
    monkeypatch.setattr("app.views.create_video.pipeline_jobs",lambda:manager)
    return manager


def test_ai_failure_choice_defaults_to_broll_and_dispatches_resume(stages,monkeypatch):
    settings,_,_,_ = stages
    monkeypatch.setattr("pipeline.run_all.prepare_ai_bundle",Mock(side_effect=RuntimeError("Job chưa có remote ID")))
    with pytest.raises(PipelineError):
        run_all(RunConfig(topic="UI chọn bỏ AI",ai_clips=1,ai_confirmed=True,ai_failure_action="stop"),settings=settings)
    project = next(settings.output_dir.iterdir())
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    manager = setup_manager(monkeypatch)
    ai_manager = Mock()
    ai_manager.active.return_value = None
    monkeypatch.setattr("app.views.create_video.ai_video_jobs",lambda:ai_manager)
    at = app()
    assert not at.exception
    assert next(item for item in at.radio if item.label == "Xử lý khi Clip AI lỗi").value.startswith("Bỏ qua")
    next(button for button in at.button if button.label == "Áp dụng lựa chọn").click().run()
    assert not at.exception
    config = manager.submit.call_args.args[0]
    assert config.resume == project and config.ai_failure_decision == "skip"


def test_first_page_and_new_run_ai_off_by_default(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path,gemini_api_key=SecretStr("fixture-private"),gemini_model="fixture")
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    project = create_project(settings.output_dir,"Project cũ")
    manager = setup_manager(monkeypatch)
    at = app()
    assert not at.exception and at.sidebar.radio[0].options[0] == "Tạo video theo danh mục"
    assert at.sidebar.radio[0].value == "Tạo video"
    assert not at.checkbox(key="create_ai").value
    next(button for button in at.button if button.label == "Tạo video").click().run()
    assert not at.exception
    config = manager.submit.call_args.args[0]
    assert config.ai_clips == 0 and config.resume is None
    assert config.topic == "Project cũ"


def test_paid_ai_requires_explicit_pre_start_confirmation(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path,gemini_api_key=SecretStr("fixture-private"),gemini_model="fixture",
                        gateway_api_key=SecretStr("fixture-gateway-private"),ai_clip_max_per_run=2)
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    create_project(settings.output_dir,"AI fixture")
    manager = setup_manager(monkeypatch)
    at = app()
    at.checkbox(key="create_ai").check().run()
    assert not at.exception
    assert any("Sẽ tạo 1 clip, model veo-3.1, thời lượng 4" in item.value for item in at.info)
    assert next(button for button in at.button if button.label == "Tạo video").disabled
    manager.submit.assert_not_called()
    next(widget for widget in at.checkbox if widget.label.startswith("Tôi xác nhận")).check().run()
    next(button for button in at.button if button.label == "Tạo video").click().run()
    assert not at.exception
    config = manager.submit.call_args.args[0]
    assert config.ai_confirmed and config.ai_clips == 1
    # A separate fresh run needs its own confirmation, while the current
    # worker keeps the approved config captured above.
    assert next(button for button in at.button if button.label == "Tạo video").disabled


def test_review_reuses_edit_plan_and_continue_button(stages,monkeypatch):
    settings,calls,failures,inputs = stages
    project = run_all(RunConfig(topic="Review UI",mode="review"),settings=settings)
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    manager = setup_manager(monkeypatch)
    at = app()
    assert not at.exception
    assert any(item.value == "Edit Plan" for item in at.title)
    assert len(at.text_area) == len(json.loads((project/"edit_plan.json").read_text(encoding="utf-8"))["scenes"])
    next(button for button in at.button if button.label == "Tiếp tục tạo video").click().run()
    assert not at.exception
    config = manager.submit.call_args.args[0]
    assert config.resume == project and config.continue_after_review is True


def test_completed_pipeline_has_video_download_and_credits(stages,monkeypatch):
    settings,calls,failures,inputs = stages
    project = run_all(RunConfig(topic="Complete UI"),settings=settings)
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    setup_manager(monkeypatch)
    at = app()
    assert not at.exception and len(at.get("video")) == 1
    labels = [item.proto.label for item in at.get("download_button")]
    assert "Tải MP4" in labels and "Tải credits.txt" in labels and "Tải báo cáo" in labels
    assert any("1 fact / 1 nguồn" in item.value for item in at.success)


def test_background_job_returns_immediately_and_cancel_is_cooperative(tmp_path,monkeypatch):
    entered,release = Event(),Event()
    settings = Settings(root_dir=tmp_path)
    observed = []
    def fake_run(config,progress,*,settings,cancel_event):
        entered.set()
        release.wait(5)
        observed.append(cancel_event.is_set())
        return tmp_path/"output/fixture"
    monkeypatch.setattr("pipeline.run_all_jobs.run_all",fake_run)
    manager = PipelineJobs()
    key = manager.submit(RunConfig(topic="Background"),settings)
    try:
        assert entered.wait(5)
        assert manager.snapshot(key)["status"] == "queued"
        assert manager.submit(RunConfig(topic="Double click"),settings) == key
        manager.cancel(key)
    finally:
        release.set()
        manager.executor.shutdown(wait=True)
    assert observed == [True] and manager.snapshot(key)["status"] == "finished"


def test_failed_job_ui_displays_actual_payload_and_redacts_details(stages,monkeypatch):
    from providers.video_gateway import VideoRequest
    from utils.cache import write_json
    settings, _, _, _ = stages
    project = run_all(RunConfig(topic="UI failed payload"),settings=settings)
    payload = VideoRequest(prompt="A sphere rests indoors, soft light, static camera, cinematic.",format="youtube",seconds=6)
    write_json(project/"ai_video/failure.json", {"request":payload.model_dump(mode="json"),
        "sent_payload":payload.payload(),"remote_id":"fixture_remote","status":"failed","error":"generation_failed",
        "gateway_failure":{"error":{"code":"generation_failed","message":"fixture-private-gateway"}}})
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    setup_manager(monkeypatch)
    at = app()
    assert not at.exception
    captions = " ".join(item.value for item in at.caption)
    assert "veo-3.1" in captions and "6 giây" in captions and "16:9" in captions
    assert any(item.value == payload.prompt for item in at.code)
    assert all("fixture-private-gateway" not in str(item.value) for item in at.json)


def test_duration_preset_and_style_reach_shared_pipeline(tmp_path,monkeypatch):
    settings=Settings(root_dir=tmp_path,gemini_api_key=SecretStr("fixture-private"),gemini_model="fixture")
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    manager=setup_manager(monkeypatch)
    at=app()
    at.text_input(key="create_topic").set_value("Chủ đề kể chuyện")
    at.selectbox(key="create_duration_preset").set_value(90)
    at.selectbox(key="create_script_style").set_value("explain").run()
    next(b for b in at.button if b.label=="Tạo video").click().run()
    assert not at.exception
    config=manager.submit.call_args.args[0]
    assert config.duration_sec==90 and config.script_style=="explain"
