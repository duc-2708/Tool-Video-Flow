"""Fact-derived motion layout selection. No extra LLM/API calls or new claims."""
import json
import re
from urllib.parse import urlsplit
from agents.director_numbers import normalized_numbers
from schemas.visual import Visual,VisualData,VisualBar


def brief_fact(brief,index):
    return brief.facts[index-1] if type(index) is int and 1<=index<=len(brief.facts) else None


def number_detail(text):
    # Keep the original number's unit/context. Never count a year as a statistic.
    for match in re.finditer(r"(?<!\w)\d+(?:[.,]\d+)*(?:\s*(?:triệu|tỷ|nghìn|million|billion))?\s*%?",text):
        raw=match[0].strip(); numbers=normalized_numbers(raw,ignore_current_year=False)
        if len(numbers)!=1: continue
        token=next(iter(numbers));value=float(token.rstrip("%"))
        if value.is_integer() and 1900<=value<=2100: continue
        # Counting shows base value (5 nghìn -> 5.000); percentage keeps its unit.
        unit="%" if token.endswith("%") else ""
        return value,raw,unit
    try:
        from validation.grounding import extract_numbers
        extracted = extract_numbers(text)
        for num in extracted:
            val = float(num.value)
            if val.is_integer() and 1900 <= val <= 2100: continue
            return val, num.raw, (num.unit or "")
    except Exception:
        pass
    return None


def excerpt(text,words=18):
    return " ".join(text.split()[:words]).rstrip(",;:")


def assign_visuals(plan,brief,*,replace=False):
    if getattr(plan,"content_mode",None)=="explainer_v2":
        # Keep sentence-tagged v2 graphics, especially after audio resolution.
        return plan
    style=getattr(plan,"render_style",None)
    if style is not None and not style.visual_templates: return plan
    all_ids=list(dict.fromkeys(i for s in plan.scenes for i in s.fact_ids if brief_fact(brief,i)))
    sources=list(dict.fromkeys(brief_fact(brief,i).source_name or urlsplit(str(brief_fact(brief,i).source_url)).netloc for i in all_ids))
    slots=[(s,j,shot) for s in plan.scenes for j,shot in enumerate(s.shots)]
    source_slots={len(slots)-1} if len(slots)>=3 and sources else set()
    for position,(scene,j,shot) in enumerate(slots):
        if shot.visual is not None and not shot.visual.auto_generated and not replace: continue
        facts=[brief_fact(brief,i) for i in scene.fact_ids if brief_fact(brief,i)]
        content=" ".join(f.fact_vi or f.claim for f in facts)
        highlights=(shot.text_overlay or excerpt(scene.narration,6)).split()[:6]
        data=VisualData(text=shot.text_overlay or excerpt(scene.narration,22),highlight=highlights,fact_ids=scene.fact_ids[:])
        template="text_focus"
        if position==0: template="hook_card"
        elif position in source_slots:
            template="source_card"
            data=VisualData(source=" · ".join(sources),title=excerpt(scene.narration,20),
                date=str(facts[0].published_at or "") if facts else "",fact_ids=all_ids,
                source_url=str(facts[0].source_url) if facts else "")
        elif scene.role=="cta": template="text_focus"
        elif re.search(r"so với|so sánh|trong khi|lần lượt",content,re.I) and len(facts)>=2:
            # Only compare values with exactly matching units; otherwise use a stat.
            pairs=[(f,number_detail(f.fact_vi or f.claim),i) for i in scene.fact_ids if (f:=brief_fact(brief,i))]
            pairs=[p for p in pairs if p[1]]
            if len(pairs)>=2 and len({p[1][2] for p in pairs})==1 and pairs[0][1][2]=="%":
                template="compare_bars"
                data.bars=[VisualBar(label=excerpt(f.fact_vi or f.claim,8),value=n[0],unit=n[2],fact_id=i) for f,n,i in pairs[:4]]
        if template=="text_focus" and scene.role!="cta":
            if re.search(r"bước|lý do|thứ nhất|bao gồm|gồm có",scene.narration,re.I) and len(facts)>=2:
                template="steps_list";data.items=[excerpt(f.fact_vi or f.claim,16) for f in facts[:4]]
            elif facts and (number:=number_detail(content)):
                template="stat_card"
                data.value,data.number_text,data.unit=number
                data.label=excerpt(content,20)
                data.source=facts[0].source_name
                data.source_url=str(facts[0].source_url)
        shot.visual=Visual(template=template,data=data,auto_generated=True)
    cards=[shot for _,_,shot in slots if shot.visual and shot.visual.template=="source_card"]
    for shot in cards[:-1]:
        shot.visual=Visual(template="text_focus",data=VisualData(text=shot.text_overlay or "Thông tin từ nguồn"),auto_generated=True)
    from agents.presentation import normalize_cards,source_card_once
    source_card_once(plan,brief);normalize_cards(plan,brief)
    from agents.visual_diversity import select_templates
    select_templates(plan,brief)
    return plan


def visual_issues(plan,brief):
    """Visuals have the same hard provenance boundary as spoken claims."""
    issues=[]
    for scene in plan.scenes:
        for index,shot in enumerate(scene.shots,1):
            if not shot.visual or shot.visual.template=="stock": continue
            from agents.visual_policy import content_type
            data=shot.visual.data
            if content_type(scene,shot)!="event": continue  # Background examples are group 3.
            ids=data.fact_ids or scene.fact_ids
            if any(not brief_fact(brief,i) for i in ids):
                issues.append((scene.id,f"Shot {index}: visual có fact_id không tồn tại."));continue
            facts=[brief_fact(brief,i) for i in ids]
            for bar in data.bars:
                if bar.fact_id is not None and bar.fact_id not in ids:
                    issues.append((scene.id,f"Shot {index}: fact_id của thanh so sánh nằm ngoài fact tham chiếu."))
            base=" ".join((f.fact_vi or f.claim)+" "+f.claim+" "+(f.evidence_quote or "")+" "+f.source_name+" "+str(f.published_at or "") for f in facts)
            allowed=normalized_numbers(base,ignore_current_year=False)
            content=" ".join([data.text,data.label,data.title,data.number_text,*data.items,*[b.label for b in data.bars]])
            actual=normalized_numbers(content,ignore_current_year=False)
            values=[]
            if data.value is not None: values.append((data.value,data.unit))
            values.extend((b.value,b.unit) for b in data.bars)
            for value,unit in values:
                actual |= normalized_numbers(f"{value:.8f}".rstrip("0").rstrip(".")+unit,ignore_current_year=False)
            from validation.grounding import numbers_match, normalize_number, entity_matches, extract_entities, get_grounding_mode, repair_visual_grounding

            truly_missing = []
            for act_str in actual:
                matched_allow = next((allow_str for allow_str in allowed if numbers_match(act_str, allow_str)), None)
                if matched_allow:
                    if data.value is not None:
                        act_norm = normalize_number(act_str)
                        all_norm = normalize_number(matched_allow)
                        if act_norm and all_norm and all_norm.unit and data.unit != all_norm.unit:
                            old_u = data.unit or ""
                            data.unit = all_norm.unit
                            note = f"[grounding, tự sửa] Cảnh {scene.id}, shot {index}: '{data.value}{old_u}' -> '{data.value}{data.unit}'"
                            if getattr(plan, "review_notes", None) is not None and note not in plan.review_notes:
                                plan.review_notes.append(note)
                    continue
                truly_missing.append(act_str)

            if truly_missing:
                mode = get_grounding_mode()
                if mode != "block":
                    repaired, note = repair_visual_grounding(scene, shot, brief)
                    if repaired and note and getattr(plan, "review_notes", None) is not None and note not in plan.review_notes:
                        plan.review_notes.append(note)
                else:
                    issues.append((scene.id,f"Shot {index}: số liệu mẫu không có trong fact tham chiếu: {sorted(truly_missing)}; hợp lệ: {sorted(allowed)}."))
            names={f.source_name for f in facts}|{urlsplit(str(f.source_url)).netloc for f in facts}
            if data.source and any(s.strip() not in names for s in data.source.split(" · ")):
                issues.append((scene.id,f"Shot {index}: nguồn mẫu không có trong brief: {data.source}."))
            if data.source_url and data.source_url not in {str(f.source_url) for f in facts}:
                issues.append((scene.id,f"Shot {index}: URL nguồn mẫu không có trong brief."))
            if data.date and data.date not in {str(f.published_at or "") for f in facts}:
                issues.append((scene.id,f"Shot {index}: ngày nguồn mẫu không có trong brief."))
            # Every descriptive item must be an excerpt/rephrasing of referenced text.
            from agents.validation_rules import textkey,proper_names,ORDINARY
            brief_entities = extract_entities(base + " " + brief.topic, sentence_boundary=False)
            # Never join field boundaries into invented entities ("Analytica Vụ").
            for text in (data.text,data.label,data.title,*data.items,*[b.label for b in data.bars]):
                for match in proper_names(text):
                    name=match[0]
                    name=re.sub(r"^(?:Vụ(?: kiện)?|Công ty|Ngân hàng|Sản phẩm)\s+","",name)
                    if all(w in ORDINARY for w in name.split()): continue
                    if textkey(name) in textkey(base+" "+brief.topic):
                        continue
                    if any(entity_matches(name, be.raw) for be in brief_entities):
                        continue
                    mode = get_grounding_mode()
                    if mode != "block":
                        repaired, note = repair_visual_grounding(scene, shot, brief)
                        if repaired and note and getattr(plan, "review_notes", None) is not None and note not in plan.review_notes:
                            plan.review_notes.append(note)
                    else:
                        issues.append((scene.id,f"Shot {index}: tên riêng mẫu không có trong brief: {name}."))
                for quote in re.findall(r'[“"]([^”"]{3,200})[”"]',text):
                    if textkey(quote) not in textkey(base):
                        issues.append((scene.id,f"Shot {index}: trích dẫn đồ họa không có trong fact tham chiếu: {quote!r}."))
    return issues


def covered_sources(plan):
    return {s.strip() for scene in plan.scenes for shot in scene.shots if shot.visual and shot.visual.template=="source_card" for s in shot.visual.data.source.split(" · ") if s.strip()}


def remove_repeated_attribution(plan,brief):
    covered=covered_sources(plan)
    for scene in plan.scenes:
        for name in covered:
            scene.narration=re.sub(r"^Theo\s+"+re.escape(name)+r",\s*","",scene.narration,flags=re.I)
        if scene.narration: scene.narration=scene.narration[0].upper()+scene.narration[1:]
    return plan


def create_visual_plan_v3(*args, **kwargs):
    from agents.visual_planner_v3 import create_visual_plan_v3 as _impl
    return _impl(*args, **kwargs)

