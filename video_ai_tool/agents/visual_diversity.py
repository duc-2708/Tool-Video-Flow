"""Presentation-only selection/repairs (groups 2/3). Never validates event facts."""
import re
from collections import Counter
from agents.director_numbers import normalized_numbers
from agents.presentation import card_phrase,shot_context,valid_card,TRAILING_CUTOFF,LEADING_CUTOFF,clean_semantic_label,labels_are_duplicate

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
    used_set={s.casefold() for s in used}
    candidates=[]
    for phrase in CONCEPTS:
        m=re.search(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',context,re.I)
        if m:
            label=m[0] if len(m[0].split())>=3 else ' '.join(('Bảo vệ' if phrase in {'danh tính','phòng thủ'} else ('Phân tích' if phrase in {'điểm yếu','lỗ hổng phần mềm'} else 'Vấn đề'),m[0]))
            candidates.append(label)
    candidates.extend(c.strip(' ,:') for c in re.split(r'(?<!\d)\.|\.(?!\d)|[!?;:—]',context) if valid_card(c))
    phrase=card_phrase('',context,used=used_set)
    if not GENERIC.fullmatch(phrase): candidates.append(phrase)

    # First check clean semantic candidates
    for c in candidates:
        cleaned = clean_semantic_label(c)
        if cleaned and valid_card(cleaned) and cleaned.casefold() not in used_set and not any(labels_are_duplicate(cleaned, u) for u in used_set):
            return cleaned[:1].upper()+cleaned[1:], False

    # Extract clean clauses (3-6 words) from context rather than arbitrary sliding windows
    clauses = re.split(r'(?<!\d)\.|\.(?!\d)|[!?;:—–,\(\)“”\"\[\]]|\b(?:và|hoặc|nhưng|mà|để|như|khi|sau khi|trong khi|thay vì|bởi vì)\b', context, flags=re.I)
    for cl in clauses:
        cl_clean = clean_semantic_label(cl)
        if cl_clean and valid_card(cl_clean) and cl_clean.casefold() not in used_set and not any(labels_are_duplicate(cl_clean, u) for u in used_set):
            return cl_clean[:1].upper()+cl_clean[1:], True
        words = cl.strip().split()
        if len(words) >= 3:
            for n_words in (4, 3, 5):
                for idx in range(len(words) - n_words + 1):
                    sub = clean_semantic_label(' '.join(words[idx:idx+n_words]))
                    if sub and valid_card(sub) and sub.casefold() not in used_set and not any(labels_are_duplicate(sub, u) for u in used_set):
                        return sub[:1].upper()+sub[1:], True
    # Fallback to any valid subclause from context
    for cl in clauses:
        words = cl.strip().split()
        if len(words) >= 3:
            for n_words in (4, 3, 5):
                for idx in range(len(words) - n_words + 1):
                    sub = clean_semantic_label(' '.join(words[idx:idx+n_words]))
                    if sub and valid_card(sub):
                        return sub[:1].upper()+sub[1:], True
    return 'Hạ tầng trọng yếu', False



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
    allowed = {n.rstrip('%') for n in normalized_numbers(text, ignore_current_year=False)}
    from editor.format_number import parse_display_number
    import re
    # Extract raw tokens
    for token in re.findall(r'\b\d+(?:[.,]\d+)*\b', text):
        if ',' in token and '.' not in token:
            clean = token.replace(',', '.')
        elif '.' in token and ',' not in token:
            parts = token.split('.')
            if len(parts) == 2 and len(parts[1]) != 3:
                clean = token
            else:
                clean = token.replace('.', '')
        else:
            clean = token.replace('.', '').replace(',', '.')
        try:
            val = float(clean)
            allowed.add(str(int(val)) if val.is_integer() else str(val))
        except ValueError:
            pass
    # Extract parsed display numbers
    for m in re.finditer(r'(?<!\w)(\d+(?:[.,]\d+)*\s*(?:[A-Za-z%€$đ]+)?)(?!\w)', text):
        p = parse_display_number(m.group(1))
        if p:
            allowed.add(str(int(p.value)) if p.value.is_integer() else str(p.value))
            allowed.add(str(int(p.full_numeric_value)) if p.full_numeric_value.is_integer() else str(p.full_numeric_value))
    return allowed


def numeric_mismatches(scene,shot,brief=None):
    v=getattr(shot,'visual',None) or (getattr(shot,'spec',None) and getattr(shot.spec,'visual',None))
    if not v or v.template not in {'stat_card','ring_percent','line_growth','strike_replace','compare_bars'}: return []
    base=getattr(scene,'narration',None) or (getattr(scene,'spec',None) and getattr(scene.spec,'narration','')) or ''
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
        base = scene.narration
        if brief: base += ' ' + ' '.join((f.fact_vi or f.claim) + ' ' + f.claim + ' ' + (f.evidence_quote or '') for f in brief.facts)
        allowed = values_in(base)

        for index,shot in enumerate(scene.shots,1):
            # Tự động chuẩn hóa chuỗi số thô > 6 chữ số sang quy mô rút gọn (triệu, tỷ)
            v = shot.visual
            if v and v.data:
                raw_num = str(v.data.number_text or (v.data.value if v.data.value is not None else ""))
                if re.search(r'\b\d{7,}\b', raw_num):
                    from editor.format_number import parse_display_number
                    parsed = parse_display_number(f"{raw_num} {v.data.unit or ''}")
                    if parsed:
                        v.data.value = parsed.value
                        v.data.number_text = parsed.formatted_number
                        v.data.unit = parsed.unit_display
                        notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id}, shot {index}: chuẩn hóa chuỗi số thô {raw_num} thành {parsed.formatted_text}.')

            bad=numeric_mismatches(scene,shot,brief)
            if not bad: continue
            v=shot.visual;v.template='text_focus'
            v.data.value=None;v.data.number_text='';v.data.bars=[];v.data.unit=''
            text,_=concept_card(re.sub(r'\d+(?:[.,]\d+)*','',shot_context(scene,shot)))
            v.data.text=text;v.data.label='';shot.card_text=text
            notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id}, shot {index}: số {bad} không có trong lời đọc/brief; đổi thẻ chữ, không đếm tới số giả.')

        vp = getattr(scene, 'visual_plan', None)
        if vp and getattr(vp, 'data', None):
            raw_vp_num = str(vp.data.number_text or (vp.data.value if vp.data.value is not None else ""))
            if re.search(r'\b\d{7,}\b', raw_vp_num):
                from editor.format_number import parse_display_number
                parsed = parse_display_number(f"{raw_vp_num} {vp.data.unit or ''}")
                if parsed:
                    vp.data.value = parsed.value
                    vp.data.number_text = parsed.formatted_number
                    vp.data.unit = parsed.unit_display
                    notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id} visual_plan: chuẩn hóa chuỗi số thô {raw_vp_num} thành {parsed.formatted_text}.')
            has_percent_evidence = ('%' in base) or ('phần trăm' in base.lower())
            if vp.data.unit == '%' and not has_percent_evidence:
                vp.data.unit = ''
                notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id} visual_plan: đơn vị % không có căn cứ; xóa đơn vị %.')
            actual = []
            if getattr(vp.data, 'value', None) is not None:
                actual.append(vp.data.value)
            if getattr(vp.data, 'bars', None):
                actual.extend(b.value for b in vp.data.bars)
            bad = [x for x in actual if not values_in(f'{x:.10f}'.rstrip('0').rstrip('.')) <= allowed]
            if bad:
                vp.scene_type = 'text_focus'
                vp.data.value = None
                vp.data.bars = []
                vp.data.unit = ''
                notes.append(f'[visual_number, nhóm 2] Cảnh {scene.id} visual_plan: số {bad} không có trong lời đọc/brief; đổi sang text_focus.')
            elif vp.data.value is None:
                vp.data.unit = '' 

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
    if not any(getattr(s, 'visual_plan', None) for s in plan.scenes):
        plan_illustrations(plan,brief)
    return plan
