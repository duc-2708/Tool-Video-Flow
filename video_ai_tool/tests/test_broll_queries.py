"""Neutral, local stock-query repair; no networking or paid generation."""
import json
import re
from copy import deepcopy
from unittest.mock import Mock
import pytest
from agents.broll_queries import sanitize_broll_query,BrollQueryResponse
from agents.plan_structure import normalize_plan_structure
from agents.director import validate_plan,DirectorRequest,director_diagnostics
from agents.adaptive import duration_for_brief,fact_schedule
from agents.story_style import story_blueprint
from schemas.edit_plan import EditPlan,Shot
from schemas.research_brief import ResearchBrief
from tests.test_director import fixture_plan
from tests.test_storytelling import story_data,ThreePass,create

def assert_query(query):
    assert re.fullmatch(r"[a-z]+(?: [a-z]+){1,3}",query)
    assert not re.search(r"spacex|starship|tesla|elon|musk|gemini|iphone",query,re.I)

@pytest.mark.parametrize("query",[
    "kỹ sư phòng điều khiển", "SpaceX Starship rocket launch engineers control room technology system catch",
    "Động cơ tên lửa PHÓNG!!! ban đêm 🎬", "Elon Musk Tesla iphone factory machinery assembly testing laboratory closeup",
    "???",None,42])
def test_sanitizer_latin_english_short_neutral(query):
    actual=sanitize_broll_query(query,"Tên lửa phóng ban đêm")
    assert_query(actual)
    assert sanitize_broll_query(actual)==actual

def test_only_uncleanable_shot_calls_gemini_once_then_fallback(story_data):
    settings=story_data[0]
    raw=fixture_plan()
    raw["scenes"][1]["shots"][0]["query"]="???"
    provider=Mock();provider.generate_json.return_value=json.dumps({"query":"SpaceX Starship"})
    normalized=normalize_plan_structure(raw,query_provider=provider,diagnostics=director_diagnostics(settings))
    provider.generate_json.assert_not_called()  # Group 2 repairs are code-only.
    for scene in normalized["scenes"]:
        for shot in scene["shots"]: assert_query(shot["query"])
    assert normalized["scenes"][1]["review_notes"]["warnings"]
    log=(settings.logs_dir/"director_errors.log").read_text(encoding="utf-8")
    assert "shot 1" in log and "→" in log

def test_query_only_regeneration_success_and_timeout_fallback():
    provider=Mock();provider.generate_json.return_value='{"query":"engineers control room"}'
    assert sanitize_broll_query("???","rocket",provider=provider)=="engineers control room"
    provider.generate_json.assert_called_once()
    provider=Mock();provider.generate_json.side_effect=TimeoutError("mock query timeout")
    value=sanitize_broll_query("???","SpaceX Starship Elon Musk",provider=provider)
    assert value=="rocket launch night"
    provider.generate_json.assert_called_once()

def test_video_queries_unique_stable_and_different_contexts():
    raw=fixture_plan()
    for scene in raw["scenes"]:
        scene["narration"]="Tên lửa phóng và kỹ sư tại phòng điều khiển."
        for shot in scene["shots"]: shot["query"]="SpaceX Starship launch rocket technology system catch"
    original=deepcopy(raw)
    normalized=normalize_plan_structure(raw)
    queries=[s["query"] for scene in normalized["scenes"] for s in scene["shots"]]
    assert len(queries)==len(set(queries))
    for query in queries: assert_query(query)
    assert normalize_plan_structure(normalized)==normalized
    assert raw==original
    assert sanitize_broll_query("???","Công nghệ máy tính")!=sanitize_broll_query("???","Du lịch thành phố")

def test_partial_rewrite_avoids_queries_already_used_in_other_scenes():
    plan=normalize_plan_structure(fixture_plan())
    retained={s["query"] for c in plan["scenes"] if c["id"]!=2 for s in c["shots"]}
    row={"scene_id":2,"narration":"Dựng video tại bàn máy tính","overlays":[],"broll_query":"video editing"}
    normalized=normalize_plan_structure({"scenes":[row]},reference=plan)
    assert not retained.intersection(normalized["scenes"][0]["shot_queries"])

def test_three_passes_long_broll_does_not_fail_or_rewrite_narration(story_data):
    settings,brief,outline,written,final=story_data
    written=deepcopy(written);final=deepcopy(final)
    for row in written["scenes"]+final["scenes"]:
        row["broll_query"]="SpaceX Starship rocket launch engineers control room technology system catch"
    plan,provider=create((settings,brief,outline,written,final),ThreePass(outline,written,final))
    assert len(provider.calls)==3
    assert all(s.narration.endswith(row["narration"]) for s,row in zip(plan.scenes,final["scenes"]))
    queries=[s.query for scene in plan.scenes for s in scene.shots]
    assert len(queries)==len(set(queries))
    assert not plan.humanization_fallback_scene_ids
    for query in queries: assert_query(query)

@pytest.mark.parametrize("real_output",[False,True])
def test_regression_ace8ccb3_exact_saved_query_error(real_output):
    from config.settings import ROOT_DIR
    root=ROOT_DIR/("output" if real_output else "tests/fixtures")/"auto-cong-nghe-ace8ccb3"
    if not (root/"edit_plan.draft.json").exists(): pytest.skip("Project thật đã dọn; snapshot vẫn được kiểm tra")
    draft=json.loads((root/"edit_plan.draft.json").read_text(encoding="utf-8"))
    assert draft["plan"] is None  # Original bug discarded the plan before Pydantic succeeded.
    error="\n".join(draft["warnings"])
    bad=re.search(r"input_value='([^']+)'",error).group(1)
    paths=re.findall(r"scenes\.(\d+)\.shots\.(\d+)\.query",error)
    assert len(paths)==19
    brief=ResearchBrief.model_validate_json((root/"brief.json").read_text(encoding="utf-8"))
    config=json.loads((root/"run_state.json").read_text(encoding="utf-8"))["config"]
    duration=duration_for_brief(brief,config["duration_sec"])
    blueprint=story_blueprint(duration,len(brief.facts));refs=fact_schedule(blueprint,len(brief.facts))
    counts=[len(r["shot_durations_sec"]) for r in blueprint]
    assert sum(counts)==19
    raw={"title":brief.topic,"format":config["video_format"],"voice":config["voice"],"music":{"mood":"calm","volume":.1},
        "target_duration_sec":duration,"video_type":config["video_type"],"script_style":"storytelling",
        "scenes":[{"id":r["id"],"role":r["role"],"narration":brief.facts[refs[r["id"]][0]-1].fact_vi,
            "fact_ids":refs[r["id"]],"pattern_interrupt":True,"transition_out":"cut","sfx":"none",
            "shots":[{"type":"stock_video","query":bad,"duration_sec":d,"effect":"zoom_in","text_overlay":None} for d in r["shot_durations_sec"]]} for r in blueprint]}
    plan=EditPlan.model_validate(normalize_plan_structure(raw))
    validate_plan(plan,brief,DirectorRequest(video_type=plan.video_type,video_format=plan.format,duration_sec=duration),check_style=False)
    queries=[s.query for scene in plan.scenes for s in scene.shots]
    assert len(set(queries))==len(queries)==19
    for query in queries: assert_query(query)
