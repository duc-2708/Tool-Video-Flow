"""Edge requests are mocked; decoding, silence and concatenation use bundled FFmpeg."""
import json
import shutil
from pathlib import Path
from unittest.mock import Mock
import aiohttp
import pytest
from edge_tts.exceptions import NoAudioReceived,WebSocketError
from config.settings import ROOT_DIR
from providers.tts_edge import EdgeTTSProvider,audio_duration,audio_metadata_path
from providers.tts_text import clean_tts_text,split_tts_text
from pipeline.assets import run_assets,load_assets,refresh_audio,repair_asset_timings,persist,assets_diagnostics
from pipeline.run_all import asset_files
from tests.test_assets import asset_settings,sample_mp3
from tests.test_director import fixture_plan
from utils.cache import write_json
from utils.diagnostics import Diagnostics
from tests.test_run_all import stages
from tests.test_streamlit_ui import ui_settings,open_app,button


def provider(settings,monkeypatch,sample,behavior=None):
    calls=[];sleeps=[]
    def communicate(text,voice,**kwargs):
        calls.append((text,voice))
        class Request:
            def save_sync(self,path):
                if behavior: behavior(text,voice,len(calls))
                shutil.copyfile(sample,path)
        return Request()
    monkeypatch.setattr("providers.tts_edge.edge_tts.Communicate",communicate)
    monkeypatch.setattr("providers.tts_edge.time.sleep",sleeps.append)
    return EdgeTTSProvider(settings,Diagnostics(settings.logs_dir,filename="assets_errors.log",secrets=["fixture-secret"])),calls,sleeps


def metadata(path):
    return json.loads(audio_metadata_path(path).read_text(encoding="utf-8"))


def test_clean_unicode_markup_xml_controls_and_comparisons():
    text=clean_tts_text('🔥 **Xin** #chào_ `bạn` <b>Việt Nam</b> & 2 < 3 > 1. “Đẹp” 【nhé】\x00\u200b 🏳️‍🌈')
    assert "Việt Nam" in text and "và" in text and "nhỏ hơn" in text and "lớn hơn" in text
    assert not any(char in text for char in ['🔥','*','#','_','`','<','>','&','\x00','\u200b','【','】'])
    assert "không đọc" not in clean_tts_text('<script>không đọc</script><speak>Chỉ đọc chữ</speak>')
    assert clean_tts_text("1️⃣ ✨") == ""
    assert clean_tts_text("&lt;b&gt;Xin chào&lt;/b&gt;")=="Xin chào"


def test_chunks_prefer_whole_sentences_and_enforce_hard_limit():
    first="Một cảnh quay rất rõ ràng. "*5
    second="Đây là phần diễn giải tiếp theo. "*5
    clean=clean_tts_text(first+second+"x"*650)
    chunks=split_tts_text(clean)
    assert len(chunks)>=3 and all(0<len(chunk)<=300 for chunk in chunks)
    assert chunks[0].endswith(".")
    assert "".join("".join(chunks).split())=="".join(clean.split())


def test_sanitized_text_succeeds_and_accented_text_stays_readable(asset_settings,sample_mp3,monkeypatch):
    tts,calls,_=provider(asset_settings,monkeypatch,sample_mp3)
    out=asset_settings.output_dir/"project/audio/scene_2.mp3"
    tts.synthesize("**Chào bạn** 😃 <em>tiếng Việt</em> & thế giới!",asset_settings.default_voice,out,scene_id=2,duration_sec=3)
    assert calls==[("Chào bạn tiếng Việt và thế giới!",asset_settings.default_voice)]
    assert not metadata(out)["audio_silent"] and audio_duration(out)>0


@pytest.mark.parametrize("text",["✨🔥 #`_*", "... !!! --", "<speak> </speak>\x00\u200b"])
def test_empty_or_punctuation_only_never_calls_service_and_uses_planned_silence(asset_settings,sample_mp3,monkeypatch,text):
    tts,calls,_=provider(asset_settings,monkeypatch,sample_mp3)
    out=asset_settings.output_dir/"project/audio/scene_2.mp3"
    duration=tts.synthesize(text,asset_settings.default_voice,out,scene_id=2,duration_sec=3.25)
    assert not calls and duration==pytest.approx(3.25,abs=.002)
    assert metadata(out)["audio_silent"] and "cảnh 2 không có giọng đọc" in metadata(out)["warnings"][0]


@pytest.mark.parametrize("error",[NoAudioReceived("No audio was received"),aiohttp.ClientConnectionError("network"),WebSocketError("ws"),TimeoutError("timeout")])
def test_transient_errors_twice_then_succeed_with_exponential_backoff(asset_settings,sample_mp3,monkeypatch,error):
    def fail_twice(text,voice,count):
        if count<=2: raise error
    tts,calls,sleeps=provider(asset_settings,monkeypatch,sample_mp3,fail_twice)
    out=asset_settings.output_dir/"project/audio/scene_2.mp3"
    tts.synthesize("Lời đọc hợp lệ.",asset_settings.default_voice,out,scene_id=2,duration_sec=4)
    assert len(calls)==3 and sleeps==[2,4] and not metadata(out)["audio_silent"]
    log=(asset_settings.logs_dir/"assets_errors.log").read_text(encoding="utf-8")
    assert "cảnh 2" in log and "attempt=2/5" in log and "cleaned_text=" in log and "text_length=" in log
    assert asset_settings.default_voice in log and type(error).__name__ in log


def test_only_failed_chunk_retries_and_successful_chunks_are_cached(asset_settings,sample_mp3,monkeypatch):
    text="Phần đầu là một câu chuyện cụ thể. "*6+"Phần cuối có ví dụ thực tế. "*7
    chunks=split_tts_text(text)
    failed=0
    def behavior(value,voice,count):
        nonlocal failed
        if value==chunks[1] and failed<2:
            failed+=1;raise NoAudioReceived("transient")
    tts,calls,_=provider(asset_settings,monkeypatch,sample_mp3,behavior)
    out=asset_settings.output_dir/"project/audio/scene_2.mp3"
    tts.synthesize(text,asset_settings.default_voice,out,scene_id=2,duration_sec=8)
    assert sum(value==chunks[0] for value,_ in calls)==1
    assert sum(value==chunks[1] for value,_ in calls)==3
    assert len(calls)==len(chunks)+2
    assert audio_duration(out)==pytest.approx(len(chunks)*audio_duration(sample_mp3),abs=.015)
    tts.synthesize(text,asset_settings.default_voice,out,scene_id=2,duration_sec=8)
    assert len(calls)==len(chunks)+2


def test_primary_exhausted_fallback_voice_succeeds(asset_settings,sample_mp3,monkeypatch):
    def behavior(text,voice,count):
        if voice==asset_settings.default_voice: raise NoAudioReceived("primary failed")
    tts,calls,sleeps=provider(asset_settings,monkeypatch,sample_mp3,behavior)
    out=asset_settings.output_dir/"project/audio/scene_2.mp3"
    tts.synthesize("Lời đọc hợp lệ.",asset_settings.default_voice,out,scene_id=2,duration_sec=3)
    assert len(calls)==6 and sleeps==[2,4,8,16]
    assert metadata(out)["voice_used"]==asset_settings.default_voice_fallback
    assert not metadata(out)["audio_silent"] and metadata(out)["warnings"]


def test_simplified_text_is_tried_after_fallback_voice(asset_settings,sample_mp3,monkeypatch):
    def behavior(text,voice,count):
        if voice==asset_settings.default_voice or "+" in text: raise NoAudioReceived("bad content")
    tts,calls,_=provider(asset_settings,monkeypatch,sample_mp3,behavior)
    out=asset_settings.output_dir/"project/audio/scene_2.mp3"
    tts.synthesize("Một ý + một ví dụ.",asset_settings.default_voice,out,scene_id=2,duration_sec=3)
    assert len(calls)==11 and "+" not in calls[-1][0]
    assert not metadata(out)["audio_silent"] and any("rút gọn" in w for w in metadata(out)["warnings"])


def test_exhaustion_is_bounded_then_silence_and_next_run_can_recover(asset_settings,sample_mp3,monkeypatch):
    def fail(*args): raise NoAudioReceived("fixture-secret no audio")
    tts,calls,sleeps=provider(asset_settings,monkeypatch,sample_mp3,fail)
    out=asset_settings.output_dir/"project/audio/scene_2.mp3"
    duration=tts.synthesize("Tiếng Việt vẫn rõ ràng.",asset_settings.default_voice,out,scene_id=2,duration_sec=4.4)
    assert len(calls)==15 and sleeps==[2,4,8,16]*3
    assert duration==pytest.approx(4.4,abs=.003) and metadata(out)["audio_silent"]
    assert "cảnh 2 không có giọng đọc" in metadata(out)["warnings"][0]
    log=(asset_settings.logs_dir/"assets_errors.log").read_text(encoding="utf-8")
    assert "fixture-secret" not in log and "[REDACTED]" in log and "attempt=5/5" in log
    recovered,new_calls,_=provider(asset_settings,monkeypatch,sample_mp3)
    recovered.synthesize("Tiếng Việt vẫn rõ ràng.",asset_settings.default_voice,out,scene_id=2,duration_sec=4.4)
    assert len(new_calls)==1 and not metadata(out)["audio_silent"]  # Silence was never cached as speech.


def fake_tts(sample,fail_scene=None):
    class TTS:
        def __init__(self): self.calls=[]
        def synthesize(self,text,voice,path):
            self.calls.append((text,path))
            if path.stem==f"scene_{fail_scene}": raise NoAudioReceived("mock failure")
            path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(sample,path)
            return audio_duration(path)
    return TTS()


def test_refresh_only_failed_scene_preserves_other_audio_and_all_stock(asset_settings,sample_mp3,monkeypatch):
    path=asset_settings.output_dir/"project/edit_plan.json"
    write_json(path,fixture_plan());original=path.read_bytes()
    run_assets(path,asset_settings,tts=fake_tts(sample_mp3,2),providers=[])
    _,before,manifest=load_assets(path)
    assert manifest.scenes[1].audio_silent
    other_audio={r.scene_id:(path.parent/r.audio_path).read_bytes() for r in manifest.scenes if r.scene_id!=2}
    other_rows={r.scene_id:r.model_dump() for r in manifest.scenes if r.scene_id!=2}
    stock={p.name:p.read_bytes() for p in (path.parent/"clips").iterdir()}
    search=Mock(side_effect=AssertionError("Do not fetch stock when repairing audio"))
    monkeypatch.setattr("pipeline.assets.resolve_stock",search)
    tts=fake_tts(sample_mp3)
    refresh_audio(path,asset_settings,2,tts=tts)
    _,after,result=load_assets(path)
    assert len(tts.calls)==1 and tts.calls[0][1].stem=="scene_2"
    assert not result.scenes[1].audio_silent and result.scenes[1].audio_error is None
    assert {r.scene_id:r.model_dump() for r in result.scenes if r.scene_id!=2}==other_rows
    assert {r.scene_id:(path.parent/r.audio_path).read_bytes() for r in result.scenes if r.scene_id!=2}==other_audio
    assert {p.name:p.read_bytes() for p in (path.parent/"clips").iterdir()}==stock
    assert original==path.read_bytes()
    assert "cảnh 2 không có giọng đọc" not in (path.parent/"report.md").read_text(encoding="utf-8")
    assert asset_files(path.parent,path)[0]
    search.assert_not_called()


def test_target_duration_never_mutates_audio_resolved_shots(asset_settings,sample_mp3):
    path=asset_settings.output_dir/"project/edit_plan.json"
    data=fixture_plan();data["target_duration_sec"]=60.
    write_json(path,data)
    run_assets(path,asset_settings,tts=fake_tts(sample_mp3),providers=[])
    _,resolved,manifest=load_assets(path)
    assert resolved.duration_sec==pytest.approx(8*audio_duration(sample_mp3))
    assert resolved.duration_sec!=60
    assert all(len(scene.shots)==len(row.shots) for scene,row in zip(resolved.scenes,manifest.scenes))
    assert any("giữ nguyên timing audio" in w for w in manifest.warnings)
    assert asset_files(path.parent,path)[0]
    # Reproduce old code's inflation (resolved has 3x as many shots as manifest).
    resolved.scenes[1].shots*=3
    repair_asset_timings(resolved,manifest,path.parent)
    persist(path.parent,resolved,manifest,assets_diagnostics(asset_settings))
    assert asset_files(path.parent,path)[0]


def test_tts_failure_error_message_never_claims_stock_missing(asset_settings,sample_mp3):
    path=asset_settings.output_dir/"project/edit_plan.json"
    write_json(path,fixture_plan())
    run_assets(path,asset_settings,tts=fake_tts(sample_mp3),providers=[])
    _,resolved,manifest=load_assets(path)
    manifest.scenes[1].audio_path=None
    manifest.scenes[1].audio_error="NoAudioReceived"
    manifest.scenes[1].shots=[]
    manifest.status="partial"
    persist(path.parent,resolved,manifest,assets_diagnostics(asset_settings))
    with pytest.raises(ValueError,match="TTS lỗi ở cảnh 2") as caught: asset_files(path.parent,path)
    assert "thiếu shot" not in str(caught.value)


def test_one_button_pipeline_renders_silence_and_keeps_warning_in_report(stages,sample_mp3,monkeypatch):
    from pipeline.run_all import run_all,RunConfig
    settings,calls,_,_=stages
    def assets(path,settings,**kwargs):
        calls.append("assets")
        return run_assets(path,settings,tts=fake_tts(sample_mp3,2),providers=[],**kwargs)
    monkeypatch.setattr("pipeline.run_all.run_assets",assets)
    project=run_all(RunConfig(topic="TTS dự phòng"),settings=settings)
    state=json.loads((project/"run_state.json").read_text(encoding="utf-8"))
    assert state["status"]=="done" and "render" in calls
    assert "cảnh 2 không có giọng đọc" in (project/"report.md").read_text(encoding="utf-8")
    from editor.timeline import build_timeline
    from editor.captions import Captions,find_font
    from schemas.style import StyleRenderDefaults
    timeline=build_timeline(project/"edit_plan.resolved.json")
    timeline.plan.render_style=StyleRenderDefaults(captions={"enabled":False})
    captions=Captions(timeline,(540,960),find_font(ROOT_DIR))
    scene=next(s for s in timeline.scenes if s.spec.id==2)
    assert captions.overlay(scene.start+scene.duration/2).getbbox()
    assert captions.overlay(timeline.scenes[0].start+.2) is None


def test_assets_ui_shows_silence_and_can_retry_just_selected_scene(ui_settings,sample_mp3,monkeypatch):
    from pipeline.projects import create_project
    project=create_project(ui_settings.output_dir,"TTS UI fixture")
    path=project/"edit_plan.json"
    write_json(path,fixture_plan())
    run_assets(path,ui_settings,tts=fake_tts(sample_mp3,2),providers=[])
    calls=[]
    def refresh(path,settings,scene_id):
        calls.append(scene_id)
        return refresh_audio(path,settings,scene_id,tts=fake_tts(sample_mp3))
    monkeypatch.setattr("app.views.assets.refresh_audio",refresh)
    at=open_app();at.radio[0].set_value("Assets").run()
    assert not at.exception and any("cảnh 2 không có giọng đọc" in e.value for e in at.error)
    next(s for s in at.selectbox if s.label=="Cảnh để nghe và xem b-roll").set_value(2).run()
    button(at,"Chạy lại riêng audio cảnh 2").click().run()
    assert not at.exception and calls==[2]
    assert not any("không có giọng đọc" in e.value for e in at.error)
    assert not load_assets(path)[2].scenes[1].audio_silent
