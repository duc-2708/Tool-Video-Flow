"""Project-level pass recovery without another outline/write request."""
import json
from unittest.mock import Mock
import pytest
from agents.director import create_edit_plan,DirectorRequest,DirectorDraftError,director_diagnostics
from providers.llm_gemini import GeminiTransientError
from schemas.story import StoryOutline,WrittenScript,HumanizedScript
from tests.test_storytelling import story_data,ThreePass
from utils.cache import JsonCache


def invoke(data,provider,project):
    settings,brief,_,_,_=data
    return create_edit_plan(brief,DirectorRequest(video_type="story",video_format="tiktok",duration_sec=90,script_style="storytelling"),
        provider,settings,JsonCache(settings.cache_dir),director_diagnostics(settings),lambda message:None,draft_path=project/"edit_plan.draft.json")


@pytest.mark.parametrize("failed_schema,expected",[(WrittenScript,[WrittenScript,HumanizedScript]),(HumanizedScript,[HumanizedScript])])
def test_resume_only_calls_failed_and_later_passes(story_data,failed_schema,expected):
    settings,brief,outline,written,final=story_data
    project=settings.output_dir/"project"
    class Failing(ThreePass):
        def generate_json(self,prompt,schema):
            if schema is failed_schema: raise GeminiTransientError(504,"Mock retry budget exhausted")
            return super().generate_json(prompt,schema)
    with pytest.raises(DirectorDraftError): invoke(story_data,Failing(outline,written,final),project)
    state=json.loads((project/"director_state.json").read_text(encoding="utf-8"))
    assert state["stages"]["outline"]["status"]=="done"
    if failed_schema is HumanizedScript: assert state["stages"]["written"]["status"]=="done"
    assert (project/"edit_plan.draft.json").exists()
    resumed=ThreePass(outline,written,final)
    result=invoke(story_data,resumed,project)
    assert [schema for schema,_ in resumed.calls]==expected
    assert result.scenes and all(s.fact_ids for s in result.scenes)
    state=json.loads((project/"director_state.json").read_text(encoding="utf-8"))
    assert state["stages"]["humanized"]["status"]=="done" and "error" not in state


def test_changed_brief_invalidates_old_passes(story_data):
    settings,brief,outline,written,final=story_data
    project=settings.output_dir/"changed"
    class Failing(ThreePass):
        def generate_json(self,prompt,schema):
            if schema is WrittenScript: raise GeminiTransientError(504,"mock")
            return super().generate_json(prompt,schema)
    with pytest.raises(DirectorDraftError): invoke(story_data,Failing(outline,written,final),project)
    brief.topic+=" phiên bản cập nhật"
    fresh=ThreePass(outline,written,final)
    invoke(story_data,fresh,project)
    assert [schema for schema,_ in fresh.calls]==[StoryOutline,WrittenScript,HumanizedScript]


def test_tampered_checkpoint_is_not_reused(story_data):
    from agents.director_state import DirectorState
    from utils.atomic_io import write_json_atomic
    settings,brief,outline,_,_=story_data
    path=settings.output_dir/"tamper/director_state.json"
    state=DirectorState(path,{"input":"fixed"},director_diagnostics(settings),Mock())
    state.save("outline",StoryOutline.model_validate(outline))
    edited=json.loads(path.read_text(encoding="utf-8"));edited["stages"]["outline"]["data"]["hook"]="altered"
    write_json_atomic(path,edited)
    state=DirectorState(path,{"input":"fixed"},director_diagnostics(settings),Mock())
    assert state.load("outline",StoryOutline) is None
