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
    from validation.grounding import proper_names, entity_matches, extract_entities
    from agents.validation_rules import textkey
    base=brief.topic+" "+" ".join((f.fact_vi or f.claim)+" "+f.claim+" "+(f.evidence_quote or "")+" "+f.source_name for f in brief.facts)
    allowed=" "+textkey(base)+" "
    brief_entities = extract_entities(base, sentence_boundary=False)
    results = []
    for m in proper_names(text):
        name = m[0]
        if " " + textkey(name) + " " in allowed:
            continue
        if any(entity_matches(name, be.raw) for be in brief_entities):
            continue
        results.append(name)
    return list(dict.fromkeys(results))


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
                actual_nums = normalized_numbers(content,ignore_current_year=False)
                base_nums = normalized_numbers(base,ignore_current_year=False)
                from validation.grounding import numbers_match
                missing = [a for a in actual_nums if not any(numbers_match(a, b) for b in base_nums)]
                if missing: issues.append((scene.id,f"Câu {index} event có số không có trong fact tham chiếu: {sorted(missing)}."))
                names=unknown_names(sentence.text,brief)
                if names: issues.append((scene.id,f"Câu {index} event có tên riêng ngoài brief: {names}."))
            elif sentence.type in {"explain","opinion"}:
                issues.extend((scene.id,f"Câu {index}: "+m) for m in background_issues(sentence.text,brief,sentence.type))
            elif sentence.type=="cta":
                issues.extend((scene.id,f"Câu {index}: "+m) for m in background_issues(sentence.text,brief,"cta"))
                if is_cta_event_claim(sentence.text, brief):
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


def is_cta_event_claim(text: str, brief) -> bool:
    """
    Check if a CTA sentence contains an empirical factual event claim or is an assertion labeled as CTA.
    Exempts:
    - Pure questions (ends with ? or starts with question words without factual assertions).
    - Call to action / comment invitations ('bình luận', 'theo dõi', 'bạn nghĩ sao').
    - Capitalized first word (not treated as an entity name).
    - Trivial CTA numbers ('1 bình luận', '2 phương án').
    """
    if not text:
        return False

    raw_text = text.strip()

    # 1. Clean trivial quantities in CTA (e.g. "1 bình luận", "2 phương án", "một ý kiến")
    quantity_text = re.sub(
        r"\b\d+\s*(?:bình luận|like|thả tim|lựa chọn|phương án|câu hỏi|người|bạn)\b",
        "",
        raw_text,
        flags=re.I,
    )
    quantity_text = re.sub(
        r"\bmột\s+(?:bình luận|like|chia sẻ|lần|câu hỏi|ý kiến|cách|góc nhìn)\b",
        "",
        quantity_text,
        flags=re.I,
    )

    # 2. Extract concrete empirical numbers
    numbers = normalized_numbers(quantity_text, ignore_current_year=False)
    if numbers == {"100"} and re.search(r"100%\s*(?:không|\?|$)", raw_text, re.I):
        numbers = set()

    # 3. Check for pure question
    is_question = raw_text.endswith("?") or bool(
        re.search(r"^(?:liệu|theo bạn|bạn có nghĩ|có nên|phải chăng|bạn nghĩ sao|ai sẽ|liệu rằng)\b", raw_text, re.I)
    )

    # 4. Check for pure call to action / comment invitation without event assertions
    is_invitation = bool(
        re.search(
            r"\b(?:bình luận|để lại ý kiến|chia sẻ ý kiến|theo dõi|follow|đăng ký|ủng hộ kênh|cho mình biết|hãy cho biết|đừng quên|bạn nghĩ sao)\b",
            raw_text,
            re.I,
        )
    )

    # 5. Extract entity names from brief (exclude first word capitalization)
    from agents.proper_names import proper_names
    entity_tokens = set()
    if brief and getattr(brief, "facts", None):
        fields = [brief.topic, *[v for f in brief.facts for v in (f.fact_vi or f.claim, f.claim, f.source_name)]]
        entity_tokens = {m[0] for val in fields for m in proper_names(val)}

    words = raw_text.split()
    body_text = " ".join(words[1:]) if len(words) > 1 else ""
    mentioned_entities = [t for t in entity_tokens if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", body_text)]

    # 6. Check for event action assertion
    has_event_action = bool(
        re.search(
            r"\b(?:bị kiện|nộp đơn kiện|đệ đơn kiện|bị phạt|thông báo|tuyên bố|ký kết|ra mắt|công bố|phán quyết|kết luận|khởi kiện)\b",
            raw_text,
            re.I,
        )
    )
    has_entity_event = bool(
        mentioned_entities and (
            has_event_action or re.search(r"(?<!\w)(?:" + "|".join(re.escape(t) for t in mentioned_entities) + r")\s+(?:đã|vừa|mới)\s+\w+", raw_text, re.I)
        )
    )

    if numbers:
        return True
    if has_entity_event or (has_event_action and (mentioned_entities or re.search(r"\b(?:đã|vừa|mới)\s+\w+", raw_text, re.I))):
        return True
    is_opinion = bool(re.search(r"\b(?:nghĩ|tin|quan điểm|đánh giá|theo mình|cho rằng|cảm thấy)\b", raw_text, re.I))
    if is_opinion and not is_question and not is_invitation and not re.match(r"^\s*(?:ví dụ|minh họa|chẳng hạn)\b", raw_text, re.I):
        return True
    return False


def split_assertion_and_cta(text: str) -> tuple[str, str]:
    """Split a sentence into an assertion part and a CTA question/invitation part."""
    raw = text.strip()
    parts = re.split(r"(?<=[.?!])\s+", raw)
    if len(parts) >= 2:
        last = parts[-1].strip()
        if last.endswith("?") or re.search(r"\b(?:bình luận|theo dõi|bạn nghĩ|ý kiến|theo bạn|bạn có)\b", last, re.I):
            return " ".join(parts[:-1]).strip(), last

    split_match = re.search(
        r"\s*[,;–—]\s*(?=(?:bạn nghĩ sao|theo bạn|bạn có nghĩ|bạn đồng ý|hãy để lại|hãy bình luận|đừng quên|liệu\b|anh em nghĩ sao|bạn có tin|bạn có)\b)",
        raw,
        re.I
    )
    if split_match:
        assert_part = raw[:split_match.start()].strip()
        cta_part = raw[split_match.end():].strip()
        if assert_part and not assert_part.endswith((".", "!", "?")):
            assert_part += "."
        if cta_part:
            cta_part = cta_part[0].upper() + cta_part[1:]
            if not cta_part.endswith((".", "!", "?")):
                cta_part += "?"
        return assert_part, cta_part

    return raw, ""


def find_matching_facts_for_cta(text: str, brief) -> list[int]:
    """Find 1-based fact_ids in brief that match numbers, names, or key phrases in text."""
    if not brief or not getattr(brief, "facts", None):
        return []

    text_nums = normalized_numbers(text, ignore_current_year=False)
    from agents.proper_names import proper_names
    from agents.validation_rules import textkey

    words = text.split()
    sub_text = " ".join(words[1:]) if len(words) > 1 else text
    text_names = {m[0].lower() for m in proper_names(sub_text)}

    scored_facts = []
    for idx, fact in enumerate(brief.facts, 1):
        fact_str = f"{fact.fact_vi or fact.claim} {fact.claim} {fact.source_name or ''}"
        fact_nums = normalized_numbers(fact_str, ignore_current_year=False)
        fact_names = {m[0].lower() for m in proper_names(fact_str)}

        score = 0
        common_nums = text_nums.intersection(fact_nums)
        if common_nums:
            score += len(common_nums) * 6
        elif text_nums and fact_nums and not common_nums:
            score -= 3

        common_names = text_names.intersection(fact_names)
        if common_names:
            score += len(common_names) * 5

        t_key = set(textkey(text).split())
        f_key = set(textkey(fact_str).split())
        overlap = t_key.intersection(f_key)
        score += len(overlap)

        if score > 0 and (common_nums or common_names or len(overlap) >= 4):
            scored_facts.append((idx, score))

    scored_facts.sort(key=lambda x: x[1], reverse=True)
    if scored_facts and scored_facts[0][1] >= 5:
        best_score = scored_facts[0][1]
        return [idx for idx, s in scored_facts if s >= best_score * 0.8]
    return []


def repair_cta_sentences(plan, brief):
    """
    Repair CTA sentences that contain event claims following the 3-step priority:
    1(a) Match fact in brief -> re-label to 'event' with fact_ids (or split into event + cta question).
    1(b) No fact match, but general explanation/opinion -> re-label to 'opinion'/'explain', strip ungrounded numbers/names.
    1(c) Ungrounded assertion -> cut assertion, keep pure CTA question, log review_notes.
    Only fails if all 3 fail and no valid sentence remains in scene.
    """
    if not is_v2(plan): return []
    fixed = []
    review_notes = getattr(plan, "review_notes", None)
    if review_notes is None:
        review_notes = []
        setattr(plan, "review_notes", review_notes)

    for scene in plan.scenes:
        if not getattr(scene, "sentences", None):
            continue
        new_sentences = []
        scene_modified = False

        for index, sentence in enumerate(scene.sentences, 1):
            if sentence.type != "cta":
                new_sentences.append(sentence)
                continue

            if not is_cta_event_claim(sentence.text, brief):
                new_sentences.append(sentence)
                continue

            assert_part, cta_part = split_assertion_and_cta(sentence.text)
            clean_assert = assert_part.rstrip(".!?, ").strip()
            if clean_assert and not clean_assert.endswith((".", "!", "?")):
                clean_assert += "."

            # 1(a) Match fact in brief
            matched_facts = find_matching_facts_for_cta(assert_part or sentence.text, brief)
            if matched_facts:
                ev_sent = type(sentence)(text=clean_assert, type="event", fact_ids=matched_facts)
                new_sentences.append(ev_sent)
                scene_modified = True
                msg = f"Câu {index}: CTA chứa khẳng định sự kiện khớp fact #{matched_facts}; tách/chuyển nhãn sang event."
                fixed.append((scene.id, msg))
                review_notes.append(f"[cta_repair, nhóm 2] Cảnh {scene.id}: {msg}")
                if cta_part:
                    new_sentences.append(type(sentence)(text=cta_part, type="cta", fact_ids=[]))
                elif scene.role == "cta" or scene == plan.scenes[-1]:
                    new_sentences.append(type(sentence)(text="Bạn nghĩ sao về điều này? Hãy để lại ý kiến dưới phần bình luận nhé.", type="cta", fact_ids=[]))
                continue

            # 1(b) Not matching fact, but general explanation or opinion
            is_opinion = bool(re.search(r"\b(?:nghĩ|tin|quan điểm|đánh giá|theo mình|cho rằng|cảm thấy|dường như|rõ ràng)\b", assert_part, re.I))
            unknown = unknown_names(assert_part, brief)
            actual_nums = normalized_numbers(assert_part, ignore_current_year=False)

            if (is_opinion or not actual_nums) and not unknown:
                new_type = "opinion" if is_opinion else "explain"
                exp_sent = type(sentence)(text=clean_assert, type=new_type, fact_ids=[])
                new_sentences.append(exp_sent)
                scene_modified = True
                msg = f"Câu {index}: CTA là nhận định/giải thích chung; chuyển nhãn sang '{new_type}'."
                fixed.append((scene.id, msg))
                review_notes.append(f"[cta_repair, nhóm 2] Cảnh {scene.id}: {msg}")
                if cta_part:
                    new_sentences.append(type(sentence)(text=cta_part, type="cta", fact_ids=[]))
                elif scene.role == "cta" or scene == plan.scenes[-1]:
                    new_sentences.append(type(sentence)(text="Bạn nghĩ sao về điều này? Hãy để lại ý kiến dưới phần bình luận nhé.", type="cta", fact_ids=[]))
                continue

            # 1(c) Ungrounded assertion -> cut assertion, keep pure CTA question
            cta_final = cta_part if cta_part else "Bạn nghĩ sao về chuyện này? Hãy để lại ý kiến dưới phần bình luận nhé."
            cta_sent = type(sentence)(text=cta_final, type="cta", fact_ids=[])
            new_sentences.append(cta_sent)
            scene_modified = True
            msg = f"Câu {index}: Cắt bỏ khẳng định không có căn cứ trong CTA, giữ lại câu hỏi tương tác."
            fixed.append((scene.id, msg))
            review_notes.append(f"[cta_repair, nhóm 2] Cảnh {scene.id}: {msg}")

        if scene_modified and new_sentences:
            scene.sentences = new_sentences

    if fixed:
        sync_narration(plan)
    return fixed
