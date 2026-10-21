"""Video titles never cause scene retries; checked pass-two fallback is local."""
from copy import deepcopy
from datetime import datetime
import json
from unittest.mock import Mock
import pytest
from agents.director import DirectorRequest,validate_plan,brief_hash,failing_scene_ids
from agents.director_title import title_numbers,ensure_title
from agents.director_story import humanize
from schemas.story import VideoTitle,HumanizedScript
from tests.test_storytelling import story_data,create,ThreePass


def plan_for(story_data):
    plan,_=create(story_data)
    return plan


def test_topic_version_current_year_and_month_are_video_scoped(story_data):
    plan=plan_for(story_data)
    settings,brief,_,_,_=story_data
    brief.topic="Sản phẩm thử nghiệm 5.5"
    plan.title="Sản phẩm thử nghiệm 5.5 trong tháng 10 năm 2026"
    assert not title_numbers(plan,brief,now=datetime(2026,10,21))["invalid"]
    plan.brief_hash=brief_hash(brief)
    provider=Mock()
    ensure_title(plan,brief,provider=provider,now=datetime(2026,10,21))
    provider.generate_json.assert_not_called()
    assert failing_scene_ids(ValueError("Tiêu đề chứa số liệu không có trong các fact được phép."),plan.model_dump())==set()


@pytest.mark.parametrize("source,title",[("0,10 đô","Giá $0.10"),("1 triệu","Quy mô 1M"),("75 phần trăm","Mức tăng 75%")])
def test_title_numbers_share_locale_and_spoken_normalization(story_data,source,title):
    plan=plan_for(story_data);brief=story_data[1]
    brief.facts[0].fact_vi=source;plan.title=title
    assert not title_numbers(plan,brief,now=datetime(2026,10,21))["invalid"]


def test_ordinal_count_must_match_actual_outline_items(story_data):
    plan=plan_for(story_data);brief=story_data[1]
    body_ids={s.id for s in plan.scenes if s.role=="body"}
    count=len({s.point_id for s in plan.story_outline.scenes if s.scene_id in body_ids})
    for title in (f"Top {count} cách dựng",f"{count} điều về dựng cảnh"):
        plan.title=title
        assert not title_numbers(plan,brief)["invalid"]
    brief.facts[0].fact_vi="Có 99 thao tác được nguồn mô tả."
    plan.title="Top 99 cách dựng"
    assert "99" in title_numbers(plan,brief)["invalid"]
    plan.title=f"Top {count} cách dựng giá ${count}"
    assert str(count) in title_numbers(plan,brief)["invalid"]


def test_invalid_title_gets_exactly_one_request_then_topic_fallback(story_data):
    plan=plan_for(story_data);brief=story_data[1]
    before=[s.model_dump(mode="json") for s in plan.scenes]
    plan.title="Giá 987654 đô"
    provider=Mock();provider.generate_json.return_value=json.dumps({"title":"Giá 999999 đô"})
    ensure_title(plan,brief,provider=provider)
    provider.generate_json.assert_called_once()
    prompt,schema=provider.generate_json.call_args.args
    assert schema is VideoTitle and "allowed_numbers" in prompt
    assert plan.title==brief.topic and plan.review_notes
    assert [s.model_dump(mode="json") for s in plan.scenes]==before


def test_bad_title_does_not_retry_any_scene(story_data):
    settings,brief,outline,written,final=story_data
    written=deepcopy(written);written["title"]="Bản tin giá 987654 đô"
    class Provider(ThreePass):
        def generate_json(self,prompt,schema):
            if schema is VideoTitle:
                self.calls.append((schema,prompt));return json.dumps({"title":"Bản tin giá 999999 đô"})
            return super().generate_json(prompt,schema)
    provider=Provider(outline,written,final)
    plan,_=create((settings,brief,outline,written,final),provider)
    assert len(provider.calls)==3
    assert sum(schema is HumanizedScript for schema,_ in provider.calls)==1
    assert sum(schema is VideoTitle for schema,_ in provider.calls)==0
    assert plan.title==brief.topic


def test_humanize_api_failure_uses_checked_pass_two(story_data):
    settings,brief,outline,written,final=story_data
    class Provider(ThreePass):
        def generate_json(self,prompt,schema):
            if schema is HumanizedScript:
                self.calls.append((schema,prompt));raise TimeoutError("mock humanize timeout")
            return super().generate_json(prompt,schema)
    provider=Provider(outline,written,final)
    plan,_=create(story_data,provider)
    assert set(plan.humanization_fallback_scene_ids)=={s.id for s in plan.scenes}
    assert any("lượt 2" in warning for warning in plan.review_notes)
    assert all(s.narration.endswith(row["narration"]) for s,row in zip(plan.scenes,written["scenes"]))
    validate_plan(plan,brief,DirectorRequest(video_type="story",video_format="tiktok",duration_sec=90))


def test_single_scene_failure_retries_only_it_and_keeps_other_rewrites(story_data):
    settings,brief,outline,written,final=story_data
    selections=[]
    def human(prompt):
        data=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1]);ids=data["selected_scene_ids"];selections.append(ids)
        rows=[deepcopy(row) for row in written["scenes"] if row["scene_id"] in ids]
        for row in rows:
            if row["scene_id"]==3:
                row["narration"]="Có thể nói rằng bạn chọn đoạn trước khi ghép. Bạn muốn thử không?"
            elif row["scene_id"]==4:
                row["narration"]=row["narration"].replace("Riêng đoạn","Riêng nhịp")
        return {"scenes":rows,"approved":True,"issues":[]}
    plan,_=create(story_data,ThreePass(outline,written,human))
    assert selections[1:]==[]
    assert not plan.humanization_fallback_scene_ids
    assert any(e.rule_id=="cliches" and e.scene_id==3 for e in plan.validation_events)
    assert "Có thể nói rằng" in plan.scenes[2].narration
    assert "Riêng nhịp" in plan.scenes[3].narration
    log=(settings.logs_dir/"director_errors.log").read_text(encoding="utf-8")
    assert "đối tượng=tiêu đề" in log and "đối tượng=cảnh 3" in log and "tập số" in log
