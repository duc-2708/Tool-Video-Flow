"""Motion is offline/optional; real browser checks need an installed Chromium."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pytest
from config.settings import Settings,ROOT_DIR
from editor.captions import find_font,word_timings
from schemas.visual import Visual,VisualData
from schemas.style import CaptionStyle
from utils.word_timing import align_words,save_words,read_words
from utils.diagnostics import Diagnostics
from pipeline.render_motion import scene_payload,render_scene,browser_page,capture,html_document
from tests.test_assets import asset_settings,sample_mp3
from tests.test_timeline import render_project,hashes


def sample_scene(tmp_path,template="steps_list",duration=.3):
    visual=Visual(template=template,data=VisualData(text="Đọc sâu nguồn",value=5000.,label="Dữ liệu",items=["Hiểu câu hỏi","Kiểm tra nguồn","Rút ý chính"],
        bars=[{"label":"Trước","value":20.},{"label":"Sau","value":40.}],highlight=["nguồn"]),
        beats=[{"at_word_index":0,"action":"reveal"},{"at_sec":.15,"action":"reveal"}])
    spec=SimpleNamespace(id=1,narration="Bạn hiểu nguồn tin này thế nào?")
    shot=SimpleNamespace(start=0.,duration=duration,path=None,spec=SimpleNamespace(visual=visual))
    return SimpleNamespace(spec=spec,audio=tmp_path/"scene_1.mp3",duration=duration,start=0.,shots=[shot])


def has_chromium():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except ImportError: return False


@pytest.fixture
def chromium():
    if not has_chromium(): pytest.skip("Chromium tùy chọn chưa cài; mock fallback vẫn được kiểm tra")


def test_estimate_matches_exact_narration_tokens_and_duration(tmp_path):
    text="Một câu tiếng Việt gồm vài từ."
    path=tmp_path/"scene_1.words.json"
    words=save_words(path,text,4.)
    assert [w["text"] for w in words]==text.split()
    assert words[-1]["end"]==pytest.approx(4.)
    assert json.loads(path.read_text(encoding="utf-8"))["timing_source"]=="estimated_characters"
    assert word_timings(text,4.,path)==[(w["text"],w["start"],w["end"]) for w in words]
    assert align_words(text,4.,[{"text":"bad","start":-1,"end":float("nan")}])[1]=="estimated_characters"


def test_boundary_offsets_and_gaps_preserved(tmp_path):
    observed=[{"text":"Xin","start":.2,"end":.5},{"text":"chào","start":.8,"end":1.2}]
    words,source=align_words("Xin chào!",2.,observed)
    assert source=="word_boundary" and words[1]["start"]==.8
    assert words[-1]["text"]=="chào!"
    words,source=align_words("30 bạn",2.,[{"text":"ba mươi","start":.1,"end":.9},{"text":"bạn","start":1.,"end":1.4}])
    assert source=="boundary_projected" and len(words)==2


def test_edge_collects_boundaries_and_chunk_cache_avoids_request(asset_settings,sample_mp3,monkeypatch):
    calls=[]
    class Request:
        def __init__(self,text,voice,**options): calls.append(options)
        async def stream(self):
            yield {"type":"audio","data":sample_mp3.read_bytes()}
            yield {"type":"WordBoundary","text":"Xin","offset":2_000_000,"duration":3_000_000}
            yield {"type":"WordBoundary","text":"chào","offset":8_000_000,"duration":4_000_000}
    monkeypatch.setattr("providers.tts_edge.edge_tts.Communicate",Request)
    from providers.tts_edge import EdgeTTSProvider
    tts=EdgeTTSProvider(asset_settings,Diagnostics(asset_settings.logs_dir))
    path=asset_settings.output_dir/"audio/scene_1.mp3"
    for _ in range(2): tts.synthesize("Xin chào",asset_settings.default_voice,path)
    words=read_words(path.with_suffix(".words.json"))
    assert len(calls)==1 and calls[0]["boundary"]=="WordBoundary"
    assert words[0]["start"]==pytest.approx(.2) and words[1]["start"]==pytest.approx(.8)
    assert json.loads(path.with_suffix(".words.json").read_text(encoding="utf-8"))["timing_source"]=="word_boundary"


def test_async_stream_error_propagates_to_retry_not_a_hung_queue(asset_settings,sample_mp3,monkeypatch):
    calls=[]
    class Request:
        def __init__(self,*args,**options): calls.append(options)
        async def stream(self):
            if len(calls)<=2: raise TimeoutError("fixture timeout")
            yield {"type":"audio","data":sample_mp3.read_bytes()}
    monkeypatch.setattr("providers.tts_edge.edge_tts.Communicate",Request)
    sleep=Mock();monkeypatch.setattr("providers.tts_edge.time.sleep",sleep)
    from providers.tts_edge import EdgeTTSProvider
    path=asset_settings.output_dir/"scene_1.mp3"
    EdgeTTSProvider(asset_settings,Diagnostics(asset_settings.logs_dir)).synthesize("Xin chào",asset_settings.default_voice,path)
    assert len(calls)==3 and [c.args[0] for c in sleep.call_args_list]==[2,4]
    assert json.loads(path.with_suffix(".words.json").read_text(encoding="utf-8"))["timing_source"]=="estimated_characters"


@pytest.mark.parametrize("error",[ModuleNotFoundError("playwright"),RuntimeError("Chromium missing")])
def test_missing_engine_returns_static_fallback(tmp_path,monkeypatch,error):
    @contextmanager
    def unavailable(size): raise error;yield
    monkeypatch.setattr("pipeline.render_motion.browser_page",unavailable)
    scene=sample_scene(tmp_path)
    assert render_scene(scene,tmp_path/"cache",size=(270,480),font=find_font(ROOT_DIR),caption_style=CaptionStyle(),
        diagnostics=Diagnostics(tmp_path/"logs")) is None
    assert "Pillow" in (tmp_path/"logs/diagnostics.log").read_text(encoding="utf-8") if (tmp_path/"logs/diagnostics.log").exists() else True
    assert not list((tmp_path/"cache").glob("*.mp4"))


def test_data_is_inert_no_html_or_script_injection(tmp_path):
    scene=sample_scene(tmp_path);scene.shots[0].spec.visual.data.text='</script><img src="https://bad.invalid" onerror="window.BAD=1">'
    html=html_document(scene_payload(scene,(270,480),CaptionStyle()),find_font(ROOT_DIR))
    assert "\\u003c/script" in html and '<img src="https://bad.invalid"' not in html


@pytest.mark.parametrize("template",["hook_card","steps_list","compare_bars"])
def test_render_at_deterministic_backward_seeks_and_beats(tmp_path,chromium,template):
    scene=sample_scene(tmp_path,template,duration=3.)
    save_words(scene.audio.with_suffix(".words.json"),scene.spec.narration,3.)
    payload=scene_payload(scene,(270,480),CaptionStyle(appearance="pill"))
    with browser_page((270,480)) as page:
        capture(page,payload,find_font(ROOT_DIR))
        shots=[]
        for t in (1.2,.01,1.2):
            page.evaluate("t => renderAt(t)",t);shots.append(hashlib.sha256(page.screenshot()).hexdigest())
        assert shots[0]==shots[2] and shots[0]!=shots[1]
        assert page.evaluate("() => document.fonts.check('20px Phudu')")
        assert page.evaluate("() => document.querySelector('#captions').getBoundingClientRect().bottom")<480*.82
        assert page.evaluate("() => window.Motion.countUp(5000,1)")==5000
        assert page.evaluate("() => window.Motion.typing('abcd',.5)")=="ab"


def test_scene_cache_hit_skips_chromium_and_invalidates_changed_data(tmp_path,chromium,monkeypatch):
    scene=sample_scene(tmp_path)
    kwargs=dict(size=(270,480),font=find_font(ROOT_DIR),caption_style=CaptionStyle(),fps=10)
    first=render_scene(scene,tmp_path/"cache",**kwargs)
    assert first and not first["cache_hit"]
    browser=Mock(side_effect=AssertionError("cache must not render"));monkeypatch.setattr("pipeline.render_motion.browser_page",browser)
    second=render_scene(scene,tmp_path/"cache",**kwargs)
    assert second["cache_hit"] and first["path"]==second["path"];browser.assert_not_called()
    scene.shots[0].spec.visual.data.text="Thay đổi"
    assert render_scene(scene,tmp_path/"cache",**kwargs) is None
    browser.assert_called_once()


def test_motion_disabled_keeps_original_render_and_does_not_import_engine(render_project,monkeypatch):
    import editor.render as editor
    motion=Mock(side_effect=AssertionError("disabled"));monkeypatch.setattr("pipeline.render_motion.render_scene",motion)
    before=hashes(render_project)
    result=editor.run_render(render_project/"edit_plan.resolved.json",settings=Settings(root_dir=ROOT_DIR))
    assert result["width"]==540 and result["height"]==960 and result["fps"]==15
    assert not result.get("motion_enabled") and hashes(render_project)==before
    motion.assert_not_called()


def test_optional_motion_data_omitted_from_legacy_serialization():
    assert "beats" not in Visual().model_dump(mode="json")
    assert "old_value" not in VisualData(bars=[{"label":"A","value":2.}]).model_dump(mode="json")["bars"][0]


def test_motion_configuration_blank_values_use_defaults():
    settings=Settings(motion_enabled="",motion_fps="",motion_scale="")
    assert (settings.motion_enabled,settings.motion_fps,settings.motion_scale)==(False,30,1.)


def test_supported_and_static_templates_mix_without_screenshot_for_static(tmp_path,chromium):
    scene=sample_scene(tmp_path,duration=.4)
    from copy import deepcopy
    second=deepcopy(scene.shots[0]);second.start=.2;second.duration=.2;second.spec.visual=Visual(template="text_focus")
    scene.shots[0].duration=.2;scene.shots.append(second)
    static=Mock(return_value=np.full((480,270,3),100,dtype=np.uint8))
    result=render_scene(scene,tmp_path/"cache",size=(270,480),font=find_font(ROOT_DIR),caption_style=CaptionStyle(),fps=10,static_frame=static)
    assert result and static.call_count==2


def test_motion_enabled_renderer_composes_cached_scenes_audio_and_preserves_inputs(render_project,monkeypatch,chromium):
    import editor.render as editor
    from utils.cache import write_json
    path=render_project/"edit_plan.resolved.json"
    data=json.loads(path.read_text(encoding="utf-8"))
    data["render_style"]={}
    data["scenes"][0]["shots"][0]["visual"]={"template":"hook_card","data":{"text":"Hiểu câu chuyện"}}
    write_json(path,data);before=hashes(render_project)
    monkeypatch.setattr(editor,"prepare_graphics",lambda *args:None)  # Fixture tests transport, not grounding.
    result=editor.run_render(path,settings=Settings(root_dir=ROOT_DIR,motion_enabled=True,motion_scale=.25,motion_fps=10))
    assert (result["width"],result["height"],result["fps"])==(270,480,10)
    assert len(result["motion_scenes"])==1 and not result["motion_scenes"][0]["cache_hit"]
    from editor.runtime import VideoFileClip
    with VideoFileClip(result["path"]) as reader: assert reader.audio is not None
    assert hashes(render_project)==before
    second=editor.run_render(path,settings=Settings(root_dir=ROOT_DIR,motion_enabled=True,motion_scale=.25,motion_fps=10))
    assert second["motion_scenes"][0]["cache_hit"]


def test_enabled_missing_browser_renders_static_video_instead_of_crash(render_project,monkeypatch):
    import editor.render as editor
    from utils.cache import write_json
    path=render_project/"edit_plan.resolved.json";data=json.loads(path.read_text(encoding="utf-8"))
    data["render_style"]={}
    data["scenes"][0]["shots"][0]["visual"]={"template":"hook_card","data":{"text":"Mẫu kiểm thử"}}
    write_json(path,data);before=hashes(render_project)
    monkeypatch.setattr(editor,"prepare_graphics",lambda *args:None)
    @contextmanager
    def unavailable(size): raise ModuleNotFoundError("playwright");yield
    monkeypatch.setattr("pipeline.render_motion.browser_page",unavailable)
    result=editor.run_render(path,settings=Settings(root_dir=ROOT_DIR,motion_enabled=True,motion_scale=.25,motion_fps=10))
    assert not result["motion_scenes"] and any("Motion không sẵn sàng" in w for w in result["warnings"])
    assert Path(result["path"]).is_file() and hashes(render_project)==before
