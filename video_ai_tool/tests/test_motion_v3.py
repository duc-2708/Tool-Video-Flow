"""Controlled AI uses mocked gateway only; typography uses local Chromium."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import json
import pytest
from config.settings import Settings,ROOT_DIR
from schemas.edit_plan import EditPlan
from schemas.assets import ResolvedEditPlan
from schemas.research_brief import ResearchBrief
from schemas.visual import Visual,VisualData,VisualBar
from schemas.style import CaptionStyle
from tests.test_director import fixture_plan,fixture_brief
from tests.test_timeline import render_project,hashes
from tests.test_motion import sample_scene,chromium
from agents.visual_diversity import repair_cards,repair_numeric_cards,select_templates,numeric_mismatches,GENERIC
from pipeline.controlled_ai import create_backgrounds,eligible_slots,estimate
from pipeline.render_motion import scene_payload,browser_page,capture
from editor.captions import Captions,find_font
from editor.motion.icons import icon_for
from utils.atomic_io import write_json_atomic
from utils.caption_timing import display_words,phrase_groups

FIXTURE=ROOT_DIR/'tests/fixtures/black_october'


def graphics_plan():
    plan=EditPlan.model_validate(fixture_plan())
    for scene in plan.scenes:
        for shot in scene.shots:
            shot.visual=Visual(template='text_focus',content_type='explain',data=VisualData(text='Ý chính cần nhớ'))
            shot.card_text='Ý chính cần nhớ'
    return plan


def test_real_black_october_generic_and_numeric_regression():
    plan=ResolvedEditPlan.model_validate_json((FIXTURE/'edit_plan.resolved.json').read_text(encoding='utf-8'))
    brief=ResearchBrief.model_validate_json((FIXTURE/'brief.json').read_text(encoding='utf-8'))
    narration=[s.narration for s in plan.scenes]
    select_templates(plan,brief);repair_numeric_cards(plan,brief)
    cards=[(s,shot) for s in plan.scenes for shot in s.shots if shot.visual and shot.visual.template not in {'stock','source_card','quote_card'}]
    assert sum(bool(GENERIC.fullmatch(shot.card_text or '')) for _,shot in cards)<=1
    assert not any(GENERIC.fullmatch(shot.card_text or '') for s,shot in cards if s is not plan.scenes[-1])
    for i,(scene,shot) in enumerate(cards):
        assert 3<=len(shot.card_text.split())<=6
        assert shot.card_text.casefold() not in [(q.card_text or '').casefold() for _,q in cards[max(0,i-2):i]]
        assert not numeric_mismatches(scene,shot,brief)
    assert len({q.visual.template for _,q in cards})>=3
    assert narration==[s.narration for s in plan.scenes]


def test_presentation_never_hides_group1_invalid_card():
    plan=graphics_plan();shot=plan.scenes[1].shots[0]
    shot.visual.content_type='event';shot.card_text='999 triệu người dùng';shot.visual.data.text=shot.card_text;shot.visual.data.fact_ids=[1]
    repair_cards(plan,brief=fixture_brief())
    assert shot.card_text=='999 triệu người dùng'
    from agents.visual_planner import visual_issues
    assert any('999' in message for _,message in visual_issues(plan,fixture_brief()))


def test_numeric_target_never_rounds_to_hundred(tmp_path,chromium):
    scene=sample_scene(tmp_path,'ring_percent',3)
    scene.spec.narration='Có 75 phần trăm người dùng.'
    scene.shots[0].spec.visual.data=VisualData(text='Tỷ lệ người dùng',value=75,unit='%')
    plan=NS(scenes=[scene.spec],review_notes=[])
    scene.spec.shots=[scene.shots[0].spec]
    assert repair_numeric_cards(plan)==[]
    with browser_page((270,480)) as page:
        capture(page,scene_payload(scene,(270,480),CaptionStyle()),find_font(ROOT_DIR))
        page.evaluate('()=>renderAt(2.8)')
        assert page.locator('.ring-value').inner_text()=='75%'
    scene.shots[0].spec.visual.data.value=100
    assert repair_numeric_cards(plan) and scene.shots[0].spec.visual.template=='text_focus'


@pytest.mark.parametrize('text,value',[('0,10 đô',.1),('1 triệu người',1000000),('75 phần trăm',75)])
def test_numeric_normalized_match(text,value):
    plan=graphics_plan();scene=plan.scenes[0];scene.narration=text
    shot=scene.shots[0];shot.visual.template='stat_card';shot.visual.data.value=value
    assert not numeric_mismatches(scene,shot)


def test_template_content_map_and_adjacent_variety():
    plan=graphics_plan()
    for scene in plan.scenes: scene.narration='Đây là dữ liệu đã có trong bài.'
    plan.scenes[1].shots[0].visual.data.value=75;plan.scenes[1].shots[0].visual.data.unit='%'
    plan.scenes[2].shots[0].visual.data.bars=[VisualBar(label='Trước',value=5),VisualBar(label='Sau',value=10)]
    plan.scenes[2].narration='Thay vì mức cũ, đây là mức mới.'
    plan.scenes[3].shots[0].visual.data.items=['Đọc bài gốc','Đối chiếu dữ liệu']
    select_templates(plan)
    assert plan.scenes[1].shots[0].visual.template=='ring_percent'
    assert plan.scenes[2].shots[0].visual.template=='strike_replace'
    assert plan.scenes[3].shots[0].visual.template=='steps_list'
    names=[q.visual.template for s in plan.scenes for q in s.shots]
    assert len(set(names))>=3 and all(a!=b for a,b in zip(names,names[1:]))


def test_caption_display_gaps_and_tail_merge():
    words=[('Một',.1,.3),('cụm',1.5,1.7),('rõ',2.7,2.9),('nghĩa',3.8,4.)]
    repaired=display_words(words,4.)
    assert all(b[1]-a[2]<=.6 for a,b in zip(repaired,repaired[1:]))
    assert len(phrase_groups(repaired))==1 and len(phrase_groups(repaired)[0])==4
    assert [w[1] for w in repaired]==[w[1] for w in words]


def test_keyword_fallback_excludes_citation_prefix():
    from agents.visual_diversity import concept_card
    for used in ((),('Cắt ghép video',)):
        text,_=concept_card('Theo example.com, bạn có thể cắt và ghép video.',used)
        assert 'example' not in text.casefold() and 'theo' not in text.casefold()


def test_profile_ratios_keep_strict_structured_output():
    from providers.llm.openai_client import response_format
    from schemas.style import VisualTemplateRatios
    ratios=VisualTemplateRatios(stat_card=.3,icon_card=.4)
    assert ratios.icon_card==.4
    assert response_format(EditPlan)[0]['type']=='json_schema'


def test_missing_icon_map_uses_licensed_default(tmp_path):
    import shutil
    shutil.copytree(ROOT_DIR/'assets/icons',tmp_path/'assets/icons')
    name,uri=icon_for(tmp_path,'từ khóa chưa có')
    assert name=='lightbulb' and uri.startswith('data:image/svg+xml;base64,')
    assert 'ISC License' in (tmp_path/'assets/icons/LICENSE').read_text(encoding='utf-8')


def ai_project(render_project):
    path=render_project/'edit_plan.resolved.json';data=json.loads(path.read_text(encoding='utf-8'))
    for scene in data['scenes']:
        for shot in scene['shots']:
            shot.update(card_text='Bảo vệ hạ tầng',visual={'template':'hook_card','data':{'text':'Bảo vệ hạ tầng'}})
    write_json_atomic(path,data)
    return render_project


def test_zero_ai_never_calls_gateway(render_project,monkeypatch,tmp_path):
    project=ai_project(render_project)
    submit=Mock();monkeypatch.setattr('pipeline.controlled_ai.create_job',submit)
    assert create_backgrounds(project,Settings(root_dir=tmp_path))['clips']==[]
    submit.assert_not_called()


def test_clip_fail_falls_back_to_gradient(render_project,monkeypatch,tmp_path):
    project=ai_project(render_project)
    submit=Mock(side_effect=TimeoutError('network timeout, job may exist'))
    monkeypatch.setattr('pipeline.controlled_ai.create_job',submit)
    result=create_backgrounds(project,Settings(root_dir=tmp_path,ai_clips_per_video=1),confirmed=True)
    assert submit.call_count==1 and result['clips']==[] and 'gradient' in result['warnings'][0]
    assert 'timeout' in (tmp_path/'logs/gateway_video_errors.log').read_text(encoding='utf-8')


def test_only_hook_climax_not_data_cards():
    plan=graphics_plan()
    plan.scenes[3].style_purpose='cao trào'
    slots=eligible_slots(plan)
    assert {s.id for s,_,_ in slots}=={1,4}
    for q in plan.scenes[0].shots: q.visual.template='stat_card';q.visual.data.value=10
    assert {s.id for s,_,_ in eligible_slots(plan)}=={4}


def test_confirmation_and_config_defaults(render_project,tmp_path):
    project=ai_project(render_project)
    with pytest.raises(ValueError,match='xác nhận'):
        create_backgrounds(project,Settings(root_dir=tmp_path,ai_clips_per_video=1))
    settings=Settings(ai_clips_per_video='',ai_clip_model='',ai_clip_max_sec='',ai_clip_budget_per_day='')
    assert settings.ai_clips_per_video==0 and settings.ai_clip_max_sec==6
    with pytest.raises(ValueError,match='AI_CLIP_MODEL'): Settings(ai_clip_model='seedance-2.5')


def test_theme_prompt_is_safe_and_manual_prompt_retained():
    from pipeline.controlled_ai import background_prompt
    from agents.video_prompt_writer import validate_ai_prompt,fallback_prompt
    plan=NS(title='công nghệ AI',style_profile=NS(category_id='cong-nghe'))
    shot=NS(ai_prompt=None)
    value=background_prompt(plan,shot)
    assert 'cool light' in value and validate_ai_prompt(value)==value
    shot.ai_prompt=fallback_prompt('hoa')
    assert background_prompt(plan,shot)==shot.ai_prompt


def test_daily_budget_atomic_and_retry_counted(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from pipeline.ai_budget import reserve,remaining
    settings=Settings(root_dir=tmp_path,ai_clip_budget_per_day=2)
    def attempt(key):
        try: reserve(settings,key);return True
        except ValueError: return False
    with ThreadPoolExecutor(max_workers=4) as pool: result=list(pool.map(attempt,['a','retry-a','b','c']))
    assert sum(result)==2 and remaining(settings)==0


def test_quality_report_detects_fixture_failures(tmp_path):
    from editor.quality import presentation_metrics
    scene=sample_scene(tmp_path,'stat_card',8.)
    scene.spec.shots=[scene.shots[0].spec];scene.shots[0].spec.visual.data.value=999
    scene.shots[0].spec.card_text='Một thẻ dữ liệu'
    scene.shots[0].spec.visual.beats=[]
    scene.shots[0].shot_id=1;scene.spec.id=1
    data=presentation_metrics(NS(scenes=[scene]),[{'scene_id':1,'quality':[{'shot_id':1,'issues':['text_overflow','card_empty_over_40_percent']}]}])
    assert data['text_overflow'] and data['empty_cards_over_40_percent'] and data['numbers_not_in_narration_or_brief']


@pytest.mark.parametrize('motion,mascot',[(False,False),(True,False)])
def test_disabled_motion_mascot_still_render(render_project,motion,mascot,chromium,monkeypatch):
    from editor.render import run_render
    project=ai_project(render_project);before=hashes(project)
    result=run_render(project/'edit_plan.resolved.json',settings=Settings(root_dir=ROOT_DIR,motion_enabled=motion,mascot_enabled=mascot,motion_scale=.25,motion_fps=5))
    assert Path(result['path']).is_file() and hashes(project)==before
    report=json.loads((project/'quality_report.json').read_text(encoding='utf-8'))
    assert report['sample_interval_sec']==2.5 and len(report['frames'])==2


def test_controlled_generation_failure_retries_once_then_gradient(render_project,monkeypatch,tmp_path):
    from pydantic import SecretStr
    from pipeline.ai_budget import remaining
    project=ai_project(render_project)
    gateway=Mock()
    gateway.create.side_effect=[({'id':'initial'},None),({'id':'simpler'},None)]
    gateway.status.return_value={'status':'failed','error':{'code':'generation_failed','message':'upstream fixture failure'}}
    monkeypatch.setattr('pipeline.ai_video.VideoGateway',lambda *a:gateway)
    settings=Settings(root_dir=tmp_path,gateway_api_key=SecretStr('fake-secret'),ai_clips_per_video=1)
    result=create_backgrounds(project,settings,confirmed=True)
    assert not result['clips'] and result['warnings'] and gateway.create.call_count==2
    create_backgrounds(project,settings,confirmed=True)
    assert gateway.create.call_count==2 and remaining(settings)==1
    assert 'fake-secret' not in (tmp_path/'logs/gateway_video_errors.log').read_text(encoding='utf-8')


def test_director_controlled_prompts_only_for_eligible_slots(monkeypatch):
    from agents.video_prompt_writer import fill_plan_prompts,fallback_prompt
    plan=graphics_plan();writer=Mock(return_value=fallback_prompt('công nghệ'))
    monkeypatch.setattr('agents.video_prompt_writer.write_video_prompt',writer)
    before=[q.type for s in plan.scenes for q in s.shots]
    fill_plan_prompts(plan,fixture_brief(),Mock(),Mock(),limit=1,controlled=True)
    assert writer.call_count==1 and plan.scenes[0].shots[0].ai_prompt
    assert before==[q.type for s in plan.scenes for q in s.shots]


def test_ambiguous_background_slot_blocks_changed_prompt(render_project,monkeypatch,tmp_path):
    from agents.video_prompt_writer import fallback_prompt
    project=ai_project(render_project);submit=Mock(side_effect=TimeoutError('lost POST'))
    monkeypatch.setattr('pipeline.controlled_ai.create_job',submit)
    settings=Settings(root_dir=tmp_path,ai_clips_per_video=1)
    create_backgrounds(project,settings,confirmed=True)
    data=json.loads((project/'edit_plan.resolved.json').read_text(encoding='utf-8'))
    data['scenes'][0]['shots'][0]['ai_prompt']=fallback_prompt('cây hoa')
    write_json_atomic(project/'edit_plan.resolved.json',data)
    result=create_backgrounds(project,settings,confirmed=True)
    assert submit.call_count==1 and 'dashboard' in result['warnings'][0]
