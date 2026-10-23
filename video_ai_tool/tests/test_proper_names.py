"""Vietnamese sentence openings, shared graphic detection, layer-specific review."""
import json
from pathlib import Path
import pytest
from agents.proper_names import proper_names
from agents.explainer_guard import sentence_issues,sentence_background_warnings,sync_narration
from agents.validation_rules import RuleViolation,run_rules
from agents.director import validate_plan,DirectorRequest
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from schemas.explainer import ScriptSentence
from schemas.visual import Visual,VisualData
from tests.test_explainer_v2 import setup


@pytest.mark.parametrize("text",[
    "Trải nghiệm này có thể giúp bạn hiểu quy trình.",
    "Nhiều người dùng muốn tìm hiểu thêm.",
    "Một ví dụ. Trải nghiệm mới! Nhiều lựa chọn? Khi nào: Nếu cần — Mỗi bước.",
    "- Trải nghiệm mới\n• Nhiều người dùng\n1. Thực tế là vậy\n2) Giả sử cần thử.",
    "Bạn có thể Trải nghiệm, Nhiều cách vẫn phù hợp."])
def test_common_vietnamese_words_never_entities(text):
    assert not list(proper_names(text))


@pytest.mark.parametrize("text,expected",[
    ("Cambridge là ví dụ nền.",["Cambridge"]),
    ("Meta có sản phẩm.",["Meta"]),
    ("OpenAI và GPT-5 là ví dụ.",["OpenAI","GPT-5"]),
    ("Ví dụ về Cambridge Analytica thường được nhắc đến.",["Cambridge Analytica"]),
    ("Dẫn dắt: Cambridge Analytica.",["Cambridge Analytica"])])
def test_foreign_and_multiword_names_keep_actual_spans(text,expected):
    names=list(proper_names(text))
    assert [n[0] for n in names]==expected
    assert all(text[n.start():n.end()]==n[0] for n in names)


@pytest.mark.parametrize("kind",["explain","opinion","cta"])
def test_background_proper_name_is_group_three(tmp_path,kind):
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    scene=plan.scenes[2]
    scene.sentences=[ScriptSentence(type=kind,text="Ví dụ về Cambridge Analytica có thể giúp mình nghĩ về quyền riêng tư.")]
    sync_narration(plan)
    from agents.explainer_visuals import build_v2_shots
    build_v2_shots(plan,brief)
    plan=validate_plan(plan,brief,request,check_style=False,allow_merge=False)
    scene=plan.scenes[2]
    warnings=[e for e in plan.validation_events if e.rule_id=="sentence_background_names"]
    assert warnings and all(e.group==3 and e.action=="warning" for e in warnings)
    assert any("ví dụ nền, nên kiểm tra" in w for w in scene.review_notes.warnings)
    assert not sentence_issues(plan,brief)


def test_true_event_name_is_hard_then_repaired_once(tmp_path):
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    event=plan.scenes[0].sentences[0]
    event.text="FictionCorp thông báo kế hoạch cắt giảm 5.000 việc làm."
    sync_narration(plan)
    untouched=plan.scenes[1].narration
    assert any("tên riêng ngoài brief" in text for _,text in sentence_issues(plan,brief))
    plan=validate_plan(plan,brief,request,check_style=False,allow_merge=False,diagnostics=diagnostics)
    event=plan.scenes[0].sentences[0]
    assert "FictionCorp" not in event.text
    assert plan.scenes[1].narration==untouched
    fixes=[e for e in plan.validation_events if e.rule_id=="sentence_grounding" and e.action=="fixed"]
    assert fixes and all(e.group==1 for e in fixes)
    count=len(fixes)
    plan=validate_plan(plan,brief,request,check_style=False,allow_merge=False)
    assert len([e for e in plan.validation_events if e.rule_id=="sentence_grounding" and e.action=="fixed"])==count


def test_unrepairable_event_still_hard(tmp_path):
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    plan.scenes[0].sentences[0].text="FictionCorp thông báo kế hoạch."
    plan.scenes[0].sentences[0].fact_ids=[]
    sync_narration(plan)
    with pytest.raises(RuleViolation,match="nhóm 1"):
        validate_plan(plan,brief,request,check_style=False,allow_merge=False)


def test_background_overlay_uses_same_sentence_layer(tmp_path):
    from agents.validation_rules import Context,names_quotes,unsupported_numbers
    brief,outline,script,settings,request,diagnostics,plan=setup(tmp_path)
    scene=plan.scenes[2]
    scene.sentences=[ScriptSentence(type="explain",text="Cambridge Analytica có thể là ví dụ để kiểm tra.")]
    sync_narration(plan)
    for shot in scene.shots:
        shot.visual=Visual(template="text_focus",sentence_index=1,data=VisualData(text="Cambridge Analytica"))
        shot.text_overlay="Cambridge Analytica"
    assert not names_quotes(Context(plan,brief))
    assert not unsupported_numbers(Context(plan,brief))


def test_real_2ccb3f80_draft_revalidates_without_api():
    root=Path(__file__).parent/"fixtures/explainer_names"
    draft=json.loads((root/"edit_plan.draft.json").read_text(encoding="utf-8"))
    plan=EditPlan.model_validate(draft["plan"])
    brief=ResearchBrief.model_validate_json((root/"brief.json").read_text(encoding="utf-8"))
    original={s.id:s.narration for s in plan.scenes}
    request=DirectorRequest(video_type="news",video_format=plan.format,duration_sec=60,content_mode="explainer_v2")
    plan=validate_plan(plan,brief,request,check_style=False,allow_merge=False)
    assert {s.id:s.narration for s in plan.scenes}==original
    assert not [e for e in plan.validation_events if e.rule_id=="sentence_grounding" and e.action=="error"]
    assert all(not any("câu nền: Trải" in w or "câu nền: Nhiều" in w for w in s.review_notes.warnings) for s in plan.scenes)
