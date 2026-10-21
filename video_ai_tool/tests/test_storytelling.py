"""Three-pass storytelling, style checks, stable evidence and no network."""
import json
import math
from copy import deepcopy
from unittest.mock import Mock
import pytest
from pydantic import SecretStr
from config.settings import Settings,ROOT_DIR
from agents.director import DirectorRequest,DirectorDraftError,create_edit_plan,director_diagnostics,validate_plan
from agents.director_story import rewrite_script
from agents.story_style import story_blueprint,style_issues,data_advice
from agents.vietnamese_tts import tts_text
from agents.director_numbers import normalized_numbers
from schemas.story import StoryOutline,WrittenScript,HumanizedScript
from tests.test_director import fixture_brief
from utils.cache import JsonCache,write_json


@pytest.fixture
def story_data(tmp_path):
    settings = Settings(root_dir=tmp_path,gemini_api_key=SecretStr("fixture-secret"),gemini_model="mock")
    settings.prompts_dir.mkdir()
    for path in (ROOT_DIR/"prompts").glob("director*.txt"):
        (settings.prompts_dir/path.name).write_text(path.read_text(encoding="utf-8"),encoding="utf-8")
    brief = fixture_brief()
    brief.facts = [brief.facts[0].model_copy(deep=True) for _ in range(16)]
    for index,fact in enumerate(brief.facts):
        fact.fact_vi = f"Thao tác dựng video ở công đoạn này giúp chọn đoạn cần giữ trước khi ghép. Người dựng có thể sắp xếp cảnh theo nhịp kể và kiểm tra lại từng đoạn. Chi tiết minh họa cho khâu dựng đã được nguồn nêu rõ."
    blueprint = story_blueprint(90,len(brief.facts))
    points = [{"id":i,"idea":name,"fact_ids":list(range(1,17))} for i,name in enumerate(["Bối cảnh","Diễn biến","Điểm khác","Ý nghĩa"],1)]
    outline = {"angle_index":1,"hook":"Bạn dựng video có đúng nhịp?","open_loop":"Chọn đoạn trước hay ghép trước?",
        "payoff":"Chọn đoạn trước khi ghép.","payoff_fact_ids":[1],"main_points":points,
        "scenes":[{"scene_id":row["id"],"point_id":min(4,(row["id"]-1)//3+1),"fact_ids":[1] if row["role"] in {"hook","cta"} else [row["id"]],"purpose":"Khai thác một chi tiết có căn cứ."} for row in blueprint]}
    openings = ["Đầu tiên","Sau đó","Riêng đoạn","Còn nhịp","Phần ghép","Ở đây","Chỗ này","Điểm khác","Với cảnh","Đến đoạn","Nhìn lại"]
    rows = []
    for index,row in enumerate(blueprint):
        narration = "Bạn dựng video có đúng nhịp?" if row["role"]=="hook" else "Mạch dựng bắt đầu từ chọn đoạn. Bạn muốn thử cách làm này chứ?" if row["role"]=="cta" else openings[index-1]+", bạn chọn đoạn cần giữ trước khi ghép. Bạn muốn xem bước tiếp theo chứ?"
        rows.append({"scene_id":row["id"],"narration":narration,"overlays":["Chọn đoạn trước"]*len(row["shot_durations_sec"]),"broll_query":"video editing"})
    written = {"title":"Nhịp dựng video","scenes":rows}
    final = {"scenes":deepcopy(rows),"approved":True,"issues":[]}
    return settings,brief,outline,written,final


class ThreePass:
    model_name = "story-mock"
    def __init__(self,outline,written,final):
        self.outline,self.written,self.final = outline,written,final
        self.calls=[]
        self.close=Mock()
    def generate_json(self,prompt,schema):
        self.calls.append((schema,prompt))
        value = self.outline if schema is StoryOutline else self.written if schema is WrittenScript else self.final
        if callable(value): value=value(prompt)
        return json.dumps(value,ensure_ascii=False)


def create(data,provider=None):
    settings,brief,outline,written,final=data
    provider = provider or ThreePass(outline,written,final)
    plan = create_edit_plan(brief,DirectorRequest(video_type="story",video_format="tiktok",duration_sec=90,script_style="storytelling"),provider,
        settings,JsonCache(settings.cache_dir),director_diagnostics(settings),lambda _:None)
    return plan,provider


def test_three_pass_90_seconds_has_correct_words_scenes_and_evidence(story_data):
    plan,provider=create(story_data)
    assert [schema for schema,_ in provider.calls]==[StoryOutline,WrittenScript,HumanizedScript]
    assert 11<=len(plan.scenes)<=14 and plan.duration_sec==pytest.approx(90)
    assert 216<=sum(len(s.narration.split()) for s in plan.scenes)<=252
    assert not style_issues(plan)
    assert all(s.fact_ids and all(1<=i<=len(story_data[1].facts) for i in s.fact_ids) for s in plan.scenes)
    assert all(s.narration.startswith("Theo Fixture,") for s in plan.scenes)
    assert plan.story_outline.open_loop and plan.story_outline.payoff_fact_ids


@pytest.mark.parametrize("duration,low,high",[(60,8,10),(90,11,14),(120,14,18)])
def test_scene_count_presets(duration,low,high):
    schedule=story_blueprint(duration,30)
    assert low<=len(schedule)<=high
    assert sum(sum(r["shot_durations_sec"]) for r in schedule)==pytest.approx(duration)
    assert all(1.5<=d<=4 for r in schedule for d in r["shot_durations_sec"])


def test_style_rejects_cliches_hook_and_keeps_grounding(story_data):
    plan,_=create(story_data)
    plan.scenes[0].narration="Chào mọi người, hôm nay chúng ta sẽ tìm hiểu."
    plan.scenes[1].narration="Có thể nói rằng nhiều người làm việc. Bạn muốn biết không?"
    assert 1 in style_issues(plan) and 2 in style_issues(plan)
    plan.scenes[1].fact_ids=[999]
    with pytest.raises(ValueError,match="fact_id không tồn tại"):
        validate_plan(plan,story_data[1],DirectorRequest(video_type="story",video_format="tiktok",duration_sec=90))


@pytest.mark.parametrize("raw,spoken",[("30%","ba mươi phần trăm"),("1 triệu token","một triệu token"),("$0.10","không phẩy một không đô la Mỹ")])
def test_spoken_numbers_preserve_numeric_grounding(raw,spoken):
    assert tts_text(raw)==spoken
    assert normalized_numbers(raw)==normalized_numbers(spoken)


def test_humanize_repairs_only_offending_scene(story_data):
    settings,brief,outline,written,final=story_data
    final=deepcopy(final)
    final["scenes"][2]["narration"]="Có thể nói rằng bạn chọn đoạn cần giữ trước khi ghép. Bạn muốn xem bước tiếp theo chứ?"
    attempt=0
    def human(prompt):
        nonlocal attempt
        attempt+=1
        if attempt==1: return final
        data=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1])
        assert data["selected_scene_ids"]==[3]
        return {"scenes":[written["scenes"][2]],"approved":True,"issues":[]}
    provider=ThreePass(outline,written,human)
    plan,_=create(story_data,provider)
    assert len(provider.calls)==3 and any(e.rule_id=="cliches" and e.group==3 for e in plan.validation_events)
    assert plan.scenes[1].narration.endswith(written["scenes"][1]["narration"])


def test_outline_invalid_fact_stops_before_writing(story_data):
    data=list(deepcopy(story_data))
    data[2]["scenes"][0]["fact_ids"]=[999]
    provider=ThreePass(data[2],data[3],data[4])
    with pytest.raises(DirectorDraftError,match="bản nháp"):
        create(data,provider)
    assert provider.calls[0][0] is StoryOutline and all(schema.__name__=="OutlineRepairs" for schema,_ in provider.calls[1:])


def test_thin_brief_recommends_shorter_duration():
    from agents.adaptive import duration_for_brief
    advice=data_advice(fixture_brief(),180)
    assert advice["thin"] and advice["suggested_duration"]==duration_for_brief(fixture_brief(),180)
    assert "dữ liệu mỏng, nên tăng số nguồn hoặc giảm thời lượng" in advice["warning"]


def test_rewrite_one_scene_preserves_facts_and_other_scenes(story_data,monkeypatch):
    plan,_=create(story_data)
    settings,brief,_,_,_=story_data
    project=settings.output_dir/"rewrite"
    write_json(project/"brief.json",brief.model_dump(mode="json"))
    write_json(project/"edit_plan.json",plan.model_dump(mode="json"))
    before=plan.model_dump(mode="json")
    scene=plan.scenes[2]
    result={"scenes":[{"scene_id":scene.id,"narration":scene.narration.replace("Riêng đoạn","Riêng cảnh"),"overlays":[s.text_overlay for s in scene.shots],"broll_query":"video editing"}],"approved":True,"issues":[]}
    provider=ThreePass(None,None,result)
    monkeypatch.setattr("agents.director.director_provider",lambda *args:provider)
    rewrite_script(project/"brief.json",settings,style="review",scene_id=scene.id)
    after=json.loads((project/"edit_plan.json").read_text(encoding="utf-8"))
    assert [s["fact_ids"] for s in after["scenes"]]==[s["fact_ids"] for s in before["scenes"]]
    assert all(a==b for a,b in zip(after["scenes"],before["scenes"]) if a["id"]!=scene.id)


@pytest.mark.parametrize("raw",["$1,200.50","$1.200,50","$1,234.50","1M token","1.2M token","75%"])
def test_tts_locale_numbers_preserve_value(raw):
    assert normalized_numbers(raw)==normalized_numbers(tts_text(raw))


def test_humanizer_cannot_approve_unsupported_claim(story_data):
    settings,brief,outline,written,final=story_data
    def reject(prompt):
        data=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1])
        selected=data["selected_scene_ids"]
        return {"scenes":[r for r in written["scenes"] if r["scene_id"] in selected],"approved":False,
            "issues":[{"scene_id":2,"reason":"Khẳng định không được fact hỗ trợ."}]}
    provider=ThreePass(outline,written,reject)
    with pytest.raises(DirectorDraftError): create(story_data,provider)
    draft=json.loads((settings.output_dir/"edit_plan.draft.json").read_text(encoding="utf-8"))
    assert draft["failed_scene_ids"]==[2] and draft["plan"]["scenes"]
    assert len([s for s,_ in provider.calls if s is HumanizedScript])==3


def test_cached_three_pass_plan_keeps_evidence_and_needs_no_extra_calls(story_data):
    plan,provider=create(story_data)
    again,_=create(story_data,provider)
    assert len(provider.calls)==3
    assert [s.fact_ids for s in again.scenes]==[s.fact_ids for s in plan.scenes]


@pytest.mark.parametrize("count",[1,2])
def test_three_real_director_passes_accept_one_or_two_facts(story_data,count):
    from agents.adaptive import duration_for_brief,fact_schedule,validate_reuse
    settings,brief,_,_,_=story_data
    brief.facts=brief.facts[:count]
    schedule=story_blueprint(duration_for_brief(brief,60),count)
    assigned=fact_schedule(schedule,count)
    outline={"angle_index":1,"hook":"Bạn ghép cảnh thế nào?","open_loop":"Chọn đoạn hay ghép trước?",
        "payoff":"Chọn đoạn trước khi ghép.","payoff_fact_ids":assigned[schedule[-1]["id"]],
        "main_points":[{"id":1,"idea":"Chọn đoạn trước khi ghép","fact_ids":list(range(1,count+1))}],
        "scenes":[{"scene_id":r["id"],"point_id":1,"fact_ids":assigned[r["id"]],"purpose":"Giải thích quy trình dựng."} for r in schedule]}
    narration=["Bạn ghép cảnh thế nào?","Đầu tiên, chọn đoạn cần giữ. Bạn hãy kiểm tra nhịp kể.",
        "Sau đó, ghép các cảnh theo thứ tự. Cách sắp xếp cần giữ mạch kể.","Bạn muốn thử cách chọn đoạn trước khi ghép chứ?"]
    rows=[{"scene_id":r["id"],"narration":narration[0] if i==0 else narration[-1] if i==len(schedule)-1 else narration[i],
        "overlays":["Chọn đoạn"]*len(r["shot_durations_sec"]),"broll_query":"video editing"} for i,r in enumerate(schedule)]
    provider=ThreePass(outline,{"title":"Quy trình dựng","scenes":rows},{"scenes":rows,"approved":True,"issues":[]})
    plan=create_edit_plan(brief,DirectorRequest(video_type="story",video_format="tiktok",duration_sec=60,script_style="storytelling"),
        provider,settings,JsonCache(settings.cache_dir),director_diagnostics(settings),lambda _:None)
    assert len(provider.calls)==3 and plan.duration_sec<60
    assert plan.requested_duration_sec==60 and plan.adaptive
    validate_reuse(plan.scenes)
    assert all(s.fact_ids for s in plan.scenes)
