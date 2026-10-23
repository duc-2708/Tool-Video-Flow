"""Saved Guardian plans and a corrupted profile, with entirely offline repairs."""
import json
import re
from pathlib import Path
from unittest.mock import Mock
import pytest
from pydantic import SecretStr
from config.settings import ROOT_DIR,Settings
from schemas.style import StyleAnalysis,AnalysisRecord,StyleProfile
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from agents.content_plan import finalize_content_plan,scene_seconds,draft_presentation
from agents.director import validate_plan,DirectorRequest,run_director
from agents.researcher import run_research
from agents.broll_queries import sanitize_broll_query,unique_query
from agents.research_expansion import thin_research
from pipeline.style_profile import aggregate
from pipeline.style_safety import template_text,BROKEN,sanitize_profile
from utils.json_response import parse_json_object
from utils.cache import write_json
from tests.test_director import fixture_plan,fixture_brief
from tests.test_researcher import source,response_data,FakeLLM,fake_queries

FIXTURES=Path(__file__).parent/"fixtures/guardian_presentation"


def records_from_paid_raw():
    paths=[FIXTURES/"cong_nghe_1.raw.txt",Path(__file__).parent/"fixtures/style_raw/cong_nghe_2.raw.txt",
        Path(__file__).parent/"fixtures/style_raw/cong_nghe_4.raw.txt"]
    return [AnalysisRecord(filename=f"sample_{i}.mp4",file_hash=str(i),notes_hash="notes",model="fixture",prompt_hash="fixture",
        analysis=StyleAnalysis.model_validate(parse_json_object(path.read_text(encoding="utf-8")))) for i,path in enumerate(paths)]


def test_real_corrupted_profile_rebuild_preserves_ordinary_vietnamese():
    original=(FIXTURES/"cong-nghe.before.json").read_text(encoding="utf-8")
    assert "{topic} thích" in original and "{topic} nhỏ" in original
    profile=aggregate(records_from_paid_raw(),"công nghệ")
    result=profile.model_dump_json().casefold()
    for phrase in ["giải thích","sử dụng","phân tích","đánh giá","cao trào","chia nhỏ","ví dụ"]:
        assert phrase in result
    sent=json.dumps({"structure":[s.name for s in profile.structure],"rules":profile.reusable_rules,"narration":profile.narration_rules},ensure_ascii=False)
    assert not BROKEN.search(sent)
    current=ROOT_DIR/"config/style_profiles/cong-nghe.json"
    if current.exists():
        data=json.loads(current.read_text(encoding="utf-8"))
        assert not BROKEN.search(json.dumps(data["structure"],ensure_ascii=False))


@pytest.mark.parametrize("sentence",["Giải thích và sử dụng ví dụ để phân tích, đánh giá.","Cao trào và kết; chia nhỏ nội dung.","Mức hài hước: Cao, châm biếm nhẹ nhàng."])
def test_explicit_entities_never_replace_common_syllables(sentence):
    assert template_text(sentence,["Giải","Sử","Phân","Đánh","Ví","Cao","Chia","Nhẹ","Giải thích","Sử dụng","Phân tích","Đánh giá","Cao trào","Chia nhỏ","Ví dụ"])==sentence
    value=template_text("Giải thích SpaceX, dùng SpaceXpress làm ví dụ.",["SpaceX"])
    assert "Giải thích {topic}" in value and "SpaceXpress" in value


def test_placeholder_validation_falls_back_to_original_without_entities():
    warnings=[]
    value=template_text("Giải thích SpaceX, Microsoft, Nvidia và Google bằng ví dụ.",["SpaceX","Microsoft","Nvidia","Google"],warnings)
    assert warnings and "Giải thích" in value and "ví dụ" in value
    assert not any(name in value for name in ["SpaceX","Microsoft","Nvidia","Google"])
    assert len(re.findall(r"\{\w+\}",value))<=2
    profile=aggregate(records_from_paid_raw(),"test")
    profile.reference_entities=["SpaceX"]
    profile.reusable_rules=["Giải thích SpaceX bằng ví dụ"]
    assert sanitize_profile(profile).reusable_rules==["Giải thích {topic} bằng ví dụ"]


@pytest.mark.parametrize("historical",[False,True])
def test_saved_guardian_plan_timing_and_max_four_shots(historical):
    folder=FIXTURES/"historical" if historical else FIXTURES
    draft=json.loads((folder/"edit_plan.draft.json").read_text(encoding="utf-8"))
    brief=ResearchBrief.model_validate_json((folder/"brief.json").read_text(encoding="utf-8"))
    plan=EditPlan.model_validate(draft["plan"])
    original=[(s.narration,list(s.fact_ids)) for s in plan.scenes]
    plan.style_profile=aggregate(records_from_paid_raw(),"test")
    request=DirectorRequest(video_type=plan.video_type or "news",video_format=plan.format,duration_sec=60,style_profile=plan.style_profile)
    plan=EditPlan.model_validate(draft_presentation(plan.model_dump(mode="json"),brief,request))
    assert [(s.narration,s.fact_ids) for s in plan.scenes]==original
    for scene in plan.scenes:
        assert scene.duration_sec==pytest.approx(scene_seconds(scene))
        assert len(scene.shots)==min(4,max(1,round(scene.duration_sec/plan.style_profile.shot_seconds.mean)))
    assert EditPlan.model_validate_json(plan.model_dump_json()).duration_sec==pytest.approx(plan.duration_sec)
    if not historical:
        assert plan.requested_duration_sec==60 and 23<plan.duration_sec<28
        assert len(plan.scenes[2].shots)<=4 and plan.scenes[2].duration_sec<10
        assert any("tăng số nguồn" in w for w in plan.review_notes)


@pytest.mark.parametrize("mean,words",[(1.5,1),(3,15),(4,100)])
def test_content_timing_exact_formula_rounding_and_audio_stage_contract(mean,words):
    from pipeline.assets import retime_scene
    plan=EditPlan.model_validate(fixture_plan());plan.style_profile=aggregate(records_from_paid_raw(),"test")
    plan.style_profile.shot_seconds.mean=mean
    plan.scenes[1].narration=" ".join(["từ"]*words)
    finalize_content_plan(plan,fixture_brief())
    scene=plan.scenes[1]
    assert scene.duration_sec==pytest.approx(max(words/2.6+.8,2.5))
    assert len(scene.shots)==min(4,max(1,round(scene.duration_sec/mean)))
    resolved=retime_scene(scene,scene.duration_sec)
    assert all(1.5<=s.duration_sec<=4 and not s.planning_duration for s in resolved.shots)


def test_query_repair_stays_on_water_energy_topic_and_uses_related_variants():
    context="Hạn hán gây khô hạn nguồn nước; trung tâm dữ liệu dùng điện và năng lượng."
    query=sanitize_broll_query("???",context)
    assert set(query.split()) & {"water","drought","energy","power","data","center"}
    used=set();values=[]
    for _ in range(10):
        value=unique_query(query,context,used);used.add(value);values.append(value)
    assert len(set(values))==10
    assert all(v.split()[:2]==query.split()[:2] for v in values)
    assert not any(v in {"city skyline","news studio","office team meeting"} for v in values)


def test_production_director_writes_vietnamese_title_stock_and_real_duration(tmp_path,monkeypatch):
    settings=Settings(root_dir=tmp_path,gemini_model="mock",gemini_api_key=SecretStr("test-key"))
    brief=fixture_brief();path=tmp_path/"project/brief.json";write_json(path,brief.model_dump(mode="json"))
    plan=EditPlan.model_validate(fixture_plan());plan.title="The future of artificial intelligence"
    plan.scenes[1].shots[0].type="ai_video"
    monkeypatch.setattr("agents.director.create_edit_plan",lambda *a,**kw:plan)
    api=Mock();monkeypatch.setattr("agents.director.director_provider",lambda *a:api)
    result=run_director(path,settings,duration_sec=60,progress=lambda _:None)
    value=EditPlan.model_validate_json(result.read_text(encoding="utf-8"))
    assert value.title==brief.topic and value.requested_duration_sec==60
    assert all(s.type!="ai_video" for scene in value.scenes for s in scene.shots)
    assert value.duration_sec==pytest.approx(sum(scene_seconds(s) for s in value.scenes))
    api.generate_json.assert_not_called()


def test_content_repair_never_weakens_number_grounding():
    plan=EditPlan.model_validate(fixture_plan());brief=fixture_brief()
    plan.scenes[1].narration+=" Giá chính xác 987654321 đô la."
    finalize_content_plan(plan,brief)
    from agents.validation_rules import RuleViolation
    with pytest.raises(RuleViolation,match="987654321"):
        validate_plan(plan,brief,DirectorRequest(video_type="review",video_format="tiktok",duration_sec=60))


@pytest.mark.parametrize("has_new_sources",[False,True])
def test_research_expands_once_then_continues_with_grounded_data(tmp_path,monkeypatch,source,has_new_sources):
    settings=Settings(root_dir=tmp_path,gemini_model="mock",gemini_api_key=SecretStr("test-key"))
    settings.prompts_dir.mkdir();(settings.prompts_dir/"researcher.txt").write_text("Test instructions",encoding="utf-8")
    extras=[type(source).model_validate({**source.model_dump(mode="json"),"url":f"https://paper{i}.example/article","source_name":f"paper{i}"}) for i in range(4)]
    initial=response_data(source);expanded=response_data(source)
    expanded["facts"]+= [{**initial["facts"][0],"source_url":str(s.url),"claim":s.text,"fact_vi":s.text} for s in extras]
    api=FakeLLM([json.dumps(initial),json.dumps(expanded)])
    api.close=Mock()
    monkeypatch.setattr("agents.researcher.GeminiProvider",lambda _:api)
    monkeypatch.setattr("agents.researcher.generate_queries",fake_queries)
    requests=[]
    def collect(self,query,limit,lang):
        requests.append(query)
        return (extras if has_new_sources and len(requests)>2 else [source]),[]
    monkeypatch.setattr("sources.web_search.WebSearch.collect",collect)
    result=run_research("Dựng video",settings,use_youtube=False,output_dir=tmp_path/"project",progress=lambda _:None)
    brief=ResearchBrief.model_validate_json(result.read_text(encoding="utf-8"))
    sources=json.loads(result.with_name("sources.json").read_text(encoding="utf-8"))
    assert sources["research_expansion"]["attempted"]
    assert len(requests)==(3 if has_new_sources else 6)
    assert sources["research_expansion"]["added_sources"]==(4 if has_new_sources else 0)
    assert api.calls==(2 if has_new_sources else 1)
    assert len(brief.facts)>=3 and all(f.evidence_quote in source.text for f in brief.facts)
    if not has_new_sources: assert any("vẫn mỏng" in warning for warning in brief.risks)
    else: assert not thin_research(brief)
    api.close.assert_called_once()
