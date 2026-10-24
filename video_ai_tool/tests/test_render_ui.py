"""Render UI: safe playback/download and worker submission without shell calls."""
from pathlib import Path
from unittest.mock import Mock
import pytest
from streamlit.testing.v1 import AppTest
from config.settings import ROOT_DIR,Settings
from pipeline.projects import create_project
from utils.cache import write_json


def open_render():
    app = AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=20).run()
    app.sidebar.radio[0].set_value("Render").run()
    return app


def test_render_page_requires_assets(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path)
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    create_project(settings.output_dir,"Fixture render")
    app = open_render()
    assert not app.exception
    assert any("Hãy tạo Assets" in info.value for info in app.info)


def test_render_page_starts_shared_worker_and_shows_output(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path)
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    project = create_project(settings.output_dir,"Fixture render")
    write_json(project/"edit_plan.resolved.json",{})
    folder = project/"render"
    folder.mkdir()
    (folder/"fixture.mp4").write_bytes(b"offline fixture UI")
    report = {"filename":"fixture.mp4","mode":"preview","width":540,"height":960,"fps":30,"duration_sec":12.,"render_seconds":6.,"warnings":["Cảnh 1: fallback"]}
    write_json(folder/"preview.json",report)
    manager = Mock()
    manager.active.return_value = None
    manager.submit.return_value = "fixture-job"
    manager.snapshot.return_value = {"status":"complete","progress":1.,"message":"Render hoàn tất"}
    monkeypatch.setattr("app.views.render.render_jobs",lambda:manager)
    app = open_render()
    assert not app.exception and len(app.get("video")) == 1
    labels = [item.proto.label for item in app.get("download_button")]
    assert "Tải MP4" in labels
    button = next(item for item in app.button if item.label == "Render xem nhanh")
    button.click().run()
    assert not app.exception
    manager.submit.assert_called_once()
    assert manager.submit.call_args.args[:2] == (project/"edit_plan.resolved.json","preview")
    assert any("Render hoàn tất" in item.value for item in app.success)


def test_render_page_active_worker_keeps_buttons_disabled(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path)
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    project = create_project(settings.output_dir,"Fixture running")
    write_json(project/"edit_plan.resolved.json",{})
    manager = Mock()
    manager.active.return_value = "running-job"
    manager.snapshot.return_value = {"status":"running","progress":.42,"message":"Đang dựng hình"}
    monkeypatch.setattr("app.views.render.render_jobs",lambda:manager)
    app = open_render()
    assert not app.exception
    assert all(button.disabled for button in app.button if button.label.startswith("Render"))
    assert app.get("progress")[0].proto.value == 42


@pytest.mark.parametrize("label,forced",[("Xem trước cảnh",False),("Render lại chỉ cảnh này",True)])
def test_scene_preview_controls_use_shared_worker(tmp_path,monkeypatch,label,forced):
    settings=Settings(root_dir=tmp_path)
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    project=create_project(settings.output_dir,"Fixture scene preview")
    write_json(project/"edit_plan.resolved.json",{"scenes":[{"id":7}]})
    manager=Mock();manager.active.return_value=None;manager.snapshot.return_value=None;manager.submit.return_value="scene-job"
    monkeypatch.setattr("app.views.render.render_jobs",lambda:manager)
    app=open_render()
    next(t for t in app.toggle if t.label=="Bật Motion").set_value(True).run()
    next(b for b in app.button if b.label==label).click().run()
    assert not app.exception
    call=manager.submit.call_args
    assert call.args[0]==project/"edit_plan.resolved.json" and call.args[1]=="preview"
    assert call.args[2].motion_enabled and call.args[2].motion_scale==.5
    assert call.kwargs["scene_id"]==7
    assert call.kwargs.get("force_scene")== (7 if forced else None)
