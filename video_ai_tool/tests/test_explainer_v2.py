"""Offline regression from the paid Barclays outline/written/humanized checkpoint."""
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock
import pytest
from config.settings import Settings,ROOT_DIR
from agents.director import DirectorRequest,validate_plan
from agents.explainer_director import (script_plan,create_explainer_plan,check_open_loop,quality_notes,checkpoint_summary,critique)
from agents.validation_rules import RuleViolation
from agents.explainer_research import prioritize_sources,question_queries,knowledge_notes
from agents.explainer_visuals import VIEWS
from schemas.explainer import ExplainerOutline,ExplainerScript,ScriptSentence
from schemas.research_brief import ResearchBrief
from schemas.source import SourceDocument
from utils.diagnostics import Diagnostics

FIX=Path(__file__).parent/"fixtures/explainer_barclays"


def data():
    brief=ResearchBrief.model_validate_json((FIX/"brief.json").read_text(encoding="utf-8"))
    kinds=["cause","mechanism","metaphor","example","counterpoint","consequence"]
    paragraphs=[
        [("event","Barclays thông báo kế hoạch cắt giảm 5.000 việc làm.",[1]),("explain","Vì sao tự động hóa có thể làm thay đổi cách tổ chức công việc?",[])],
        [("explain","Thường là, công việc được chia thành các khâu nhỏ. Máy xử lý phần lặp lại, còn người kiểm tra tình huống khó.",[])],
        [("explain","Bạn có thể hình dung chuyện này giống bếp làm bánh. Máy trộn nguyên liệu chưa thể thay việc chọn món và kiểm tra chất lượng.",[])],
        [("explain","Ví dụ, hồ sơ đi qua phần mềm vẫn có thể cần người xem lại trường hợp ngoại lệ. Vai trò thường chuyển từ nhập liệu sang kiểm soát.",[])],
        [("explain","Mặt trái thường nằm ở đào tạo và trách nhiệm. Nếu bàn giao vội, sai sót có thể khó phát hiện hơn.",[])],
        [("opinion","Theo mình, tự động hóa có thể đổi cách chia việc vì phần lặp lại chuyển cho máy, còn người tập trung kiểm tra và quyết định.",[]),("cta","Bạn muốn học kỹ năng nào để thích nghi?",[])]]
    outline=ExplainerOutline(angle="Công việc đổi cách tổ chức",hook=paragraphs[0][1][1],open_loop=paragraphs[0][1][1],payoff=paragraphs[-1][0][1],
        beats=[dict(id=i+1,kind=k,idea="Ý "+str(i),new_information=texts[0][1],fact_ids=[1] if i==0 else []) for i,(k,texts) in enumerate(zip(kinds,paragraphs))])
    script=ExplainerScript(title="AI đổi cách chia việc như thế nào?",scenes=[dict(scene_id=i+1,kind=k,new_information=texts[0][1],
        sentences=[dict(type=t,text=s,fact_ids=ids) for t,s,ids in texts],shot_queries=["employee sorting documents","automated document processing"]) for i,(k,texts) in enumerate(zip(kinds,paragraphs))])
    return brief,outline,script


class Provider:
    model_name="mock-explainer"
    def __init__(self,weak=False,loop=True): self.calls=[];self.weak=weak;self.loop=loop
    def generate_json(self,prompt,schema):
        self.calls.append((schema.__name__,prompt))
        brief,outline,script=data()
        if schema.__name__=="ExplainerOutline": value=outline.model_dump(mode="json")
        elif schema.__name__=="ExplainerScript": value=script.model_dump(mode="json")
        elif schema.__name__=="ScriptCritic": value=dict(explanation=2 if self.weak else 4,novelty=4,hook=4,open_loop=4,naturalness=4,comments=["Cảnh cơ chế cần rõ hơn"],weak_scenes=[dict(scene_id=2,reason="Chỉ ra người kiểm tra ngoại lệ")] if self.weak else [])
        elif schema.__name__=="ExplainerRepairs":
            row=script.scenes[1].model_dump(mode="json");row["sentences"][0]["text"]="Thường là, phần mềm xử lý hồ sơ lặp lại trước. Người kiểm tra ngoại lệ để tránh bỏ sót tình huống khó."
            value={"scenes":[row]}
        elif schema.__name__=="LoopReview": value=dict(answered=self.loop,reason="Kết trả lời cơ chế" if self.loop else "Chưa trả lời",replacement_question="")
        else: raise AssertionError(schema)
        return json.dumps(value,ensure_ascii=False)


def setup(tmp_path):
    brief,outline,script=data();settings=Settings(root_dir=ROOT_DIR)
    request=DirectorRequest(video_type="news",video_format="tiktok",duration_sec=60,content_mode="explainer_v2",script_style="explain")
    diagnostics=Diagnostics(tmp_path/"logs")
    plan=script_plan(script,outline,brief,request,settings)
    return brief,outline,script,settings,request,diagnostics,plan


def test_three_novel_ideas_and_legacy_state_regression(tmp_path):
    summary=checkpoint_summary(FIX/"director_state.json")
    assert set(summary)=={"outline","written","humanized"}
    assert "reference_texts" not in json.dumps(summary)
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    assert not quality_notes(outline)
    assert len({b.new_information for b in outline.beats[:3]})==3
    validate_plan(plan,brief,request,check_style=False,allow_merge=False)
    assert 150<=sum(len(s.narration.split()) for s in plan.scenes)<=180
    assert all(2.5<=q.duration_sec<=4 for s in plan.scenes for q in s.shots)
    assert len(plan.title)<=60 and all(not s.narration.startswith("Theo The Guardian") for s in plan.scenes)
    assert all(not VIEWS.intersection(q.query.split()) for s in plan.scenes for q in s.shots)


def test_explain_estimate_allowed_event_fabrication_blocked(tmp_path):
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    plan.scenes[1].sentences=[ScriptSentence(type="explain",text="Thường là, khoảng 30 hồ sơ có thể đi qua cùng quy trình.")]
    from agents.explainer_guard import sync_narration
    sync_narration(plan)
    from agents.explainer_visuals import build_v2_shots
    build_v2_shots(plan,brief)
    validate_plan(plan,brief,request,check_style=False,allow_merge=False)
    plan.scenes[1].sentences=[ScriptSentence(type="event",text="Barclays cắt giảm 987654321 việc làm.",fact_ids=[1])]
    sync_narration(plan);build_v2_shots(plan,brief)
    with pytest.raises(RuleViolation,match="987654321"): validate_plan(plan,brief,request,check_style=False,allow_merge=False)


def test_mislabeled_company_claim_is_not_a_background_loophole(tmp_path):
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    from agents.explainer_guard import background_issues
    assert background_issues("Barclays đã cắt khoảng 90 nhân viên.",brief)
    assert not background_issues("Thường là, hàng chục hồ sơ đi qua cùng quy trình.",brief)


@pytest.mark.parametrize("answered",[True,False])
def test_loop_is_semantic_or_removed_never_assigns_unrelated_fact(tmp_path,answered):
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    ids=[s.fact_ids[:] for s in plan.scenes]
    check_open_loop(plan,Provider(loop=answered),"prompt",diagnostics)
    assert bool(plan.explainer_outline.open_loop)==answered
    assert [s.fact_ids for s in plan.scenes]==ids
    if not answered: assert "?" not in plan.scenes[0].narration


def test_critic_only_rewrites_weak_scene_and_does_not_change_accepted_scenes(tmp_path):
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    provider=Provider(weak=True)
    before={s.id:s.model_dump(mode="json") for s in plan.scenes}
    revised=critique(plan,brief,request,settings,provider,"prompt",diagnostics,{})
    assert revised.scenes[1].narration!=plan.scenes[1].narration
    for s in revised.scenes:
        if s.id!=2: assert s.model_dump(mode="json")==before[s.id]
    assert sum(n=="ExplainerRepairs" for n,_ in provider.calls)==1
    assert revised.script_critic.explanation==2


def test_three_pass_checkpoint_resume_does_not_pay_twice(tmp_path):
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    provider=Provider()
    path=tmp_path/"edit_plan.draft.json"
    result=create_explainer_plan(brief,request,provider,settings,diagnostics,lambda _:None,draft_path=path)
    count=len(provider.calls)
    again=create_explainer_plan(brief,request,provider,settings,diagnostics,lambda _:None,draft_path=path)
    assert len(provider.calls)==count
    assert again.model_dump(mode="json")==result.model_dump(mode="json")


def test_liveblog_demoted_and_only_live_warns():
    from datetime import datetime,timezone
    def source(url): return SourceDocument(title="Article",url=url,source_name="Paper",platform="web",text="x"*400,retrieved_at=datetime.now(timezone.utc).isoformat(),source_lang="en",content_kind="article")
    live=source("https://paper.example/live/updates");article=source("https://other.example/story/details")
    kept,notes=prioritize_sources([live,article]);assert kept==[article] and notes
    kept,notes=prioritize_sources([live]);assert kept==[live] and "nguồn nhiều tin lẫn lộn" in notes[0]


def test_question_search_and_knowledge_notes_are_separate_from_facts(tmp_path):
    brief,*_=data();facts=deepcopy(brief.facts);diagnostics=Diagnostics(tmp_path/"logs")
    provider=Mock()
    provider.generate_json.return_value=json.dumps({"questions":[{"question":"Vì sao thay đổi?","query_vi":"tự động hóa ngân hàng cơ chế","query_en":"bank automation workflow explained"}]})
    questions,queries=question_queries(brief.topic,["vi","en"],provider,diagnostics)
    assert {q.source_lang for q in queries}=={"vi","en"}
    brief.research_questions=questions
    provider.generate_json.return_value=json.dumps({"knowledge_notes":[{"text":"Thường là, tự động hóa xử lý phần việc lặp lại.","analogy":"Có thể hình dung như máy trộn trong bếp.","confidence":"medium","source":"kiến thức nền"}]})
    knowledge_notes(brief,provider,diagnostics)
    assert brief.knowledge_notes and brief.facts==facts


def test_code_critic_catches_listing_even_when_model_scores_five(tmp_path):
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    plan.scenes[2].sentences=[ScriptSentence(type="event",text="Barclays cắt giảm 5.000 việc làm.",fact_ids=[1])]
    from agents.explainer_guard import sync_narration
    sync_narration(plan)
    assert any(i==3 and "kể lại tin" in message for i,message in quality_notes(outline,plan))


def test_source_name_reporting_verbs_are_removed_not_only_theo(tmp_path):
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    from agents.explainer_guard import limit_attribution
    plan.scenes[0].sentences[0].text="The Guardian cho biết Barclays cắt giảm 5.000 việc làm."
    limit_attribution(plan,brief)
    assert "The Guardian" not in plan.scenes[0].narration


def test_render_preserves_background_visual_tags_and_resolved_timing(tmp_path):
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    from agents.visual_planner import assign_visuals
    before=plan.model_dump(mode="json")
    assign_visuals(plan,brief)
    assert plan.model_dump(mode="json")==before


def test_v2_selection_reaches_run_config_in_ui(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from tests.test_create_video_ui import setup_manager
    from pydantic import SecretStr
    settings=Settings(root_dir=tmp_path,gemini_model="mock",gemini_api_key=SecretStr("mock-not-real"))
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    manager=setup_manager(monkeypatch)
    at=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=30).run()
    at.sidebar.radio[0].set_value("Tạo video").run()
    at.text_input(key="create_topic").set_value("Barclays giải thích").run()
    at.checkbox(key="create_explainer_v2").check().run()
    next(b for b in at.button if b.label=="Tạo video").click().run()
    assert not at.exception and manager.submit.call_args.args[0].content_mode=="explainer_v2"
