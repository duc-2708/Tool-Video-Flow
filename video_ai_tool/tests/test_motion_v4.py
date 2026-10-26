"""Original vector scenes, offline Chromium and immutable real-project fixtures."""
import hashlib
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest

from config.settings import ROOT_DIR, Settings
from schemas.assets import ResolvedEditPlan
from schemas.research_brief import ResearchBrief
from schemas.style import CaptionStyle
from schemas.visual import VisualData
from agents.illustrations import TYPES, enough, plan_illustrations, spoken_stat
from pipeline.render_motion import browser_page, capture, scene_payload
from editor.captions import find_font
from tests.test_motion import chromium, sample_scene
from tests.test_assets import sample_mp3
from tests.test_timeline import render_project

FIXTURE = ROOT_DIR / 'tests/fixtures/ai_self_report'


def real_plan():
    return ResolvedEditPlan.model_validate_json((FIXTURE/'edit_plan.resolved.json').read_text(encoding='utf-8'))


def real_brief():
    return ResearchBrief.model_validate_json((FIXTURE/'brief.json').read_text(encoding='utf-8'))


def data_for(name):
    data = VisualData(text='Kiểm tra báo cáo', label='Năng suất tự báo cáo', value=50, unit='%',
        items=['Đọc báo cáo gốc', 'Đối chiếu cách đo', 'Tìm kiểm chứng độc lập'],
        bars=[{'label':'Mốc cũ','value':20}, {'label':'Mốc mới','value':50}], source='Nguồn thử')
    if name == 'timeline_march': data.items=['Tháng một năm trước', 'Tháng tám năm nay', 'Năm sau kiểm chứng']
    return data


@pytest.fixture(scope='module')
def scene_page():
    from tests.test_motion import has_chromium
    if not has_chromium(): pytest.skip('Chromium tùy chọn chưa cài')
    with browser_page((270,480)) as page: yield page


@pytest.mark.parametrize('name', TYPES)
def test_all_scene_types_deterministic_and_large(tmp_path, scene_page, name):
    scene=sample_scene(tmp_path,'text_focus',6.)
    payload=scene_payload(scene,(270,480),CaptionStyle(),{'mascot_enabled':False})
    data=data_for(name)
    assert enough(name,data)
    payload['visual_plan']={'scene_type':name,'data':data.model_dump(mode='json'),
        'camera':{'kind':'pan_left','amount':.06},'beats':[],'mascot_state':'idle'}
    page=scene_page
    capture(page,payload,find_font(ROOT_DIR))
    first=page.evaluate('()=>renderAt(1.2)')
    one=page.screenshot()
    page.evaluate('()=>renderAt(3.8)')
    assert hashlib.sha256(one).digest()!=hashlib.sha256(page.screenshot()).digest()
    page.evaluate('()=>renderAt(1.2)')
    assert hashlib.sha256(one).digest()==hashlib.sha256(page.screenshot()).digest()
    assert first['illustrated'] and first['moving_elements']>=4
    rect=page.locator('.scene-illustration').bounding_box()
    assert rect['height']>=480*.55
    assert page.evaluate('()=>anime.running.length')==0
    assert page.locator('.action-mascot').is_hidden()
    assert page.evaluate("()=>[...document.querySelectorAll('.ill-label')].every(e=>e.textContent.trim().split(/\\s+/).length<=6)")
    if name in {'stack_cards','ring','gauge','bar_grow'}:
        boxes=page.locator('.depth-foreground .ill-label' if name!='stack_cards' else '.depth-middle .ill-label').evaluate_all("els=>els.map(e=>{const b=e.getBoundingClientRect();return {top:b.top,bottom:b.bottom}})")
        assert all(a['bottom']<=b['top']+1 for a,b in zip(boxes,boxes[1:])), 'Labels must not cover each other'
    if name=='terminal_type':
        page.evaluate('()=>renderAt(4.8)')
        texts=page.locator('.depth-foreground .ill-label').all_text_contents()
        assert all(item.replace(' ','') in text.replace(' ','') for item,text in zip(data.items,texts)), 'Typing must finish before the hold interval'
    if name=='magnifier_check':
        page.evaluate('()=>renderAt(.2)')
        early=page.locator('.verdict').evaluate_all("els=>els.map(e=>+e.getAttribute('opacity'))")
        page.evaluate('()=>renderAt(3)')
        late=page.locator('.verdict').evaluate_all("els=>els.map(e=>+e.getAttribute('opacity'))")
        assert early[-1]==0 and late[-1]==1


def test_svg_quality_catches_overlapping_labels(tmp_path,scene_page):
    payload=scene_payload(sample_scene(tmp_path,'text_focus',6.),(270,480),CaptionStyle())
    payload['visual_plan']={'scene_type':'stack_cards','data':data_for('stack_cards').model_dump(mode='json')}
    capture(scene_page,payload,find_font(ROOT_DIR))
    scene_page.evaluate("()=>{renderAt(2);const n=document.querySelector('.depth-middle .ill-label');n.parentNode.append(n.cloneNode(true));}")
    assert 'illustration_label_overlap' in scene_page.evaluate('()=>checkMotionQuality().issues')


def test_real_project_variety_and_numeric_grounding():
    plan=real_plan();brief=real_brief();before=[s.narration for s in plan.scenes]
    plan_illustrations(plan,brief)
    names=[s.visual_plan.scene_type for s in plan.scenes]
    assert all(a!=b for a,b in zip(names,names[1:]))
    assert len(set(names))>=4
    assert plan.scenes[0].visual_plan.data.value==50
    assert plan.scenes[0].visual_plan.data.unit=='%'
    assert before==[s.narration for s in plan.scenes]
    assert spoken_stat('Báo cáo vào tháng tám năm hai nghìn không trăm hai mươi lăm.',{'8','2025'}) is None
    assert spoken_stat('Năng suất tăng năm mươi phần trăm.',{'999'}) is None


def timeline_scene(spec,tmp_path):
    return NS(spec=spec,duration=8.,audio=tmp_path/'scene.mp3',start=0.,shots=[
        NS(spec=q,start=i*8/len(spec.shots),duration=8/len(spec.shots),path=None) for i,q in enumerate(spec.shots)])


def test_render_rebinds_snapshot_and_missing_data_falls_back(tmp_path):
    plan=real_plan();plan_illustrations(plan,real_brief());spec=plan.scenes[0]
    spec.visual_plan.data.value=999
    scene=timeline_scene(spec,tmp_path)
    payload=scene_payload(scene,(270,480),CaptionStyle(),{'illustrations_enabled':True,'allowed_numbers':['50%']})
    assert payload['visual_plan']['data']['value']==50
    spec.visual_plan.scene_type='line_draw'
    for q in spec.shots:
        if q.visual: q.visual.data.bars=[]
    payload=scene_payload(scene,(270,480),CaptionStyle(),{'illustrations_enabled':True})
    assert payload['visual_plan'] is None and payload['illustration_fallback']
    assert all(s['template'] in {'source_card','stock','text_focus'} for s in payload['shots'])


def test_unsupported_chart_number_uses_text_instead(tmp_path):
    plan=real_plan();plan_illustrations(plan,real_brief());spec=plan.scenes[0]
    spec.narration='Đây là ví dụ kiểm tra phương pháp đo lường.'
    for q in spec.shots:
        if q.visual:
            q.visual.data.value=999;q.visual.data.number_text='999';q.visual.data.bars=[]
    spec.visual_plan.scene_type='ring'
    payload=scene_payload(timeline_scene(spec,tmp_path),(270,480),CaptionStyle(),{'illustrations_enabled':True})
    assert payload['visual_plan'] is None
    assert all(s['data'].get('value') is None for s in payload['shots'] if s['template']=='text_focus')


def test_local_assets_have_license_and_no_remote_scene_resources():
    root=ROOT_DIR/'editor/motion/scenes'
    for name in TYPES:
        assert all((root/name/('scene.'+ext)).is_file() for ext in ('html','js','css'))
    assert 'MIT License' in (ROOT_DIR/'assets/vendor/anime/LICENSE').read_text(encoding='utf-8')
    assert 'CC0' in (ROOT_DIR/'assets/illustrations/LICENSE').read_text(encoding='utf-8')
    for path in root.rglob('*'):
        if path.suffix in {'.html','.js','.css'}:
            text=path.read_text(encoding='utf-8')
            assert 'fetch(' not in text and 'setTimeout(' not in text
    from editor.motion.theme import mascot_uris
    assert set(mascot_uris(ROOT_DIR,states=('idle','point','shrug','surprised','think')))=={'idle','point','shrug','surprised','think'}


def test_gateway_background_never_uses_more_than_approved_span(tmp_path,monkeypatch):
    import numpy as np
    from pipeline.controlled_ai import backgrounds_for_scene
    from utils.atomic_io import write_json_atomic
    clip=tmp_path/'clip.mp4';clip.write_bytes(b'fixture media')
    write_json_atomic(tmp_path/'render/ai_backgrounds.json',{'clips':[{'scene_id':1,'shot_id':1,'path':'clip.mp4','job_path':'job.json',
        'sha256':hashlib.sha256(clip.read_bytes()).hexdigest(),'seconds':4}]})
    monkeypatch.setattr('pipeline.controlled_ai.load_job',lambda path:{'clip_path':'clip.mp4'})
    times=[]
    class Video:
        duration=8.
        def __init__(self,*a,**k): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def get_frame(self,t): times.append(t);return np.zeros((16,16,3),dtype=np.uint8)
    monkeypatch.setattr('editor.runtime.VideoFileClip',Video)
    shot=NS(shot_id=1,start=0,duration=7.,spec=NS(visual=NS(template='hook_card')))
    result=backgrounds_for_scene(NS(spec=NS(id=1),start=0,shots=[shot]),tmp_path)
    assert result[0]['duration']==4 and result[0]['provider_duration_sec']==8 and max(times)<4


def test_review_tool_keeps_video_when_qc_is_unavailable(tmp_path,monkeypatch):
    from pipeline.motion_review import review
    from utils.atomic_io import write_json_atomic
    source=tmp_path/'source';source.mkdir()
    write_json_atomic(source/'edit_plan.resolved.json',{'title':'Fixture review'})
    def render(path,**kwargs):
        folder=path.parent/'render';folder.mkdir(exist_ok=True)
        video=folder/'fixture.mp4';video.write_bytes(b'fixture playable result placeholder')
        sheet=folder/'sheet.png';sheet.write_bytes(b'fixture preview placeholder')
        return {'path':str(video),'contact_sheet':str(sheet),'render_seconds':1.,'total_seconds':2.,
            'width':540,'height':960,'duration_sec':3.,'warnings':['QC unavailable']}
    monkeypatch.setattr('pipeline.motion_review.run_render',render)
    result=review(source,Settings(root_dir=tmp_path),scales=(.5,))
    assert result['runs'][0]['quality_pending'] and result['original_inputs_unchanged']
    assert (tmp_path/'source/edit_plan.resolved.json').is_file()


def test_final_export_keeps_30fps_despite_24fps_preview_setting(render_project,scene_page):
    from editor.render import run_render
    settings=Settings(root_dir=ROOT_DIR,motion_enabled=True,motion_scenes_enabled=False,motion_fps=24,
        motion_workers=1,mascot_enabled=False,render_width=240,render_height=426)
    result=run_render(render_project/'edit_plan.resolved.json',mode='final',settings=settings)
    assert result['fps']==30
    from imageio_ffmpeg import read_frames
    reader=read_frames(result['path'])
    try: assert next(reader)['fps']==pytest.approx(30)
    finally: reader.close()


def test_missing_local_library_keeps_old_renderer(tmp_path,scene_page):
    scene=sample_scene(tmp_path,'text_focus',3.)
    payload=scene_payload(scene,(270,480),CaptionStyle())
    payload['visual_plan']={'scene_type':'checklist','data':data_for('checklist').model_dump(mode='json')}
    page=scene_page
    capture(page,payload,find_font(ROOT_DIR))
    page.evaluate('()=>{window.anime=null}')
    assert not page.evaluate('()=>renderAt(1)')['illustrated']
    assert page.locator('.content').is_visible()


def test_amplitude_33ms_cached_without_modifying_audio(tmp_path,sample_mp3,monkeypatch):
    from editor.motion.amplitude import envelope
    before=sample_mp3.read_bytes()
    data=envelope(sample_mp3,tmp_path/'amplitude')
    assert data['interval_sec']==.033 and data['values']
    assert all(0<=x<=1 for x in data['values'])
    call=Mock(side_effect=AssertionError('cache must not decode again'))
    monkeypatch.setattr('editor.motion.amplitude.subprocess.run',call)
    assert envelope(sample_mp3,tmp_path/'amplitude')==data
    assert sample_mp3.read_bytes()==before


def test_optional_scene_config_and_strict_schema():
    from providers.llm.openai_client import response_format
    from schemas.edit_plan import EditPlan
    assert Settings(motion_scenes_enabled='',min_card_hold_sec='').motion_scenes_enabled
    assert Settings().min_card_hold_sec==1.2
    assert response_format(EditPlan)[0]['type']=='json_schema'


@pytest.mark.parametrize('value',['bad data',{'scene_type':'unknown','camera':{'amount':999}}, {'scene_type':'ring','data':{'value':'not a number'}}])
def test_optional_visual_plan_cannot_block_valid_script(value):
    from tests.test_director import fixture_plan
    from schemas.edit_plan import EditPlan
    raw=fixture_plan();raw['scenes'][0]['visual_plan']=value
    plan=EditPlan.model_validate(raw)
    assert plan.scenes[0].narration==raw['scenes'][0]['narration']
    assert plan.scenes[0].visual_plan.scene_type=='text_focus'
    assert plan.scenes[0].visual_plan.repair_notes
    plan_illustrations(plan)
    assert any('illustration_data, nhóm 2' in n for n in plan.review_notes)


def test_caption_phrases_meaningful_and_word_mode_preserved():
    from utils.caption_timing import phrase_groups
    text='Đọc báo cáo gốc. Bạn cần đối chiếu cách đo của nghiên cứu này.'
    words=[(s,i*.2,(i+1)*.2) for i,s in enumerate(text.split())]
    groups=phrase_groups(words)
    assert all(2<=len(g)<=4 for g in groups)
    assert all(g[-1][0].lower().strip('.,') not in {'của','và','cho'} for g in groups[:-1])
    assert len(phrase_groups(words,count=1))==len(words)


def test_motion_scene_plan_regressions():
    from schemas.motion_scene import MotionScenePlan
    from schemas.visual import VisualData
    # 1. Dựng MotionScenePlan với repair_notes=[] không lỗi
    p1 = MotionScenePlan(repair_notes=[])
    assert p1.repair_notes == []
    p2 = MotionScenePlan(scene_type='versus_scale', repair_notes=['note_a'])
    assert p2.repair_notes == ['note_a']

    # 2. Khóa lạ từ LLM -> cảnh báo nhóm 3, không dừng
    p3 = MotionScenePlan(extra_field='something', data={'extra_data': 123, 'text': 'Nội dung'})
    assert any('[illustration_extra, nhóm 3]' in n and 'extra_field' in n for n in p3.repair_notes)
    assert any('[illustration_extra, nhóm 3]' in n and 'extra_data' in n for n in p3.repair_notes)
    assert not hasattr(p3, 'extra_field')

    # 3. Một cảnh hỏng -> rơi về text_focus còn các cảnh khác bình thường
    plan = real_plan()
    brief = real_brief()
    import agents.illustrations
    orig_payload_fn = agents.illustrations._scene_payload

    def faulty_scene_payload(scene, index, previous, used, brief):
        if index == 0:
            raise ValueError("Lỗi nhân tạo cảnh 0 để kiểm tra cách ly")
        return orig_payload_fn(scene, index, previous, used, brief)

    agents.illustrations._scene_payload = faulty_scene_payload
    try:
        plan_illustrations(plan, brief)
    finally:
        agents.illustrations._scene_payload = orig_payload_fn

    assert plan.scenes[0].visual_plan.scene_type == 'text_focus'
    assert any('illustration_data, nhóm 2' in n and 'Cảnh 1' in n for n in plan.review_notes)
    other_types = [s.visual_plan.scene_type for s in plan.scenes[1:]]
    assert any(t != 'text_focus' for t in other_types)
