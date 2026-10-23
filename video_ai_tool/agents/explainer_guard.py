"""Sentence-level boundary: background knowledge cannot launder event claims."""
import re
from agents.director_numbers import normalized_numbers


def is_v2(plan): return getattr(plan,"content_mode",None)=="explainer_v2"


def event_text(scene):
    return " ".join(s.text for s in scene.sentences if s.type=="event") if scene.sentences else scene.narration


SOFT=r"thường|có thể|nhiều khả năng|theo mình|mình nghĩ|giả sử|hình dung|ví dụ|tưởng tượng"


def background_issues(text,brief,kind="explain"):
    from agents.proper_names import proper_names
    base=brief.topic+" "+" ".join((f.fact_vi or f.claim)+" "+f.claim+" "+f.source_name for f in brief.facts)
    errors=[]
    quantity_text=re.sub(r"\bmột(?=\s+(?:cách|cỗ|chiếc|bước|nhóm|người|việc|phần|ý|khâu|câu|loại|quy|điểm|tấm|bức))","",text,flags=re.I)
    actual=normalized_numbers(quantity_text,ignore_current_year=False)
    fields=[brief.topic,*[value for f in brief.facts for value in (f.fact_vi or f.claim,f.claim,f.source_name)]]
    company_tokens={m[0] for value in fields for m in proper_names(value)}
    mentioned=[t for t in company_tokens if re.search(r"(?<!\w)"+re.escape(t)+r"(?!\w)",text)]
    if actual:
        rounded=all(re.fullmatch(r"\d+%?",n) and int(n.rstrip("%"))%10==0 for n in actual)
        if not re.search(r"khoảng|ước chừng|ước tính|xấp xỉ|hàng\s+(?:chục|trăm|nghìn|triệu)",text,re.I) or not rounded or mentioned:
            errors.append("Số nền phải làm tròn, có từ ước lượng và không gắn với công ty/người thật; chuyển dữ kiện cụ thể sang event và dẫn fact.")
    if mentioned and re.search(r"đã|thông báo|tuyên bố|báo cáo|bị|quyết định|khẳng định|sẽ\s+(?:cắt|sa thải|đạt|tăng|giảm)",text,re.I):
        errors.append("Câu đang kể sự kiện cụ thể về "+", ".join(mentioned)+"; không được gắn nhãn kiến thức nền.")
    if re.search(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{4})?\b|[“\"][^”\"]+[”\"]",text) and mentioned:
        errors.append("Ngày/trích dẫn gắn với thực thể phải là event có căn cứ.")
    return list(dict.fromkeys(errors))


def unknown_names(text,brief):
    from agents.proper_names import proper_names
    from agents.validation_rules import textkey
    base=brief.topic+" "+" ".join((f.fact_vi or f.claim)+" "+f.claim+" "+(f.evidence_quote or "")+" "+f.source_name for f in brief.facts)
    allowed=" "+textkey(base)+" "
    return list(dict.fromkeys(m[0] for m in proper_names(text) if " "+textkey(m[0])+" " not in allowed))


def sentence_background_warnings(plan,brief):
    if not is_v2(plan): return []
    return [(scene.id,f"Câu {index}: ví dụ nền, nên kiểm tra lại tên riêng ngoài brief: {', '.join(names)}.")
        for scene in plan.scenes for index,sentence in enumerate(scene.sentences,1)
        if sentence.type in {"explain","opinion","cta"} and (names:=unknown_names(sentence.text,brief))]


def repair_event_names(plan,brief):
    """One local attempt per invalid event sentence; never invent a replacement claim.

Use the existing Vietnamese fact, not an invented assertion with an anonymized
subject. Other sentences/IDs remain intact. Unreferenced events still fail.
"""
    if not is_v2(plan): return []
    fixed=[]
    for scene in plan.scenes:
        for index,sentence in enumerate(scene.sentences,1):
            names=unknown_names(sentence.text,brief) if sentence.type=="event" else []
            valid=[i for i in sentence.fact_ids if type(i) is int and 1<=i<=len(brief.facts)]
            if not names or not valid: continue
            replacement=brief.facts[valid[0]-1].fact_vi or brief.facts[valid[0]-1].claim
            if not replacement or unknown_names(replacement,brief): continue
            old=sentence.text
            sentence.text=replacement;sentence.fact_ids=[valid[0]]
            fixed.append((scene.id,f"Câu {index}: tự sửa tên riêng ngoài brief {names}; dùng fact #{valid[0]} đã có căn cứ. {old!r} → {replacement!r}"))
    if fixed: sync_narration(plan)
    return fixed


def sentence_issues(plan,brief):
    if not is_v2(plan): return []
    from agents.validation_rules import textkey
    issues=[]
    for scene in plan.scenes:
        if not scene.sentences:
            issues.append((scene.id,"Cần nhãn type cho từng câu lời đọc Explainer v2."));continue
        if " ".join(scene.narration.split())!=" ".join(" ".join(s.text for s in scene.sentences).split()):
            issues.append((scene.id,"Nhãn câu không khớp narration; sửa danh sách câu có nhãn rồi đồng bộ lời đọc."))
        for index,sentence in enumerate(scene.sentences,1):
            ids=sentence.fact_ids
            if sentence.type=="event":
                if not ids or any(type(i) is not int or not 1<=i<=len(brief.facts) for i in ids):
                    issues.append((scene.id,f"Câu {index} event cần fact_ids tồn tại."));continue
                base=" ".join((brief.facts[i-1].fact_vi or brief.facts[i-1].claim)+" "+brief.facts[i-1].claim for i in ids)
                content=sentence.text
                # Names like 24h/5.5 remain legitimate only when the full name is in brief.
                from agents.director_sources import number_names
                for name in number_names(brief): content=re.sub(re.escape(name),"",content,flags=re.I)
                missing=normalized_numbers(content,ignore_current_year=False)-normalized_numbers(base,ignore_current_year=False)
                if missing: issues.append((scene.id,f"Câu {index} event có số không có trong fact tham chiếu: {sorted(missing)}."))
                names=unknown_names(sentence.text,brief)
                if names: issues.append((scene.id,f"Câu {index} event có tên riêng ngoài brief: {names}."))
            elif sentence.type in {"explain","opinion"}:
                issues.extend((scene.id,f"Câu {index}: "+m) for m in background_issues(sentence.text,brief,sentence.type))
            elif sentence.type=="cta":
                issues.extend((scene.id,f"Câu {index}: "+m) for m in background_issues(sentence.text,brief,"cta"))
                if normalized_numbers(sentence.text,ignore_current_year=False) or re.search(r"đã|thông báo|bị phạt",sentence.text,re.I):
                    issues.append((scene.id,f"Câu {index}: CTA không được chứa khẳng định sự kiện; gắn nhãn event và dẫn fact."))
    return issues


def sync_narration(plan):
    for scene in plan.scenes:
        scene.narration=" ".join(s.text for s in scene.sentences)
        scene.fact_ids=list(dict.fromkeys(i for s in scene.sentences if s.type=="event" for i in s.fact_ids))


def limit_attribution(plan,brief):
    names=sorted({f.source_name for f in brief.facts},key=len,reverse=True)
    for scene in plan.scenes:
        for sentence in scene.sentences:
            for name in names:
                escaped=re.escape(name)
                sentence.text=re.sub(r"\bTheo\s+"+escaped+r",\s*","",sentence.text,flags=re.I).strip()
                sentence.text=re.sub(r"^"+escaped+r"\s+(?:cho biết|cho hay|ghi nhận|thông tin thêm|đưa tin|báo cáo|nhận định)[,:\s]*","",sentence.text,flags=re.I).strip()
            if sentence.type in {"explain","opinion"}:
                sentence.text=re.sub(r"(?:đây là\s+)?minh chứng(?: cho việc)?", "đây có thể là dấu hiệu, nhưng chưa đủ để kết luận rằng",sentence.text,flags=re.I)
                sentence.text=re.sub(r"rất rõ ràng|chắc chắn|chứng tỏ","có thể",sentence.text,flags=re.I)
            if sentence.text: sentence.text=sentence.text[0].upper()+sentence.text[1:]
    sync_narration(plan)
