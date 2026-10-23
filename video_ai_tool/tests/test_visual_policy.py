"""Explainer graphics policy, real Meta regression and local editorial choices."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from agents.visual_policy import (background_warnings,content_type,review_for_render,
    ordered_label,save_decision,load_decisions,selected_choice)
from agents.visual_planner import visual_issues,assign_visuals
from agents.validation_rules import Context,visual_grounding,visual_background
from schemas.visual import Visual,VisualData
from schemas.explainer import ScriptSentence
from schemas.research_brief import ResearchBrief
from schemas.assets import ResolvedEditPlan
from tests.test_visual_templates import fixture


def example(kind="explain"):
    plan,brief=fixture();scene=plan.scenes[1];shot=scene.shots[0]
    scene.narration="Vụ Cambridge Analytica là ví dụ nền về quyền riêng tư."
    scene.sentences=[ScriptSentence(type=kind,text=scene.narration,fact_ids=[1] if kind=="event" else [])]
    shot.visual=Visual(template="text_focus",sentence_index=1,content_type=kind,
        data=VisualData(text="Vụ Cambridge Analytica",label="Ví dụ nền"))
    return plan,brief,scene,shot


@pytest.mark.parametrize("kind",["explain","opinion","cta"])
def test_background_name_is_warning_only(kind):
    plan,brief,scene,shot=example(kind)
    assert not visual_grounding(Context(plan,brief))
    assert any("ví dụ nền, nên kiểm tra lại" in f.message for f in visual_background(Context(plan,brief)))
    records=review_for_render(plan,brief)
    assert records and shot.visual.data.text=="Vụ Cambridge Analytica"
    assert all(r["action"]=="unchanged" for r in records)


def test_specific_background_number_warns_not_stops():
    plan,brief,scene,shot=example()
    shot.visual.data.text="Cambridge Analytica có 987654 tài khoản"
    assert not visual_issues(plan,brief)
    assert any("ước lượng" in text for _,text in background_warnings(plan,brief))
    assert review_for_render(plan,brief)[0]["action"]=="unchanged"


def test_event_invalid_neutralized_only_in_memory(tmp_path):
    plan,brief,scene,shot=example("event")
    shot.visual.data.value=987654321
    assert visual_issues(plan,brief)
    records=review_for_render(plan,brief)
    assert records[0]["action"]=="neutral"
    assert "Cambridge" not in shot.visual.data.text and shot.visual.data.value is None
    assert scene.narration.startswith("Vụ Cambridge Analytica")  # Graphic repair doesn't rewrite narration.
    assert shot.text_overlay==shot.visual.data.text


def test_sentence_association_wins_over_legacy_visual_default():
    plan,brief,scene,shot=example()
    shot.visual.content_type="event"
    assert content_type(scene,shot)=="explain"
    assert not visual_issues(plan,brief)


def test_field_boundaries_never_form_fake_entity():
    plan,brief,scene,shot=example("event")
    brief.facts[0].fact_vi="Vụ Cambridge Analytica liên quan dữ liệu."
    shot.visual.data.text="Cambridge Analytica"
    shot.visual.data.label="Vụ việc về dữ liệu"
    assert not visual_issues(plan,brief)
    assert ordered_label("Cambridge Analytica Vụ","Vụ Cambridge Analytica liên quan dữ liệu.")=="Vụ Cambridge Analytica"
    shot.visual.data.text="Cambridge Analytica Vụ"
    records=review_for_render(plan,brief)
    assert shot.visual.data.text=="Vụ Cambridge Analytica"
    assert any("thứ tự" in text for row in records for text in row["warnings"])


def test_keep_decision_survives_reload_and_is_respected(tmp_path):
    plan,brief,scene,shot=example("event")
    save_decision(tmp_path,scene,1,"keep")
    decisions=load_decisions(tmp_path)
    assert selected_choice(decisions,scene,1)=="keep"
    result=review_for_render(plan,brief,decisions)
    assert result[0]["action"]=="keep" and shot.visual.data.text=="Vụ Cambridge Analytica"
    assert any("chịu trách nhiệm" in m for m in result[0]["warnings"])
    scene.narration+=" Nội dung đã thay đổi."
    assert selected_choice(decisions,scene,1) is None


def test_explicit_neutral_choice_for_background(tmp_path):
    plan,brief,scene,shot=example()
    save_decision(tmp_path,scene,1,"neutral")
    assert review_for_render(plan,brief,load_decisions(tmp_path))[0]["action"]=="neutral"


def test_real_meta_resolved_regression(tmp_path):
    from editor.graphics import prepare_graphics
    root=Path(__file__).parent/"fixtures/visual_meta"
    plan=ResolvedEditPlan.model_validate_json((root/"edit_plan.resolved.json").read_text(encoding="utf-8"))
    original=plan.model_dump_json()
    (tmp_path/"brief.json").write_bytes((root/"brief.json").read_bytes())
    timeline=SimpleNamespace(project=tmp_path,plan=plan,warnings=[])
    prepare_graphics(timeline)
    assert all("Cambridge Analytica Vụ" not in w for w in timeline.warnings)
    assert not visual_issues(plan,ResearchBrief.model_validate_json((root/"brief.json").read_text(encoding="utf-8")))
    assert json.loads(original)["scenes"][1]["narration"]==plan.scenes[1].narration


def test_edit_ui_choice_buttons_without_api(tmp_path):
    from streamlit.testing.v1 import AppTest
    from utils.atomic_io import write_json_atomic
    plan,brief,scene,shot=example("event")
    write_json_atomic(tmp_path/"plan.json",plan.model_dump(mode="json"))
    write_json_atomic(tmp_path/"brief.json",brief.model_dump(mode="json"))
    code='''
from pathlib import Path
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from utils.diagnostics import Diagnostics
from app.visual_review import render_visual_controls
p=Path(PROJECT)
plan=EditPlan.model_validate_json((p/'plan.json').read_text(encoding='utf-8'))
brief=ResearchBrief.model_validate_json((p/'brief.json').read_text(encoding='utf-8'))
render_visual_controls(plan,brief,p,Diagnostics(p/'logs'))
'''.replace("PROJECT",repr(str(tmp_path)))
    app=AppTest.from_string(code).run(timeout=30)
    assert not app.exception
    key=f"visual_{tmp_path.name}_{scene.id}_1_keep"
    app.button(key=key).click().run(timeout=30)
    assert not app.exception
    assert selected_choice(load_decisions(tmp_path),scene,1)=="keep"
    key=f"visual_{tmp_path.name}_{scene.id}_1_neutral"
    app.button(key=key).click().run(timeout=30)
    assert not app.exception
    assert selected_choice(load_decisions(tmp_path),scene,1)=="neutral"


def test_broken_card_does_not_stop_frames(monkeypatch,tmp_path):
    from editor.render import Frames
    from editor.captions import find_font
    from config.settings import ROOT_DIR
    from utils.diagnostics import Diagnostics
    plan,brief,scene,shot=example()
    timeline=SimpleNamespace(plan=plan,scenes=[SimpleNamespace(spec=scene)],warnings=[])
    slot=SimpleNamespace(scene_id=scene.id,shot_id=1,spec=shot,start=0,duration=3,fallback=True,path=None)
    monkeypatch.setattr("editor.render.Card",lambda *a,**k: (_ for _ in ()).throw(ValueError("bad card")))
    frames=Frames(timeline,(180,320),find_font(ROOT_DIR),Diagnostics(tmp_path/"logs"))
    try:
        assert frames.frame(slot,.1).shape==(320,180,3)
        assert frames.frame(slot,.2).shape==(320,180,3)
        assert len(timeline.warnings)==1
    finally: frames.close()


def test_missing_brief_neutralizes_event_graphics(tmp_path):
    from editor.graphics import prepare_graphics
    plan,brief,scene,shot=example("event")
    timeline=SimpleNamespace(project=tmp_path,plan=plan,warnings=[])
    prepare_graphics(timeline)
    assert shot.visual.content_type=="explain"
    assert any("thiếu brief" in text for text in timeline.warnings)
