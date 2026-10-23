"""Category references, detailed scene profiles and automatic selection, offline."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest
from config.categories import resolve_category
from config.settings import ROOT_DIR
from schemas.style import StyleAnalysis
from schemas.edit_plan import EditPlan
from pipeline.style_learner import analyze_one,analyze_batch,reference_dir
from pipeline.style_library import list_videos,record_path,read_record,confirm_category,save_upload
from pipeline.category_style import rebuild_category,resolve_profile,save_category_edits,profile_file,choose_profile,token,compare_plan
from pipeline.style_profile import guidance,copying_scenes
from agents.story_style import story_blueprint,style_issues
from agents.director import DirectorRequest,create_edit_plan,director_diagnostics
from tests.test_style_learner import style_settings,observed
from tests.test_storytelling import story_data,ThreePass
from tests.test_run_all import stages
from tests.test_director import fixture_plan
from tests.test_create_video_ui import setup_manager
from utils.cache import JsonCache,write_json


@pytest.fixture
def category_settings(style_settings):
    data={"categories":[{"id":identity,"name":name,"enabled":True,"keywords_vi":[name],"keywords_en":["news"],"rss":[],"suggested_type":kind}
        for identity,name,kind in [("cong-nghe","công nghệ","news"),("du-lich","du lịch","story")]]}
    write_json(style_settings.root_dir/"config/categories.yaml",data)
    return style_settings


def add_video(settings,name,*,category="cong-nghe",kind="news",analysis=None):
    folder=reference_dir(settings)/category
    folder.mkdir(exist_ok=True)
    (folder/name).write_bytes((category+name).encode())
    result=analysis or observed()
    result.suggested_type=kind
    provider=Mock();provider.analyze.return_value=result
    relative=category+"/"+name
    analyze_one(settings,relative,provider=provider)
    return relative


def test_category_id_aliases_and_folder_classification(category_settings):
    settings=category_settings
    assert resolve_category(settings,"công nghệ").category_id=="cong-nghe"
    add_video(settings,"a.mp4")
    add_video(settings,"a.mp4",category="du-lich")
    (reference_dir(settings)/"_unsorted").mkdir()
    (reference_dir(settings)/"_unsorted/free.mp4").write_bytes(b"free")
    assert list_videos(settings,"công nghệ")==["cong-nghe/a.mp4"]
    assert set(list_videos(settings,"_unsorted"))=={"a.mp4","_unsorted/free.mp4"}
    assert record_path(settings,"du-lich/a.mp4")!=record_path(settings,"cong-nghe/a.mp4")
    assert read_record(settings,"cong-nghe/a.mp4").category_confirmed


def test_guess_does_not_move_until_confirmation_and_moves_notes(category_settings):
    settings=category_settings
    source=reference_dir(settings)/"a.mp4"
    source.with_suffix(".txt").write_text("Ghi chú tay",encoding="utf-8")
    provider=Mock();provider.analyze.return_value=observed()
    analyze_one(settings,"a.mp4",provider=provider)
    assert source.is_file() and not read_record(settings,"a.mp4").category_confirmed
    # User may override Gemini's technology guess to travel.
    new_name=confirm_category(settings,"a.mp4","du lịch")
    assert new_name=="du-lich/a.mp4" and not source.exists()
    destination=reference_dir(settings)/new_name
    assert destination.with_suffix(".txt").read_text(encoding="utf-8")=="Ghi chú tay"
    record=read_record(settings,new_name)
    assert record.category_id=="du-lich" and record.category_confirmed
    assert analyze_one(settings,new_name,provider=provider)["status"]=="cached"
    provider.analyze.assert_called_once()


def test_confirm_never_overwrites_existing_video(category_settings):
    settings=category_settings
    add_video(settings,"a.mp4")
    provider=Mock();provider.analyze.return_value=observed()
    analyze_one(settings,"a.mp4",provider=provider)
    with pytest.raises(FileExistsError): confirm_category(settings,"a.mp4","cong-nghe")
    assert (reference_dir(settings)/"a.mp4").exists()


def test_upload_is_local_confined_and_has_no_api_call(category_settings):
    settings=category_settings
    name=save_upload(settings,"uploaded.mp4",b"video bytes","công nghệ")
    assert name=="cong-nghe/uploaded.mp4"
    with pytest.raises(FileExistsError): save_upload(settings,"uploaded.mp4",b"new", "cong-nghe")
    with pytest.raises(ValueError): save_upload(settings,"../outside.mp4",b"bad")


@pytest.mark.parametrize("case",["backwards","overlap"])
def test_detailed_scene_schema_repairs_inconsistent_timings(case):
    data=observed().model_dump(mode="json")
    if case=="backwards": data["scenes"][0]["end_sec"]=0
    elif case=="overlap": data["scenes"][1]["start_sec"]=1
    elif case=="duration": data["scenes"][-1]["end_sec"]=35
    elif case=="count": data["scene_count"]=9
    else: data["avg_scene_sec"]=99
    result=StyleAnalysis.model_validate(data)
    assert result.analysis_warnings
    assert all(s.end_sec>s.start_sec for s in result.scenes)
    assert all(a.end_sec<=b.start_sec for a,b in zip(result.scenes,result.scenes[1:]))


def test_unknown_category_guess_warns_without_discarding_observations(category_settings):
    settings=category_settings
    (reference_dir(settings)/"b.mp4").write_bytes(b"different")
    bad=observed();bad.category_guess.category_id="invented"
    provider=Mock();provider.analyze.side_effect=[bad,observed()]
    results=analyze_batch(settings,["a.mp4","b.mp4"],provider=provider)
    assert [r["status"] for r in results]==["done","done"]
    assert results[0]["analysis"]["category_guess"] is None
    assert any("category_guess" in w for w in results[0]["warnings"])


def test_rebuild_confidence_duration_table_and_deduplicated_connectors(category_settings):
    settings=category_settings
    for i in range(3):
        analysis=observed();analysis.connective_phrases*=2
        add_video(settings,f"sample{i}.mp4",analysis=analysis)
    profile=rebuild_category(settings,"công nghệ")
    assert profile.video_count==3 and profile.confidence_label=="ổn"
    assert profile_file(settings,"cong-nghe").is_file()
    assert [r.duration_sec for r in profile.scene_pacing][:3]==[30,60,90]
    assert [r.scene_count for r in profile.scene_pacing][:3]==[3,6,9]
    assert len(profile.connective_phrases)==1 and profile.connective_frequencies[0].video_count==3
    assert profile.narrative_flows and profile.scene_patterns
    assert all(sum(r.durations_sec)==pytest.approx(r.duration_sec) for r in profile.scene_pacing)
    assert "reference_texts" not in guidance(profile)


def test_hash_rebuild_on_add_delete_and_locked_edits_survive(category_settings):
    settings=category_settings
    first=add_video(settings,"first.mp4")
    profile=rebuild_category(settings,"cong-nghe")
    path=profile_file(settings,"cong-nghe");before=path.read_bytes()
    assert rebuild_category(settings,"cong-nghe").source_signature==profile.source_signature
    assert path.read_bytes()==before
    save_category_edits(settings,"cong-nghe",reusable_rules=["Quy tắc tay đã khóa"],connective_phrases=["Cụm tự sửa"],locked_fields=["reusable_rules"])
    second=add_video(settings,"second.mp4")
    changed=rebuild_category(settings,"cong-nghe")
    assert changed.source_signature!=profile.source_signature and changed.video_count==2
    assert changed.reusable_rules==["Quy tắc tay đã khóa"]
    assert changed.connective_phrases!=["Cụm tự sửa"]
    (reference_dir(settings)/second).unlink()
    refreshed=rebuild_category(settings,"cong-nghe")
    assert refreshed.video_count==1 and refreshed.confidence_label=="yếu"
    assert refreshed.reference_files==[first]
    assert rebuild_category(settings,"cong-nghe",force=True).reusable_rules==["Quy tắc tay đã khóa"]


def test_unanalysed_file_refreshes_notice_without_calling_gemini(category_settings,monkeypatch):
    settings=category_settings
    provider=Mock();monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",provider)
    add=reference_dir(settings)/"cong-nghe";add.mkdir()
    (add/"pending.mp4").write_bytes(b"pending")
    result=resolve_profile(settings,"công nghệ","news")
    assert result[1]=="@default" and result[0].video_count==0
    assert any("chưa có video mẫu" in w for w in result[2])
    assert any("chưa có phân tích" in w for w in result[2])
    provider.assert_not_called()


def test_select_type_specific_profile_and_allow_opt_out(category_settings):
    settings=category_settings
    add_video(settings,"news.mp4",kind="news")
    add_video(settings,"review.mp4",kind="review")
    profile,preset,_=resolve_profile(settings,"công nghệ","review")
    assert preset=="@category:cong-nghe:review" and profile.reference_files==["cong-nghe/review.mp4"]
    # A generic automatic category selector is refined after topic discovery picks a type.
    assert choose_profile(settings,"cong-nghe",token("cong-nghe"),"review")[1]==preset
    assert choose_profile(settings,"cong-nghe","none","news")== (None,None,[])
    fallback,preset,warnings=resolve_profile(settings,"du lịch","story")
    assert preset=="@default" and fallback.confidence_label=="mặc định"
    assert "chưa có video mẫu cho danh mục này" in warnings


def test_director_blueprint_uses_scene_table_but_respects_facts(category_settings):
    settings=category_settings;add_video(settings,"sample.mp4")
    profile=rebuild_category(settings,"cong-nghe")
    rows=story_blueprint(60,20,profile)
    assert len(rows)==6 and rows[0]["style_section"]=="hook"
    assert rows[-1]["style_section"]=="kết"
    assert rows[0]["transition_hint"]=="fade" and rows[-1]["transition_hint"]=="cut"
    assert any("{topic}" in r["connective_template"] for r in rows)
    assert sum(sum(r["shot_durations_sec"]) for r in rows)==pytest.approx(60)
    assert all(1.5-1e-8<=d<=4+1e-8 for r in rows for d in r["shot_durations_sec"])
    assert len(story_blueprint(30,1,profile))==2


def test_category_references_still_detect_copied_narration(category_settings):
    settings=category_settings;add_video(settings,"sample.mp4")
    profile=rebuild_category(settings,"cong-nghe")
    plan=EditPlan.model_validate(fixture_plan());plan.style_profile=profile
    plan.scenes[1].narration=profile.reference_texts[-1]
    assert any(scene_id==2 for scene_id,score in copying_scenes(plan))
    report=compare_plan(plan,profile)
    assert len(report["summary"])==3 and report["patterns"] and report["scenes"]


def test_three_pass_director_gets_category_scene_table_and_connectors(story_data,monkeypatch):
    settings,brief,outline,written,final=story_data
    (settings.prompts_dir/"style_analyze.md").write_text((ROOT_DIR/"prompts/style_analyze.md").read_text(encoding="utf-8"),encoding="utf-8")
    monkeypatch.setattr("pipeline.style_learner.inspect_video",lambda path,settings:{"duration_sec":30.,"size_bytes":path.stat().st_size})
    add_video(settings,"sample.mp4")
    profile=resolve_profile(settings,"cong-nghe","news")[0]
    blueprint=story_blueprint(90,len(brief.facts),profile)
    outline=deepcopy(outline)
    outline["scenes"]=outline["scenes"][:len(blueprint)]
    rows=[]
    for i,row in enumerate(blueprint):
        source=deepcopy(written["scenes"][min(i,len(written["scenes"])-1)])
        source["scene_id"]=row["id"]
        source["overlays"]=["Dựng video"]*len(row["shot_durations_sec"])
        rows.append(source)
    provider=ThreePass(outline,{"title":"Dựng video","scenes":rows},{"scenes":rows,"approved":True,"issues":[]})
    plan=create_edit_plan(brief,DirectorRequest(category="công nghệ",video_type="news",video_format="tiktok",duration_sec=90),provider,settings,JsonCache(settings.cache_dir),director_diagnostics(settings),lambda m:None)
    assert len(provider.calls)==3
    for _,prompt in provider.calls:
        data=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1])
        assert data["style_profile"]["scene_pacing"] and data["style_profile"]["connective_phrases"]
        assert "reference_texts" not in data["style_profile"]
    assert len(plan.scenes)==len(blueprint) and plan.style_profile.category_id=="cong-nghe"


def test_create_form_category_auto_loads_profile_and_manual_off(category_settings,monkeypatch):
    settings=category_settings;add_video(settings,"sample.mp4")
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    manager=setup_manager(monkeypatch)
    at=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=30).run()
    assert not at.exception
    at.sidebar.radio[0].set_value("Tạo video").run()
    at.selectbox(key="create_category").set_value("cong-nghe").run()
    assert not at.exception
    assert at.selectbox(key="create_style_preset").value=="@category:cong-nghe:news"
    at.selectbox(key="create_style_preset").set_value(None).run()
    at.text_input(key="create_topic").set_value("Chủ đề test").run()
    next(b for b in at.button if b.label=="Tạo video").click().run()
    assert not at.exception
    assert manager.submit.call_args.args[0].style_preset=="none"
    assert manager.submit.call_args.args[0].category=="cong-nghe"


def test_sample_tabs_show_scene_table_and_category_profile(category_settings,monkeypatch):
    settings=category_settings;add_video(settings,"sample.mp4")
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    at=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=30).run()
    at.sidebar.radio[0].set_value("Phong cách mẫu").run()
    at.session_state["style_category_tabs"]="công nghệ"
    at.run()
    assert not at.exception
    assert any(item.label=="Tổng hợp lại" for item in at.button)
    assert any(m.label=="Số video mẫu làm cơ sở" and m.value=="1" for m in at.metric)
    assert len(at.dataframe)>=3


def test_discovery_handoff_picks_profile_for_suggested_type(category_settings,monkeypatch):
    from tests.test_topic_discovery import suggestion,NOW
    settings=category_settings
    add_video(settings,"news.mp4",kind="news")
    add_video(settings,"review.mp4",kind="review")
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    at=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=30).run()
    assert not at.exception
    at.sidebar.radio[0].set_value("Khám phá chủ đề").run()
    row=suggestion();row["suggested_type"]="review"
    at.session_state["discovery_result"]={"category":"công nghệ","topics":[row],"sources":[],"warnings":[],"gemini_error":None,
        "excluded_history":[],"raw_news":[],"groups":[],"generated_at":NOW.isoformat()}
    at.run()
    assert not at.exception
    next(b for b in at.button if b.label=="Tạo video từ chủ đề này").click().run()
    assert not at.exception and at.sidebar.radio[0].value=="Tạo video"
    assert at.selectbox(key="create_type").value=="review"
    assert at.selectbox(key="create_style_preset").value=="@category:cong-nghe:review"


def test_auto_category_ui_loads_category_then_default_without_api(category_settings,monkeypatch):
    settings=category_settings;add_video(settings,"news.mp4")
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    manager=Mock();manager.active.return_value=None;manager.snapshot.return_value=None;manager.submit_auto.return_value="worker"
    monkeypatch.setattr("app.views.auto_category.auto_jobs",lambda:manager)
    at=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=30).run()
    assert not at.exception and at.selectbox(key="auto_style_preset").value=="@category:cong-nghe"
    at.button(key="auto_start").click().run()
    assert manager.submit_auto.call_args.args[0]["style_preset"]=="@category:cong-nghe"
    at.selectbox(key="auto_category").set_value("du lịch").run()
    assert not at.exception and at.selectbox(key="auto_style_preset").value=="@default"
    assert any("chưa có video mẫu cho danh mục này" in element.value for element in at.info)


def test_category_connective_repetition_stays_quality_warning(category_settings):
    from agents.validation_rules import run_rules
    from tests.test_director import fixture_brief
    settings=category_settings;add_video(settings,"news.mp4")
    profile=rebuild_category(settings,"cong-nghe")
    plan=EditPlan.model_validate(fixture_plan());plan.style_profile=profile
    for scene in plan.scenes[1:4]:
        scene.narration="Nhưng điều đáng nói về dựng video là bạn có thể cắt và ghép video."
    run_rules(plan,fixture_brief(),DirectorRequest(video_type="news",video_format="tiktok",duration_sec=45),allow_merge=False)
    assert any(event.rule_id=="transitions" and event.group==3 for event in plan.validation_events)
