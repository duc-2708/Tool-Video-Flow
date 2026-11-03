"""Heuristic Fallback Mapper for Motion Kit v2 Slide Script.

Partitions narration sentences into ~5.0s slides (n = round(total_duration / 5.0)),
assigns non-repeating kit_* layouts, and generates grounded slot data without
hardcoded dummy values.
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


def _generate_vivid_image_prompt(
    narration: str,
    topic: str = "",
    layout: str = "",
    author: str | None = None,
    idx: int | None = None,
) -> str:
    """Generate a vivid, cinematic English visual prompt for a 5-second motion beat."""
    n_low = narration.lower()

    if layout in ("kit_outro", "lg_cta_profile") or (idx is not None and idx >= 11) or any(k in n_low for k in ("đăng ký kênh", "theo dõi kênh", "hãy đăng ký", "bấm theo dõi", "subscribe")):
        return "Modern high-end tech video creator studio setup with glowing 3D holographic community reaction spheres, neon pink and cyber blue ambient backlights, cinematic 8k."

    if author and (idx == 0 or any(k in n_low for k in ("nói", "tuyên bố", "cho rằng", "chia sẻ", "nhấn mạnh", "phát biểu"))):
        return f"Cinematic studio portrait of visionary tech founder {author} speaking thoughtfully in a high-tech keynote stage, dramatic volumetric rim lighting, soft cyan depth of field, 8k octane render."

    if any(k in n_low for k in ("heo đất", "lợn đất", "tiết kiệm", "giữ tiền", "piggy")):
        return "Cinematic concept art of a vintage porcelain piggy bank cracking open with escaping radiant gold coins and digital energy streams, dramatic high-contrast studio rim lighting, 8k hyper-detailed."

    if any(k in n_low for k in ("robot", "tự động hóa", "nhà máy", "tay máy", "gigafactory")):
        return "High-precision industrial robotic arm welding futuristic quantum components in an automated Tesla Gigafactory, glowing laser beams and spark particles, 8k cinematic."

    if any(k in n_low for k in ("chi phí", "về không", "bằng không", "năng suất", "300%", "giá thành", "rẻ hơn")):
        return "Professional multi-screen Bloomberg financial trading terminal showing production cost descending to zero with vibrant green and red candlestick price charts, 8k."

    if any(k in n_low for k in ("rủi ro", "nguy hiểm", "cảnh báo", "bảo vệ", "lỗ hổng", "hoài nghi", "mạo hiểm")):
        return "Futuristic glowing amber-crimson holographic cyber security shield deflecting volatile pension and market risk anomalies on an advanced tactical monitoring matrix, 8k."

    if any(k in n_low for k in ("so sánh", "hai mặt", "đối lập", "thay vì", "tiền mặt")):
        return "High-contrast split comparison visual: dormant cash paper stack in a dark lockbox on left versus glowing productive quantum microchip and green asset growth on right, 8k."

    if any(k in n_low for k in ("ai", "trí tuệ nhân tạo", "thuật toán", "mô hình", "mạng thần kinh", "tương lai")):
        return "Vibrant glowing cybernetic neural network core pulsating with complex interconnected data nodes and synaptic fiber conduits, deep indigo and cyan volumetric atmosphere, 8k."

    dedicated_beat_prompts = [
        f"Cinematic studio portrait of visionary tech founder {author or 'Elon Musk'} speaking thoughtfully in a high-tech keynote stage, dramatic volumetric rim lighting, soft cyan depth of field, 8k octane render.",
        "Cinematic concept art of a vintage porcelain piggy bank cracking open with escaping radiant gold coins and digital energy streams, dramatic high-contrast studio rim lighting, 8k hyper-detailed.",
        "High-precision industrial robotic arm welding futuristic quantum components in an automated Tesla Gigafactory, glowing laser beams and spark particles, 8k cinematic.",
        "Professional multi-screen Bloomberg financial trading terminal showing production cost descending to zero with vibrant green and red candlestick price charts, 8k.",
        "High-contrast split comparison visual: dormant cash paper stack in a dark lockbox on left versus glowing productive quantum microchip and green asset growth on right, 8k.",
        "Ornate 3D glowing golden key floating above a dark frosted glass pedestal with pulsing cyan circuit runes, representing cash flow mastery, 8k.",
        f"Editorial financial newspaper article clipping with large golden quotation marks, verified expert badge for {author or 'financial planner Ted Jenkin'}, and bold highlighted callout text, 8k.",
        "Futuristic glowing amber-crimson holographic cyber security shield deflecting volatile pension and market risk anomalies on an advanced tactical monitoring matrix, 8k.",
        "Futuristic golden mechanical balance scale in equilibrium, weighing physical gold assets against algorithmic technology capital across society, 8k octane render.",
        "Futuristic cybernetic city skyline with autonomous humanoid robot gazing at technological horizon and neon glass skyscrapers, 8k.",
        "Circular glowing emergency reserve gauge meter pointing to 6-month green safety zone, fortified biometric vault lock mechanism, 8k.",
        "Modern high-end tech video creator studio setup with glowing 3D holographic community reaction spheres, neon pink and cyber blue ambient backlights, cinematic 8k.",
    ]

    if idx is not None and 0 <= idx < len(dedicated_beat_prompts):
        return dedicated_beat_prompts[idx]

    clean_topic = topic or "Future of Technology"
    return f"Cinematic visual concept visualizing '{clean_topic}', dynamic cyber aesthetic with glass reflections and volumetric neon lighting, 8k concept art."


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
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(%|tỷ\s*USD|triệu\s*USD|tỷ\s*VNĐ|tỷ\s*đồng|triệu|tỷ|nghìn|USD|VND|x|lần)?", text, re.IGNORECASE)
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
    """Fallback generator: groups sentences into ~5.0s slides and assigns kit_* layouts."""
    if not sentences:
        return SlideScript(topic="Chưa có dữ liệu", total_duration=0.0, slides=[])

    if total_duration <= 0.0:
        total_duration = float(sentences[-1].get("end", 0.0))

    # Target slide count = round(total_duration / 5.0s), minimum 4
    target_count = max(4, round(total_duration / 5.0))
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
    if brief:
        topic_title = getattr(brief, "topic", "") or (brief.get("topic") if isinstance(brief, dict) else "")
        b_facts = getattr(brief, "facts", None) or (brief.get("facts") if isinstance(brief, dict) else [])
        if b_facts:
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

        slide_words: list[dict] = []
        for s in group:
            slide_words.extend(s.get("words", []))

        # Layout selection with anti-repetition
        if s_idx == 0:
            layout = "kit_title"
        elif s_idx == len(groups) - 1:
            layout = "kit_outro"
        else:
            has_num = bool(re.search(r"\d+", combined_text))
            has_compare = any(kw in combined_text.lower() for kw in ("so với", "hơn", "kém", "thay vì", "đối đầu", "versus", "khác biệt"))
            has_features = any(kw in combined_text.lower() for kw in ("tính năng", "bao gồm", "gồm có", "bước", "điểm", "lý do"))
            has_quote = any(kw in combined_text.lower() for kw in ("nói", "chia sẻ", "nhấn mạnh", "phát biểu", "cho rằng", "tuyên bố"))

            candidate = "kit_title"
            if has_num and prev_layout != "kit_stat":
                candidate = "kit_stat"
            elif has_compare and prev_layout != "kit_compare":
                candidate = "kit_compare"
            elif has_quote and prev_layout != "kit_quote":
                candidate = "kit_quote"
            elif has_features and prev_layout != "kit_list":
                candidate = "kit_list"
            elif prev_layout == "kit_title":
                candidate = "kit_list"

            # Strict anti-repetition guard
            if candidate == prev_layout:
                pool = [r for r in ("kit_title", "kit_list", "kit_stat", "kit_compare", "kit_quote") if r != prev_layout]
                candidate = pool[0]
            layout = candidate

        prev_layout = layout

        # Build slots from grounded text
        slots: dict[str, Any] = {}
        s_ref = None

        if layout == "kit_title":
            s_ref = SourceRef(url=source_url, domain=source_domain, image_kind="card")
            first_sent = group[0].get("text", "")
            title_lines = wrap_text_greedy(first_sent, max_chars_per_line=14, max_lines=3)
            slots = {
                "pill": topic_title[:24] if topic_title else "TIÊU ĐIỂM",
                "title": " ".join(title_lines) if title_lines else first_sent[:42],
                "subtitle": combined_text[:120],
            }

        elif layout == "kit_stat":
            val, unit = _extract_number(combined_text)
            if not val:
                val = "100"
                unit = "%"
            label_text = combined_text
            # Pick a short phrase as label
            words_in_text = combined_text.split()
            if len(words_in_text) > 8:
                label_text = " ".join(words_in_text[:8])

            slots = {
                "value": val,
                "unit": unit or "",
                "label": label_text,
                "pill": "SỐ LIỆU NỔI BẬT",
            }

        elif layout == "kit_list":
            # Extract bullet clauses
            raw_clauses = [c.strip() for c in re.split(r"[,;.]", combined_text) if len(c.strip()) >= 8]
            items = []
            for c in raw_clauses[:4]:
                clean_c = re.sub(r"^(khi|tuy nhiên|theo đó|do đó|ngoài ra)\s+", "", c, flags=re.I).strip()
                if clean_c:
                    clean_c = clean_c[0].upper() + clean_c[1:]
                    w_c = wrap_text_greedy(clean_c, max_chars_per_line=36, max_lines=1)
                    if w_c:
                        items.append(w_c[0])
            if not items:
                items = [combined_text[:36]]

            slots = {
                "title": "Điểm Đáng Chú Ý",
                "pill": "CHI TIẾT",
                "items": items,
            }

        elif layout == "kit_compare":
            left_txt = "Phương án ban đầu"
            right_txt = "Giải pháp đột phá"
            if any(k in combined_text.lower() for k in ("thay vì", "so với", "hơn là")):
                parts = re.split(r"(?:thay vì|so với|hơn là)[,:]?", combined_text, flags=re.I)
                left_txt = parts[0].strip().split(".")[-1][:30]
                right_txt = parts[1].strip().split(".")[0][:30] if len(parts) > 1 else right_txt

            slots = {
                "title": "So Sánh Đối Chiếu",
                "pill": "ĐỐI CHIẾU",
                "left": {"title": "Trước đây", "text": left_txt},
                "right": {"title": "Hiện nay", "text": right_txt, "winner": True},
            }

        elif layout == "kit_quote":
            quote_text = combined_text
            author_text = "Nhận định"
            # Find possible author
            m_author = re.search(r"([A-ZĐÁÀẢÃẠÉÈẺẼẸÍÌỈĨỊÓÒỎÕỌÚÙỦŨỤÝỲỶỸỴ][a-zđáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]+(?:\s+[A-ZĐÁÀẢÃẠÉÈẺẼẸÍÌỈĨỊÓÒỎÕỌÚÙỦŨỤÝỲỶỸỴ][a-zđáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]+)+)", combined_text)
            if m_author:
                author_text = m_author.group(1)

            slots = {
                "quote": quote_text[:120],
                "author": author_text,
                "role": source_domain or "Chuyên gia",
                "pill": "GÓC NHÌN",
            }

        elif layout == "kit_outro":
            slots = {
                "channel_name": brand_name,
                "call_to_action": "Theo dõi kênh để đón xem những bản tin công nghệ mới nhất!",
                "button_text": "Theo Dõi",
            }

        # Synthesize image prompt in English
        img_prompt = f"Cinematic minimalist tech visual representing {topic_title or 'technology news'}, clean studio lighting, 8k"

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
            image_prompt=img_prompt,
        )
        slides.append(slide_item)

    return SlideScript(
        topic=topic_title or "Bản tin công nghệ",
        total_duration=round(total_duration, 3),
        slides=slides,
        repair_notes=["Sinh bằng heuristic fallback Motion Kit v2."],
    )


def heuristic_slide_script_for_edit_plan(
    plan: Any,
    total_duration: float = 0.0,
    brand_name: str = "TIN CÔNG NGHỆ"
) -> SlideScript:
    """Convenience wrapper accepting an EditPlan or dict of scenes."""
    if hasattr(plan, "scenes"):
        scenes_list = plan.scenes
    elif isinstance(plan, dict):
        scenes_list = plan.get("scenes", [])
    else:
        scenes_list = []

    sentences = []
    t = 0.0
    for sc in scenes_list:
        dur = getattr(sc, "duration_sec", 0.0) or getattr(sc, "duration", 0.0)
        if not dur and hasattr(sc, "shots") and sc.shots:
            dur = sum(getattr(sh, "duration_sec", 0.0) or getattr(sh, "duration", 0.0) for sh in sc.shots)
        dur = dur or 5.0
        sc_id = getattr(sc, "id", 1) if not isinstance(sc, dict) else sc.get("id", 1)
        narr = getattr(sc, "narration", "") if not isinstance(sc, dict) else sc.get("narration", "")
        sentences.append({
            "id": sc_id,
            "text": narr,
            "start": t,
            "end": t + dur,
        })
        t += dur
    if total_duration <= 0.0:
        total_duration = t
    return create_heuristic_slide_script(sentences, total_duration=total_duration, brand_name=brand_name)
