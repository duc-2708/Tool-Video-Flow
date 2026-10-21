"""Offline category orchestration: fallback, adaptive evidence, resume and cost gates."""
import json
from pathlib import Path
from threading import Event
from unittest.mock import Mock
import pytest
from agents.researcher import NoResearchDataError
from agents.adaptive import duration_for_brief,fact_schedule
from agents.story_style import story_blueprint
from agents.director import brief_hash,validate_plan,DirectorRequest
from schemas.edit_plan import EditPlan
from pipeline.auto_category import run_auto,AutoCategoryError
from pipeline.run_all import ApprovalRequired
from pipeline.topics_history import history_rows
from tests.test_run_all import stages
from tests.test_topic_discovery import suggestion
from utils.cache import write_json


def read(project): return json.loads((project/"run_state.json").read_text(encoding="utf-8"))

@pytest.fixture
def discovered(monkeypatch):
    rows=[]
    for i in range(3):
        rows.append({**suggestion(),"topic":f"Sản phẩm thử nghiệm {i+1} ra mắt","cluster_id":f"group{i}","source_urls":[f"https://example.test/event{i}"]})
    result={"topics":rows,"warnings":[],"category":"công nghệ"}
    discovery=Mock(return_value=result)
    monkeypatch.setattr("pipeline.auto_category.discover_topics",discovery)
    return rows,discovery


def test_category_calls_existing_steps_and_marks_history_only_on_completion(stages,discovered):
    settings,calls,_,_=stages
    project=run_auto("công nghệ",duration=45,settings=settings,render_mode="preview")
    state=read(project)
    assert calls==["research","director","assets","render"]
    assert state["status"]=="done" and state["steps"]["discovery"]["status"]=="done"
    assert state["config"]["ai_clips"]==0 and state["config"]["mode"]=="auto"
    assert state["auto_category"]["selected_topic"]==discovered[0][0]["topic"]
    assert len(history_rows(settings.output_dir))==1
    report=(project/"report.md").read_text(encoding="utf-8")
    assert "công nghệ" in report and "Nội dung có hỗ trợ AI" in report


def test_first_topic_without_data_tries_next_and_records_reason(stages,discovered,monkeypatch):
    import pipeline.run_all as module
    settings,calls,_,_=stages
    original=module.run_research
    def research(topic,*args,**kwargs):
        if topic==discovered[0][0]["topic"]:
            calls.append("research_empty");raise NoResearchDataError("Không có nguồn dùng được fixture")
        return original(topic,*args,**kwargs)
    monkeypatch.setattr(module,"run_research",research)
    project=run_auto("công nghệ",duration=45,settings=settings)
    assert calls==["research_empty","research","director","assets","render"]
    assert read(project)["auto_category"]["selected_topic"]==discovered[0][1]["topic"]
    assert len(history_rows(settings.output_dir))==1 and history_rows(settings.output_dir)[0]["topic"]==discovered[0][1]["topic"]
    assert "Không có nguồn dùng được" in (project/"report.md").read_text(encoding="utf-8")


def test_zero_fact_brief_switches_topic(stages,discovered,monkeypatch):
    import pipeline.run_all as module
    settings,_,_,_=stages
    original=module.run_research
    def research(topic,*args,**kwargs):
        path=original(topic,*args,**kwargs)
        if topic==discovered[0][0]["topic"]:
            data=json.loads(path.read_text(encoding="utf-8"));data["facts"]=[];write_json(path,data)
        return path
    monkeypatch.setattr(module,"run_research",research)
    project=run_auto("công nghệ",duration=45,settings=settings)
    assert read(project)["status"]=="done" and len(read(project)["auto_category"]["skipped"])==1


def test_three_empty_topics_report_all_reasons_without_render(stages,discovered,monkeypatch):
    settings,calls,_,_=stages
    research=Mock(side_effect=NoResearchDataError("0 fact hợp lệ từ nguồn"))
    monkeypatch.setattr("pipeline.run_all.run_research",research)
    with pytest.raises(AutoCategoryError,match="Tất cả 3 chủ đề"):
        run_auto("công nghệ",duration=45,settings=settings)
    project=next(p for p in settings.output_dir.iterdir() if p.is_dir())
    assert research.call_count==3 and not calls and not history_rows(settings.output_dir)
    report=(project/"report.md").read_text(encoding="utf-8")
    assert all(row["topic"] in report for row in discovered[0])


def test_quota_error_is_not_misclassified_as_missing_facts(stages,discovered,monkeypatch):
    from providers.llm_base import ProviderError
    settings,_,_,_=stages
    research=Mock(side_effect=ProviderError("Gemini quota exhausted"))
    monkeypatch.setattr("pipeline.run_all.run_research",research)
    with pytest.raises(AutoCategoryError,match="quota"):
        run_auto("công nghệ",duration=45,settings=settings)
    research.assert_called_once()


def test_review_resume_does_not_discover_or_research_again(stages,discovered):
    settings,calls,_,_=stages
    project=run_auto("công nghệ",duration=45,settings=settings,review=True)
    assert calls==["research","director"] and read(project)["status"]=="waiting_review"
    assert not history_rows(settings.output_dir)
    run_auto(resume=project,settings=settings)
    assert calls==["research","director","assets","render"] and read(project)["status"]=="done"
    discovered[1].assert_called_once()
    run_auto(resume=project,settings=settings)
    assert len(calls)==4 and len(history_rows(settings.output_dir))==1


def test_cancel_then_resume_discovery(stages,discovered):
    settings,_,_,_=stages
    cancel=Event();cancel.set()
    project=run_auto("công nghệ",duration=45,settings=settings,cancel_event=cancel)
    assert read(project)["status"]=="cancelled"
    discovered[1].assert_not_called()
    run_auto(resume=project,settings=settings)
    assert read(project)["status"]=="done"


def test_resume_asset_failure_keeps_discovery_research_and_script(stages,discovered):
    settings,calls,failures,_=stages
    failures["assets"]=1
    with pytest.raises(AutoCategoryError,match="assets"):
        run_auto("công nghệ",duration=45,settings=settings)
    project=next(p for p in settings.output_dir.iterdir() if p.is_dir())
    assert calls==["research","director","assets"]
    run_auto(resume=project,settings=settings)
    assert calls==["research","director","assets","assets","render"]
    assert read(project)["status"]=="done"
    discovered[1].assert_called_once()


def test_ai_error_never_stops_category_video(stages,discovered,monkeypatch):
    settings,calls,_,_=stages
    ai=Mock(side_effect=RuntimeError("AI failed fixture"))
    monkeypatch.setattr("pipeline.run_all.prepare_ai_bundle",ai)
    project=run_auto("công nghệ",duration=45,settings=settings,ai_clips=1,ai_confirmed=True)
    assert read(project)["status"]=="done" and "render" in calls
    assert read(project)["steps"]["ai_video"]["status"]=="skipped"
    ai.assert_called_once()


def test_next_video_chooses_next_unused_topic_in_new_project(stages,discovered):
    settings,_,_,_=stages
    first=run_auto("công nghệ",duration=45,settings=settings)
    second=run_auto("công nghệ",duration=45,settings=settings)
    assert first!=second and read(first)["status"]==read(second)["status"]=="done"
    assert read(first)["config"]["topic"]==discovered[0][0]["topic"]
    assert read(second)["config"]["topic"]==discovered[0][1]["topic"]
    assert len(history_rows(settings.output_dir))==2


def test_paid_approval_required_before_discovery(stages,discovered):
    settings,calls,_,_=stages
    with pytest.raises(ApprovalRequired): run_auto("công nghệ",settings=settings,ai_clips=1)
    assert not calls;discovered[1].assert_not_called()
    assert not settings.output_dir.exists()


@pytest.mark.parametrize("count",[1,2])
def test_thin_facts_still_render_shorter_grounded_plan(stages,discovered,monkeypatch,count):
    import pipeline.run_all as module
    from schemas.research_brief import ResearchBrief
    settings,calls,_,_=stages
    original=module.run_research
    def research(*args,**kwargs):
        path=original(*args,**kwargs)
        data=json.loads(path.read_text(encoding="utf-8"));data["facts"]=data["facts"][:count]
        for fact in data["facts"]:
            fact["fact_vi"]="Người dựng có thể chọn đoạn cần giữ trước khi ghép thành video. Quy trình này giúp sắp xếp lại các cảnh theo thứ tự và kiểm tra nhịp kể trước khi xuất bản."
            fact["evidence_quote"]="chọn đoạn cần giữ trước khi ghép"
        write_json(path,data);return path
    def director(path,settings,**kwargs):
        calls.append("director")
        brief=ResearchBrief.model_validate_json(path.read_text(encoding="utf-8"))
        target=duration_for_brief(brief,kwargs["duration_sec"])
        rows=story_blueprint(target,count);assignment=fact_schedule(rows,count)
        plan=EditPlan.model_validate({"title":"Quy trình dựng","format":"tiktok","voice":settings.default_voice,"music":{"mood":"calm","volume":.1},
            "video_type":"news","adaptive":True,"target_duration_sec":target,"requested_duration_sec":kwargs["duration_sec"],"brief_hash":brief_hash(brief),
            "scenes":[{"id":r["id"],"role":r["role"],"narration":"Bạn có thể chọn đoạn trước khi ghép video.","fact_ids":assignment[r["id"]],
                "pattern_interrupt":True,"sfx":"pop","transition_out":"cut","shots":[{"type":"stock_video","query":"video editing","duration_sec":d,"effect":"zoom_in","text_overlay":"Chọn đoạn trước"} for d in r["shot_durations_sec"]]} for r in rows]})
        write_json(path.parent/"edit_plan.json",plan.model_dump(mode="json"));return path.parent/"edit_plan.json"
    old_render=module.run_render
    def render(path,**kwargs):
        result=old_render(path,**kwargs)
        result["duration_sec"]=json.loads(path.read_text(encoding="utf-8"))["target_duration_sec"]
        return result
    monkeypatch.setattr(module,"run_research",research);monkeypatch.setattr(module,"run_director",director);monkeypatch.setattr(module,"run_render",render)
    project=run_auto("công nghệ",duration=60,settings=settings)
    state=read(project)
    assert state["status"]=="done" and state["render_result"]["duration_sec"]<60
    assert state["summary"]["facts"]==count
    if count==2: assert 30<=state["render_result"]["duration_sec"]<=40
    assert "vì dữ liệu mỏng" in (project/"report.md").read_text(encoding="utf-8")


def test_auto_ui_is_first_and_ai_off_by_default(tmp_path,monkeypatch):
    from config.settings import Settings,ROOT_DIR
    from pydantic import SecretStr
    from streamlit.testing.v1 import AppTest
    settings=Settings(root_dir=tmp_path,gemini_api_key=SecretStr("fixture"),gemini_model="mock")
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    manager=Mock();manager.active.return_value=None;manager.snapshot.return_value=None;manager.submit_auto.return_value="mock"
    monkeypatch.setattr("app.views.auto_category.auto_jobs",lambda:manager)
    app=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=25).run()
    assert not app.exception and app.sidebar.radio[0].value=="Tạo video theo danh mục"
    assert not app.checkbox(key="auto_ai").value and app.radio(key="auto_mode").value=="Tự động hoàn toàn"
    app.button(key="auto_start").click().run()
    assert not app.exception
    params=manager.submit_auto.call_args.args[0]
    assert params["ai_clips"]==0 and not params["review"]
