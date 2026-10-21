# file: tests/test_timeline.py
"""Offline Editor integration: real bundled FFmpeg, no APIs or project configuration."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event
from types import SimpleNamespace
import wave

from imageio_ffmpeg import get_ffmpeg_exe
import numpy as np
from PIL import Image
import pytest

from config.settings import ROOT_DIR,Settings
from editor.timeline import build_timeline,confined
from schemas.assets import ResolvedEditPlan
from editor.captions import Captions,find_font,word_timings,wrap_lines
from editor.effects import cover,cover_box,transition
from editor.audio_mix import build_audio
from editor.render import Frames,run_render
from editor.jobs import RenderJobs
from tests.test_director import fixture_plan
from utils.cache import write_json,cache_key
from utils.diagnostics import Diagnostics
from utils.media import video_info


def ffmpeg(*args):
    subprocess.run([get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y",*map(str,args)],capture_output=True,check=True,timeout=30)


@pytest.fixture
def render_project(tmp_path):
    project = tmp_path/"project"
    (project/"audio").mkdir(parents=True)
    (project/"clips").mkdir()
    data = fixture_plan()
    data["scenes"] = [data["scenes"][0],data["scenes"][-1]]
    for scene in data["scenes"]:
        scene["shots"] = [scene["shots"][0]]
        scene["shots"][0].update(duration_sec=2.,text_overlay="Dựng video dễ hiểu")
        scene["transition_out"] = "fade"
        ffmpeg("-f","lavfi","-i","sine=frequency=330:duration=1.62","-c:a","libmp3lame",project/f"audio/scene_{scene['id']}.mp3")
    data.update(source_plan_hash="fixture",timing_basis="audio",warnings=[])
    write_json(project/"edit_plan.resolved.json",data)
    (project/"credits.txt").write_text("Nguồn fixture; không có stock bên ngoài.\n",encoding="utf-8")
    return project


def hashes(project):
    return {str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in project.rglob("*") if p.is_file() and not p.is_relative_to(project/"render")}


def test_timeline_matches_real_audio_and_keeps_inputs(render_project):
    before = hashes(render_project)
    t = build_timeline(render_project/"edit_plan.resolved.json")
    assert t.duration == pytest.approx(3.24,abs=.003)
    for scene in t.scenes:
        assert sum(s.duration for s in scene.shots) == pytest.approx(scene.duration,abs=1e-10)
        assert scene.shots[0].start == scene.start
    assert t.scenes[1].start == t.scenes[0].duration
    assert all(s.fallback for scene in t.scenes for s in scene.shots)
    assert hashes(render_project) == before


def test_missing_audio_fails_with_scene_and_instruction(render_project):
    (render_project/"audio/scene_8.mp3").unlink()
    with pytest.raises(ValueError,match="Thiếu audio cảnh 8.*Assets"):
        build_timeline(render_project/"edit_plan.resolved.json")


def test_manifest_partial_audio_not_replaced_by_stale_file(render_project):
    data = json.loads((render_project/"edit_plan.resolved.json").read_text(encoding="utf-8"))
    write_json(render_project/"assets.json",{"source_plan_hash":"fixture","resolved_plan_hash":cache_key(ResolvedEditPlan.model_validate(data).model_dump(mode="json")),"status":"partial","warnings":[],"scenes":[{"scene_id":1,"audio_path":None,"shots":[]}]})
    with pytest.raises(ValueError,match="Thiếu audio cảnh 1"):
        build_timeline(render_project/"edit_plan.resolved.json")


@pytest.mark.parametrize("source,target",[((1920,1080),(540,960)),((1080,1920),(960,540)),((500,500),(540,960))])
def test_cover_preserves_aspect_no_borders(source,target):
    box = cover_box(source,target)
    assert (box[2]-box[0])/(box[3]-box[1]) == pytest.approx(target[0]/target[1])
    for effect in ["none","zoom_in","zoom_out","pan_left","pan_right"]:
        frame = cover(np.full((source[1],source[0],3),137,np.uint8),target,effect,.6)
        assert frame.shape == (target[1],target[0],3)
        assert np.all(frame == 137)


@pytest.mark.parametrize("kind",["fade","zoom","whip"])
def test_transitions_endpoints_and_dimensions(kind):
    a,b = np.full((40,30,3),30,np.uint8),np.full((40,30,3),200,np.uint8)
    assert np.array_equal(transition(a,b,0,kind),a)
    assert np.array_equal(transition(a,b,1,kind),b)
    assert transition(a,b,.5,kind).shape == a.shape


@pytest.mark.parametrize("size",[(540,960),(960,540),(1080,1920),(1920,1080)])
def test_vietnamese_captions_stay_in_safe_box(render_project,size):
    timeline = build_timeline(render_project/"edit_plan.resolved.json")
    captions = Captions(timeline,size,find_font(ROOT_DIR))
    for start,end,words,active in captions.entries:
        layer = captions.overlay((start+end)/2)
        box = layer.getbbox()
        assert box and box[0] >= size[0]*.09 and box[2] <= size[0]*.90
        assert box[3] < size[1]*.82
        assert 2 <= len(words) <= 4
    font = captions.font
    assert all(font.getlength(line) <= size[0]*.76 for line in wrap_lines("Đ"*200,font,size[0]*.76))


def test_word_sidecar_and_invalid_sidecar_fallback(tmp_path):
    path = tmp_path/"words.json"
    path.write_text(json.dumps({"words":[{"text":"Xin","start":.1,"end":.4},{"text":"chào","start":.5,"end":1.2}]}),encoding="utf-8")
    assert word_timings("Xin chào",2,path)[0] == ("Xin",.1,.4)
    path.write_text("{bad",encoding="utf-8")
    result = word_timings("Xin chào",2,path)
    assert result[0][1] == 0 and result[-1][2] == pytest.approx(2)
    assert result[0][2] == pytest.approx(2*3/7)


@pytest.mark.parametrize("with_music",[False,True])
def test_audio_no_clipping_optional_music_and_sfx(render_project,tmp_path,with_music):
    t = build_timeline(render_project/"edit_plan.resolved.json")
    assets = tmp_path/"assets"
    if with_music:
        (assets/"music").mkdir(parents=True)
        (assets/"sfx").mkdir()
        ffmpeg("-f","lavfi","-i","sine=frequency=100:duration=0.6","-filter:a","volume=6",assets/"music/fixture.wav")
        ffmpeg("-f","lavfi","-i","sine=frequency=800:duration=0.1",assets/"sfx/pop.wav")
    resources = []
    audio,music = build_audio(t,assets,resources)
    try:
        samples = audio.get_frame(np.arange(0,t.duration,1/44100))
        assert samples.shape[1] == 2 and np.max(np.abs(samples)) <= .981
        assert np.max(np.abs(samples)) > .5
        assert bool(music) == with_music
        assert audio.duration == pytest.approx(t.duration)
        assert np.max(np.abs(samples[0])) == 0
    finally:
        audio.close()


def test_short_video_loops_and_broken_clip_falls_back(render_project,tmp_path):
    ffmpeg("-f","lavfi","-i","color=c=red:s=96x160:d=0.4:r=30","-c:v","libx264",render_project/"clips/scene_1_shot_1_short.mp4")
    t = build_timeline(render_project/"edit_plan.resolved.json")
    diagnostics = Diagnostics(tmp_path/"logs")
    frames = Frames(t,(90,160),find_font(ROOT_DIR),diagnostics)
    try:
        assert frames.at(1.2).shape == (160,90,3)
        assert frames.at(1.2)[80,45,0] > 200
    finally:
        frames.close()
    (render_project/"clips/scene_1_shot_1_short.mp4").write_bytes(b"broken fixture")
    frames = Frames(t,(90,160),find_font(ROOT_DIR),diagnostics)
    try:
        assert frames.at(.5).mean() > 10
        assert any("clip hỏng" in warning for warning in t.warnings)
        assert "Traceback" in diagnostics.path.read_text(encoding="utf-8")
    finally:
        frames.close()


def test_real_preview_render_codec_audio_and_immutable_inputs(render_project,tmp_path):
    before = hashes(render_project)
    updates = []
    result = run_render(render_project/"edit_plan.resolved.json",settings=Settings(root_dir=ROOT_DIR),
                        diagnostics=Diagnostics(tmp_path/"logs"),progress=lambda value,message: updates.append(value))
    output = Path(result["path"])
    width,height,duration = video_info(output)
    assert (width,height) == (540,960) and abs(duration-result["duration_sec"]) < 1/30+.03
    assert output.stat().st_size > 10000 and updates[-1] == 1.
    assert hashes(render_project) == before
    credits = (render_project/"render/credits.txt").read_text(encoding="utf-8")
    assert credits.startswith((render_project/"credits.txt").read_text(encoding="utf-8"))
    assert "Không sử dụng" in credits
    probe = subprocess.run([get_ffmpeg_exe(),"-hide_banner","-i",str(output)],capture_output=True,timeout=20).stderr.decode(errors="replace")
    assert "h264" in probe and "yuv420p" in probe and "aac" in probe
    assert output.read_bytes().find(b"moov") < output.read_bytes().find(b"mdat")


def test_import_moviepy_does_not_export_dotenv(tmp_path):
    (tmp_path/".env").write_text("EDITOR_IMPORT_MARKER=fixture\n",encoding="utf-8")
    env = {**os.environ,"PYTHONPATH":str(ROOT_DIR)}
    env.pop("PYTHON_DOTENV_DISABLED",None)
    env.pop("EDITOR_IMPORT_MARKER",None)
    env["FFMPEG_BINARY"] = "fixture-missing-system-ffmpeg.exe"
    process = subprocess.run([sys.executable,"-c","import os; import editor.render; assert 'EDITOR_IMPORT_MARKER' not in os.environ; assert 'PYTHON_DOTENV_DISABLED' not in os.environ"],cwd=tmp_path,env=env,capture_output=True,timeout=30)
    assert process.returncode == 0,process.stderr.decode(errors="replace")


def test_music_ducks_during_narration(tmp_path):
    rate = 44100
    times = np.arange(3*rate)/rate
    voice = .15*np.sin(2*np.pi*400*times)*(times >= 1.)
    music_samples = .3*np.sin(2*np.pi*90*times)
    assets = tmp_path/"assets"
    (assets/"music").mkdir(parents=True)
    def wav(path,samples):
        with wave.open(str(path),"wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(rate)
            stream.writeframes((samples*32767).astype("<i2").tobytes())
    audio_path = tmp_path/"voice.wav"
    wav(audio_path,voice)
    wav(assets/"music/bg.wav",music_samples)
    timeline = SimpleNamespace(duration=3.,scenes=[SimpleNamespace(audio=audio_path,start=0.,duration=3.,spec=SimpleNamespace(sfx="none"))],plan=SimpleNamespace(music=SimpleNamespace(volume=.9)))
    with_music,_ = build_audio(timeline,assets,[])
    timeline.plan.music.volume = 0.
    without,_ = build_audio(timeline,assets,[])
    try:
        def music_rms(start,end):
            t = np.arange(start,end,1/rate)
            residual = with_music.get_frame(t)-without.get_frame(t)
            return np.sqrt(np.mean(residual**2))
        assert music_rms(1.7,2.1) < music_rms(.75,.95)*.4
    finally:
        with_music.close()
        without.close()


def test_worker_runs_in_background_and_reports_original_error(render_project,tmp_path,monkeypatch):
    entered,release = Event(),Event()
    def fake_render(*args,**kwargs):
        kwargs["progress"](.4,"Fixture chạy nền")
        entered.set()
        release.wait(5)
        raise ValueError("Fixture lỗi gốc")
    monkeypatch.setattr("editor.render.run_render",fake_render)
    manager = RenderJobs()
    job_id = manager.submit(render_project/"edit_plan.resolved.json","preview",Settings(root_dir=tmp_path))
    try:
        assert entered.wait(5)
        assert manager.snapshot(job_id)["progress"] == .4
        assert manager.active(render_project) == job_id
        assert manager.submit(render_project/"edit_plan.resolved.json","final",Settings(root_dir=tmp_path)) == job_id
    finally:
        release.set()
        manager.executor.shutdown(wait=True)
    result = manager.snapshot(job_id)
    assert result["status"] == "failed" and result["error"] == "Fixture lỗi gốc"
    assert "ValueError" in result["traceback"]


def test_reject_path_escape(tmp_path):
    with pytest.raises(ValueError,match="vượt khỏi"):
        confined(tmp_path,"../outside.mp4")
