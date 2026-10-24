"""Regression: actual job-guarantee project, editorial repairs never relax facts."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pytest
from config.settings import ROOT_DIR,Settings
from schemas.edit_plan import EditPlan
from schemas.assets import ResolvedEditPlan
from schemas.research_brief import ResearchBrief
from agents.presentation import (card_phrase,valid_card,normalize_cards,source_card_once,quality_findings,
    humanize_locally,repair_generic_hook,vietnamese_terms)
from agents.validation_rules import Context,RULES,RuleViolation,run_rules
from tests.test_visual_templates import fixture
from editor.templates.core import Card
from editor.templates.theme import load_theme
from editor.layout import card_box,caption_box
from utils.diagnostics import Diagnostics

PROJECT=ROOT_DIR/"output/auto-cong-nghe-d37c14e9"
FIX=Path(__file__).parent/"fixtures/job_guarantee"


def actual():
    root=PROJECT if (PROJECT/"edit_plan.json").exists() else FIX
    return (EditPlan.model_validate_json((root/"edit_plan.json").read_text(encoding="utf-8")),
        ResearchBrief.model_validate_json((root/"brief.json").read_text(encoding="utf-8")))


@pytest.mark.parametrize("text",["AI có thể đổi tác vụ trước khi nghề biến mất; công việc tạm thời có thể cho",
    "Có thể hiểu là, đó là rủi ro, không phải kết cục có thể", "Công việc của", "Kỹ năng và", "Hỗ trợ cho",
    "Bảo đảm việc làm có thể", "Chính sách kéo dài quá nhiều từ để làm thẻ và không có ý chính"])
def test_card_selects_complete_phrase_not_truncated_narration(text):
    result=card_phrase(text,text+" Người lao động học kỹ năng mới và chuyển hướng.")
    assert valid_card(result) and 3<=len(result.split())<=6
    assert result.casefold() not in {text.casefold()}


def test_actual_project_all_cards_repaired_and_one_source_at_end():
    plan,brief=actual()
    source_card_once(plan,brief);normalize_cards(plan,brief)
    cards=[q for s in plan.scenes for q in s.shots if q.visual and q.visual.template!="stock"]
    assert sum(q.visual.template=="source_card" for q in cards)==1
    assert plan.scenes[-1].shots[-1].visual.template=="source_card"
    for shot in cards:
        if shot.visual.template=="source_card":
            assert not shot.visual.data.title and len(shot.visual.data.source.split(" · "))<=2
        else:
            assert valid_card(shot.card_text) and 1<=len(shot.emphasis)<=2
            assert shot.visual.data.text==shot.card_text
    assert not normalize_cards(plan,brief)  # Idempotent, no cycling queries/cards.


def test_modal_repetition_warns_group_three_even_without_style_check():
    plan,brief=fixture();plan.scenes[0].narration="Có thể hiểu là một cách diễn giải."
    plan.scenes[1].narration="Có thể hình dung cách tiếp cận này có lẽ thay đổi."
    assert quality_findings(plan)
    rule=next(r for r in RULES if r.id=="presentation_voice")
    assert rule.group==3 and rule.check(Context(plan,brief,check_style=False))
    assert next(r for r in RULES if r.id=="card_text").group==2


def test_no_forced_modal_prefix_and_no_forecast_strengthening():
    plan,brief=actual();before=plan.scenes[2].narration
    humanize_locally(plan,brief)
    assert not plan.scenes[1].narration.startswith("Có thể hiểu")
    assert not any("job guarantee" in s.narration.casefold() for s in plan.scenes)
    # True background uncertainty is retained and warned, never mechanically asserted.
    assert plan.scenes[2].narration==before
    assert any("presentation_voice" in w for w in plan.review_notes)


def test_generic_hook_uses_existing_fact_and_twelve_words():
    plan,brief=actual();repair_generic_hook(plan,brief)
    hook=plan.scenes[0]
    assert len(hook.narration.split())<=12 and "?" not in hook.narration
    assert "9,3" in hook.narration and hook.fact_ids and hook.sentences[0].type=="event"
    from agents.explainer_guard import sentence_issues
    assert not [s for s in sentence_issues(plan,brief) if s[0]==hook.id]


def test_event_fabricated_card_is_not_silently_removed_by_group_two():
    plan,brief=fixture();shot=plan.scenes[1].shots[0]
    from schemas.visual import Visual,VisualData
    shot.visual=Visual(template="text_focus",data=VisualData(text="Thông tin từ nguồn",fact_ids=[1]))
    shot.card_text="987654321 việc làm bị mất"
    normalize_cards(plan,brief)
    from agents.visual_planner import visual_issues
    assert any("987654321" in text for _,text in visual_issues(plan,brief))
    with pytest.raises(RuleViolation): run_rules(plan,brief,check_style=False,allow_merge=False)


def test_text_focus_is_centered_and_source_hides_all_internal_labels():
    theme=load_theme();size=(540,960)
    card=Card("text_focus",{"text":"Ghế dự phòng","highlight":["dự","phòng"]},3,size,theme)
    layer=card.panel(1)
    # Compare white/accent text pixels in inner card, excluding accent border.
    a=np.array(layer);mask=(a[:,:,0]>170)&(a[:,:,1]>150)&(a[:,:,3]>0)
    x,y,w,h=card_box(size,"text_focus");mask[:round(y+15)]=False
    yy,xx=np.where(mask)
    assert len(yy) and abs((yy.min()+yy.max())/2-(y+h/2))<h*.16
    source=Card("source_card",{"source":"The Guardian","date":"2026-10-23","title":"NGUỒN DỮ KIỆN SỰ KIỆN event facts"},3,size,theme)
    clean=Card("source_card",{"source":"The Guardian","date":"2026-10-23"},3,size,theme)
    assert np.array_equal(np.array(source.panel(1)),np.array(clean.panel(1)))
    stat=Card("stat_card",{"value":5000,"label":"Việc làm bị ảnh hưởng","source":"Hidden source"},3,size,theme)
    plain=Card("stat_card",{"value":5000,"label":"Việc làm bị ảnh hưởng"},3,size,theme)
    assert np.array_equal(np.array(stat.panel(1)),np.array(plain.panel(1)))


def test_graphic_does_not_open_stock_decoder_or_search(tmp_path):
    from editor.render import Frames
    from schemas.visual import Visual,VisualData
    from editor.captions import find_font
    spec=SimpleNamespace(visual=Visual(template="text_focus",data=VisualData(text="Một lưới đệm")),card_text="Một lưới đệm")
    shot=SimpleNamespace(scene_id=1,shot_id=1,spec=spec,start=0.,duration=3.,path=tmp_path/"ferris_wheel.mp4",fallback=False)
    timeline=SimpleNamespace(plan=SimpleNamespace(render_style=None),scenes=[],warnings=[])
    frames=Frames(timeline,(270,480),find_font(ROOT_DIR),Diagnostics(tmp_path/"logs"))
    try:
        assert frames.frame(shot,1).shape==(480,270,3) and not frames.cache
    finally: frames.close()


def test_source_text_vietnamese_and_geometry():
    assert vietnamese_terms("job guarantee") == "bảo đảm việc làm"
    for name in ("text_focus","hook_card","steps_list","compare_bars","source_card"):
        x,y,w,h=card_box((1080,1920),name);_,top,_,height=caption_box((1080,1920),name)
        assert 0<top-(y+h)<1920*.025 and top+height<=1920*.82+1e-5


def test_render_neutral_policy_cannot_resurrect_pending_fabricated_card(tmp_path):
    from tests.test_visual_policy import example
    from editor.graphics import prepare_graphics
    from utils.atomic_io import write_json_atomic
    plan,brief,scene,shot=example("event")
    plan.content_mode="explainer_v2"  # Keep explicit cards in preparation.
    shot.card_text="Cambridge Analytica mất 987654321 hồ sơ"
    write_json_atomic(tmp_path/"brief.json",brief.model_dump(mode="json"))
    timeline=SimpleNamespace(plan=plan,project=tmp_path,warnings=[])
    prepare_graphics(timeline)
    assert "987654321" not in shot.visual.data.text and "987654321" not in (shot.card_text or "")
    assert any(row["action"]=="neutral" for row in timeline.visual_review)


def test_profile_sentence_mode_cannot_expand_graphic_captions_beyond_four(tmp_path):
    from editor.captions import Captions,find_font
    from schemas.style import StyleRenderDefaults
    from schemas.visual import Visual
    shot=SimpleNamespace(start=0.,duration=4.,spec=SimpleNamespace(visual=Visual(template="text_focus")))
    scene=SimpleNamespace(start=0.,duration=4.,audio=tmp_path/"scene_1.mp3",audio_silent=False,shots=[shot],
        spec=SimpleNamespace(narration="Một câu rất dài cần được chia thành nhiều cụm nhỏ."))
    timeline=SimpleNamespace(plan=SimpleNamespace(render_style=StyleRenderDefaults(captions={"mode":"sentence"})),scenes=[scene])
    captions=Captions(timeline,(1080,1920),find_font(ROOT_DIR))
    assert all(len(entry[2])<=4 for entry in captions.entries)


def test_story_humanized_shot_card_fields_survive_normalization():
    from agents.director_story import apply_words
    from schemas.story import SceneWords
    plan,brief=fixture();scene=plan.scenes[1]
    apply_words(plan,[SceneWords(scene_id=scene.id,narration=scene.narration,overlays=[None]*len(scene.shots),
        broll_query="office employee discussion",card_texts=["Kỹ năng mới"],emphasis=[["Kỹ","năng"]])])
    assert scene.shots[0].card_text=="Kỹ năng mới" and scene.shots[0].emphasis==["Kỹ","năng"]


def test_explainer_writer_receives_and_retains_authored_cards(tmp_path):
    from tests.test_explainer_v2 import data
    from agents.explainer_director import script_plan
    from schemas.explainer import ShotCard
    from agents.director import DirectorRequest
    brief,outline,script=data()
    # Unique authored card: Motion3 intentionally repairs cards repeated within
    # the previous two slots; that is covered by test_motion_v3's real fixture.
    script.scenes[1].shot_cards=[ShotCard(card_text="Tổ chức công việc mới",emphasis=["công","việc"])]
    plan=script_plan(script,outline,brief,DirectorRequest(video_type="news",video_format="tiktok",duration_sec=60,content_mode="explainer_v2"),Settings(root_dir=ROOT_DIR))
    assert plan.scenes[1].shots[0].card_text=="Tổ chức công việc mới"
