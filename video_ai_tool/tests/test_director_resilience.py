"""Scene-only repair, warning metadata and recoverable drafts. Offline."""
import json
from copy import deepcopy
from unittest.mock import Mock
import pytest
from agents.director import (content_scene_count,timing_blueprint,numbers,validate_plan,DirectorRequest,
    create_edit_plan,DirectorDraftError,SceneRepairs,fill_missing_facts,director_diagnostics)
from config.settings import Settings
from schemas.edit_plan import EditPlan
from utils.cache import JsonCache
from tests.test_director import fixture_brief,fixture_plan,FakeDirector,director_settings


def test_four_facts_reduce_content_scenes_but_keep_exact_duration():
    assert content_scene_count(45,4) == 4
    schedule = timing_blueprint(45,4)
    assert len([scene for scene in schedule if scene["role"] == "body"]) == 4
    assert sum(sum(scene["shot_durations_sec"]) for scene in schedule) == pytest.approx(45)
    assert all(1.5<=duration<=4 for scene in schedule for duration in scene["shot_durations_sec"])


@pytest.mark.parametrize("a,b",[("$0.10","0,10 đô"),("1M","1 triệu"),("1 triệu","1.000.000"),("75%","75 phần trăm"),("Model 5.5","Model 5,5")])
def test_numeric_normalization(a,b):
    assert numbers(a) == numbers(b)


def test_missing_fact_and_unknown_number_warn_instead_of_raising():
    brief = fixture_brief()
    brief.facts *= 4
    plan = EditPlan.model_validate(fixture_plan())
    plan.scenes[1].narration += " Mức phí 0,10 đô."
    with pytest.raises(ValueError,match="grounding_numbers"):
        validate_plan(plan,brief,DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45))


def test_number_without_any_referenced_fact_still_raises():
    plan = EditPlan.model_validate(fixture_plan())
    plan.scenes[-1].narration = "Mức giá 999 đô."
    with pytest.raises(ValueError,match="grounding_numbers"):
        validate_plan(plan,fixture_brief(),DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45))


def test_add_unused_fact_is_metadata_repair_not_narration_rewrite(tmp_path):
    brief = fixture_brief()
    brief.facts = [brief.facts[0].model_copy(deep=True) for _ in range(16)]
    plan = EditPlan.model_validate(fixture_plan())
    before = [scene.narration for scene in plan.scenes]
    fill_missing_facts(plan,brief,director_diagnostics(Settings(root_dir=tmp_path)))
    assert all(len(scene.fact_ids)>=1 for scene in plan.scenes if scene.role == "body")
    assert [scene.narration for scene in plan.scenes] == before


def test_retry_only_replaces_failed_scene(director_settings):
    bad,good = fixture_plan(),fixture_plan()
    bad["scenes"][1]["narration"] = "Đây là sản phẩm tốt nhất."
    good["scenes"][0]["narration"] = "Cảnh đã đạt không được thay đổi."
    provider = FakeDirector([bad,good],[{"approved":False,"issues":["Cảnh 2 không có căn cứ so sánh."]},{"approved":True,"issues":[]}])
    plan = create_edit_plan(fixture_brief(),DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45),provider,
        director_settings,JsonCache(director_settings.cache_dir),director_diagnostics(director_settings),lambda _:None)
    assert plan.scenes[0].narration.endswith(bad["scenes"][0]["narration"])
    assert plan.scenes[1].narration.endswith(good["scenes"][1]["narration"])
    repair_prompt = next(prompt for schema,prompt in provider.prompts if schema is SceneRepairs)
    payload = json.loads(repair_prompt.split("INPUT_DATA_JSON:\n")[1])
    assert [item["scene"]["id"] for item in payload["failed_scenes"]] == [2]
    assert "allowed_numbers" in payload["failed_scenes"][0]


def test_exhaustion_preserves_draft_and_last_error(director_settings,tmp_path):
    provider = FakeDirector([fixture_plan()],[{"approved":False,"issues":["Cảnh 2 có khẳng định chưa được fact hỗ trợ."]}])
    director_settings = director_settings.model_copy(update={"retry_attempts":8})
    path = tmp_path/"project/edit_plan.draft.json"
    with pytest.raises(DirectorDraftError,match="bản nháp"):
        create_edit_plan(fixture_brief(),DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45),provider,
            director_settings,JsonCache(director_settings.cache_dir),director_diagnostics(director_settings),lambda _:None,draft_path=path)
    draft = json.loads(path.read_text(encoding="utf-8"))
    assert draft["attempts"] == 3 and provider.plan_calls == 3
    assert draft["plan"]["scenes"] and draft["warnings"] and draft["failed_scene_ids"] == [2]
    assert draft["status"] == "draft_requires_review"
    assert not (path.parent/"edit_plan.json").exists()
