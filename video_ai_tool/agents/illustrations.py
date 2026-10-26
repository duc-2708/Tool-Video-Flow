"""Group 2/3 animated-scene selection; never invents a numerical value."""
import re
from contextlib import contextmanager
from contextvars import ContextVar
from schemas.motion_scene import MotionScenePlan,SceneCamera,normalize_motion_payload
from schemas.visual import VisualData,VisualBeat
from agents.visual_diversity import concept_card,numeric_mismatches,GENERIC
from agents.director_numbers import normalized_numbers

_diagnostics=ContextVar('illustration_diagnostics',default=None)


@contextmanager
def illustration_diagnostics(diagnostics):
    """Carry the caller's redacting logger without a new settings/API read."""
    token=_diagnostics.set(diagnostics)
    try: yield
    finally: _diagnostics.reset(token)

TYPES=('versus_scale','bar_grow','gauge','ring','line_draw','flow_chain','magnifier_check','funnel_filter','checklist','terminal_type','timeline_march','stack_cards','network_nodes')

# Complete noun phrases only, matched in the actual narration. This lexicon
# selects spoken concepts; it never supplies a missing step, number or claim.
CONCEPT_LABELS=(
    'báo cáo nội bộ','tự đánh giá năng suất','năng suất tăng','kiểm định độc lập',
    'tác động công nghệ','cải thiện công việc','công cụ mới','góc nhìn một chiều',
    'đo lường khách quan','cầu thủ tự chấm điểm','trọng tài bên ngoài',
    'chuyên gia độc lập','tiêu chuẩn đánh giá','dữ liệu nội bộ','tính khách quan',
    'kiểm chứng độc lập','phương pháp đo lường','quyền riêng tư','dữ liệu cá nhân',
    'hạ tầng trọng yếu','lỗ hổng phần mềm','phòng thủ mạng','chi phí vận hành',
    'thị trường việc làm','kỹ năng mới','quy trình làm việc','nguồn thông tin',
)


def concept_labels(text):
    found=[]
    for phrase in CONCEPT_LABELS:
        if match:=re.search(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',text,re.I):
            found.append((match.start(),match[0][:1].upper()+match[0][1:]))
    return [label for _,label in sorted(found)]


def spoken_stat(text,allowed):
    from agents.vietnamese_tts import spoken_to_digits
    digits=spoken_to_digits(text)
    accepted={str(n).rstrip('%') for n in allowed}
    candidates={n for n in normalized_numbers(text,ignore_current_year=False) if n.rstrip('%') in accepted}
    for token in sorted(candidates,key=lambda n:('%' not in n,-abs(float(n.rstrip('%'))))):
        value=float(token.rstrip('%'))
        if 1900<=value<=2100 and value.is_integer(): continue
        raw=str(int(value)) if value.is_integer() else str(value)
        if re.search(r'(?:ngày|tháng|năm)\s+'+re.escape(raw)+r'\b',digits,re.I): continue
        return value,('%' if token.endswith('%') else ''),token
    return None


def enough(name,data):
    import math
    n=len([s for s in data.items if str(s).strip()])
    if name in {'bar_grow','gauge','ring'}: return data.value is not None and math.isfinite(data.value) and (name!='ring' or 0<=data.value<=100 and data.unit=='%')
    if name=='line_draw': return len(data.bars)>=2 and all(math.isfinite(b.value) for b in data.bars)
    if name in {'flow_chain','funnel_filter','network_nodes'}: return n>=3
    if name=='versus_scale': return n>=2 or len(data.bars)>=2
    if name=='timeline_march': return n>=2 and sum(bool(re.search(r'\d|ngày|tháng|năm',x,re.I)) for x in data.items)>=2
    return n>=2 if name in TYPES else False


def scene_data(scene,brief=None):
    visuals=[s for s in scene.shots if s.visual and s.visual.template not in {'stock','source_card','quote_card'}]
    data=VisualData(text=concept_card(scene.narration)[0],fact_ids=scene.fact_ids[:])
    items=concept_labels(scene.narration)
    for shot in visuals:
        v=shot.visual
        for label in [shot.card_text or v.data.text,*v.data.items]:
            if label and not GENERIC.fullmatch(label.strip()) and not re.search(r'\b(?:nội|xu|dễ|thêm|phương)$|^(?:liệu|dường|lẽ)\b',label,re.I):
                label=concept_card(label)[0] if not 2<=len(label.split())<=6 else label
                if label.casefold() not in {x.casefold() for x in items}: items.append(label)
        date_value=bool(v.data.number_text and re.search(r'(?:ngày|tháng)\s+'+re.escape(v.data.number_text.strip())+r'\b',scene.narration,re.I))
        if data.value is None and v.data.value is not None and not date_value and not numeric_mismatches(scene,shot,brief):
            data.value=v.data.value;data.unit=v.data.unit;data.number_text=v.data.number_text;data.label=v.data.label or shot.card_text or v.data.text
        if len(v.data.bars)>=2 and not numeric_mismatches(scene,shot,brief): data.bars=[b.model_copy(deep=True) for b in v.data.bars[:4]]
        if not data.source and v.data.source: data.source=v.data.source;data.source_url=v.data.source_url
    # Multiple already spoken concepts may be illustrated, but never append
    # imaginary quantities, a fake process step, or a fake pass/fail decision.
    if len(items)<3:
        clauses=re.split(r'[.!?;:,]|\b(?:nhưng|trong khi|thay vì|bởi vì)\b',scene.narration,flags=re.I)
        for clause in clauses:
            if len(clause.split())<3: continue
            label,_=concept_card(clause,items)
            if label not in items and not GENERIC.fullmatch(label): items.append(label)
            if len(items)>=5: break
    data.items=items[:5]
    if data.value is None and brief:
        facts=[brief.facts[i-1] for i in scene.fact_ids if 1<=i<=len(brief.facts)]
        allowed=normalized_numbers(' '.join((f.fact_vi or f.claim)+' '+f.claim+' '+(f.evidence_quote or '') for f in facts),ignore_current_year=False)
        if found:=spoken_stat(scene.narration,allowed):
            data.value,data.unit,data.number_text=found
            data.label=next((x for x in items if re.search(r'năng suất|tỷ lệ|doanh thu|chi phí|quy mô',x,re.I)),items[0] if items else data.text)
            if facts: data.source=facts[0].source_name;data.source_url=str(facts[0].source_url)
    return data


def _scene_payload(scene,index,previous,used,brief):
        data=scene_data(scene,brief);text=scene.narration.casefold();preferred=[]
        if re.search(r'so với|thay vì|không phải|trước.+sau|chênh',text): preferred.append('versus_scale')
        if data.value is not None: preferred.extend(['ring','gauge','bar_grow'] if data.unit=='%' else ['bar_grow','gauge'])
        if data.bars: preferred.append('line_draw')
        if re.search(r'có thật|kiểm chứng|phản bác|đúng|sai|báo cáo',text): preferred.append('magnifier_check')
        if re.search(r'lọc|loại bỏ|đầu vào|đầu ra|chọn lọc',text): preferred.append('funnel_filter')
        if scene.information_kind=='mechanism' or re.search(r'quy trình|bước|sau đó|dẫn tới',text): preferred.append('flow_chain')
        if re.search(r'tiêu chí|kiểm tra|cần làm|hãy',text): preferred.append('checklist')
        if re.search(r'tháng|mốc thời gian|ngày',text): preferred.append('timeline_march')
        if re.search(r'mã|phần mềm|lệnh|thuật toán',text): preferred.append('terminal_type')
        if re.search(r'kết nối|mạng|hạ tầng|dữ liệu',text): preferred.append('network_nodes')
        preferred+=['stack_cards','network_nodes','terminal_type','magnifier_check','flow_chain','checklist','versus_scale']
        candidates=list(dict.fromkeys(n for n in preferred if enough(n,data)))
        if data.value is not None:
            numeric=[n for n in candidates if n in {'ring','gauge','bar_grow','line_draw'}]
            candidates=numeric+[n for n in candidates if n not in numeric]
        chosen=next((n for n in candidates if n!=previous and n not in used),next((n for n in candidates if n!=previous),'text_focus'))
        old=scene.visual_plan
        camera=old.camera if old else SceneCamera(kind=('push_in','pan_left','pull_out','pan_right')[index%4])
        state='surprised' if scene.role=='hook' else 'shrug' if scene.role=='cta' else 'think' if re.search(r'sai|kiểm chứng|phản',text) else 'point'
        beats=[VisualBeat(at_sec=.15+i*.6,action=f'item_{i}') for i in range(min(5,len(data.items)))]
        notes=list(getattr(old,'repair_notes',[]) or [])
        if old and old.data!=data:
            notes.append('[illustration_binding, nhóm 2] Đồng bộ visual_plan.data từ visual.data/lời đọc đã qua chính sách căn cứ; không dùng snapshot dữ liệu rời.')
        return dict(scene_type=chosen,data=data,camera=camera,mascot_state=state,beats=beats,repair_notes=notes)


def _construct(payload):
    clean,notes=normalize_motion_payload(payload,MotionScenePlan,origin='internal')
    result=MotionScenePlan.model_validate(clean,context={'motion_origin':'internal'})
    return result,list(dict.fromkeys([*notes,*getattr(result,'repair_notes',[])]))


def _publish(plan,scene,notes,diagnostics):
    safe=[]
    for note in notes:
        message=f'Cảnh {scene.id}: {note}'
        if diagnostics: message=diagnostics.redact(message)
        if message not in plan.review_notes:
            plan.review_notes.append(message)
            if diagnostics:
                try: diagnostics.record(message)
                except OSError:
                    plan.review_notes.append(f'Cảnh {scene.id}: [illustration_log, nhóm 3] Không ghi được log; giữ cảnh báo trong kế hoạch.')
        review=getattr(scene,'review_notes',None)
        if review and message not in review.warnings:
            review.warnings.append(message)
        safe.append(diagnostics.redact(note) if diagnostics else note)
    if scene.visual_plan is not None and 'repair_notes' in type(scene.visual_plan).model_fields:
        scene.visual_plan.repair_notes=list(dict.fromkeys(safe))


def _log_director_error(message: str, error: BaseException | None = None, diagnostics=None):
    if diagnostics:
        try:
            if error: diagnostics.record_exception(error, message)
            else: diagnostics.record(message)
            return
        except OSError: pass
    try:
        from pathlib import Path
        from utils.diagnostics import Diagnostics
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        diag = Diagnostics(log_dir, filename="director_errors.log")
        if error: diag.record_exception(error, message)
        else: diag.record(message)
    except Exception:
        pass


def plan_illustrations(plan,brief=None,*,diagnostics=None):
    """Isolate presentation failure per scene. Never retry an LLM or facts."""
    diagnostics=diagnostics or _diagnostics.get()
    previous=None;used=set()
    for index,scene in enumerate(plan.scenes):
        payload=None;notes=[]
        try:
            payload=_scene_payload(scene,index,previous,used,brief)
            scene.visual_plan,notes=_construct(payload)
        except Exception as error:
            _log_director_error(f'Cảnh {scene.id} [illustration_data, nhóm 2]: lỗi lập kế hoạch ({type(error).__name__}), tự sửa cục bộ 1 lần; không gọi LLM', error, diagnostics)
            notes.append(f'[illustration_data, nhóm 2] {type(error).__name__} khi lập kế hoạch; thử sửa cục bộ 1 lần, dùng text_focus.')
            repaired=dict(payload) if isinstance(payload,dict) else {}
            repaired.pop('camera', None)
            repaired.pop('beats', None)
            fallback_text = concept_card(scene.narration)[0] if getattr(scene, 'narration', None) else 'Minh họa nội dung'
            repaired.update(scene_type='text_focus', data=VisualData(text=fallback_text), camera=SceneCamera(), beats=[], mascot_state='idle', repair_notes=notes)
            try:
                scene.visual_plan,more=_construct(repaired);notes.extend(more)
            except Exception as retry_error:
                _log_director_error(f'Cảnh {scene.id} [illustration_data, nhóm 2]: tự sửa thất bại ({type(retry_error).__name__}); fallback text_focus', retry_error, diagnostics)
                notes.append(f'[illustration_data, nhóm 2] Tự sửa thất bại ({type(retry_error).__name__}); giữ text_focus/đường dựng tĩnh, không đổi lời đọc/fact.')
                try:
                    from schemas.motion_scene import MotionScenePlan as CurrentPlan
                    scene.visual_plan=CurrentPlan(scene_type='text_focus')
                except Exception:
                    scene.visual_plan=None
        _publish(plan,scene,list(dict.fromkeys(notes)),diagnostics)
        chosen=scene.visual_plan.scene_type if scene.visual_plan else 'text_focus'
        previous=chosen;used.add(chosen)
    if not any(s.visual_plan is not None for s in plan.scenes):
        msg = '[illustration_data, nhóm 1] Không dựng nổi bất kỳ cảnh nào trong kế hoạch hoạt họa (visual_plan).'
        _log_director_error(msg, diagnostics=diagnostics)
        raise RuntimeError(msg)
    if len(used-{'text_focus'})<4:
        note='[illustration_variety, nhóm 3] Chưa đủ dữ liệu cho4scene_type khác nhau; không bịa số/bước để đạt chỉ tiêu.'
        if note not in plan.review_notes: plan.review_notes.append(note)
    return plan
