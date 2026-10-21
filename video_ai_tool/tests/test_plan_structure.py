"""Shot array normalization at every Director boundary, including real draft."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from agents.plan_structure import normalize_plan_structure
from agents.director import validate_plan,DirectorRequest,director_diagnostics
from agents.director_story import apply_words
from schemas.edit_plan import EditPlan,Scene
from schemas.research_brief import ResearchBrief
from schemas.story import WrittenScript,HumanizedScript
from tests.test_storytelling import story_data,create,ThreePass
from tests.test_director import fixture_plan


@pytest.mark.parametrize("size",[0,1,7])
def test_pad_and_trim_parallel_arrays_without_changing_shots_or_facts(size):
    raw=fixture_plan();scene=raw["scenes"][1];n=len(scene["shots"])
    expected=deepcopy(scene["shots"])
    scene.update(overlays=["Ý chính"]*size,broll_queries=["video editing"]*size,
        effects=["zoom_in"]*size,types=["stock_video"]*size,sfx=["none"]*size)
    normalized=normalize_plan_structure(raw)
    actual=normalized["scenes"][1]
    assert len(actual["shots"])==n and actual["fact_ids"]==scene["fact_ids"]
    assert [s["duration_sec"] for s in actual["shots"]]==[s["duration_sec"] for s in expected]
    assert all(s["text_overlay"] is None for s in actual["shots"][size:])
    assert all(isinstance(s["query"],str) for s in actual["shots"])
    assert actual["review_notes"]["warnings"]
    assert normalize_plan_structure(normalized)==normalized
    EditPlan.model_validate(normalized)
    assert raw["scenes"][1]["overlays"]==["Ý chính"]*size


def test_empty_scene_creates_default_shot_before_schema_validation():
    scene=deepcopy(fixture_plan()["scenes"][0]);scene["shots"]=[]
    parsed=Scene.model_validate(scene)
    assert len(parsed.shots)==1 and parsed.shots[0].duration_sec==3
    assert parsed.shots[0].query=="video editing"
    assert parsed.review_notes.warnings


def test_validate_plan_normalizes_even_a_model_with_empty_shots():
    from tests.test_director import fixture_brief
    plan=EditPlan.model_validate(fixture_plan())
    plan.scenes[0].shots=[]
    validate_plan(plan,fixture_brief(),DirectorRequest(video_type="review",video_format="tiktok",duration_sec=45),check_style=False)
    assert plan.scenes[0].shots and plan.scenes[0].review_notes.warnings


def test_words_arrays_have_exact_reference_length():
    plan=EditPlan.model_validate(fixture_plan());scene=plan.scenes[1];n=len(scene.shots)
    raw={"title":"Dựng cảnh","scenes":[{"scene_id":scene.id,"narration":scene.narration,"overlays":[],
        "broll_query":["video editing"]*(n+2),"effects":[],"types":["stock_video"],"sfx":["pop"]*(n+3)}]}
    value=normalize_plan_structure(raw,reference=plan)
    row=WrittenScript.model_validate(value).scenes[0]
    assert all(len(getattr(row,name))==n for name in ("overlays","shot_queries","shot_effects","shot_types","shot_sfx"))
    assert row.overlays==[None]*n and row.shot_effects==["none"]*n
    apply_words(plan,[row])
    assert len(plan.scenes[1].shots)==n and plan.scenes[1].sfx=="pop"
    assert plan.scenes[1].review_notes.warnings


def test_all_three_passes_normalize_before_validation(story_data,monkeypatch):
    import agents.director as director
    import agents.director_story as story
    settings,brief,outline,written,final=story_data
    written=deepcopy(written);final=deepcopy(final)
    written["scenes"][1]["overlays"]=[]
    final["scenes"][1]["overlays"]=["Ý chính"]*20
    seen=[]
    def spy(value,**kwargs):
        if isinstance(value,dict):
            if "main_points" in value: seen.append("outline")
            elif "title" in value and "scenes" in value and "format" not in value: seen.append("write")
            elif "approved" in value and "scenes" in value: seen.append("humanize")
        return normalize_plan_structure(value,**kwargs)
    monkeypatch.setattr(director,"normalize_plan_structure",spy)
    monkeypatch.setattr(story,"normalize_plan_structure",spy)
    plan,provider=create((settings,brief,outline,written,final),ThreePass(outline,written,final))
    assert {"outline","write","humanize"}<=set(seen)
    assert len(provider.calls)==3 and plan.scenes[1].review_notes.warnings
    assert len(plan.scenes[1].shots)==len(final["scenes"][1]["overlays"][:len(plan.scenes[1].shots)])
    assert not plan.humanization_fallback_scene_ids


def test_retry_single_scene_normalizes_instead_of_rejecting_count(story_data):
    settings,brief,outline,written,final=story_data
    selected=[]
    def result(prompt):
        payload=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1]);ids=payload["selected_scene_ids"];selected.append(ids)
        rows=[deepcopy(r) for r in written["scenes"] if r["scene_id"] in ids]
        for row in rows:
            if row["scene_id"]==3:
                row["overlays"]=[]
                if len(selected)==1: row["narration"]="Có thể nói rằng bạn chọn đoạn trước khi ghép. Bạn muốn thử không?"
        return {"scenes":rows,"approved":True,"issues":[]}
    plan,_=create(story_data,ThreePass(outline,written,result))
    assert selected[1:]==[]
    assert not plan.humanization_fallback_scene_ids
    assert all(s.text_overlay is None for s in plan.scenes[2].shots)


@pytest.mark.parametrize("real_output",[False,True])
def test_regression_actual_auto_cong_nghe_draft(real_output):
    from config.settings import ROOT_DIR
    root=ROOT_DIR/("output" if real_output else "tests/fixtures")/"auto-cong-nghe-8a211210"
    if not (root/"edit_plan.draft.json").exists(): pytest.skip("Project thật đã được chuyển/xóa; bản snapshot vẫn được kiểm tra.")
    draft=json.loads((root/"edit_plan.draft.json").read_text(encoding="utf-8"))
    assert any("overlay" in w for w in draft["warnings"])
    brief=ResearchBrief.model_validate_json((root/"brief.json").read_text(encoding="utf-8"))
    plan=EditPlan.model_validate(normalize_plan_structure(draft)["plan"])
    counts=[len(s.shots) for s in plan.scenes]
    request=DirectorRequest(video_type=plan.video_type,video_format=plan.format,duration_sec=plan.target_duration_sec)
    # Draft also has pre-existing word-budget/style defects, independent of counts.
    validate_plan(plan,brief,request,check_style=False)
    rows={"title":plan.title,"scenes":[{"scene_id":s.id,"narration":s.narration,
        "overlays":["Ý chính"]*(1 if s.id==2 else len(s.shots)+2),"broll_query":s.shots[0].query} for s in plan.scenes]}
    words=WrittenScript.model_validate(normalize_plan_structure(rows,reference=plan))
    apply_words(plan,words.scenes)
    validate_plan(plan,brief,request,check_style=False)
    assert [len(s.shots) for s in plan.scenes]==counts
    assert plan.scenes[1].review_notes.warnings
