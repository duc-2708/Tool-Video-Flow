"""Heuristic Fallback Mapper for Light Glass Slide Script.

Partitions narration sentences into 5-10 slides (~6.5s per slide),
assigns non-repeating layouts, and generates grounded slot data.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from schemas.slide_script import (
    SlideScript,
    SlideItem,
    SourceRef,
    EmphasisItem,
    wrap_text_greedy,
)


def _clean_domain(url: str | None) -> str:
    if not url:
        return "Nguồn tin tức"
    try:
        p = urlparse(url)
        netloc = p.netloc or url
        return re.sub(r"^www\.", "", netloc).split(":")[0].strip()
    except Exception:
        return "Nguồn tin tức"


def _extract_number(text: str) -> tuple[str | None, str | None]:
    """Find the first prominent number and its unit in text."""
    # Pattern e.g. 25%, 2.5 tỷ, 100 triệu, 500
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(%|tỷ\s*USD|triệu\s*USD|tỷ\s*VNĐ|tỷ\s*đồng|triệu|tỷ|nghìn|USD|VND)?", text, re.IGNORECASE)
    if m:
        val = m.group(1).replace(",", ".")
        unit = (m.group(2) or "").strip()
        return val, unit
    return None, None


def _find_emphasis_phrases(sentence_text: str, words: list[dict] | None = None, slide_start: float = 0.0) -> list[EmphasisItem]:
    """Extract 1-2 key phrases (<= 3 words) present verbatim in text."""
    items: list[EmphasisItem] = []
    
    # 1. Number emphasis
    num_match = re.search(r"\b(\d+(?:[.,]\d+)?(?:\s*%)?)\b", sentence_text)
    if num_match:
        phrase = num_match.group(1)
        start_sec, end_sec = None, None
        if words:
            for w in words:
                if phrase in str(w.get("text", "")):
                    start_sec = max(0.0, float(w.get("start", 0.0)) - slide_start)
                    end_sec = max(0.0, float(w.get("end", 0.0)) - slide_start)
                    break
        items.append(EmphasisItem(phrase=phrase, kind="number", start_sec=start_sec, end_sec=end_sec))

    # 2. Capitalized / Tech term emphasis
    caps_match = re.search(r"\b([A-ZĐÁÀẢÃẠÉÈẺẼẸÍÌỈĨỊÓÒỎÕỌÚÙỦŨỤÝỲỶỸỴ][a-zđáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]+(?:\s+[A-ZĐÁÀẢÃẠÉÈẺẼẸÍÌỈĨỊÓÒỎÕỌÚÙỦŨỤÝỲỶỸỴ][a-zđáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]+)?)\b", sentence_text)
    if caps_match:
        phrase = caps_match.group(1)
        # Avoid common sentence starters
        lower = phrase.lower()
        if lower not in {"nhưng", "tuy nhiên", "do đó", "vì vậy", "sau đó", "trong khi", "đây là", "theo đó", "hiện tại"}:
            start_sec, end_sec = None, None
            if words:
                w_tokens = phrase.split()
                for i, w in enumerate(words):
                    if w_tokens[0].lower() in str(w.get("text", "")).lower():
                        start_sec = max(0.0, float(w.get("start", 0.0)) - slide_start)
                        end_sec = max(0.0, float(words[min(len(words)-1, i + len(w_tokens) - 1)].get("end", 0.0)) - slide_start)
                        break
            items.append(EmphasisItem(phrase=phrase, kind="name", start_sec=start_sec, end_sec=end_sec))

    return items[:2]


def create_heuristic_slide_script(
    sentences: list[dict[str, Any]],
    brief: Any = None,
    total_duration: float = 0.0,
    brand_name: str = "TIN CÔNG NGHỆ"
) -> SlideScript:
    """Fallback generator: groups sentences into 5-10 slides and generates grounded slots."""
    if not sentences:
        return SlideScript(topic="Chưa có dữ liệu", total_duration=0.0, slides=[])

    if total_duration <= 0.0:
        total_duration = float(sentences[-1].get("end", 0.0))

    # Target slide count = round(total_duration / 6.5s), clamp to [5, 10]
    target_count = max(5, min(10, round(total_duration / 6.5)))
    if len(sentences) < target_count:
        target_count = max(1, len(sentences))

    # Partition sentences into target_count contiguous slices
    n_sent = len(sentences)
    k, m = divmod(n_sent, target_count)
    groups: list[list[dict[str, Any]]] = []
    idx = 0
    for i in range(target_count):
        size = k + (1 if i < m else 0)
        group = sentences[idx : idx + size]
        if group:
            groups.append(group)
        idx += size

    # Prepare brief information
    topic_title = ""
    source_url = None
    source_domain = None
    facts = []
    if brief:
        topic_title = getattr(brief, "topic", "") or (brief.get("topic") if isinstance(brief, dict) else "")
        b_facts = getattr(brief, "facts", None) or (brief.get("facts") if isinstance(brief, dict) else [])
        if b_facts:
            facts = b_facts
            first_fact = b_facts[0]
            source_url = str(getattr(first_fact, "source_url", "") or (first_fact.get("source_url") if isinstance(first_fact, dict) else ""))
            source_domain = _clean_domain(source_url)
    
    slides: list[SlideItem] = []
    prev_layout: str | None = None

    for s_idx, group in enumerate(groups):
        slide_id = f"slide_{s_idx + 1}"
        s_start = float(group[0].get("start", 0.0))
        s_end = float(group[-1].get("end", 0.0))
        s_dur = max(0.1, s_end - s_start)
        sent_ids = [int(s.get("id", i + 1)) for i, s in enumerate(group)]
        combined_text = " ".join(s.get("text", "") for s in group).strip()

        # Gather words for timing
        slide_words: list[dict] = []
        for s in group:
            slide_words.extend(s.get("words", []))

        # Layout selection
        if s_idx == 0:
            layout = "lg_source_headline"
        elif s_idx == len(groups) - 1:
            layout = "lg_cta_profile"
        else:
            # Check content heuristics
            has_num = bool(re.search(r"\d+", combined_text))
            has_compare = any(kw in combined_text.lower() for kw in ("so với", "hơn", "kém", "thay vì", "đối đầu", "versus", "khác biệt"))
            has_features = any(kw in combined_text.lower() for kw in ("tính năng", "bao gồm", "gồm có", "bước", "điểm", "lý do"))

            candidate = "lg_note_card"
            if has_num and prev_layout != "lg_stat_hero":
                candidate = "lg_stat_hero"
            elif has_compare and prev_layout != "lg_vs_compare":
                candidate = "lg_vs_compare"
            elif has_features and prev_layout != "lg_shot_features":
                candidate = "lg_shot_features"
            elif prev_layout == "lg_note_card":
                candidate = "lg_shot_features"
            
            # Strict anti-repetition guard
            if candidate == prev_layout:
                pool = [r for r in ("lg_note_card", "lg_shot_features", "lg_stat_hero", "lg_vs_compare") if r != prev_layout]
                candidate = pool[0]
            layout = candidate

        prev_layout = layout

        # Build slots
        slots: dict[str, Any] = {}
        s_ref = None

        if layout == "lg_source_headline":
            s_ref = SourceRef(url=source_url, domain=source_domain, image_kind="card")
            first_sent = group[0].get("text", "")
            # Wrap headline to <= 3 lines x 14 chars
            title_lines = wrap_text_greedy(first_sent, max_chars_per_line=14, max_lines=3)
            slots = {
                "pill": "TIÊU ĐIỂM CÔNG NGHỆ",
                "title": " ".join(title_lines) if title_lines else first_sent[:42],
                "text": combined_text,
                "source": source_domain or "Bản tin công nghệ",
            }

        elif layout == "lg_stat_hero":
            val, unit = _extract_number(combined_text)
            # Find short label
            label_text = "Chỉ số quan trọng"
            for w in combined_text.split(".")[0].split(","):
                if re.search(r"\d+", w):
                    clean_w = re.sub(r"\d+(?:[.,]\d+)?%?", "", w).strip()
                    if clean_w:
                        label_text = clean_w[:28]
                        break
            slots = {
                "value": val or "100",
                "unit": unit or "",
                "label": label_text,
                "sub_pill": "DỮ LIỆU ĐÁNG CHÚ Ý",
                "text": combined_text,
            }

        elif layout == "lg_shot_features":
            # Extract 2-3 items from sentences or clauses
            clauses = [c.strip() for c in re.split(r"[,;.]", combined_text) if len(c.strip()) >= 5]
            items = []
            for c in clauses[:3]:
                w_c = wrap_text_greedy(c, max_chars_per_line=40, max_lines=1)
                if w_c:
                    items.append(w_c[0])
            if not items:
                items = [combined_text[:40]]
            slots = {
                "title": "Các điểm chính",
                "badge": "TỔNG HỢP",
                "items": items,
                "text": combined_text,
            }

        elif layout == "lg_vs_compare":
            halves = re.split(r"(?:so với|thay vì|hơn|nhưng)", combined_text, flags=re.I)
            left_txt = halves[0].strip() if halves else combined_text
            right_txt = halves[1].strip() if len(halves) > 1 else "Giai đoạn trước"
            slots = {
                "left": {"label": "HIỆN TẠI", "text": left_txt[:28]},
                "right": {"label": "SO SÁNH", "text": right_txt[:28]},
                "winner": 1,
                "text": combined_text,
            }

        elif layout == "lg_note_card":
            slots = {
                "chip": "NHẬN ĐỊNH CHUYÊN GIA",
                "text": combined_text,
            }

        elif layout == "lg_cta_profile":
            slots = {
                "pill": "THEO DÕI ĐỂ KHÔNG BỎ LỠ",
                "channel_name": brand_name,
                "channel_handle": f"@{brand_name.lower().replace(' ', '')}",
                "text": combined_text or "Đăng ký kênh để đón xem video mới nhất!",
            }

        # Emphasis phrases
        emphasis = _find_emphasis_phrases(combined_text, slide_words, slide_start=s_start)

        slide_item = SlideItem(
            id=slide_id,
            layout=layout,
            sentence_ids=sent_ids,
            slots=slots,
            source_ref=s_ref,
            emphasis=emphasis,
            t_start=round(s_start, 3),
            t_end=round(s_end, 3),
            duration=round(s_dur, 3),
            narration=combined_text,
        )
        slides.append(slide_item)

    return SlideScript(
        topic=topic_title or "Bản tin công nghệ",
        total_duration=round(total_duration, 3),
        slides=slides,
        repair_notes=["Sinh bằng heuristic fallback light_glass_slots."],
    )
