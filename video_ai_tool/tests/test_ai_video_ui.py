"""AI video UI tests never contact the gateway."""
from unittest.mock import Mock
from pydantic import SecretStr
from streamlit.testing.v1 import AppTest
from config.settings import ROOT_DIR,Settings
from pipeline.projects import create_project


def test_ai_video_defaults_and_paid_button_dispatch(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path,gateway_api_key=SecretStr("fixture-ui-private-gateway-key"))
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    project = create_project(settings.output_dir,"Fixture AI video")
    manager = Mock()
    manager.active.return_value = None
    manager.submit.return_value = "fixture-worker"
    manager.snapshot.return_value = {"status":"completed","progress":1.,"message":"Fixture complete"}
    monkeypatch.setattr("app.views.ai_video.ai_video_jobs",lambda:manager)
    app = AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=20).run()
    app.sidebar.radio[0].set_value("AI Video").run()
    assert not app.exception
    assert next(widget for widget in app.selectbox if widget.label == "Model tạo video").value == "veo-3.1"
    assert next(widget for widget in app.selectbox if widget.label == "Thời lượng clip (giây)").value == 4
    statuses = "\n".join(item.value for item in app.sidebar.text)
    assert "GATEWAY_API_KEY: Đã có" in statuses and "fixture-ui-private-gateway-key" not in statuses
    manager.submit.assert_not_called()
    next(button for button in app.button if button.label.startswith("Tạo 1 clip")).click().run()
    assert not app.exception
    manager.submit.assert_called_once()
    args = manager.submit.call_args.args
    assert args[0] == project and args[1].model == "veo-3.1" and args[1].seconds == 4


def test_missing_gateway_key_disables_paid_button(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path)
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    create_project(settings.output_dir,"Fixture no key")
    app = AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=20).run()
    app.sidebar.radio[0].set_value("AI Video").run()
    assert not app.exception
    assert next(button for button in app.button if button.label.startswith("Tạo 1 clip")).disabled


def test_idless_job_recovery_ui_requires_confirmation_and_dispatches_existing_id(tmp_path,monkeypatch):
    from pipeline.ai_video import save_job,diagnostics_for
    from providers.video_gateway import VideoRequest
    from utils.cache import cache_key
    settings = Settings(root_dir=tmp_path,gateway_api_key=SecretStr("fixture-ui-private"))
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    project = create_project(settings.output_dir,"Khôi phục clip")
    request = VideoRequest(prompt="UI recovery fixture")
    path = project/"ai_video"/(cache_key(request.model_dump(mode="json"))+".json")
    save_job(path,{"request":request.model_dump(),"remote_id":None,"status":"ambiguous","error":"Job chưa có remote ID"},diagnostics_for(settings))
    manager = Mock()
    manager.active.return_value = None
    manager.submit.return_value = "recover-worker"
    manager.snapshot.return_value = {"status":"completed","progress":1.,"message":"Fixture"}
    monkeypatch.setattr("app.views.ai_video.ai_video_jobs",lambda:manager)
    app = AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=20).run()
    app.sidebar.radio[0].set_value("AI Video").run()
    assert not app.exception
    assert any("Job chưa có remote ID" in item.value for item in app.error)
    assert next(b for b in app.button if b.label.startswith("Đã kiểm tra dashboard")).disabled
    assert any("pipeline.ai_video resume" in item.value and str(path) in item.value for item in app.code)
    next(item for item in app.text_input if item.label == "Remote ID từ dashboard").set_value("from_dashboard").run()
    next(b for b in app.button if b.label == "Tiếp tục job có sẵn").click().run()
    assert not app.exception
    assert manager.submit.call_args.kwargs == {"job_path":path,"remote_id":"from_dashboard"}
    manager.submit.reset_mock()
    next(item for item in app.checkbox if item.label.startswith("Tôi đã kiểm tra dashboard")).check().run()
    next(b for b in app.button if b.label.startswith("Đã kiểm tra dashboard")).click().run()
    assert not app.exception
    assert manager.submit.call_args.kwargs == {"job_path":path,"recreate_confirmed":True}
    assert not next(item for item in app.checkbox if item.label.startswith("Tôi đã kiểm tra dashboard")).value
