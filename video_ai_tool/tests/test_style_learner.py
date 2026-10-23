"""Reference style learning, grounding separation and orchestration without APIs."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from pydantic import SecretStr, ValidationError
from config.settings import Settings, ROOT_DIR
from schemas.style import StyleAnalysis, AnalysisRecord, StyleProfile, StyleRenderDefaults
from schemas.edit_plan import EditPlan
from pipeline.style_learner import analyze_one, analyze_batch, estimate_batch, VideoStyleProvider, inspect_video
from pipeline.style_profile import aggregate, save_profile, load_profile, guidance, copying_scenes, apply_defaults
from agents.director import DirectorRequest, create_edit_plan, director_diagnostics, validate_plan
from agents.story_style import story_blueprint
from agents.validation_rules import RuleViolation
from tests.test_director import fixture_brief, fixture_plan, FakeDirector
from tests.test_run_all import stages
from tests.test_storytelling import story_data, ThreePass
from tests.test_auto_category import discovered
from utils.cache import JsonCache


def observed():
    return StyleAnalysis(duration_sec=30,
        category_guess={"category_id":"cong-nghe","confidence":.85,"reason":"Ví dụ phân tích mock"},suggested_type="news",
        narrative_flow="hook → giải thích → kết",connective_phrases=["Nhưng điều đáng nói về {topic} là..."],scene_count=3,avg_scene_sec=10,
        scenes=[{"start_sec":start,"end_sec":end,"purpose":purpose,"narration_summary":"Tóm tắt một ý quan sát được trong video mẫu.","word_count":round((end-start)*2.6),"words_per_sec":2.6,
            "shot_count":max(1,round((end-start)/3)),"average_shot_sec":(end-start)/max(1,round((end-start)/3)),"visual_types":["stock b-roll"],"camera_effects":["zoom_in"],"overlays":[],"sfx":[],"music":"nhẹ",
            "transition_to_next":{"type":"fade","connective_template":"Nhưng điều đáng nói về {topic} là..." if purpose!="kết" else ""}}
            for start,end,purpose in [(0,3,"hook"),(3,27,"giải thích"),(27,30,"kết")]],
        transcript_outline=[{"start_sec": 0, "end_sec": 30, "summary": "Một vật thể chuyển động chậm giữa khu rừng yên tĩnh khi ánh nắng bắt đầu lên."}],
        hook={"technique": "Câu hỏi", "template": "Điều gì khiến {topic} khác biệt?", "word_count": 7},
        structure=[{"name": name, "duration_sec": seconds, "purpose": "Gợi tò mò" if name=="hook" else "Triển khai rồi kết", "transition": "cut"}
                   for name, seconds in [("hook",3),("body",24),("ending",3)]],
        narration_style={"pronouns":["mình","bạn"],"intimacy":"Gần gũi","average_sentence_words":12,
            "rhetorical_questions":"Mở đầu bằng câu hỏi","examples":"So sánh ngắn","catchphrases":[],
            "humor":"Nhẹ","words_per_sec":2.6,"voice_emotion":"Tò mò"},
        pacing={"average_shot_sec":3,"cuts_per_10_sec":3,"pattern_interrupts":[10,20],"rhythm":"Tăng dần"},
        visual_style={"types":["stock b-roll"],"transitions":["fade"],"camera_effects":["zoom_in"],"aspect_ratio":"9:16","colors":["warm"]},
        captions={"font_scale":.075,"mode":"word","highlight_color":"#FFAA00"},
        audio={"mood":"curious","music_volume":.12,"sfx_types":["pop"],"sfx_per_10_sec":1,"ducking":True},
        cta_ending={"technique":"Đặt câu hỏi","has_cta":True},
        strengths=["Hook nhanh","Nhịp rõ","Chữ dễ đọc"],weaknesses=["Chuyển ý hơi gấp"],
        reusable_rules=["Mở bằng câu hỏi", "Mỗi cảnh một ý", "Nối ý tự nhiên", "Giữ shot ngắn",
                        "Nhấn từ quan trọng", "Hạ nhạc khi nói", "Dùng ví dụ ngắn", "Kết bằng câu hỏi"])


def record(filename="a.mp4", file_hash="a"):
    return AnalysisRecord(filename=filename,file_hash=file_hash,notes_hash="notes",model="mock",prompt_hash="prompt",analysis=observed())


def profile(name="Khám phá khoa học"):
    return aggregate([record()],name)


@pytest.fixture
def style_settings(tmp_path,monkeypatch):
    settings=Settings(root_dir=tmp_path,gemini_api_key=SecretStr("fixture-style-secret"),gemini_model="mock",retry_attempts=1)
    settings.prompts_dir.mkdir()
    for path in (ROOT_DIR/"prompts").glob("director*.txt"):
        (settings.prompts_dir/path.name).write_text(path.read_text(encoding="utf-8"),encoding="utf-8")
    (settings.prompts_dir/"style_analyze.md").write_text((ROOT_DIR/"prompts/style_analyze.md").read_text(encoding="utf-8"),encoding="utf-8")
    folder=tmp_path/"assets/reference_videos";folder.mkdir(parents=True)
    (folder/"a.mp4").write_bytes(b"mock video bytes")
    monkeypatch.setattr("pipeline.style_learner.inspect_video",lambda path,settings:{"duration_sec":30.,"size_bytes":path.stat().st_size})
    return settings


def test_analysis_schema_valid_and_invalid():
    assert StyleAnalysis.model_validate_json(observed().model_dump_json()).duration_sec==30
    bad=observed().model_dump();bad["transcript_outline"][0]["end_sec"]=80
    recovered=StyleAnalysis.model_validate(bad)
    assert recovered.normalization_notes and all(p.end_sec<=recovered.duration_sec+1 for p in recovered.transcript_outline)
    bad=observed().model_dump();bad["captions"]["color"]="not a color"
    recovered=StyleAnalysis.model_validate(bad)
    assert recovered.captions.color is None and recovered.analysis_warnings
    assert "not a color" in recovered.captions.color_note


def test_hash_cache_avoids_second_upload_and_invalidates_notes(style_settings):
    provider=Mock();provider.analyze.return_value=observed()
    first=analyze_one(style_settings,"a.mp4",provider=provider)
    second=analyze_one(style_settings,"a.mp4",provider=provider)
    assert [first["status"],second["status"]]==["done","cached"]
    provider.analyze.assert_called_once()
    assert (style_settings.prompts_dir/"style_analyze.md").read_text(encoding="utf-8") in provider.analyze.call_args.args[1]
    saved=style_settings.root_dir/"assets/reference_videos/analysis/a.json"
    assert AnalysisRecord.model_validate_json(saved.read_text(encoding="utf-8")).file_hash
    (saved.parent.parent/"a.txt").write_text("Ghi chú mới",encoding="utf-8")
    analyze_one(style_settings,"a.mp4",provider=provider)
    assert provider.analyze.call_count==1
    analyze_one(style_settings,"a.mp4",provider=provider,force=True)
    assert provider.analyze.call_count==1  # Existing raw is immutable, including relearn.
    (saved.parent.parent/"a.mp4").write_bytes(b"changed video")
    analyze_one(style_settings,"a.mp4",provider=provider)
    assert provider.analyze.call_count==2


def test_rename_uses_same_hash_cache(style_settings):
    folder=style_settings.root_dir/"assets/reference_videos"
    (folder/"b.mp4").write_bytes((folder/"a.mp4").read_bytes())
    provider=Mock();provider.analyze.return_value=observed()
    analyze_one(style_settings,"a.mp4",provider=provider)
    assert analyze_one(style_settings,"b.mp4",provider=provider)["status"]=="cached"
    provider.analyze.assert_called_once()


def test_one_file_failure_does_not_break_batch_and_redacts_key(style_settings):
    folder=style_settings.root_dir/"assets/reference_videos";(folder/"b.mp4").write_bytes(b"second video")
    provider=Mock();provider.analyze.side_effect=[RuntimeError("API fixture-style-secret failed"),observed()]
    results=analyze_batch(style_settings,["a.mp4","b.mp4"],provider=provider)
    assert [r["status"] for r in results]==["failed","done"]
    assert "fixture-style-secret" not in json.dumps(results)
    assert "fixture-style-secret" not in (style_settings.logs_dir/"style_learner_errors.log").read_text(encoding="utf-8")


def test_estimate_no_api_and_max_batch(style_settings,monkeypatch):
    provider=Mock();monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",provider)
    estimate=estimate_batch(style_settings,["a.mp4"])
    assert 0<estimate["estimated_input_tokens"]<12000 and estimate["total_duration_sec"]==30
    provider.assert_not_called()
    with pytest.raises(ValueError,match="Tối đa"):
        estimate_batch(style_settings,[f"{i}.mp4" for i in range(6)])


def test_path_escape_is_rejected_without_upload(style_settings):
    provider=Mock()
    with pytest.raises(ValueError,match="Chọn file"):
        analyze_one(style_settings,"../a.mp4",provider=provider)
    provider.assert_not_called()


def test_real_size_and_duration_limits(tmp_path,monkeypatch):
    path=tmp_path/"large.mp4";path.write_bytes(b"x"*(1024*1024+1))
    settings=Settings(style_max_file_mb=1)
    with pytest.raises(ValueError,match="giới hạn 1 MB"): inspect_video(path,settings)
    path.write_bytes(b"mock")
    monkeypatch.setattr("pipeline.style_learner.subprocess.run",lambda *a,**k:SimpleNamespace(stderr=b"Duration: 00:20:00.00 Video: h264"))
    with pytest.raises(ValueError,match="vượt giới hạn"): inspect_video(path,settings)


@pytest.mark.parametrize("failed",[False,True])
def test_uploaded_file_deleted_on_success_and_generation_error(style_settings,monkeypatch,failed):
    llm=Mock();llm.client.files.upload.return_value=SimpleNamespace(name="files/mock",uri="https://example.com/mock",state=SimpleNamespace(name="ACTIVE"))
    llm.generate_media_json.return_value=observed().model_dump_json()
    if failed: llm.generate_media_json.side_effect=RuntimeError("network failure")
    monkeypatch.setattr("pipeline.style_learner.GeminiProvider",lambda settings:llm)
    provider=VideoStyleProvider(style_settings)
    if failed:
        with pytest.raises(RuntimeError): provider.analyze(style_settings.root_dir/"assets/reference_videos/a.mp4","prompt",lambda message:None)
    else:
        assert provider.analyze(style_settings.root_dir/"assets/reference_videos/a.mp4","prompt",lambda message:None).duration_sec==30
    llm.client.files.delete.assert_called_once_with(name="files/mock")
    provider.close();llm.close.assert_called_once()


def test_profile_deduplicates_per_video_and_sorts_frequency(style_settings):
    first,second=record(),record("b.mp4","b")
    second.analysis.reusable_rules=["Mở bằng câu hỏi.","Mở bằng câu hỏi",*second.analysis.reusable_rules[1:]]
    result=aggregate([first,second,deepcopy(second)],"Khám phá khoa học")
    assert len(result.reference_hashes)==2
    assert all(row.video_count==2 for row in result.rule_frequencies)
    assert len(result.reusable_rules)==8
    assert sum(s.fraction for s in result.structure)==pytest.approx(1)
    result.reusable_rules=["Quy tắc sửa tay"]
    save_profile(style_settings,result)
    assert load_profile(style_settings,result.slug).reusable_rules==["Quy tắc sửa tay"]
    assert "reference_texts" not in guidance(result)


def test_profile_chooses_majority_caption_instead_of_first_video():
    records=[record("a.mp4","a"),record("b.mp4","b"),record("c.mp4","c")]
    records[0].analysis.captions.mode="sentence"
    records[0].analysis.captions.color="#112233"
    result=aggregate(records,"Đa số")
    assert result.captions.mode=="word" and result.captions.color=="#FFFFFF"


def test_preset_changes_blueprint_not_fact_budget():
    preset=profile();preset.shot_seconds.mean=1.8
    rows=story_blueprint(90,12,preset)
    assert len(rows)>len(story_blueprint(90,12))
    assert len(rows)<=24 and all("style_section" in row for row in rows)
    assert sum(sum(r["shot_durations_sec"]) for r in rows)==pytest.approx(90)
    assert all(1.5<=d<=4 for r in rows for d in r["shot_durations_sec"])
    assert len(story_blueprint(30,1,preset))==2


def test_director_receives_guidance_without_transcript(style_settings):
    preset=profile();save_profile(style_settings,preset)
    provider=FakeDirector([fixture_plan()])
    request=DirectorRequest(script_style=None,video_type="review",video_format="tiktok",duration_sec=45,style_preset=preset.slug)
    plan=create_edit_plan(fixture_brief(),request,provider,style_settings,JsonCache(style_settings.cache_dir),director_diagnostics(style_settings),lambda m:None)
    prompt=next(prompt for schema,prompt in provider.prompts if schema is EditPlan)
    data=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1])
    assert data["style_profile"]["reusable_rules"]==preset.reusable_rules
    assert "reference_texts" not in data["style_profile"]
    assert all(preset.reference_texts[0] not in prompt for _,prompt in provider.prompts)
    assert plan.style_preset==preset.slug and plan.render_style.captions.mode=="word"
    assert plan.music.volume==.12


def test_copied_sentence_is_hard_and_only_that_scene(style_settings):
    raw=fixture_plan();preset=profile();plan=EditPlan.model_validate(raw)
    apply_defaults(plan,preset)
    plan.scenes[1].narration=preset.reference_texts[0]
    assert copying_scenes(plan)[0][0]==2
    with pytest.raises(RuleViolation) as error:
        validate_plan(plan,fixture_brief(),DirectorRequest(video_type="review",video_format="tiktok",duration_sec=45))
    assert any(e.rule_id=="originality" and e.scene_id==2 for e in error.value.events)
    assert not copying_scenes(EditPlan.model_validate(raw))


def test_copied_scene_retry_preserves_all_other_scenes(story_data):
    settings,brief,outline,written,final=story_data
    preset=profile();preset.shot_seconds.mean=90/(2*len(written["scenes"]))
    written=deepcopy(written)
    copied="Người dựng có thể sắp xếp cảnh theo nhịp kể và kiểm tra lại từng đoạn."
    written["scenes"][2]["narration"]=copied
    preset.reference_texts=[copied]
    selected=[]
    def human(prompt):
        data=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1]);ids=data["selected_scene_ids"];selected.append(ids)
        rows=[deepcopy(r) for r in written["scenes"] if r["scene_id"] in ids]
        if len(selected)>1:
            rows[0]["narration"]="Bạn sắp xếp cảnh theo mạch kể. Mỗi đoạn được kiểm tra trước khi nối tiếp."
        return {"scenes":rows,"approved":True,"issues":[]}
    provider=ThreePass(outline,written,human)
    plan=create_edit_plan(brief,DirectorRequest(video_type="story",video_format="tiktok",duration_sec=90,
        style_profile=preset,style_preset=preset.slug),provider,settings,JsonCache(settings.cache_dir),director_diagnostics(settings),lambda m:None)
    assert selected[1:]==[[3]]
    assert plan.scenes[0].narration.endswith(written["scenes"][0]["narration"])
    assert not copying_scenes(plan)


def test_run_all_passes_selected_preset(stages,monkeypatch):
    from pipeline.run_all import RunConfig, run_all
    import pipeline.run_all as module
    settings,calls,failures,inputs=stages
    actual=module.run_director;seen=[]
    def director(path,settings,**kwargs):
        seen.append(kwargs["style_preset"])
        return actual(path,settings,**kwargs)
    monkeypatch.setattr(module,"run_director",director)
    project=run_all(RunConfig(topic="Preset fixture",style_preset="khoa-hoc"),settings=settings)
    assert seen==["khoa-hoc"] and "render" in calls
    assert json.loads((project/"run_state.json").read_text(encoding="utf-8"))["config"]["style_preset"]=="khoa-hoc"


def test_style_model_fallback():
    assert Settings(gemini_model="base").require_style_model()=="base"
    assert Settings(gemini_model="base",gemini_style_model="video-model").require_style_model()=="video-model"


def test_edit_plan_wire_schema_excludes_reference_snapshot():
    from providers.style_schema import response_schema
    wire=response_schema(EditPlan)
    assert "style_profile" not in wire["properties"]
    assert "StyleProfile" not in wire.get("$defs",{})
    assert "reference_texts" not in json.dumps(wire)
    assert response_schema(StyleAnalysis)["properties"]["transcript_outline"]


def test_category_passes_preset_and_keeps_it_on_resume(stages,discovered,monkeypatch):
    from pipeline.auto_category import run_auto
    import pipeline.run_all as module
    settings,calls,_,_=stages;seen=[];actual=module.run_director
    def director(path,settings,**kwargs):
        seen.append(kwargs["style_preset"])
        return actual(path,settings,**kwargs)
    monkeypatch.setattr(module,"run_director",director)
    project=run_auto("công nghệ",duration=45,settings=settings,style_preset="khoa-hoc",review=True)
    state=json.loads((project/"run_state.json").read_text(encoding="utf-8"))
    assert state["auto_category"]["config"]["style_preset"]=="khoa-hoc"
    run_auto(resume=project,settings=settings)
    assert seen==["khoa-hoc"] and "render" in calls


def test_manual_render_edits_survive_validation_and_profile_reload(style_settings):
    plan=EditPlan.model_validate(fixture_plan());preset=profile()
    apply_defaults(plan,preset)
    plan.render_style.captions.font_scale=.09
    plan.music.volume=.04
    plan.scenes[1].shots[0].effect="pan_right"
    restored=EditPlan.model_validate_json(plan.model_dump_json())
    validate_plan(restored,fixture_brief(),DirectorRequest(video_type="review",video_format="tiktok",duration_sec=45),allow_merge=False)
    assert restored.render_style.captions.font_scale==.09 and restored.music.volume==.04
    assert restored.scenes[1].shots[0].effect=="pan_right"
