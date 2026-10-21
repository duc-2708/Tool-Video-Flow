"""Style UI selection and preview stay offline; render defaults use saved plan."""
import json
from unittest.mock import Mock
import pytest
from streamlit.testing.v1 import AppTest
from config.settings import ROOT_DIR
from pipeline.style_profile import save_profile
from tests.test_style_learner import style_settings, profile
from tests.test_create_video_ui import setup_manager
from tests.test_timeline import render_project
from schemas.style import StyleRenderDefaults
from editor.captions import Captions, find_font
from editor.timeline import build_timeline


def app(page):
    at=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=30).run()
    return at.sidebar.radio[0].set_value(page).run()


def test_style_page_estimates_before_dispatch_and_never_shows_key(style_settings,monkeypatch):
    monkeypatch.setattr("config.settings.get_settings",lambda:style_settings)
    manager=Mock();manager.active.return_value=None;manager.snapshot.return_value=None
    manager.submit_analysis.return_value="style-worker"
    monkeypatch.setattr("app.views.style_samples.style_jobs",lambda:manager)
    provider=Mock();monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",provider)
    at=app("Phong cách mẫu")
    assert not at.exception
    assert next(b for b in at.button if b.label=="Phân tích video đã chọn").disabled
    assert any("token đầu vào" in value.value for value in at.markdown)
    assert not any("fixture-style-secret" in value.value for value in at.markdown)
    next(c for c in at.checkbox if c.label.startswith("Tôi đồng ý upload")).check().run()
    next(b for b in at.button if b.label=="Phân tích video đã chọn").click().run()
    assert not at.exception
    assert manager.submit_analysis.call_args.args[0]==["a.mp4"]
    provider.assert_not_called()


def test_video_form_passes_style_preset(style_settings,monkeypatch):
    monkeypatch.setattr("config.settings.get_settings",lambda:style_settings)
    preset=profile();save_profile(style_settings,preset)
    manager=setup_manager(monkeypatch)
    at=app("Tạo video")
    assert not at.exception
    at.text_input(key="create_topic").set_value("Chủ đề fixture").run()
    at.selectbox(key="create_style_preset").set_value(preset.slug).run()
    next(b for b in at.button if b.label=="Tạo video").click().run()
    assert not at.exception
    assert manager.submit.call_args.args[0].style_preset==preset.slug


@pytest.mark.parametrize("mode",["word","phrase","sentence"])
def test_caption_preset_mode_size_and_safe_box(render_project,mode):
    timeline=build_timeline(render_project/"edit_plan.resolved.json")
    timeline.plan.render_style=StyleRenderDefaults(captions={"mode":mode,"font_scale":.09,"highlight_color":"#FFAA00"})
    captions=Captions(timeline,(540,960),find_font(ROOT_DIR))
    assert captions.font.size==round(540*.09)
    for start,end,words,active in captions.entries:
        box=captions.overlay((start+end)/2).getbbox()
        assert box and box[0]>0 and box[2]<540 and box[3]<960*.82
        if mode=="word": assert len(words)==1
