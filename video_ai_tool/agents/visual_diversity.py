"""Presentation-only selection/repairs (groups 2/3). Never validates event facts."""
import re
from collections import Counter
from agents.director_numbers import normalized_numbers
from agents.presentation import card_phrase,shot_context,valid_card

GENERIC=re.compile(r"^(?:ý chính cần nhớ|tổng kết|tóm lại|nội dung chính|điểm cần nhớ|thông tin quan trọng)[.! ]*$",re.I)
STOP=set('là và của cho với từ trong trên những các một này đó thì mà có thể cũng được đang đã như khi để bởi vì nhưng về sẽ bạn mình chúng ta đây'.split())
CONCEPTS=("an ninh mạng","hạ tầng trọng yếu","tự động quét","lỗ hổng phần mềm","mã độc tự động","điều khiển công nghiệp",
    "tài liệu mật","dữ liệu cá nhân","quyền riêng tư","danh tính","tốc độ khai thác","kỹ năng mới","thị trường việc làm",
    "lưới điện","phòng thủ","điểm yếu","ngân sách","công cụ AI","mã nguồn","thói quen","chi phí","hiệu quả")


def concept_card(context,used=()):
    """Prefer a complete existing noun phrase; keywords only as the last icon label."""
    # Citation labels are provenance, never a concept card or a capitalized
    # entity manufactured by the keyword fallback.
    context=re.sub(r'\bTheo\s+[^,!?;\n]+,\s*','',context,flags=re.I)
    used={s.casefold() for s in used}
    candidates=[]
    for phrase in CONCEPTS:
        m=re.search(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',context,re.I)
        if m:
            label=m[0] if len(m[0].split())>=3 else ' '.join(('Bảo vệ' if phrase in {'danh tính','phòng thủ'} else 'Vấn đề',m[0]))
            candidates.append(label)
    candidates.extend(c.strip(' ,:') for c in re.split(r'[.!?;:—]',context) if valid_card(c))
    phrase=card_phrase('',context,used=used)
    if not GENERIC.fullmatch(phrase): candidates.append(phrase)
    result=next((s for s in candidates if valid_card(s) and s.casefold() not in used),None)
    if result: return result[:1].upper()+result[1:],False
    # Select content keywords, never an unfinished N-word opening of narration.
    tokens=list(dict.fromkeys(w.strip(',.!?;:()“”') for w in context.split()
        if w.casefold().strip(',.!?;:()“”') not in STOP and any(c.isalpha() for c in w)))
    for index in range(max(1,len(tokens)-2)):
        label=' '.join(tokens[index:index+3])
        if len(label.split())<3: label='Minh họa '+label
        if valid_card(label) and label.casefold() not in used: return label[:1].upper()+label[1:],True
    return 'Minh họa ý tưởng',True


def repair_cards(plan,diagnostics=None,brief=None):
    history=[];notes=[];generic_used=False
    invalid=set()
    if brief:
        from agents.visual_planner import visual_issues
        for scene,message in visual_issues(plan,brief):
            m=re.match(r'Shot (\d+):',message)
            if m: invalid.add((scene,int(m[1])))
    for scene in plan.scenes:
        for index,shot in enumerate(scene.shots,1):
            v=shot.visual
            if not v or v.template in {'stock','source_card','quote_card'}: continue
            if (scene.id,index) in invalid: continue  # Preserve evidence for unchanged group 1.
            old=shot.card_text or v.data.text or v.data.label
            generic=bool(GENERIC.fullmatch(old.strip()))
            allowed_generic=generic and scene is plan.scenes[-1] and not generic_used
            if allowed_generic: generic_used=True
            duplicate=old.casefold() in {s.casefold() for s in history[-2:]}
            if duplicate or generic and not allowed_generic or not valid_card(old):
                text,icon=concept_card(shot_context(scene,shot),history[-2:])
                shot.card_text=text;shot.emphasis=text.split()[-2:]
                v.data.text=text;v.data.highlight=shot.emphasis
                if v.template=='stat_card': v.data.label=text
                if shot.text_overlay: shot.text_overlay=text
                # text_focus/icon_card already paint a licensed concept icon;
                # repairing a label must not discard valid numeric/list data.
                note=f'[visual_card, nhóm 2] Cảnh {scene.id}, shot {shot.id if hasattr(shot,"id") else scene.shots.index(shot)+1}: {old!r} → {text!r}; '+('minh họa icon.' if icon else 'cụm ý chính riêng.')
                notes.append(note)
            history.append(shot.card_text or v.data.text)
    for note in notes:
        if note not in plan.review_notes: plan.review_notes.append(note)
        if diagnostics: diagnostics.record(note)
    return notes


def values_in(text):
    return {n.rstrip('%') for n in normalized_numbers(text,ignore_current_year=False)}


def numeric_mismatches(scene,shot,brief=None):
    v=shot.visual
    if not v or v.template not in {'stat_card','ring_percent','line_growth','strike_replace','compare_bars'}: return []
    base=scene.narration
    if brief: base+=' '+' '.join((f.fact_vi or f.claim)+' '+f.claim+' '+(f.evidence_quote or '') for f in brief.facts)
    allowed=values_in(base)
    actual=[]
    if v.data.value is not None: actual.append(v.data.value)
    actual.extend(b.value for b in v.data.bars)
    return [x for x in actual if not values_in(f'{x:.10f}'.rstrip('0').rstrip('.'))<=allowed]


def repair_numeric_cards(plan,brief=None):
    """Render only, AFTER existing provenance review. No bypass of Director group 1."""
    notes=[]
    for scene in plan.scenes:
        for index,shot in enumerate(scene.shots,1):
            bad=numeric_mismatches(scene,shot,brief)
            if not bad: continue
            v=shot.visual;v.template='text_focus'
            v.data.value=None;v.data.number_text='';v.data.bars=[];v.data.unit=''
            text,_=concept_card(re.sub(r'\d+(?:[.,]\d+)*','',shot_context(scene,shot)))
            v.data.text=text;v.data.label='';shot.card_text=text
            notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id}, shot {index}: số {bad} không có trong lời đọc/brief; đổi thẻ chữ, không đếm tới số giả.')
    plan.review_notes.extend(n for n in notes if n not in plan.review_notes)
    return notes


def select_templates(plan,brief=None):
    """Only rearrange already authored data. Never invent comparison/quote values."""
    profile=getattr(plan,'style_profile',None)
    weights=getattr(profile,'visual_template_ratios',{}) or {}
    if hasattr(weights,'model_dump'): weights=weights.model_dump()
    counts=Counter();previous=[]
    for si,scene in enumerate(plan.scenes):
        for shot in scene.shots:
            v=shot.visual
            if not v or v.template in {'stock','source_card'}: continue
            d=v.data;context=shot_context(scene,shot);choices=[]
            # Keep content/sentence association and every factual field unchanged.
            if v.template=='quote_card' and d.source and d.source_url: choices=['quote_card','text_focus','icon_card']
            elif d.bars and len(d.bars)>=2:
                if re.search(r'thay vì|không phải|trước.+sau',context,re.I): choices=['strike_replace','versus','compare_bars']
                else: choices=['compare_bars','versus','line_growth']
            elif d.value is not None:
                choices=['ring_percent','stat_card'] if d.unit=='%' and 0<=d.value<=100 else ['stat_card','text_focus']
            elif len(d.items)>=2:
                choices=['timeline','steps_list','versus'] if re.search(r'ngày|tháng|năm|mốc',context,re.I) else ['steps_list','versus','timeline']
            elif scene.role=='cta' or si==len(plan.scenes)-1: choices=['cta_card','text_focus']
            elif si==0 and shot is scene.shots[0]: choices=['hook_card']
            else: choices=['text_focus','icon_card']
            # Original numeric hook is allowed; it still goes through group-1 checks.
            if si==0 and shot is scene.shots[0]: choices=['hook_card']
            eligible=[c for c in choices if not previous or c!=previous[-1]] or choices
            name=min(eligible,key=lambda c:counts[c]/max(.05,float(weights.get(c,1))))
            if v.template!=name:
                note=f'[visual_variety, nhóm 2] Cảnh {scene.id}: {v.template} → {name}, giữ nguyên dữ liệu.'
                if note not in plan.review_notes: plan.review_notes.append(note)
            v.template=name;counts[name]+=1;previous.append(name)
    repair_cards(plan,brief=brief)
    if len(counts)<3:
        note='[visual_variety, nhóm 3] Chưa đủ dữ liệu cho 3 loại mẫu; không tạo số/trích dẫn để bù.'
        if note not in plan.review_notes: plan.review_notes.append(note)
    from agents.illustrations import plan_illustrations
    plan_illustrations(plan,brief)
    return plan
