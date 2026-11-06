"""Grounding verification and deterministic healing for Light Glass Slide Script.

Rules:
1. Every number / percentage in slots MUST exist in the slide narration or brief facts.
2. Fabricated numbers trigger layout downgrade to lg_note_card.
3. Every emphasis phrase MUST be an exact verbatim substring of the slide narration.
4. Word boundary wrapping ensures no cut-off words or orphaned characters.
5. Adjacent duplicate layouts are healed to distinct layouts.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from schemas.slide_script import (
    SlideScript,
    SlideItem,
    wrap_text_greedy,
    extract_clean_headline,
    clean_trailing_dangling,
)
from editor.motion.light_glass_slots import (
    truncate_complete_phrase,
    text_similarity,
    contains_metaphor,
    is_valid_subsequence_of_narration,
    FORBIDDEN_BOILERPLATE_LABELS,
    _sanitize_metaphor,
)


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, strip accents-insensitive punctuation."""
    if not text:
        return ""
    # Standardize unicode
    norm = unicodedata.normalize("NFKC", str(text)).lower()
    # Replace punctuation with space
    norm = re.sub(r"[^\w\s\d%.,]", " ", norm)
    # Collapse multiple spaces
    return " ".join(norm.split())


def extract_numbers_from_text(text: str) -> set[str]:
    """Extract numeric tokens (including % or commas/dots normalized)."""
    if not text:
        return set()
    matches = re.findall(r"\b\d+(?:[.,]\d+)?%?\b", str(text))
    results = set()
    for m in matches:
        clean = m.strip()
        results.add(clean)
        # Add alternative dot/comma representation
        if "," in clean:
            results.add(clean.replace(",", "."))
        if "." in clean:
            results.add(clean.replace(".", ","))
        # Add pure digits
        digits_only = re.sub(r"[^\d]", "", clean)
        if digits_only:
            results.add(digits_only)
    return results


def extract_proper_nouns(text: str) -> set[str]:
    """Find capitalized multi-word or single-word entities (excluding sentence start)."""
    if not text:
        return set()
    # Find words starting with capital letter
    tokens = text.split()
    entities = set()
    for i, t in enumerate(tokens):
        # Ignore first token of sentence
        if i == 0 or tokens[i - 1].endswith((".", "!", "?")):
            continue
        clean = re.sub(r"[^\w]", "", t)
        if clean and clean[0].isupper() and len(clean) > 1:
            entities.add(clean.lower())
    return entities


def verify_and_ground_slides(
    slide_script: SlideScript,
    sentences_by_id: dict[int, dict[str, Any]] | None = None,
    brief: Any = None,
) -> SlideScript:
    """Validate and heal SlideScript against ground truth narration and brief facts."""
    repair_notes: list[str] = list(slide_script.repair_notes)
    sentences_by_id = sentences_by_id or {}

    # 1. Build global ground-truth corpus
    global_corpus_text = []
    global_numbers: set[str] = set()

    # From brief
    if brief:
        b_topic = getattr(brief, "topic", "") or (brief.get("topic") if isinstance(brief, dict) else "")
        if b_topic:
            global_corpus_text.append(str(b_topic))
        b_facts = getattr(brief, "facts", None) or (brief.get("facts") if isinstance(brief, dict) else [])
        for f in b_facts:
            claim = getattr(f, "claim", "") or (f.get("claim") if isinstance(f, dict) else "")
            quote = getattr(f, "evidence_quote", "") or (f.get("evidence_quote") if isinstance(f, dict) else "")
            if claim:
                global_corpus_text.append(str(claim))
            if quote:
                global_corpus_text.append(str(quote))
        b_nums = getattr(brief, "key_numbers", None) or (brief.get("key_numbers") if isinstance(brief, dict) else [])
        if b_nums:
            for kn in b_nums:
                t = getattr(kn, "text", "") or (kn.get("text") if isinstance(kn, dict) else "")
                if t:
                    global_corpus_text.append(str(t))

    # From sentences
    for s_data in sentences_by_id.values():
        txt = s_data.get("text", "")
        if txt:
            global_corpus_text.append(str(txt))

    full_corpus_str = " ".join(global_corpus_text)
    global_numbers.update(extract_numbers_from_text(full_corpus_str))
    global_norm_corpus = normalize_text(full_corpus_str)

    # 2. Process each slide
    healed_slides: list[SlideItem] = []

    for s_idx, slide in enumerate(slide_script.slides):
        s_layout = slide.layout
        s_slots = dict(slide.slots)

        # Narration for this slide
        slide_narration = slide.narration
        if not slide_narration and slide.sentence_ids:
            slide_narration = " ".join(
                sentences_by_id.get(sid, {}).get("text", "") for sid in slide.sentence_ids
            ).strip()

        slide_numbers = extract_numbers_from_text(slide_narration) | global_numbers
        slide_norm_narration = normalize_text(slide_narration)

        # Grounding Rule A: Numbers in slots
        if s_layout in ("lg_stat_hero", "kit_stat"):
            val_raw = s_slots.get("value")
            val_num_tokens = extract_numbers_from_text(str(val_raw)) if val_raw is not None else set()
            is_val_grounded = bool(val_num_tokens and any(nt in slide_numbers for nt in val_num_tokens))

            if not is_val_grounded and val_raw is not None:
                # Fabricated or ungrounded number! Downgrade to kit_title / lg_note_card
                target_downgrade = "kit_title" if s_layout == "kit_stat" else "lg_note_card"
                note = f"[grounding_unverified_number, nhóm 2] Slide {slide.id}: số liệu '{val_raw}' không có căn cứ trong lời đọc hoặc brief. Hạ cấp về {target_downgrade}."
                repair_notes.append(note)
                s_layout = target_downgrade
                s_slots = {
                    "chip": "TIÊU ĐIỂM",
                    "title": extract_clean_headline(slide_narration) or clean_trailing_dangling(truncate_complete_phrase(slide_narration, 88)),
                    "subtitle": clean_trailing_dangling(truncate_complete_phrase(slide_narration, 140)) if slide_narration else "",
                    "text": clean_trailing_dangling(truncate_complete_phrase(slide_narration, 140)) if slide_narration else "Thông tin ghi nhận.",
                }

        # Check all string slots for ungrounded numbers (skip and validate date fields)
        if s_layout not in ("lg_note_card", "kit_title"):
            for k, v in list(s_slots.items()):
                if k in ("source_date", "date"):
                    if not (isinstance(v, str) and re.match(r"^\d{2}/\d{2}/\d{4}$", v.strip())):
                        del s_slots[k]
                    continue
                if isinstance(v, str):
                    slot_nums = extract_numbers_from_text(v)
                    for sn in slot_nums:
                        if sn not in slide_numbers:
                            # Strip or sanitize ungrounded number token
                            v_clean = re.sub(rf"\b{re.escape(sn)}\b", "", v).strip()
                            s_slots[k] = v_clean
                            repair_notes.append(f"[grounding_strip_number, nhóm 2] Slide {slide.id}: loại bỏ số '{sn}' không có căn cứ khỏi slot '{k}'.")
                elif isinstance(v, list) and k == "items":
                    clean_items = []
                    for item in v:
                        item_str = str(item)
                        i_nums = extract_numbers_from_text(item_str)
                        ungrounded = [n for n in i_nums if n not in slide_numbers]
                        if not ungrounded:
                            clean_items.append(item_str)
                        else:
                            repair_notes.append(f"[grounding_strip_item, nhóm 2] Slide {slide.id}: bỏ mục '{item_str}' chứa số '{ungrounded[0]}' không có căn cứ.")
                    if clean_items:
                        s_slots["items"] = clean_items
                    else:
                        s_slots["items"] = [clean_trailing_dangling(truncate_complete_phrase(slide_narration, 88))] if slide_narration else ["Nội dung trọng tâm"]

        # Grounding Rule B: Headline verification & repair
        if s_layout in ("lg_source_headline", "kit_title"):
            title_raw = str(s_slots.get("title") or s_slots.get("headline") or "").strip()
            if not title_raw:
                # Missing headline: extract clean phrase from narration
                title_raw = extract_clean_headline(slide_narration) or "Tin Công Nghệ"
                repair_notes.append(f"[grounding_heal_headline, nhóm 2] Slide {slide.id}: tự bổ sung tiêu đề từ câu đọc ('{title_raw}').")
            # Enforce clean phrase boundary without cut-off words
            s_slots["title"] = extract_clean_headline(title_raw) or clean_trailing_dangling(truncate_complete_phrase(title_raw, 88))

        # Grounding Rule C: Emphasis verification
        # Every emphasis phrase MUST be a verbatim substring of slide_narration
        clean_emphasis = []
        for emp in slide.emphasis:
            norm_phrase = normalize_text(emp.phrase)
            if norm_phrase in slide_norm_narration or normalize_text(emp.phrase) in global_norm_corpus:
                clean_emphasis.append(emp)
            else:
                repair_notes.append(f"[grounding_drop_emphasis, nhóm 2] Slide {slide.id}: bỏ cụm nhấn '{emp.phrase}' do không có trong lời đọc.")

        # Grounding Rule D: Slot character limits
        # Pill <= 28 chars, trimmed of trailing dangling words
        for p_key in ("pill", "badge", "chip", "kicker", "sub_pill"):
            if p_key in s_slots and s_slots[p_key]:
                p_val = str(s_slots[p_key]).strip()
                if len(p_val) > 28:
                    w = wrap_text_greedy(p_val, max_chars_per_line=28, max_lines=1)
                    s_slots[p_key] = clean_trailing_dangling(w[0] if w else truncate_complete_phrase(p_val, 28))
                else:
                    s_slots[p_key] = clean_trailing_dangling(p_val)

        # Features items <= 88 chars, max 4 items, trimmed of trailing dangling words
        if "items" in s_slots and isinstance(s_slots["items"], list):
            s_slots["items"] = [
                clean_trailing_dangling(truncate_complete_phrase(str(x).strip(), 88))
                for x in s_slots["items"][:4]
                if clean_trailing_dangling(truncate_complete_phrase(str(x).strip(), 88))
            ]

        # Compare sides <= 40 chars
        for side in ("left", "right"):
            if side in s_slots and isinstance(s_slots[side], dict):
                s_dict = dict(s_slots[side])
                for sub_k in ("label", "text", "title"):
                    if sub_k in s_dict and s_dict[sub_k]:
                        s_dict[sub_k] = clean_trailing_dangling(truncate_complete_phrase(str(s_dict[sub_k]).strip(), 40))
                s_slots[side] = s_dict

        # Grounding Rule P: Boilerplate labels removal
        for p_key in ("pill", "badge", "chip", "kicker", "title"):
            if p_key in s_slots and isinstance(s_slots[p_key], str) and s_slots[p_key]:
                if s_slots[p_key].lower().strip() in FORBIDDEN_BOILERPLATE_LABELS:
                    repair_notes.append(f"[grounding_strip_boilerplate, nhóm 2] Slide {slide.id}: loại bỏ nhãn mẫu '{s_slots[p_key]}' khỏi slot '{p_key}'.")
                    if p_key == "title":
                        raw_h = extract_clean_headline(slide_narration) or clean_trailing_dangling(truncate_complete_phrase(slide_narration, 88))
                        s_slots["title"] = _sanitize_metaphor(raw_h) if contains_metaphor(raw_h) else raw_h
                    else:
                        s_slots[p_key] = "TIÊU ĐIỂM"

        # Grounding Rule S: Subsequence verification (ratio >= 0.80)
        # Only enforce subsequence if slide_narration does not contain metaphors (otherwise card must use substantive meaning)
        if not contains_metaphor(slide_narration):
            for k in ("title", "subtitle"):
                if k in s_slots and isinstance(s_slots[k], str) and s_slots[k]:
                    if not is_valid_subsequence_of_narration(s_slots[k], slide_narration, 0.80):
                        if k == "title":
                            healed_t = extract_clean_headline(slide_narration) or clean_trailing_dangling(truncate_complete_phrase(slide_narration, 88))
                            if not contains_metaphor(healed_t):
                                repair_notes.append(f"[grounding_heal_subsequence, nhóm 2] Slide {slide.id}: tiêu đề '{s_slots[k]}' không khớp thứ tự câu đọc (ratio < 0.80). Đã tự sửa về '{healed_t}'.")
                                s_slots["title"] = healed_t
                        else:
                            s_slots["subtitle"] = ""

        # Grounding Rule M: Metaphor filtering from cards (enforce strictly across all card slots)
        for k in ("title", "subtitle", "quote", "text", "headline"):
            if k in s_slots and isinstance(s_slots[k], str) and s_slots[k]:
                if contains_metaphor(s_slots[k]):
                    s_slots[k] = _sanitize_metaphor(s_slots[k])
                    repair_notes.append(f"[grounding_strip_metaphor, nhóm 2] Slide {slide.id}: loại bỏ ẩn dụ/ví von khỏi slot '{k}'.")
        if "items" in s_slots and isinstance(s_slots["items"], list):
            clean_items = []
            for x in s_slots["items"]:
                str_x = str(x)
                if contains_metaphor(str_x):
                    str_x = _sanitize_metaphor(str_x)
                if str_x and not contains_metaphor(str_x):
                    clean_items.append(str_x)
            s_slots["items"] = clean_items

        # Grounding Rule Bullet: Bullet cannot overlap >= 70% with title/headline
        if s_slots.get("title") and s_slots.get("items") and isinstance(s_slots["items"], list):
            non_overlap_items = []
            for it in s_slots["items"]:
                str_it = str(it).strip()
                if str_it and text_similarity(str(s_slots["title"]), str_it) < 0.70:
                    non_overlap_items.append(str_it)
            if non_overlap_items:
                s_slots["items"] = non_overlap_items
            else:
                s_slots.pop("items", None)
                if s_layout == "kit_list":
                    s_layout = "kit_title"
                    repair_notes.append(f"[grounding_dedup_bullet, nhóm 2] Slide {slide.id}: bullet trùng >= 70% với tiêu đề; bỏ bullet và chuyển sang kit_title.")

        # Grounding Rule Subtitle & Text: New clause only (>= 6 words, <= 70% similarity with title)
        for sub_k in ("subtitle", "sub", "text"):
            if s_slots.get("title") and s_slots.get(sub_k):
                sub_w = str(s_slots[sub_k]).split()
                sim = text_similarity(str(s_slots["title"]), str(s_slots[sub_k]))
                if len(sub_w) < 6 or sim >= 0.70:
                    s_slots[sub_k] = ""

        s_image_prompt = getattr(slide, "image_prompt", "") or str(s_slots.get("image_prompt", ""))
        if s_image_prompt:
            s_slots["image_prompt"] = s_image_prompt

        healed_slide = SlideItem(
            id=slide.id,
            layout=s_layout,
            sentence_ids=slide.sentence_ids,
            slots=s_slots,
            source_ref=slide.source_ref,
            emphasis=clean_emphasis,
            t_start=slide.t_start,
            t_end=slide.t_end,
            duration=slide.duration,
            narration=slide_narration,
            image_prompt=s_image_prompt,
        )
        healed_slides.append(healed_slide)

    # 3. Structural Healing: enforce layout rules
    if healed_slides:
        # First slide MUST be kit_title, lg_source_headline, lg_note_card, or kit_photo (when real photo available)
        if healed_slides[0].layout not in ("kit_title", "lg_source_headline", "lg_note_card", "kit_photo"):
            repair_notes.append(f"[layout_structure, nhóm 2] Slide đầu đổi từ '{healed_slides[0].layout}' sang 'kit_title'.")
            healed_slides[0] = healed_slides[0].model_copy(update={"layout": "kit_title"})

        # Last slide MUST be kit_outro or lg_cta_profile
        if len(healed_slides) >= 2 and healed_slides[-1].layout not in ("kit_outro", "lg_cta_profile"):
            repair_notes.append(f"[layout_structure, nhóm 2] Slide cuối đổi từ '{healed_slides[-1].layout}' sang 'kit_outro'.")
            healed_slides[-1] = healed_slides[-1].model_copy(update={"layout": "kit_outro"})

        # Anti-repetition: no adjacent slides with identical layout
        for i in range(1, len(healed_slides) - 1):
            if healed_slides[i].layout == healed_slides[i - 1].layout:
                curr_slots = healed_slides[i].slots or {}
                has_stat = bool(curr_slots.get("value") or curr_slots.get("stat_value"))
                has_compare = bool(curr_slots.get("left") and curr_slots.get("right"))
                is_kit = str(healed_slides[i].layout).startswith("kit_")

                if is_kit:
                    candidates = []
                    if has_stat:
                        candidates.append("kit_stat")
                    if has_compare:
                        candidates.append("kit_compare")
                    candidates.extend(["kit_title", "kit_list"])
                    default_layout = "kit_title"
                else:
                    candidates = []
                    if has_stat:
                        candidates.append("lg_stat_hero")
                    if has_compare:
                        candidates.append("lg_vs_compare")
                    candidates.extend(["lg_note_card", "lg_shot_features"])
                    default_layout = "lg_note_card"

                prev_l = healed_slides[i - 1].layout
                next_l = healed_slides[min(len(healed_slides) - 1, i + 1)].layout
                alt = next((l for l in candidates if l != prev_l and l != next_l), None)
                if not alt:
                    alt = next((l for l in candidates if l != prev_l), default_layout)

                new_slots = dict(curr_slots)
                t_clean = str(new_slots.get("title") or "").strip()
                if alt in ("kit_list", "lg_shot_features"):
                    sub = new_slots.get("subtitle") or healed_slides[i].narration
                    clean_sub = clean_trailing_dangling(sub)
                    if t_clean and clean_sub.lower().startswith(t_clean.lower()):
                        remainder = clean_sub[len(t_clean):].strip()
                        remainder = re.sub(r"^(?:giúp|khiến|để|nhằm|cho thấy|và|là|có|trong|với|tại|ở|đòi hỏi)\s+", "", remainder, flags=re.I).strip()
                        remainder = re.sub(r"^[,;:\-—]\s*", "", remainder).strip()
                        if len(remainder.split()) >= 6:
                            clean_sub = remainder[0].upper() + remainder[1:]
                        else:
                            clean_sub = ""
                    if not clean_sub or len(clean_sub.split()) < 6 or (t_clean and text_similarity(clean_sub, t_clean) >= 0.70):
                        supp_text = ""
                        if i + 1 < len(healed_slides):
                            cand_supp = clean_trailing_dangling(healed_slides[i + 1].narration)
                            if cand_supp and len(cand_supp.split()) >= 6 and text_similarity(cand_supp, t_clean) < 0.70:
                                supp_text = cand_supp
                        clean_sub = supp_text
                    if not clean_sub or len(clean_sub.split()) < 6:
                        if len(healed_slides[i].narration.split()) >= 6:
                            new_slots["title"] = "Thông tin nổi bật"
                            new_slots["items"] = [clean_trailing_dangling(healed_slides[i].narration)]
                        else:
                            alt = "kit_title" if is_kit else "lg_note_card"
                            if not new_slots.get("subtitle"):
                                new_slots["subtitle"] = clean_trailing_dangling(truncate_complete_phrase(healed_slides[i].narration, 140))
                    else:
                        new_slots["items"] = [clean_trailing_dangling(clean_sub)]
                elif alt in ("kit_title", "lg_note_card") and not new_slots.get("subtitle"):
                    items = new_slots.get("items", [])
                    new_slots["subtitle"] = items[0] if items else clean_trailing_dangling(truncate_complete_phrase(healed_slides[i].narration, 140))

                if new_slots.get("title") and new_slots.get("subtitle"):
                    if text_similarity(str(new_slots["title"]), str(new_slots["subtitle"])) >= 0.70:
                        new_slots["subtitle"] = ""

                repair_notes.append(f"[layout_anti_repeat, nhóm 2] Slide {healed_slides[i].id}: đổi layout lặp '{healed_slides[i].layout}' sang '{alt}'.")
                healed_slides[i] = healed_slides[i].model_copy(update={"layout": alt, "slots": new_slots})

        # Balance layout frequency: ensure no single layout exceeds 40% of total slides when len >= 5
        from collections import Counter
        layout_counts = Counter(s.layout for s in healed_slides)
        max_allowed = int(len(healed_slides) * 0.40)
        for dom_layout, count in list(layout_counts.items()):
            if len(healed_slides) >= 5 and count > max_allowed:
                for i in range(1, len(healed_slides) - 1):
                    if healed_slides[i].layout == dom_layout:
                        prev_l = healed_slides[i - 1].layout
                        next_l = healed_slides[i + 1].layout
                        is_kit = str(dom_layout).startswith("kit_")
                        if is_kit:
                            alt_candidates = ["kit_list", "kit_title"] if dom_layout != "kit_list" else ["kit_title"]
                        else:
                            alt_candidates = ["lg_shot_features", "lg_note_card"] if dom_layout != "lg_shot_features" else ["lg_note_card"]
                        alt = next((c for c in alt_candidates if c != dom_layout and c != prev_l and c != next_l), None)
                        if alt:
                            curr_slots = dict(healed_slides[i].slots or {})
                            t_clean = str(curr_slots.get("title") or "").strip()
                            if alt in ("kit_list", "lg_shot_features"):
                                sub = curr_slots.get("subtitle") or healed_slides[i].narration
                                clean_sub = clean_trailing_dangling(sub)
                                if t_clean and clean_sub.lower().startswith(t_clean.lower()):
                                    remainder = clean_sub[len(t_clean):].strip()
                                    remainder = re.sub(r"^(?:giúp|khiến|để|nhằm|cho thấy|và|là|có|trong|với|tại|ở|đòi hỏi)\s+", "", remainder, flags=re.I).strip()
                                    remainder = re.sub(r"^[,;:\-—]\s*", "", remainder).strip()
                                    if len(remainder.split()) >= 6:
                                        clean_sub = remainder[0].upper() + remainder[1:]
                                    else:
                                        clean_sub = ""
                                if not clean_sub or len(clean_sub.split()) < 6 or (t_clean and text_similarity(clean_sub, t_clean) >= 0.70):
                                    supp_text = ""
                                    if i + 1 < len(healed_slides):
                                        cand_supp = clean_trailing_dangling(healed_slides[i + 1].narration)
                                        if cand_supp and len(cand_supp.split()) >= 6 and text_similarity(cand_supp, t_clean) < 0.70:
                                            supp_text = cand_supp
                                    clean_sub = supp_text
                                if not clean_sub or len(clean_sub.split()) < 6:
                                    alt = "kit_title" if is_kit else "lg_note_card"
                                    if not curr_slots.get("subtitle"):
                                        curr_slots["subtitle"] = clean_trailing_dangling(truncate_complete_phrase(healed_slides[i].narration, 140))
                                else:
                                    curr_slots["items"] = [clean_trailing_dangling(clean_sub)]
                            elif alt in ("kit_title", "lg_note_card") and not curr_slots.get("subtitle"):
                                items = curr_slots.get("items", [])
                                curr_slots["subtitle"] = items[0] if items else clean_trailing_dangling(truncate_complete_phrase(healed_slides[i].narration, 140))
                            if curr_slots.get("title") and curr_slots.get("subtitle"):
                                if text_similarity(str(curr_slots["title"]), str(curr_slots["subtitle"])) >= 0.70:
                                    curr_slots["subtitle"] = ""
                            healed_slides[i] = healed_slides[i].model_copy(update={"layout": alt, "slots": curr_slots})
                            repair_notes.append(f"[layout_diversity, nhóm 2] Slide {healed_slides[i].id}: đổi từ '{dom_layout}' sang '{alt}' để cân bằng tỷ lệ lặp ({count}/{len(healed_slides)}).")
                            count -= 1
                            if count <= max_allowed:
                                break

        # Diversity check: ensure at least min(4, len(healed_slides)) distinct layouts
        distinct_layouts = set(s.layout for s in healed_slides)
        target_distinct = min(4, len(healed_slides))
        if len(distinct_layouts) < target_distinct and len(healed_slides) >= 4:
            counts = Counter(s.layout for s in healed_slides)
            for i in range(1, len(healed_slides) - 1):
                cur_l = healed_slides[i].layout
                if counts[cur_l] > 1:
                    prev_l = healed_slides[i - 1].layout
                    next_l = healed_slides[i + 1].layout
                    alt = "kit_quote" if str(cur_l).startswith("kit_") else "lg_note_card"
                    if alt not in (prev_l, next_l, cur_l):
                        c_slots = dict(healed_slides[i].slots or {})
                        q_text = clean_trailing_dangling(truncate_complete_phrase(healed_slides[i].narration, 88))
                        c_slots["quote"] = q_text
                        c_slots["title"] = q_text
                        c_slots["author"] = c_slots.get("author") or "Chuyên gia phân tích"
                        c_slots["pill"] = "NHẬN ĐỊNH"
                        healed_slides[i] = healed_slides[i].model_copy(update={"layout": alt, "slots": c_slots})
                        counts[cur_l] -= 1
                        distinct_layouts.add(alt)
                        repair_notes.append(f"[layout_diversity, nhóm 2] Slide {healed_slides[i].id}: đổi sang '{alt}' để đạt >= {target_distinct} layout khác biệt.")
                        if len(distinct_layouts) >= target_distinct:
                            break

    # Final completeness and non-empty slot guarantee for all layouts
    for s_idx, sl in enumerate(healed_slides):
        s_slots = dict(sl.slots or {})
        if sl.layout in ("kit_title", "lg_note_card", "lg_source_headline"):
            if not s_slots.get("title") and not s_slots.get("headline"):
                src_txt = s_slots.get("quote") or s_slots.get("subtitle") or sl.narration
                s_slots["title"] = extract_clean_headline(src_txt) or clean_trailing_dangling(truncate_complete_phrase(src_txt, 88))
            if s_slots.get("title") and s_slots.get("subtitle"):
                if text_similarity(str(s_slots["title"]), str(s_slots["subtitle"])) >= 0.70:
                    s_slots["subtitle"] = ""
            healed_slides[s_idx] = sl.model_copy(update={"slots": s_slots})
        elif sl.layout in ("kit_list", "lg_shot_features"):
            if not s_slots.get("title"):
                s_slots["title"] = extract_clean_headline(sl.narration) or "Thông tin nổi bật"
            if not s_slots.get("items"):
                s_slots["items"] = [clean_trailing_dangling(truncate_complete_phrase(sl.narration, 88))]
            healed_slides[s_idx] = sl.model_copy(update={"slots": s_slots})
        elif sl.layout == "kit_quote":
            if not s_slots.get("quote"):
                s_slots["quote"] = clean_trailing_dangling(truncate_complete_phrase(sl.narration, 88))
            if not s_slots.get("author"):
                s_slots["author"] = "Chuyên gia phân tích"
            healed_slides[s_idx] = sl.model_copy(update={"slots": s_slots})

    return SlideScript(
        topic=slide_script.topic,
        total_duration=slide_script.total_duration,
        slides=healed_slides,
        repair_notes=repair_notes,
    )
