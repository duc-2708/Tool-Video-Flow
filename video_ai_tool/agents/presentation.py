"""Local editorial presentation repairs; no relaxation of factual validators."""
import re

TRAILING_CUTOFF = {
    'của', 'trong', 'trên', 'dưới', 'và', 'với', 'là', 'mà', 'để', 'cho', 'về',
    'các', 'những', 'một', 'cái', 'con', 'chiếc', 'bà', 'ông', 'đã', 'đang', 'sẽ',
    'lại', 'cũng', 'rất', 'hơn', 'nhất', 'ra', 'vào', 'lên', 'xuống', 'đột', 'cá',
    'vai', 'dàn', 'bối', 'sự', 'vụ', 'điều', 'việc', 'vì', 'do', 'bởi', 'hay',
    'hoặc', 'nếu', 'khi', 'tuy', 'dẫu', 'dở', 'bị', 'được', 'đóng', 'đặt', 'này',
    'kia', 'đó', 'đây', 'tới', 'ở', 'gặp', 'gọi', 'như', 'theo', 'hành', 'tạo', 'làm',
    'khiến', 'giúp', 'sau', 'bày', 'tỏ', 'lên', 'xuống', 'qua', 'lại', 'thường', 'có',
    'tài', 'đến', 'đi', 'có thể', 'giống', 'ý', 'thì', 'rằng', 'vậy', 'thế', 'nào', 'sao', 'gì', 'ai', 'đâu', 'nữa', 'chăng'
}

LEADING_CUTOFF = {
    'cố', 'việc', 'động', 'giống', 'điều', 'ngột', 'trò', 'nhạc', 'nhân', 'viên',
    'này', 'kia', 'đó', 'đây', 'thì', 'mà', 'là', 'và', 'của', 'với', 'để', 'cho',
    'về', 'bà', 'ông', 'bị', 'được', 'ra', 'vào', 'lại', 'cũng', 'hơn', 'nhất',
    'như', 'bởi', 'do', 'vì', 'đóng', 'đặt', 'tạo', 'làm', 'những', 'các', 'một',
    'khiến', 'giúp', 'sau', 'sau khi', 'trong khi', 'bởi vì', 'thay vì', 'bày', 'tỏ', 'đã'
}

TRAILING = tuple(TRAILING_CUTOFF)

KNOWN_PHRASE_EXPANSIONS = {
    'minh họa ý': 'Minh họa ý tưởng',
    'ý tưởng minh họa': 'Ý tưởng minh họa'
}

def clean_semantic_label(label: str) -> str:
    """Trim punctuation and eliminate truncated or dangling boundary words."""
    if not label: return ""
    text = " ".join(str(label).split()).strip(" .,:;!?…()“”\"'")
    low = text.lower()
    if low in KNOWN_PHRASE_EXPANSIONS:
        return KNOWN_PHRASE_EXPANSIONS[low]

    words = text.split()
    while words and words[0].lower() in LEADING_CUTOFF:
        words.pop(0)
    while words and words[-1].lower() in TRAILING_CUTOFF:
        words.pop(-1)

    # Max 4 words for clean readable presentation labels
    if len(words) > 4:
        words = words[:4]
        while words and words[-1].lower() in TRAILING_CUTOFF:
            words.pop(-1)

    if not (2 <= len(words) <= 4):
        return ""
    result = " ".join(words)
    return result[:1].upper() + result[1:]

def labels_are_duplicate(l1: str, l2: str) -> bool:
    """Check if two labels are duplicate via substring, word overlap, or core unaccented concept match."""
    s1, s2 = l1.lower().strip(), l2.lower().strip()
    if not s1 or not s2: return False
    if s1 == s2 or s1 in s2 or s2 in s1:
        return True
    w1, w2 = set(s1.split()), set(s2.split())
    if not w1 or not w2:
        return False
    jaccard = len(w1 & w2) / len(w1 | w2)
    if jaccard >= 0.30:
        return True
    try:
        from validation.grounding import normalize_entity
        e1 = normalize_entity(s1)
        e2 = normalize_entity(s2)
        stopwords = {'van', 'de', 'tim', 'ra', 'viec', 'su', 'co', 'cac', 'nhung', 'mot', 'la', 'va', 'cua'}
        c1 = set(e1.core) - stopwords
        c2 = set(e2.core) - stopwords
        if len(c1 & c2) >= 2 or (c1 and c2 and (c1 == c2 or c1.issubset(c2) or c2.issubset(c1))):
            return True
    except Exception:
        pass
    return False

MODAL=re.compile(r"\b(?:có thể|có lẽ|dường như)\b",re.I)
INTERNAL=re.compile(r"nguồn dữ kiện sự kiện|event facts|fact[_ ]ids?|sentence[_ ]index|review[_ ]notes|knowledge[_ ]notes",re.I)
TRANSLATIONS={"job guarantee":"bảo đảm việc làm","safety net":"lưới an sinh","reskilling":"đào tạo lại kỹ năng",
    "upskilling":"nâng cao kỹ năng","universal basic income":"thu nhập cơ bản phổ quát"}


def vietnamese_terms(text):
    for old,new in TRANSLATIONS.items():
        text=re.sub(r"(?<!\w)"+re.escape(old)+r"(?!\w)",new,text,flags=re.I)
    return text


def valid_card(text):
    text=" ".join(text.split()).strip(" .,:;!?…")
    words = text.split()
    if not (3 <= len(words) <= 6) or INTERNAL.search(text):
        return False
    if words[0].lower() in LEADING_CUTOFF or words[-1].lower() in TRAILING_CUTOFF:
        return False
    return not re.search(r"(?:^|\s)(?:" + "|".join(re.escape(s) for s in TRAILING_CUTOFF) + r")$", text, re.I)


def card_phrase(text,context="",*,used=None):
    """Select complete concepts, never the first N words of a spoken sentence."""
    used=used if used is not None else set()
    text=vietnamese_terms(INTERNAL.sub("",text or "")).strip(" .,:;!?…")
    context=vietnamese_terms(context or text)
    if valid_card(text) and text.casefold() not in used:
        return text[:1].upper()+text[1:]
    candidates=[]
    for match in re.finditer(r"\b\d+(?:[.,]\d+)*(?:\s+(?:triệu|tỷ|nghìn|phần trăm))?\s+(?:việc làm|người lao động|người dùng|nhân viên|công việc|đô la|USD|token)\b",context,re.I):
        candidates.append(match[0])
    # Extract meaningful noun phrases already present, preserving original order.
    phrases=("ghế dự phòng","lưới đệm","bảo đảm việc làm","công việc tạm thời","kỹ năng mới","chuyển hướng",
        "nguy cơ bị thay thế","nhà tuyển dụng cứu cánh","trợ cấp tiền mặt","công việc hữu ích","năng lực quản lý",
        "ngân sách","người lao động","công trình địa phương","thời gian học","công việc","công nghệ",
        "quyền riêng tư","dữ liệu cá nhân","vay","ngân hàng","cách tiếp cận","lựa chọn")
    expand={"lưới đệm":"Một lưới đệm","chuyển hướng":"Chuyển hướng công việc","ngân sách":"Ngân sách chương trình",
        "công việc":"Cách tổ chức công việc","công nghệ":"Tác động công nghệ","vay":"Hoạt động cho vay",
        "ngân hàng":"Hoạt động ngân hàng","lựa chọn":"Cân nhắc lựa chọn"}
    for phrase in phrases:
        match=re.search(r"(?<!\w)"+re.escape(phrase)+r"(?!\w)",context,re.I)
        if match: candidates.append(expand.get(phrase,match[0]))
    # Complete short clauses can be used; do not clip an unfinished clause.
    candidates.extend(x.strip() for x in re.split(r"[.!?;:–—]",context) if valid_card(x))
    candidates=[x for x in candidates if valid_card(x)]
    result=next((x for x in candidates if x.casefold() not in used),next(iter(candidates),"Ý chính cần nhớ"))
    return result[:1].upper()+result[1:]


def shot_context(scene,shot):
    visual=shot.visual
    if visual and visual.sentence_index and visual.sentence_index<=len(scene.sentences):
        return scene.sentences[visual.sentence_index-1].text
    return scene.narration


def normalize_cards(plan,brief=None,*,diagnostics=None):
    changes=[]
    # Expose newly authored card claims to the SAME existing factual checker.
    for scene in plan.scenes:
        for shot in scene.shots:
            if shot.card_text and shot.visual and shot.visual.template!="source_card":
                shot.visual.data.text=shot.card_text
    invalid=set()
    if brief:
        from agents.visual_planner import visual_issues
        for scene,message in visual_issues(plan,brief):
            match=re.match(r"Shot (\d+):",message)
            if match: invalid.add((scene,int(match[1])))
    for scene in plan.scenes:
        used=set()
        for index,shot in enumerate(scene.shots,1):
            visual=shot.visual
            if visual and visual.template=="source_card": continue
            if not visual or visual.template=="stock": continue
            if (scene.id,index) in invalid: continue  # Never erase evidence of a group-1 violation.
            context=shot_context(scene,shot)
            before=shot.card_text or visual.data.text or shot.text_overlay or ""
            phrase=card_phrase(before,context,used=used);used.add(phrase.casefold())
            emphasis=[s for s in shot.emphasis if s.casefold() in phrase.casefold()][:2]
            if not emphasis: emphasis=phrase.split()[-2:]
            if before!=phrase or shot.card_text!=phrase or shot.emphasis!=emphasis:
                changes.append((scene.id,f"Shot {index}: card_text {before!r} → {phrase!r}; emphasis={emphasis}."))
            shot.card_text=phrase;shot.emphasis=emphasis
            # Existing group-1 validators see these exact words; no new bypass field.
            visual.data.text=phrase;visual.data.highlight=emphasis
            if visual.template=="stat_card": visual.data.label=phrase
            if shot.text_overlay is not None: shot.text_overlay=phrase
            if visual.template=="steps_list":
                visual.data.items=[card_phrase(item,item) for item in visual.data.items[:4]]
    if diagnostics:
        for scene,message in changes: diagnostics.record(f"card_text nhóm 2; cảnh {scene}; {message}")
    return changes


def source_card_once(plan,brief=None):
    from schemas.visual import Visual,VisualData
    slots=[(scene,shot) for scene in plan.scenes for shot in scene.shots]
    cards=[shot for _,shot in slots if shot.visual and shot.visual.template=="source_card"]
    if not cards: return
    final=slots[-1][1]
    source=cards[-1].visual.model_copy(deep=True)
    if brief:
        ids=list(dict.fromkeys(i for scene in plan.scenes for i in scene.fact_ids if 1<=i<=len(brief.facts)))
        if not ids: ids=source.data.fact_ids
        facts=[brief.facts[i-1] for i in ids if 1<=i<=len(brief.facts)]
        names=list(dict.fromkeys(f.source_name for f in facts if f.source_name))[:2]
        if names:
            source.data.source=" · ".join(names);source.data.fact_ids=ids
            source.data.source_url=str(facts[0].source_url);source.data.date=facts[0].published_at or ""
    source.data.title="";source.data.text="";source.data.label=""
    for scene,shot in slots:
        if shot in cards and shot is not final:
            shot.visual=Visual(template="text_focus",content_type="explain",auto_generated=True,
                data=VisualData(text=card_phrase("",scene.narration)))
    final.visual=source;final.card_text=None;final.emphasis=[];final.text_overlay=None


def quality_findings(plan):
    result=[]
    for i,scene in enumerate(plan.scenes):
        window=plan.scenes[max(0,i-1):i+1]
        count=sum(len(MODAL.findall(s.narration)) for s in window)
        if count>1: result.append((scene.id,f"Có {count} cụm có thể/có lẽ/dường như trong {len(window)} cảnh; tối đa 1 mỗi 2 cảnh, giữ mềm nếu là ước đoán."))
        if i and re.match(r"có thể (?:hiểu|hình dung)",scene.narration,re.I) and re.match(r"có thể (?:hiểu|hình dung)",plan.scenes[i-1].narration,re.I):
            result.append((scene.id,"Hai cảnh liên tiếp mở bằng khuôn Có thể hiểu/hình dung."))
    if plan.scenes:
        hook=re.split(r"(?<=[.!?])\s+",plan.scenes[0].narration)[0]
        if re.match(r"những yếu tố nào|điều gì|bạn có biết|vì sao chuyện",hook,re.I) or len(hook.split())>12:
            result.append((plan.scenes[0].id,"Hook cần con số có căn cứ/hiểu lầm/ngược trực giác trong tối đa 12 từ; tránh câu hỏi chung."))
    return result


def humanize_locally(plan,brief):
    """Remove framing clutter, never convert a factual forecast into certainty."""
    for scene in plan.scenes:
        if scene.sentences:
            for sentence in scene.sentences:
                sentence.text=vietnamese_terms(sentence.text)
                sentence.text=re.sub(r"^Có thể (?:hiểu là|hình dung)(?: rằng| đây là)?[, :]?\s*","",sentence.text,flags=re.I)
                base=" ".join(brief.facts[i-1].fact_vi or brief.facts[i-1].claim for i in sentence.fact_ids if 1<=i<=len(brief.facts))
                if sentence.type=="event" and base and not re.search(r"có thể|có lẽ|dường như|may|might|could|ước|nguy cơ",base,re.I):
                    sentence.text=MODAL.sub("",sentence.text)
                sentence.text=" ".join(sentence.text.split())
                sentence.text=sentence.text[:1].upper()+sentence.text[1:]
            scene.narration=" ".join(s.text for s in scene.sentences)
        else: scene.narration=vietnamese_terms(scene.narration)
    for scene,message in quality_findings(plan):
        note=f"[presentation_voice, nhóm 3] Cảnh {scene}: {message}"
        if note not in plan.review_notes: plan.review_notes.append(note)
    return plan


def repair_generic_hook(plan,brief):
    """Only generic question/overlong openings; event facts remain fully validated."""
    if not plan.scenes: return
    first=plan.scenes[0]
    if not re.match(r"những yếu tố nào|điều gì|bạn có biết",first.narration,re.I): return
    from schemas.explainer import ScriptSentence
    fact=None;opening=""
    for i,f in enumerate(brief.facts,1):
        text=f.fact_vi or f.claim
        match=re.search(r"\d+(?:[.,]\d+)*\s+triệu việc làm",text,re.I)
        if match and re.search(r"nguy cơ|rủi ro",text,re.I) and "thay thế" in text.casefold():
            opening="Ước tính "+match[0]+" có nguy cơ bị thay thế.";fact=i;break
    if not opening:
        opening="Có việc làm chưa chắc đã hết lo." if re.search(r"việc làm|job guarantee",brief.topic,re.I) else "Điều quen thuộc chưa chắc đã đúng."
    first.narration=opening
    if first.sentences:
        first.sentences=[ScriptSentence(type="event" if fact else "opinion",text=opening,fact_ids=[fact] if fact else [])]
    first.fact_ids=[fact] if fact else []
    plan.review_notes.append("Hook câu hỏi chung được thay bằng điểm mở ngắn; giữ kiểm tra căn cứ nhóm 1.")
