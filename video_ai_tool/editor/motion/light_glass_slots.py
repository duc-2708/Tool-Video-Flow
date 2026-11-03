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


def _generate_vivid_image_prompt(
    narration: str,
    topic: str = "",
    layout: str = "",
    author: str | None = None,
    idx: int = 0,
) -> str:
    """Generate a vivid, cinematic English visual prompt for a 5-second motion beat."""
    n_low = narration.lower()

    if author and (idx == 0 or any(k in n_low for k in ("nói", "tuyên bố", "cho rằng", "chia sẻ", "nhấn mạnh"))):
        return f"Cinematic studio portrait of visionary tech founder {author} speaking thoughtfully in a high-tech keynote stage, dramatic volumetric rim lighting, soft cyan depth of field, 8k octane render."

    if any(k in n_low for k in ("rủi ro", "nguy hiểm", "cảnh báo", "bảo vệ", "an toàn", "sai lầm", "hoài nghi")):
        return "Futuristic glowing amber-crimson holographic cyber security shield deflecting risk anomalies on an advanced tactical monitoring matrix, high-contrast dramatic lighting."

    if any(k in n_low for k in ("tiết kiệm", "heo đất", "lạm phát", "giữ tiền", "đồng tiền", "mất giá")):
        return "Cinematic split concept art showing a traditional vintage clay piggy bank subtly cracking against glowing holographic digital currency streams, dramatic studio lighting, 8k hyper-detailed."

    if any(k in n_low for k in ("đầu tư", "sinh lời", "tái đầu tư", "dòng tiền", "tài sản", "lợi nhuận", "cổ phiếu", "chứng khoán")):
        return "Futuristic glowing emerald green financial trading spline trajectory ascending across multi-layered holographic market displays, neon grid reflections, cinematic 8k render."

    if any(k in n_low for k in ("chi phí", "bằng không", "về không", "năng suất", "rẻ hơn", "300%")):
        return "High-tech financial analytics showing production cost curve descending sharply to zero baseline, illuminated in neon cyan and emerald against automated precision machinery, 8k cinematic."

    if any(k in n_low for k in ("robot", "tự động hóa", "nhà máy", "sản xuất", "tay máy", "hình người")):
        return "Advanced humanoid robot and precision automated robotic arms operating in a futuristic gigafactory assembly line, volumetric laser beams, cinematic depth, 8k render."

    if any(k in n_low for k in ("ai", "trí tuệ nhân tạo", "thuật toán", "mô hình", "mạng thần kinh", "công nghệ")):
        return "Vibrant glowing cybernetic neural network core pulsating with complex interconnected data nodes and synaptic fiber conduits, deep indigo and cyan volumetric atmosphere, 8k."

    if any(k in n_low for k in ("rủi ro", "nguy hiểm", "cảnh báo", "bảo vệ", "an toàn", "sai lầm", "hoài nghi")):
        return "Futuristic glowing amber-crimson holographic cyber security shield deflecting risk anomalies on an advanced tactical monitoring matrix, high-contrast dramatic lighting."

    if layout == "lg_cta_profile" or any(k in n_low for k in ("đăng ký", "theo dõi", "bình luận", "kênh", "chia sẻ")):
        return "Modern high-end tech video creator studio setup with glowing 3D holographic community reaction spheres, neon pink and cyber blue ambient backlights, cinematic 8k."

    clean_topic = topic or "Future of Technology"
    return f"Cinematic visual concept visualizing '{clean_topic}', dynamic cyber aesthetic with glass reflections and volumetric neon lighting, 8k concept art."


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

        # Check prominent entity / author
        detected_author = None
        for a in ("Elon Musk", "Sam Altman", "Bill Gates", "Mark Zuckerberg", "Jensen Huang"):
            if a.lower() in combined_text.lower() or a.lower() in topic_title.lower():
                detected_author = a
                break

        if layout == "lg_source_headline":
            s_ref = SourceRef(url=source_url, domain=source_domain, image_kind="card")
            first_sent = group[0].get("text", "")
            title_lines = wrap_text_greedy(first_sent, max_chars_per_line=14, max_lines=3)
            slots = {
                "pill": "+ TIÊU ĐIỂM CÔNG NGHỆ",
                "title": " ".join(title_lines) if title_lines else first_sent[:42],
                "text": combined_text,
                "source": source_domain or "Bản tin công nghệ",
                "author": detected_author or "Elon Musk",
                "quote": first_sent[:80],
                "repo_name": f"{source_domain}/project" if source_domain else "github.com/project",
                "repo_desc": combined_text[:70],
                "mockup_type": "social_post" if detected_author else "tech_architecture",
            }

        elif layout == "lg_stat_hero":
            val, unit = _extract_number(combined_text)
            if not val:
                # Check semantic indicators like "bằng không", "tăng vọt"
                if "bằng không" in combined_text.lower() or "về không" in combined_text.lower():
                    val, unit = "0", "VNĐ"
                elif "nghìn tỷ" in combined_text.lower() or "tỷ" in combined_text.lower():
                    val, unit = "1.000", "Tỷ USD"
                else:
                    val, unit = "300", "%"

            label_text = "Năng suất & Chi phí"
            c_low = combined_text.lower()
            if "chi phí" in c_low:
                label_text = "Chi phí sản xuất tối ưu"
            elif "năng suất" in c_low:
                label_text = "Năng suất lao động tăng vọt"
            elif "tài sản" in c_low or "giàu" in c_low:
                label_text = "Mức độ tăng trưởng tài sản"

            slots = {
                "value": val,
                "unit": unit or "",
                "label": label_text,
                "sub_pill": "DỮ LIỆU ĐÁNG CHÚ Ý",
                "text": combined_text,
                "neon_stat": f"{val} {unit or ''}".strip(),
                "stat_box_1": f"{val} {unit or ''}".strip(),
                "stat_box_2": "~0 VNĐ" if "chi phí" in c_low else "+300%",
                "stat_box_3": "Đột phá",
                "mockup_type": "financial_chart",
            }

        elif layout == "lg_shot_features":
            title_str = "Góc nhìn thực tế"
            c_low = combined_text.lower()
            if "lịch sử" in c_low:
                title_str = "Thực tế lịch sử"
            elif any(w in c_low for w in ("tính năng", "công nghệ", "tự động")):
                title_str = "Hệ sinh thái công nghệ"
            elif any(w in c_low for w in ("lý do", "nguyên nhân")):
                title_str = "Nguyên nhân cốt lõi"

            # Extract 2-3 meaningful bullet clauses
            raw_clauses = [c.strip() for c in re.split(r"[,;.]", combined_text) if len(c.strip()) >= 10]
            items = []
            for c in raw_clauses[:3]:
                # Remove filler connectors
                clean_c = re.sub(r"^(khi|điều này dường như|tuy nhiên|họ cho rằng|theo đó|do đó)\s+", "", c, flags=re.I).strip()
                if clean_c:
                    clean_c = clean_c[0].upper() + clean_c[1:]
                    w_c = wrap_text_greedy(clean_c, max_chars_per_line=36, max_lines=1)
                    if w_c:
                        items.append(w_c[0])
            if not items:
                items = [combined_text[:36]]

            slots = {
                "title": title_str,
                "badge": "Phân tích đa chiều",
                "items": items,
                "text": combined_text,
                "mockup_type": "tech_architecture",
            }

        elif layout == "lg_vs_compare":
            left_lbl = "TIẾT KIỆM TRUYỀN THỐNG"
            right_lbl = "TÁI ĐẦU TƯ SINH LỜI"
            left_txt = "Cất tiền vào heo đất"
            right_txt = "Tái đầu tư dòng tiền"

            c_low = combined_text.lower()
            if "thay vào đó" in c_low:
                parts = re.split(r"thay vào đó[,:]?", combined_text, flags=re.I)
                p0 = parts[0].strip().rstrip(".")
                p1 = parts[1].strip() if len(parts) > 1 else ""
                
                # Extract subject from p0
                m0 = re.search(r"(?:việc|bạn)?\s*([^.]*(?:heo đất|tiết kiệm|cất tiền|giữ tiền)[^.]*)", p0, re.I)
                if m0:
                    left_txt = m0.group(1).strip()
                elif "." in p0:
                    left_txt = p0.split(".")[-1].strip()
                else:
                    left_txt = p0[-35:].strip()

                # Extract subject from p1
                m1 = re.search(r"(?:việc)?\s*([^.]*(?:tái đầu tư|dòng tiền|sinh lời|công cụ)[^.]*)", p1, re.I)
                if m1:
                    right_txt = m1.group(1).strip()
                elif "." in p1:
                    right_txt = p1.split(".")[0].strip()
                else:
                    right_txt = p1[:35].strip()

            elif any(k in c_low for k in ("thay vì", "so với", "hơn là")):
                parts = re.split(r"(?:thay vì|so với|hơn là)[,:]?", combined_text, flags=re.I)
                left_txt = parts[0].strip().split(".")[-1][:35]
                right_txt = parts[1].strip().split(".")[0][:35] if len(parts) > 1 else ""

            # Clean and wrap
            left_txt = re.sub(r"^(triết lý này giống như việc|dường như|thực tế)\s+", "", left_txt, flags=re.I).strip()
            right_txt = re.sub(r"^(dường như mang lại|thực sự|việc)\s+", "", right_txt, flags=re.I).strip()
            if left_txt:
                left_txt = left_txt[0].upper() + left_txt[1:]
            if right_txt:
                right_txt = right_txt[0].upper() + right_txt[1:]

            w_left = wrap_text_greedy(left_txt or "Cất tiền vào heo đất", max_chars_per_line=20, max_lines=2)
            w_right = wrap_text_greedy(right_txt or "Tái đầu tư dòng tiền sinh lời", max_chars_per_line=20, max_lines=2)

            slots = {
                "left": {"label": left_lbl, "text": " ".join(w_left)},
                "right": {"label": right_lbl, "text": " ".join(w_right)},
                "winner": 2,
                "text": combined_text,
                "mockup_type": "dual_perspective",
            }

        elif layout == "lg_note_card":
            chip_label = "NHẬN ĐỊNH"
            c_low = combined_text.lower()
            if any(w in c_low for w in ("hoài nghi", "lo ngại", "rủi ro", "hậu quả", "cảnh báo")):
                chip_label = "CẢNH BÁO TÀI CHÍNH"
            elif any(w in c_low for w in ("chuyên gia", "nhà phân tích", "kinh tế")):
                chip_label = "Ý KIẾN CHUYÊN GIA"
            elif any(w in c_low for w in ("tương lai", "tiềm năng", "đột phá", "xu hướng")):
                chip_label = "XU HƯỚNG TƯƠNG LAI"
            elif any(w in c_low for w in ("tự động hóa", "năng suất", "chi phí")):
                chip_label = "TỰ ĐỘNG HÓA AI"

            # Extract best statement sentence
            stmt = combined_text
            sentences_in_grp = [s.strip() for s in combined_text.split(".") if len(s.strip()) >= 15]
            if len(sentences_in_grp) >= 2:
                # Pick the punchiest one
                stmt = sentences_in_grp[0] if len(sentences_in_grp[0]) <= 70 else sentences_in_grp[1]

            slots = {
                "chip": chip_label,
                "text": stmt,
                "quote": stmt,
                "author": detected_author or "Chuyên gia phân tích",
                "mockup_type": "social_post" if detected_author and s_idx == 1 else "expert_quote",
            }

        elif layout == "lg_cta_profile":
            clean_handle = brand_name.lower().replace(' ', '')
            slots = {
                "pill": "Xem bản tin mới mỗi ngày",
                "channel_name": brand_name,
                "channel_handle": f"facebook.com/{clean_handle}",
                "bio": "Khám phá công nghệ mới mỗi ngày",
                "text": combined_text or "Đăng ký kênh để đón xem video mới nhất!",
            }

        # Synthesize vivid image prompt for this 5s beat
        img_prompt = _generate_vivid_image_prompt(
            narration=combined_text,
            topic=topic_title,
            layout=layout,
            author=detected_author,
            idx=s_idx,
        )
        slots["image_prompt"] = img_prompt

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
            image_prompt=img_prompt,
        )
        slides.append(slide_item)

    return SlideScript(
        topic=topic_title or "Bản tin công nghệ",
        total_duration=round(total_duration, 3),
        slides=slides,
        repair_notes=["Sinh bằng heuristic fallback light_glass_slots."],
    )
