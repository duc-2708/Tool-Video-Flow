"""Reference identity isolation, canonical numbers and the exact reported draft."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from config.settings import ROOT_DIR
from agents.director import validate_plan,DirectorRequest
from agents.director_numbers import normalized_numbers
from agents.director_sources import allowed_sources,canonical_sources
from agents.validation_rules import Context,unsupported_numbers,names_quotes,RuleViolation,groups
from agents.vietnamese_tts import spoken_to_digits,tts_text
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from tests.test_director import fixture_plan,fixture_brief
from tests.test_storytelling import story_data,ThreePass,create
from tests.test_style_learner import record,profile
from pipeline.style_profile import aggregate,guidance,save_profile,load_profile
from pipeline.style_safety import sanitize_profile,template_text


@pytest.mark.parametrize("raw,expected",[
    ("hai mươi bốn",{"24"}),("Hai mươi bốn",{"24"}),("hai mươi bốnh",{"24"}),
    ("một triệu",{"1000000"}),("75 phần trăm",{"75%"}),("bảy mươi lăm phần trăm",{"75%"}),
    ("1/2026",{"1","2026"}),("10/2026",{"10","2026"}),("1.2026",{"1","2026"}),
    ("21/10/2026",{"21","10","2026"}),("21.10.2026",{"21","10","2026"}),("21-10-2026",{"21","10","2026"}),
    ("tháng 10 năm 2026",{"10","2026"}),("tháng một năm hai nghìn không trăm hai mươi sáu",{"1","2026"}),
    ("ngày hai mươi mốt tháng mười năm hai nghìn không trăm hai mươi sáu",{"21","10","2026"}),
    ("1.000",{"1000"}),("1,5",{"1.5"}),("0,10",{"0.1"}),("$0.10",{"0.1"}),("1M",{"1000000"})])
def test_numbers_keep_calendar_boundaries_and_full_spoken_runs(raw,expected):
    actual=normalized_numbers(raw,ignore_current_year=False)
    assert actual==expected and "12026" not in actual
    if "hai mươi bốn" in raw.casefold() or "bốnh" in raw: assert "20" not in actual


def test_spoken_alias_only_resolves_to_an_authorized_source():
    brief=fixture_brief();brief.facts[0].source_name="Tin tức 24h"
    text="Theo Tin tức 24h, Theo Tin tức hai mươi bốnh, có thể cắt và ghép video."
    assert canonical_sources(text,brief)=="Theo Tin tức 24h, có thể cắt và ghép video."
    other=fixture_brief()
    assert canonical_sources(text,other)==text


def test_exact_reported_draft_loses_false_12026_and_20_but_does_not_rewrite_files():
    project=ROOT_DIR/"output/auto-tin-tuc-ee3f1898"
    path=project/"edit_plan.draft.json"
    if not path.exists(): pytest.skip("Reported local draft is not present")
    original=path.read_bytes()
    brief=ResearchBrief.model_validate_json((project/"brief.json").read_text(encoding="utf-8"))
    plan=EditPlan.model_validate(json.loads(original)["plan"])
    request=DirectorRequest(video_type=plan.video_type or "news",video_format=plan.format,duration_sec=plan.target_duration_sec or plan.duration_sec)
    validate_plan(plan,brief,request,allow_merge=False)
    assert not unsupported_numbers(Context(plan,brief))
    assert not names_quotes(Context(plan,brief))
    scene=next(s for s in plan.scenes if s.id==7)
    assert "hai mươi bốnh" not in scene.narration
    # Actual brief contains Tin tức 24h. Removing that source must reinstate
    # the hard error, rather than silently accepting a reference-channel name.
    unauthorised=brief.model_copy(deep=True)
    unauthorised.facts=[f for f in unauthorised.facts if "24h" not in (f.source_name+str(f.source_url)).casefold()]
    findings=names_quotes(Context(plan,unauthorised))
    assert any(f.scene_id==7 and "Nguồn trích dẫn" in f.message for f in findings)
    assert groups()["grounding_names_quotes"]==1
    assert path.read_bytes()==original


def test_source_names_are_exact_not_names_merely_mentioned_by_a_fact():
    brief=fixture_brief();brief.facts[0].claim+=" Reuters là ví dụ minh họa."
    plan=EditPlan.model_validate(fixture_plan());plan.scenes[1].narration="Theo Reuters, có thể cắt và ghép video."
    assert any("Nguồn trích dẫn" in f.message for f in names_quotes(Context(plan,brief)))


def test_source_with_ampersand_and_spoken_conjunction_is_one_authorized_name():
    brief=fixture_brief();brief.facts[0].source_name="Báo điện tử Thể thao & Văn hóa"
    plan=EditPlan.model_validate(fixture_plan())
    plan.scenes[1].narration="Theo Báo điện tử Thể thao và Văn hóa, có thể cắt và ghép video."
    assert not names_quotes(Context(plan,brief))
    assert "Thể thao & Văn hóa" in canonical_sources(plan.scenes[1].narration,brief)


def test_product_version_requires_whole_name_in_topic_or_brief():
    brief=fixture_brief();brief.topic="Model 5.5"
    plan=EditPlan.model_validate(fixture_plan())
    plan.scenes[1].narration="Model 5.5 có thể cắt và ghép video."
    assert not unsupported_numbers(Context(plan,brief)) and not names_quotes(Context(plan,brief))
    plan.scenes[1].narration="Giá 5.5 đô."
    assert any("5.5" in f.message for f in unsupported_numbers(Context(plan,brief)))
    plan.scenes[1].narration="Model 6.6 có thể cắt video."
    assert unsupported_numbers(Context(plan,brief))
    brief.topic="Giá USD 5.5"
    plan.scenes[1].narration="Giá USD 5.5."
    assert unsupported_numbers(Context(plan,brief))


def test_humanizer_source_retry_uses_brief_allowlist_and_only_failed_scene(story_data):
    settings,brief,outline,written,final=story_data
    count=0
    def result(prompt):
        nonlocal count
        count+=1
        payload=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1])
        assert payload["allowed_sources"]==allowed_sources(brief)
        if count==1:
            bad=deepcopy(final)
            bad["scenes"][6]["narration"]="Theo Tin tức 24h, "+bad["scenes"][6]["narration"]
            return bad
        assert payload["selected_scene_ids"]==[7]
        row=deepcopy(written["scenes"][6]);row["narration"]="Theo "+payload["allowed_sources"][0]+", "+row["narration"]
        return {"scenes":[row],"approved":True,"issues":[]}
    plan,provider=create(story_data,ThreePass(outline,written,result))
    assert count==2 and "Tin tức 24h" not in plan.scenes[6].narration
    for _,prompt in provider.calls:
        data=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1])
        assert data["allowed_sources"]==allowed_sources(brief)


def test_style_aggregation_replaces_entities_numbers_and_old_profiles_are_sanitized():
    sample=record()
    sample.analysis.entities_in_video=["Elon Musk","SpaceX","Hà Nội","Reuters"]
    sample.analysis.transcript_outline[0].summary="Elon Musk présente SpaceX tại Hà Nội, Reuters đưa giá 75 đô."
    sample.analysis.hook.template="{topic}: Elon Musk và SpaceX tại Hà Nội, giá 75 đô."
    sample.analysis.reusable_rules=["Theo Reuters, Elon Musk dùng SpaceX tại Hà Nội với giá 75 đô.","Mỗi cảnh một ý"]
    sample.analysis.scenes[0].purpose="Giới thiệu SpaceX ở Hà Nội"
    sample.analysis.scenes[0].transition_to_next.connective_template="Theo Reuters, SpaceX tăng 75 phần trăm."
    result=aggregate([sample],"Mẫu SpaceX")
    from pipeline.category_style import enrich
    result=enrich(result,[sample])
    assert any("Elon Musk" in t for t in result.reference_texts)  # local anti-copy corpus remains intact
    sent=json.dumps(guidance(result),ensure_ascii=False)
    for entity in ("Elon Musk","SpaceX","Hà Nội","Reuters","Mẫu SpaceX"):
        assert entity not in sent
    assert "75" not in json.dumps(result.reusable_rules+result.hook_templates,ensure_ascii=False)
    assert "{source}" in sent and "{topic}" in sent and "{number}" in sent
    old=profile();old.connective_phrases=["Theo Reuters, SpaceX tăng 75 đô."]
    assert "Reuters" not in json.dumps(guidance(old),ensure_ascii=False)
    assert "Reuters" in old.connective_phrases[0]  # guidance makes a copy
    assert template_text("Nhưng điều đáng nói về {topic} là...")=="Nhưng điều đáng nói về {topic} là..."
    assert template_text("Chưa đầy một ngày sau")=="Chưa đầy {number} ngày sau"
    assert template_text("Mỗi cảnh một ý")=="Mỗi cảnh một ý"


def test_no_tts_conversion_is_fed_into_director_validation(story_data,monkeypatch):
    settings,brief,outline,written,final=story_data
    for f in brief.facts: f.fact_vi+=" Tỷ lệ 30% được ghi nhận."
    written=deepcopy(written);final=deepcopy(final)
    written["scenes"][1]["narration"]+=" Tỷ lệ 30%."
    final["scenes"][1]["narration"]+=" Tỷ lệ 30%."
    converter=Mock(side_effect=AssertionError("Director must validate canonical narration"))
    monkeypatch.setattr("agents.vietnamese_tts.tts_text",converter)
    plan,_=create((settings,brief,outline,written,final))
    assert "30%" in plan.scenes[1].narration
    converter.assert_not_called()


def test_tts_keeps_authorized_numeric_names_and_reads_dates_after_validation():
    spoken=tts_text("Theo Tin tức 24h, Model 5.5 tăng 30% ngày 21/10/2026.",protected_names=["Tin tức 24h","Model 5.5"])
    assert "Tin tức 24h" in spoken and "Model 5.5" in spoken
    assert "ba mươi phần trăm" in spoken and "hai mươi mốt tháng mười năm" in spoken
    assert "hai mươi bốnh" not in spoken


def test_assets_converts_only_audio_input_and_preserves_validated_plan(tmp_path):
    from config.settings import Settings
    from pipeline.assets import run_assets
    from utils.atomic_io import write_json_atomic
    brief=fixture_brief();brief.facts[0].source_name="Tin tức 24h"
    brief.facts[0].claim+=" Mức tăng 30%."
    plan=EditPlan.model_validate(fixture_plan())
    plan.scenes[0].narration="Theo Tin tức 24h, mức tăng 30%."
    validate_plan(plan,brief,DirectorRequest(video_type="news",video_format="tiktok",duration_sec=45))
    path=tmp_path/"output/audio-boundary/edit_plan.json"
    write_json_atomic(path,plan.model_dump(mode="json"))
    write_json_atomic(path.parent/"brief.json",brief.model_dump(mode="json"))
    original=path.read_bytes();inputs=[]
    class TTS:
        def synthesize(self,text,voice,destination):
            inputs.append(text)
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(b"mock-audio")
            return 2.2
    run_assets(path,Settings(root_dir=tmp_path),tts=TTS(),providers=[])
    assert "Tin tức 24h" in inputs[0] and "ba mươi phần trăm" in inputs[0]
    assert path.read_bytes()==original
    assert "30%" in json.loads(original)["scenes"][0]["narration"]
