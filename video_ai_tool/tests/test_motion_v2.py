"""Motion v2 is local: timing, HTML/QA, original assets and bounded workers."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import hashlib
import json
import numpy as np
import pytest
from config.settings import Settings,ROOT_DIR
from editor.captions import find_font
from editor.motion.theme import contrast,load_motion_theme,mascot_uris
from editor.motion.sfx import ensure_sfx,synthesize
from agents.motion_beats import shot_beats,max_gap,prepare_motion_beats
from pipeline.render_motion import scene_payload,browser_page,capture,SUPPORTED,render_scene
from schemas.style import CaptionStyle,StyleRenderDefaults
from schemas.edit_plan import EditPlan
from schemas.visual import Visual,VisualData
from tests.test_motion import sample_scene,chromium
from tests.test_director import fixture_plan
from tests.test_timeline import render_project,hashes
from utils.word_timing import estimate_words,save_words
from utils.diagnostics import Diagnostics


@pytest.mark.parametrize("name",sorted(SUPPORTED))
def test_all_templates_deterministic_and_correct_size(tmp_path,chromium,name):
    scene=sample_scene(tmp_path,name,3.)
    data=scene.shots[0].spec.visual.data
    data.value=75;data.source="Example News";data.source_url="https://example.com/article";data.date="2026-10-23"
    payload=scene_payload(scene,(270,480),CaptionStyle())
    with browser_page((270,480)) as page:
        capture(page,payload,find_font(ROOT_DIR));images=[]
        for t in (1.2,.1,1.2):
            page.evaluate("t=>renderAt(t)",t);images.append(hashlib.sha256(page.screenshot()).hexdigest())
        assert images[0]==images[2] and images[0]!=images[1]
        assert page.evaluate("()=>checkMotionQuality().graphic.width")<=270*.9
        assert page.evaluate("()=>document.querySelector('#captions').getBoundingClientRect().bottom")<=480*.821
        if name=="source_card":
            text=page.locator(".content").inner_text()
            assert "Nguồn:" in text and "Example News" in text and "Đọc sâu nguồn" not in text


@pytest.mark.parametrize("name",["ring_percent","stat_card","line_growth","strike_replace","quote_card","timeline","versus","steps_list"])
def test_missing_data_falls_to_text_focus(tmp_path,name):
    scene=sample_scene(tmp_path,name)
    scene.shots[0].spec.visual.data=VisualData(text="Một ý chính mới")
    data=scene_payload(scene,(270,480),CaptionStyle())
    assert data["shots"][0]["template"]=="text_focus" and data["repair_notes"]


def test_beats_match_words_and_refresh_without_changing_claims():
    shot=EditPlan.model_validate(fixture_plan()).scenes[0].shots[0]
    shot.card_text="Kỹ năng làm việc";shot.visual=Visual(template="stat_card",data=VisualData(text="Kỹ năng làm việc",value=75))
    text="Bạn cần kỹ năng làm việc thay vì 75 bước cũ."
    words=estimate_words(text,12.)
    beats,notes=shot_beats(shot,words,0,12,purpose="hook")
    for beat in beats:
        if beat.get("at_word_index") is not None and beat["action"]!="count_end":
            assert abs(beat["at_sec"]-words[beat["at_word_index"]]["start"])<=.2
    assert max_gap(beats,12.)<=3.5
    assert any(b["at_sec"]>=.5 for b in beats)
    assert any(b["action"]=="strike_replace" for b in beats)
    assert any(b["action"]=="mascot_surprised" for b in beats)
    assert shot.visual.data.value==75


def test_unmatched_keywords_even_fallback_and_idempotent(tmp_path):
    scene=sample_scene(tmp_path,"steps_list",12.)
    scene.shots[0].spec.card_text="Công việc trong tương lai"
    # A real Shot object allows checking beats persistence, unlike the scene helper.
    shot=EditPlan.model_validate(fixture_plan()).scenes[0].shots[0]
    shot.card_text="Không khớp từ nào";shot.visual=Visual(template="text_focus",data=VisualData(text=shot.card_text))
    scene.shots[0].spec=shot;scene.shots[0].shot_id=1
    plan=NS(style_profile=None,review_notes=[])
    timeline=NS(plan=plan,scenes=[scene])
    scene.spec.role="hook"
    prepare_motion_beats(timeline);before=shot.visual.model_dump(mode="json")
    prepare_motion_beats(timeline)
    assert before==shot.visual.model_dump(mode="json") and plan.review_notes
    assert max_gap([b.model_dump(mode="json") for b in shot.visual.beats],12)<=3.5


def test_quality_detects_deliberately_broken_geometry_and_empty_card(tmp_path,chromium):
    scene=sample_scene(tmp_path,"text_focus",3)
    with browser_page((270,480)) as page:
        capture(page,scene_payload(scene,(270,480),CaptionStyle()),find_font(ROOT_DIR))
        page.evaluate("()=>{renderAt(1);const c=document.querySelector('.content');c.style.width='2000px';c.style.height='1500px';c.style.left='-300px';}")
        issues=page.evaluate("()=>checkMotionQuality().issues")
        assert "text_safe_area" in issues and "card_empty_over_40_percent" in issues
        page.evaluate("()=>{document.querySelector('.content').innerHTML='<div class=title style=\"width:100px;white-space:nowrap\">'+('Một chuỗi dài cần bắt lỗi tràn '.repeat(20))+'</div>';}")
        assert "text_overflow" in page.evaluate("()=>checkMotionQuality().issues")
        page.evaluate("()=>renderAt(1)")
        # Rendering resets geometry before the one layout-fit pass.
        page.evaluate("()=>{document.querySelector('.content').style.width='84%';document.querySelector('.content').style.left='8%';renderAt(1);}")
        assert "caption_overlap" not in page.evaluate("()=>checkMotionQuality().issues")


def test_original_assets_and_theme_contrast(tmp_path):
    assert set(mascot_uris(ROOT_DIR))=={"idle","point","surprised","thinking"}
    for path in (ROOT_DIR/"assets/mascot").glob("*.svg"):
        text=path.read_text(encoding="utf-8")
        assert "<image" not in text and "href=" not in text and "<script" not in text
    ensure_sfx(tmp_path/"sfx");before={p.name:p.read_bytes() for p in (tmp_path/"sfx").glob("*.wav")}
    ensure_sfx(tmp_path/"sfx")
    assert all(p.read_bytes()==before[p.name] for p in (tmp_path/"sfx").glob("*.wav"))
    for kind in ("pop","whoosh","click","chime"):
        assert np.array_equal(synthesize(kind),synthesize(kind)) and np.max(np.abs(synthesize(kind)))<=.121
    theme=load_motion_theme(ROOT_DIR,NS(style_profile=NS(category_id="cong-nghe")))
    assert theme["name"]=="cong-nghe" and contrast(theme["foreground"],theme["card"])>=4.5
    (tmp_path/"assets/mascot").mkdir(parents=True)
    (tmp_path/"assets/mascot/idle.svg").write_text('<svg><script>bad()</script></svg>',encoding="utf-8")
    assert not mascot_uris(tmp_path)


def test_parallel_workers_same_cache_and_input_hashes(render_project,chromium,monkeypatch):
    from editor.render import run_render
    from utils.atomic_io import write_json_atomic
    p=render_project/"edit_plan.resolved.json";data=json.loads(p.read_text(encoding="utf-8"))
    data["render_style"]={}
    for s in data["scenes"]:
        for shot in s["shots"]: shot["visual"]={"template":"text_focus","data":{"text":"Một ý chính mới"}}
    write_json_atomic(p,data)
    monkeypatch.setattr("editor.render.prepare_graphics",lambda *a:None)
    before=hashes(render_project)
    first=run_render(p,settings=Settings(root_dir=ROOT_DIR,motion_enabled=True,motion_workers=2,motion_scale=.25,motion_fps=5,mascot_enabled=False))
    import subprocess
    from imageio_ffmpeg import get_ffmpeg_exe
    probe=subprocess.run([get_ffmpeg_exe(),"-i",first["path"]],capture_output=True,text=True)
    assert "yuv420p(tv, bt709" in probe.stderr and "yuvj420p" not in probe.stderr
    second=run_render(p,settings=Settings(root_dir=ROOT_DIR,motion_enabled=True,motion_workers=1,motion_scale=.25,motion_fps=5,mascot_enabled=False))
    assert first["fast_motion_mux"] and all(r["cache_hit"] for r in second["motion_scenes"])
    assert [r["sha256"] for r in first["motion_scenes"]]==[r["sha256"] for r in second["motion_scenes"]]
    assert hashes(render_project)==before and Path(second["contact_sheet"]).is_file()
    # Forcing one scene never forces the other scene's cache.
    third=run_render(p,settings=Settings(root_dir=ROOT_DIR,motion_enabled=True,motion_workers=2,motion_scale=.25,motion_fps=5,mascot_enabled=False),force_scene=data["scenes"][0]["id"])
    assert not third["motion_scenes"][0]["cache_hit"] and third["motion_scenes"][1]["cache_hit"]
    full_sheet=Path(third["contact_sheet"]);before_sheet=full_sheet.read_bytes()
    single=run_render(p,settings=Settings(root_dir=ROOT_DIR,motion_enabled=True,motion_workers=2,motion_scale=.25,motion_fps=5,mascot_enabled=False),scene_id=data["scenes"][0]["id"])
    assert "_scene_" in single["filename"] and "_scene_" in Path(single["contact_sheet"]).name
    assert full_sheet.read_bytes()==before_sheet and hashes(render_project)==before


def test_motion_optional_configuration_defaults():
    settings=Settings(motion_workers="",motion_theme="",mascot_enabled="")
    assert settings.motion_workers==2 and settings.motion_theme=="auto" and settings.mascot_enabled


def test_benchmark_resamples_before_trimming_samples(tmp_path):
    import subprocess,wave
    from imageio_ffmpeg import get_ffmpeg_exe
    from pipeline.motion_benchmark import benchmark_audio
    original=tmp_path/"source_24k.wav";target=tmp_path/"benchmark_44k.wav"
    subprocess.run([get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","sine=frequency=440:duration=2.4","-ar","24000",str(original)],check=True,capture_output=True)
    speed=benchmark_audio(original,target,2.4,round(1.8*44100))
    with wave.open(str(target)) as audio:
        assert audio.getframerate()==44100 and audio.getnframes()==round(1.8*44100)
    assert speed==pytest.approx(2.4/1.8)


def test_missing_source_is_added_before_existing_grounding_policy(tmp_path):
    from editor.motion.source import ensure_source_slot
    from tests.test_visual_templates import fixture
    from utils.atomic_io import write_json_atomic
    from agents.visual_planner import visual_issues
    plan,brief=fixture()
    for scene in plan.scenes:
        for shot in scene.shots: shot.visual=Visual(template="text_focus",data=VisualData(text="Ý chính cần nhớ"))
    write_json_atomic(tmp_path/"brief.json",brief.model_dump(mode="json"))
    timeline=NS(plan=plan,project=tmp_path)
    ensure_source_slot(timeline)
    assert sum(q.visual.template=="source_card" for s in plan.scenes for q in s.shots)==1
    assert plan.scenes[-1].shots[-1].visual.template=="source_card"
    assert not [m for _,m in visual_issues(plan,brief) if "Shot "+str(len(plan.scenes[-1].shots))+":" in m]
    original=plan.model_dump(mode="json");ensure_source_slot(timeline)
    assert plan.model_dump(mode="json")==original


def test_review_keeps_group_two_beat_notes(tmp_path):
    from PIL import Image
    from editor.motion.finish import save_review
    (tmp_path/"render").mkdir()
    image=tmp_path/"cached.png";Image.new("RGB",(270,480),"#102030").save(image)
    note="motion_beats nhóm 2: không khớp từ khóa; chia nhịp theo shot."
    scene=NS(spec=NS(id=7),start=0.,duration=1.5,shots=[NS(spec=NS(visual=Visual(template="text_focus",beats=[{"at_sec":.6,"action":"refresh"}])) )])
    timeline=NS(project=tmp_path,scenes=[scene],plan=NS(review_notes=[note]),warnings=[])
    report=save_review(timeline,[{"scene_id":7,"review_frame":str(image)}],tmp_path/"not_needed.mp4")
    assert note in report["review_notes"]
    assert note in json.loads((tmp_path/"render/motion_review.json").read_text(encoding="utf-8"))["review_notes"]


@pytest.mark.parametrize("name",["text_focus","hook_card","quote_card"])
def test_card_visibility_waits_for_word_and_finishes_within_point_two(tmp_path,chromium,name):
    scene=sample_scene(tmp_path,name,3.)
    scene.shots[0].spec.visual.data=VisualData(text="Kỹ năng làm việc mới",source="Demo",source_url="https://example.invalid/demo")
    scene.shots[0].spec.visual.beats=[{"at_sec":1.,"at_word_index":2,"action":"reveal"}]
    from schemas.visual import VisualBeat
    scene.shots[0].spec.visual.beats=[VisualBeat.model_validate(b) for b in scene.shots[0].spec.visual.beats]
    payload=scene_payload(scene,(270,480),CaptionStyle())
    with browser_page((270,480)) as page:
        capture(page,payload,find_font(ROOT_DIR))
        page.evaluate("()=>renderAt(.95)")
        assert page.evaluate("()=>getComputedStyle(document.querySelector('.title,.quote')).opacity")=="0"
        page.evaluate("()=>renderAt(1.19)")
        assert page.evaluate("()=>getComputedStyle(document.querySelector('.title,.quote')).opacity")=="1"


def test_numeric_count_and_list_rows_use_their_own_word_cues(tmp_path,chromium):
    scene=sample_scene(tmp_path,"stat_card",3.)
    scene.shots[0].spec.visual.data=VisualData(text="Một giá trị mới",value=75)
    from schemas.visual import VisualBeat
    scene.shots[0].spec.visual.beats=[VisualBeat(at_sec=.5,action="reveal"),VisualBeat(at_sec=1.,action="count_up"),VisualBeat(at_sec=1.4,action="count_end")]
    with browser_page((270,480)) as page:
        capture(page,scene_payload(scene,(270,480),CaptionStyle()),find_font(ROOT_DIR))
        page.evaluate("()=>renderAt(.9)");assert page.locator(".number").inner_text()=="0"
        page.evaluate("()=>renderAt(1.41)");assert page.locator(".number").inner_text()=="75"
        scene.shots[0].spec.visual=Visual(template="timeline",data=VisualData(text="Hai mốc quan trọng",items=["Mốc đầu tiên","Mốc thứ hai"]),beats=[VisualBeat(at_sec=.1,action="reveal"),VisualBeat(at_sec=.5,action="reveal_item_0"),VisualBeat(at_sec=1.5,action="reveal_item_1")])
        capture(page,scene_payload(scene,(270,480),CaptionStyle()),find_font(ROOT_DIR))
        page.evaluate("()=>renderAt(1.)")
        assert page.evaluate("()=>[...document.querySelectorAll('.timeline-item')].map(el=>getComputedStyle(el).opacity)")==["1","0"]
        page.evaluate("()=>renderAt(1.69)")
        assert page.evaluate("()=>getComputedStyle(document.querySelectorAll('.timeline-item')[1]).opacity")=="1"


def test_count_cue_matches_vietnamese_spoken_number():
    shot=EditPlan.model_validate(fixture_plan()).scenes[0].shots[0]
    shot.visual=Visual(template="stat_card",data=VisualData(text="Bảy mươi lăm phần trăm",value=75,unit="%"))
    shot.card_text="Bảy mươi lăm phần trăm"
    words=estimate_words("Con số bảy mươi lăm phần trăm này.",4.)
    beats,_=shot_beats(shot,words,0,4.)
    cue=next(b for b in beats if b["action"]=="count_up")
    assert cue["at_word_index"]==2 and cue["at_sec"]==words[2]["start"]


def test_stale_beat_cannot_override_a_matched_word_cue():
    shot=EditPlan.model_validate(fixture_plan()).scenes[0].shots[0]
    shot.visual=Visual(template="stat_card",data=VisualData(text="Bảy mươi lăm phần trăm",value=75),beats=[{"at_sec":0,"action":"count_up"},{"at_sec":0,"action":"reveal"}])
    shot.card_text="Bảy mươi lăm phần trăm"
    words=estimate_words("Con số bảy mươi lăm phần trăm này.",4.)
    beats,notes=shot_beats(shot,words,0,4.)
    assert len([b for b in beats if b["action"]=="count_up"])==1
    assert next(b for b in beats if b["action"]=="count_up")["at_sec"]==words[2]["start"]
    assert any("căn lại beat" in n for n in notes)


def test_quality_defers_invisible_text_scheduled_for_later(tmp_path,chromium):
    scene=sample_scene(tmp_path,"text_focus",3.)
    scene.shots[0].spec.visual=Visual(template="text_focus",data=VisualData(text="Kỹ năng làm việc mới"),beats=[{"at_sec":2.,"action":"reveal"}])
    with browser_page((270,480)) as page:
        capture(page,scene_payload(scene,(270,480),CaptionStyle()),find_font(ROOT_DIR))
        page.evaluate("()=>renderAt(1.)");q=page.evaluate("()=>checkMotionQuality()")
        assert q["deferred_until_cue"] and "text_overflow" not in q["issues"]
        page.evaluate("()=>renderAt(2.19)");q=page.evaluate("()=>checkMotionQuality()")
        assert not q["deferred_until_cue"] and "text_overflow" not in q["issues"]


def test_body_scene_preview_keeps_original_mascot_and_progress_context():
    from pipeline.motion_batch import scene_options
    specs=[NS(id=i+1,role=role,style_purpose=None,transition_out="fade") for i,role in enumerate(("hook","body","cta"))]
    plan=NS(scenes=specs,render_style=StyleRenderDefaults(progress_tracker=True))
    scenes=[NS(spec=s) for s in specs]
    full=NS(plan=plan,scenes=scenes);partial=NS(plan=plan,scenes=[scenes[1]])
    kwargs=dict(theme={},mascots={"idle":"original"})
    assert scene_options(full,scenes[1],**kwargs)==scene_options(partial,scenes[1],**kwargs)
    assert not scene_options(partial,scenes[1],**kwargs)["mascot_enabled"]
    assert scene_options(partial,scenes[1],**kwargs)["progress_index"]==1
    assert scene_options(full,scenes[-1],**kwargs)["mascot_enabled"]
