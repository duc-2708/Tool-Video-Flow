"""Policy groups, targeted hard retries, configurable quality and real drafts."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from agents.validation_rules import RULES,RuleViolation,run_rules,groups
from agents.director import validate_plan,DirectorRequest,DirectorDraftError
from agents.director_story import validate_outline
from agents.director_numbers import normalized_numbers
from agents.adaptive import duration_for_brief,fact_schedule
from agents.story_style import story_blueprint
from schemas.edit_plan import EditPlan
from schemas.story import StoryOutline,HumanizedScript,WrittenScript
from schemas.research_brief import ResearchBrief
from tests.test_director import fixture_brief,fixture_plan
from tests.test_storytelling import story_data,ThreePass,create

def input_data():
    brief=fixture_brief();brief.facts=[brief.facts[0].model_copy(deep=True) for _ in range(8)]
    raw=fixture_plan()
    for i,s in enumerate(raw["scenes"],1): s["fact_ids"]=[i]
    return brief,EditPlan.model_validate(raw),DirectorRequest(video_type="review",video_format="tiktok",duration_sec=45)

def outline_for(plan,question):
    return StoryOutline(angle_index=1,hook=question,open_loop=question,payoff="Có thể cắt và ghép video.",payoff_fact_ids=[1],
        main_points=[{"id":1,"idea":"Dựng cảnh","fact_ids":list(range(1,9))}],
        scenes=[{"scene_id":s.id,"point_id":1,"fact_ids":s.fact_ids,"purpose":"Dùng fact đã có"} for s in plan.scenes])

def test_quality_is_warning_never_exception():
    brief,plan,request=input_data()
    plan.scenes[0].narration="Chào mọi người, hôm nay chúng ta sẽ nói về cách dựng video có thể nói rằng nhiều người đang quan tâm."
    plan.scenes[-1].narration="Tóm lại, cảm ơn đã xem."
    for s in plan.scenes: s.pattern_interrupt=False
    validate_plan(plan,brief,request)
    events=[e for e in plan.validation_events if e.group==3]
    assert {"hook_length","cliches","ending_style","pattern_interrupt"}<={e.rule_id for e in events}
    assert all(e.action=="warning" for e in events)

@pytest.mark.parametrize("bad,rule",[("Giá 99999 đô.","grounding_numbers"),("Elon Musk đang dùng sản phẩm này.","grounding_names_quotes"),("Theo tờ báo giả, thiết bị hoạt động.","grounding_names_quotes"),('Bạn nói "lợi nhuận vô hạn tuyệt đối".',"grounding_names_quotes")])
def test_fabricated_information_still_hard(bad,rule):
    brief,plan,request=input_data();plan.scenes[1].narration=bad
    with pytest.raises(RuleViolation) as found: validate_plan(plan,brief,request)
    assert any(e.rule_id==rule and e.scene_id==2 and e.group==1 for e in found.value.events)

def test_hypothesis_is_per_sentence_not_blanket_exemption():
    brief,plan,request=input_data();plan.scenes[1].narration="Giả sử, giá là 99999 đô."
    validate_plan(plan,brief,request);validate_plan(plan,brief,request)
    plan.scenes[1].narration+=" Giá thật là 88888 đô."
    with pytest.raises(RuleViolation,match="88888"): validate_plan(plan,brief,request)

def test_code_repairs_do_not_call_gemini():
    brief,plan,request=input_data()
    plan.scenes[1].narration="Chưa xác minh: có thể cắt ghép video."
    plan.format="youtube"
    for s in plan.scenes[1:]:
        for shot in s.shots: shot.duration_sec=2
    validate_plan(plan,brief,request)
    assert plan.format=="tiktok" and plan.duration_sec==pytest.approx(45)
    assert "chưa xác minh" not in plan.scenes[1].narration.casefold()
    assert {"forbidden_editorial","duration","format"}<={e.rule_id for e in plan.validation_events if e.action=="fixed"}

def test_fact_reuse_merges_instead_of_dropping_evidence():
    brief=fixture_brief();plan=EditPlan.model_validate(fixture_plan());duration=plan.duration_sec
    validate_plan(plan,brief,DirectorRequest(video_type="review",video_format="tiktok",duration_sec=45))
    assert sum(1 in s.fact_ids for s in plan.scenes)<=2
    assert plan.duration_sec==duration and all(s.fact_ids for s in plan.scenes if s.role=="body")
    assert any(e.rule_id=="fact_reuse" and e.action=="fixed" for e in plan.validation_events)

def test_open_loop_assigns_relevant_fact_without_stopping():
    brief,plan,request=input_data();plan.story_outline=outline_for(plan,"Vì sao có thể cắt ghép video?")
    plan.scenes[0].narration=plan.story_outline.open_loop
    validate_plan(plan,brief,request)
    assert plan.story_outline.payoff_fact_ids
    assert set(plan.story_outline.payoff_fact_ids)<=set(plan.scenes[-1].fact_ids)
    assert any(e.rule_id=="open_loop" and e.action=="fixed" for e in plan.validation_events)

def test_open_loop_without_evidence_removes_question():
    brief,plan,request=input_data();plan.story_outline=outline_for(plan,"Vì sao cá voi bay quanh sao Hỏa?")
    plan.scenes[0].narration=plan.story_outline.open_loop
    validate_plan(plan,brief,request)
    assert plan.story_outline.open_loop=="" and "?" not in plan.scenes[0].narration
    assert any(e.rule_id=="open_loop" and "bỏ" in e.message for e in plan.validation_events)

def test_yaml_can_promote_warning_to_hard(tmp_path):
    brief,plan,request=input_data();plan.scenes[1].narration="Có thể nói rằng bạn cắt ghép video."
    path=tmp_path/"validation.yaml";path.write_text("rules:\n  cliches: {group: 1}\n",encoding="utf-8")
    with pytest.raises(RuleViolation,match="cliches") as error: validate_plan(plan,brief,request,validation_path=path)
    assert error.value.scene_ids=={2}

def test_only_promoted_group_one_causes_scene_retry(story_data,monkeypatch,tmp_path):
    import agents.validation_rules as policy
    path=tmp_path/"custom.yaml";path.write_text("rules:\n  cliches: {group: 1}\n",encoding="utf-8")
    monkeypatch.setattr(policy,"DEFAULT_VALIDATION",path)
    settings,brief,outline,written,final=story_data;selected=[]
    def human(prompt):
        data=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1]);ids=data["selected_scene_ids"];selected.append(ids)
        rows=[deepcopy(r) for r in written["scenes"] if r["scene_id"] in ids]
        if len(selected)==1: rows[2]["narration"]="Có thể nói rằng bạn cắt ghép video."
        return {"scenes":rows,"approved":True,"issues":[]}
    plan,provider=create(story_data,ThreePass(outline,written,human))
    assert len(provider.calls)==4 and selected[1:]==[[3]]
    assert plan.scenes[0].narration.endswith(written["scenes"][0]["narration"])

def test_exhausted_hard_error_saves_scene_and_rule(story_data):
    settings,brief,outline,written,final=story_data;written=deepcopy(written)
    written["scenes"][2]["narration"]="Giá thật là 99999 đô."
    selected=[]
    def human(prompt):
        data=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1]);ids=data["selected_scene_ids"];selected.append(ids)
        return {"scenes":[r for r in written["scenes"] if r["scene_id"] in ids],"approved":True,"issues":[]}
    with pytest.raises(DirectorDraftError): create((settings,brief,outline,written,final),ThreePass(outline,written,human))
    draft=json.loads((settings.output_dir/"edit_plan.draft.json").read_text(encoding="utf-8"))
    assert draft["failed_scene_ids"]==[3] and selected[1:]==[[3],[3]]
    assert any(e["scene_id"]==3 and e["rule_id"]=="grounding_numbers" for e in draft["validation_errors"])
    assert draft["plan"]["scenes"][0]["narration"].endswith(written["scenes"][0]["narration"])

def test_no_quality_retry_even_if_gemini_flags_quality(story_data):
    settings,brief,outline,written,final=story_data;final=deepcopy(final)
    final["scenes"][2]["narration"]="Có thể nói rằng bạn cắt ghép video."
    final["approved"]=False;final["issues"]=[{"scene_id":3,"reason":"[cliches] Cụm sáo rỗng."}]
    plan,provider=create((settings,brief,outline,written,final),ThreePass(outline,written,final))
    assert len(provider.calls)==3 and any(e.rule_id=="cliches" and e.group==3 for e in plan.validation_events)

@pytest.mark.parametrize("a,b",[("2.95 m","hai phẩy chín lăm mét"),("2027","hai nghìn không trăm hai mươi bảy"),("1M","một triệu")])
def test_real_draft_number_parser_false_positives(a,b):
    assert normalized_numbers(a,ignore_current_year=False)==normalized_numbers(b,ignore_current_year=False)

PROJECTS=["auto-tin-tuc-07c368c9","auto-cong-nghe-8a211210","auto-cong-nghe-ace8ccb3","auto-cong-nghe-47d6390a"]
@pytest.mark.parametrize("name",PROJECTS)
@pytest.mark.parametrize("live",[False,True])
def test_all_failed_drafts_no_quality_exception(name,live):
    from config.settings import ROOT_DIR
    root=ROOT_DIR/("output" if live else "tests/fixtures")/name
    if not (root/"edit_plan.draft.json").exists(): pytest.skip("Project thật đã dọn, vẫn chạy snapshot")
    raw=json.loads((root/"edit_plan.draft.json").read_text(encoding="utf-8"))
    brief=ResearchBrief.model_validate_json((root/"brief.json").read_text(encoding="utf-8"))
    if raw["plan"]:
        plan=EditPlan.model_validate(raw["plan"])
        validate_plan(plan,brief,DirectorRequest(video_type=plan.video_type,video_format=plan.format,duration_sec=plan.target_duration_sec))
        assert not any(e.action=="error" for e in plan.validation_events)
    else:
        config=json.loads((root/"run_state.json").read_text(encoding="utf-8"))["config"]
        duration=duration_for_brief(brief,config["duration_sec"]);blueprint=story_blueprint(duration,len(brief.facts));refs=fact_schedule(blueprint,len(brief.facts))
        question=(brief.facts[0].fact_vi or brief.facts[0].claim).rstrip(".")+"?"
        outline=StoryOutline(angle_index=1,hook=question,open_loop=question,payoff="Thông tin từ brief",payoff_fact_ids=[1],
            main_points=[{"id":1,"idea":"Thông tin từ brief","fact_ids":list(range(1,len(brief.facts)+1))}],
            scenes=[{"scene_id":r["id"],"point_id":1,"fact_ids":refs[r["id"]],"purpose":"Dùng fact trong brief"} for r in blueprint])
        validate_outline(outline,brief,blueprint)
        assert not outline.open_loop or set(outline.payoff_fact_ids)<=set(outline.scenes[-1].fact_ids)
        payload={"title":brief.topic,"format":config["video_format"],"voice":config["voice"],"music":{"mood":"calm","volume":.1},"target_duration_sec":duration,"script_style":"storytelling",
            "story_outline":outline.model_dump(mode="json"),"scenes":[{"id":r["id"],"role":r["role"],"narration":brief.facts[outline.scenes[i].fact_ids[0]-1].fact_vi or brief.facts[0].claim,
                "fact_ids":outline.scenes[i].fact_ids,"sfx":"none","transition_out":"cut","shots":[{"type":"stock_video","query":"SpaceX Starship long rocket launch technology system catch","duration_sec":d,"effect":"none","text_overlay":None} for d in r["shot_durations_sec"]]} for i,r in enumerate(blueprint)]}
        plan=EditPlan.model_validate(payload)
        validate_plan(plan,brief,DirectorRequest(video_type="news",video_format=plan.format,duration_sec=duration))


@pytest.mark.parametrize("message,rule",[("Cảnh 2: hook chưa hấp dẫn.","hook_strength"),("Cảnh 2: văn phong hơi khô.","audit_clarity"),("Cảnh 2 cần ít nhất 2 fact khác nhau.","examples")])
def test_audit_quality_never_disguises_as_grounding(message,rule):
    from agents.validation_rules import audit_findings
    brief,plan,request=input_data()
    findings=audit_findings([message])
    assert findings[0][0]==rule
    run_rules(plan,brief,request,audit_issues=findings)
    assert any(e.rule_id==rule and e.group==3 and e.action=="warning" for e in plan.validation_events)


def test_schema_retry_preserves_other_scenes(tmp_path):
    from unittest.mock import Mock
    from agents.director import validated_json
    from utils.diagnostics import Diagnostics
    raw=fixture_plan();raw["scenes"][1]["narration"]=None
    fixed=fixture_plan()["scenes"][1]
    provider=Mock()
    provider.generate_json.side_effect=[json.dumps(raw),json.dumps({"scenes":[fixed]})]
    plan=validated_json(provider,"Original",EditPlan,2,Diagnostics(tmp_path))
    feedback=json.loads(provider.generate_json.call_args.args[0].split("INPUT_DATA_JSON:\n")[-1])
    assert feedback["selected_scene_ids"]==[2]
    assert plan.scenes[0].narration==raw["scenes"][0]["narration"]
    assert plan.scenes[1].narration==fixed["narration"]


def test_registry_yaml_lists_every_rule():
    import yaml
    from config.settings import ROOT_DIR
    defaults=yaml.safe_load((ROOT_DIR/"config/validation.yaml").read_text(encoding="utf-8"))["rules"]
    assert set(defaults)=={r.id for r in RULES}
    assert all(defaults[r.id]["group"]==r.group for r in RULES)
