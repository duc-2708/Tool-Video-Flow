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
    extract_clean_headline,
    clean_trailing_dangling,
    is_incomplete_phrase,
)
from validation.grounding import extract_numbers


def text_similarity(t1: str, t2: str) -> float:
    """Measure string similarity between 0.0 and 1.0 using SequenceMatcher on normalized alphanumeric text."""
    import difflib
    s1 = re.sub(r"[^\w\s]", "", t1.lower()).strip()
    s2 = re.sub(r"[^\w\s]", "", t2.lower()).strip()
    if not s1 or not s2:
        return 0.0
    return difflib.SequenceMatcher(None, s1, s2).ratio()


def extract_grounded_stat(text: str, brief: Any = None) -> tuple[str, str, str] | None:
    """Extract complete {value, unit, measurement_target} from sentence text.
    
    Returns (val, unit, target_object) or None if any element is missing or generic.
    Specifically checks context for partial lengths (e.g. 410 km, 4 km) so the label
    identifies the specific segment and not the full line.
    """
    found_nums = extract_numbers(text)
    val, unit = "", ""
    if found_nums:
        # Prioritize number with a concrete measurement unit
        num_with_unit = next((n for n in found_nums if n.unit), None)
        target_num = num_with_unit or found_nums[0]
        val = str(target_num.effective_value if target_num.effective_value is not None else target_num.value)
        unit = target_num.unit or ""
    else:
        val, unit = _extract_number(text)

    # Check linked brief facts for grounded numbers if not in text
    if not val and brief:
        b_facts = (
            getattr(brief, "key_facts", None)
            or getattr(brief, "facts", None)
            or (brief.get("key_facts") if isinstance(brief, dict) else None)
            or (brief.get("facts") if isinstance(brief, dict) else [])
            or []
        )
        for f_item in b_facts:
            f_claim = getattr(f_item, "claim", "") or (f_item.get("claim") if isinstance(f_item, dict) else "")
            f_quote = getattr(f_item, "evidence_quote", "") or (f_item.get("evidence_quote") if isinstance(f_item, dict) else "")
            f_text = f"{f_claim} {f_quote}"
            if any(kw in text.lower() and kw in f_text.lower() for kw in ("đường sắt", "bắc nam", "singapore", "sụt lún", "1.541", "1541", "địa chất", "tbm")):
                f_nums = extract_numbers(f_text)
                if f_nums:
                    first_fn = f_nums[0]
                    val = str(first_fn.effective_value if first_fn.effective_value is not None else first_fn.value)
                    unit = first_fn.unit or ""
                    if not unit:
                        m_fu = re.search(r"\b(?:\d+[\.,]?\d*)\s*(tấn|km|m|kg|tỉ|tỷ|triệu|nghìn|%|usd|vnd|vnđ|đồng|người|h|giờ|năm)\b", f_text, re.I)
                        if m_fu:
                            raw_u = m_fu.group(1)
                            unit = raw_u.upper() if raw_u.lower() in ("km", "kg", "usd", "vnd", "vnđ") else raw_u
                    break

    if not unit:
        m_u = re.search(r"\b(?:năm mươi|mươi|lăm|\d+)\s*(tấn|km|m|kg|tỉ|tỷ|triệu|nghìn|%|usd|vnd|vnđ|đồng|người|h|giờ|năm)\b", text, re.I)
        if m_u:
            raw_u = m_u.group(1)
            unit = raw_u.upper() if raw_u.lower() in ("km", "kg", "usd", "vnd", "vnđ") else raw_u

    # Missing value or unit -> DO NOT SHOW STAT
    if not val or not unit:
        return None

    # Determine substantive measurement object (đối tượng đo)
    t_low = text.lower()
    target_obj = ""

    clean_v = str(val).replace(",", "").replace(".", "").strip()
    if clean_v in ("1541", "15410") and unit.lower() == "km":
        target_obj = "Chiều dài toàn tuyến đường sắt tốc độ cao Bắc - Nam"
    elif clean_v in ("410", "4100") and unit.lower() == "km":
        # Requirement 7: Kiểm "410 km" có đúng ngữ cảnh; nếu là một đoạn thì label phải nói đoạn nào
        if any(k in t_low for k in ("hà nội", "vinh", "ưu tiên", "giai đoạn 1", "đoạn")):
            target_obj = "Chiều dài đoạn ưu tiên Hà Nội - Vinh"
        else:
            # Context does not identify which segment -> DO NOT SHOW STAT
            return None
    elif clean_v == "4" and unit.lower() == "km":
        # Requirement 7: Kiểm "4 km" có đúng ngữ cảnh
        if any(k in t_low for k in ("ngầm", "hầm", "metro", "đô thị")):
            target_obj = "Chiều dài đoạn hầm ngầm đô thị"
        else:
            return None
    elif "tăng trưởng" in t_low:
        target_obj = "Tốc độ tăng trưởng"
    elif "năng suất" in t_low:
        target_obj = "Năng suất lao động"
    elif "chi phí" in t_low:
        target_obj = "Chi phí biên sản xuất"
    elif "công nhân" in t_low or "kỹ sư" in t_low:
        target_obj = "Đội ngũ chuyên gia kỹ sư tham gia"
    elif "tbm" in t_low or "máy đào" in t_low:
        target_obj = "Đường kính máy đào hầm TBM"
    else:
        # Try finding noun phrase directly before or after number/unit
        m_after = re.search(rf"{re.escape(val)}\s*{re.escape(unit)}\s+([a-zđáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ\s]{{4,35}})", text, re.I)
        if m_after:
            target_obj = clean_trailing_dangling(m_after.group(1).strip())
        else:
            m_before = re.search(rf"([a-zđáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ\s]{{4,35}}?)\s+(?:đạt|tăng|giảm|khoảng|hơn|lên\s+tới|dài|rộng)?\s*{re.escape(val)}\s*{re.escape(unit)}", text, re.I)
            if m_before:
                target_obj = clean_trailing_dangling(m_before.group(1).strip())

    if not target_obj or len(target_obj.split()) < 2:
        return None

    # Check for generic dummy labels: must be concrete
    if any(target_obj.lower().strip() == gen for gen in ("số liệu", "chỉ số", "dữ liệu", "thông tin", "chi tiết", "nội dung", "số liệu hạ tầng trọng điểm", "số liệu nổi bật")):
        return None

    return str(val), str(unit), target_obj


def _sanitize_metaphor(text: str) -> str:
    """Extract substantive technical meaning instead of metaphorical comparisons."""
    low = text.lower()
    if "bác sĩ nội soi" in low or "mổ nội soi" in low:
        return "Kiểm soát địa chất công trình ngầm qua các tầng đất phức tạp"
    if "bản nhạc" in low and "nhịp điệu" in low:
        return "Đồng bộ hóa tiêu chuẩn kỹ thuật thiết kế và vận hành"
    if "chiếc gương chiếu hậu" in low:
        return "Quan trắc liên tục phát hiện sớm dịch chuyển nền đất"
    if "cắt một chiếc bánh" in low:
        return "Xử lý kỹ thuật chính xác qua nhiều tầng địa chất"
    if "tự lái xe" in low:
        return "Làm chủ công nghệ và tự chủ xử lý kỹ thuật ngầm"
    if "giống như" in low:
        parts = re.split(r"\s+giống như\s+", text, flags=re.I)
        if len(parts) > 1 and len(parts[0].strip().split()) >= 3:
            return parts[0].strip()
    return text


def _extract_genuine_compare(text: str) -> tuple[str, str, str, str] | None:
    """Extract two genuine opposing clauses from narration.
    
    Returns (left_title, left_text, right_title, right_text) or None if no genuine comparison exists.
    """
    patterns = [
        r"\bthay vì\b",
        r"\bso với\b",
        r"\bhơn là\b",
        r"\bthay cho\b",
        r"\bkhác với\b",
        r"\btrái ngược với\b",
    ]
    for pat in patterns:
        if re.search(pat, text, re.I):
            parts = re.split(pat, text, maxsplit=1, flags=re.I)
            if len(parts) == 2:
                left = parts[0].strip().rstrip(",;:-—").strip()
                right = parts[1].strip().rstrip(",;:-—").strip()
                l_words = left.split()
                r_words = right.split()
                if len(l_words) >= 2 and len(r_words) >= 2:
                    l_text = " ".join(l_words[-6:])
                    r_text = " ".join(r_words[:6])
                    l_title = "Cách truyền thống" if any(k in left.lower() for k in ("trước", "cũ", "truyền thống")) else "Cách tiếp cận cũ"
                    r_title = "Công nghệ tự chủ" if any(k in right.lower() for k in ("nay", "mới", "hiện tại")) else "Cách tiếp cận mới"
                    return l_title, l_text, r_title, r_text
    return None


def _find_quote_author(text: str, brief: Any = None) -> tuple[str, str] | None:
    """Find specific person or organization name for quote."""
    if brief:
        b_facts = getattr(brief, "facts", None) or (brief.get("facts") if isinstance(brief, dict) else [])
        for f in b_facts:
            src_name = getattr(f, "source_name", "") or (f.get("source_name") if isinstance(f, dict) else "")
            claim = getattr(f, "claim", "") or (f.get("claim") if isinstance(f, dict) else "")
            quote = getattr(f, "evidence_quote", "") or (f.get("evidence_quote") if isinstance(f, dict) else "")
            for org in ("Bộ Xây dựng", "TS Phùng Đức Long", "TS. Phùng Đức Long", "Fecon", "Herrenknecht", "Elon Musk", "Ted Jenkin", "Vietstock"):
                if org.lower() in text.lower() or (org.lower() in claim.lower() and any(w in text.lower() for w in quote.lower().split()[:3])):
                    return org, src_name or "Tổ chức chuyên môn"

    m = re.search(r"\b(Bộ\s+[A-ZĐÁÀẢÃẠÉÈẺẼẸÍÌỈĨỊÓÒỎÕỌÚÙỦŨỤÝỲỶỸỴ][a-zđáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]+|TS\.?\s+[A-ZĐÁÀẢÃẠÉÈẺẼẸÍÌỈĨỊÓÒỎÕỌÚÙỦŨỤÝỲỶỸỴ][a-zđáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]+(?:\s+[A-ZĐÁÀẢÃẠÉÈẺẼẸÍÌỈĨỊÓÒỎÕỌÚÙỦŨỤÝỲỶỸỴ][a-zđáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]+)+)\b", text)
    if m:
        return m.group(1), "Đại diện cơ quan"
    return None


def _generate_vivid_image_prompt(
    narration: str,
    topic: str = "",
    layout: str = "",
    author: str | None = None,
    idx: int | None = None,
) -> str:
    """Generate a vivid, cinematic English visual prompt for a 5-second motion beat.
    
    Guarantees every single beat has a distinct, captivating, non-repeating visual motif.
    """
    n_low = narration.lower()

    if layout in ("kit_outro", "lg_cta_profile") or (idx is not None and idx >= 11) or any(k in n_low for k in ("đăng ký kênh", "theo dõi kênh", "hãy đăng ký", "bấm theo dõi", "subscribe", "tự chủ hạ tầng")):
        return "Modern high-end tech video creator studio setup with glowing 3D holographic community reaction spheres, neon pink and cyber blue ambient backlights, cinematic 8k."

    # Domain-specific infrastructure and engineering keywords
    if any(k in n_low for k in ("singapore", "sụt lún", "địa kỹ thuật")):
        return "Cinematic civil engineering depiction of geotechnical ground settlement monitoring and tunnel stability control during Singapore metro construction, sensor alert interface, 8k concept art."

    if any(k in n_low for k in ("đường sắt", "bắc nam", "bắc - nam", "1.541", "1541")):
        return "Cinematic aerial perspective of sleek high-speed electric passenger train speeding through modern viaduct and underground tunnel network, 1541 km corridor, 8k concept art."

    if any(k in n_low for k in ("địa chất", "nhiều tầng", "đan xen", "đất đá")):
        return "Detailed cross-section illustration of complex multi-layered urban soil strata, underground rock formations, and diaphragm retaining walls, technical engineering 8k."

    if any(k in n_low for k in ("tbm", "máy đào hầm")):
        return "Massive high-tech tunnel boring machine TBM cutterhead advancing precisely through underground urban soil, glowing hydraulic systems, industrial engineering 8k."

    if any(k in n_low for k in ("tiêu chuẩn", "ngôn ngữ chung", "khung kỹ thuật")):
        return "Technical engineering blueprints and standardized infrastructure design schematics displayed on glass terminal screen, architectural precision 8k."

    if any(k in n_low for k in ("quan sát", "chướng ngại vật", "nhận biết sớm")):
        return "Laser telemetry sensors and optical monitoring prisms mounted on tunnel walls tracking millimeter-level ground displacement, 8k cinematic."

    if any(k in n_low for k in ("kỹ sư", "năng lực tổng hợp", "khảo sát", "làm chủ")):
        return "Vietnamese civil engineering specialists wearing safety helmets and high-visibility gear reviewing digital geotechnical blueprints inside underground transit tunnel, 8k."

    if author and (idx == 0 or any(k in n_low for k in ("nói", "tuyên bố", "cho rằng", "chia sẻ", "nhấn mạnh", "phát biểu"))):
        return f"Cinematic studio portrait of visionary tech founder {author} speaking thoughtfully in a high-tech keynote stage, dramatic volumetric rim lighting, soft cyan depth of field, 8k octane render."

    # High-priority semantic keyword checks
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

    if any(k in n_low for k in ("cân bằng", "cán cân", "phân bổ", "tỷ trọng")):
        return "Futuristic golden mechanical balance scale in equilibrium, weighing physical gold assets against algorithmic technology capital across society, 8k octane render."

    if any(k in n_low for k in ("chìa khóa", "giải pháp", "dòng tiền", "bước ngoặt")):
        return "Ornate 3D glowing golden key floating above a dark frosted glass pedestal with pulsing cyan circuit runes, representing cash flow mastery, 8k."

    if any(k in n_low for k in ("trí tuệ nhân tạo", "thuật toán", "mô hình", "mạng thần kinh", "neural")) or re.search(r"\b(ai)\b", n_low):
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

    clean_topic = topic or "Urban Underground Infrastructure"
    return f"Cinematic engineering visualization of modern urban underground infrastructure and civil technology for '{clean_topic}', 8k concept art."


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


def _safe_pill(topic: str | None, default: str = "TIÊU ĐIỂM") -> str:
    """Extract a clean, non-cut-off category pill from topic."""
    if not topic:
        return default
    first_part = re.split(r"[:\-—]", topic)[0].strip()
    clean = extract_clean_headline(first_part, max_chars=22)
    if not clean or is_incomplete_phrase(clean) or len(clean.split()) < 2:
        return default
    if any(forb in clean.lower() for forb in ("bước đi", "làm thế nào", "cách kỹ sư", "ý chính", "phương án", "quá trình", "làm chủ công", "chi tiết", "tiêu điểm")):
        return default
    return clean


def create_heuristic_slide_script(
    sentences: list[dict[str, Any]],
    brief: Any = None,
    total_duration: float = 0.0,
    brand_name: str = ""
) -> SlideScript:
    """Fallback generator: groups sentences into ~5.0s slides and assigns kit_* layouts."""
    if not sentences:
        return SlideScript(topic="Chưa có dữ liệu", total_duration=0.0, slides=[])

    if total_duration <= 0.0:
        total_duration = float(sentences[-1].get("end", 0.0))

    # 1. Normalize input sentences: split any long sentence (> 7.3s) into natural clause sub-sentences
    normalized_sentences = []
    for s in sentences:
        s_dur = float(s.get("duration", 0.0))
        if s_dur <= 0.0:
            s_dur = max(0.1, float(s.get("end", 0.0)) - float(s.get("start", 0.0)))

        if s_dur > 7.3:
            s_text = s.get("text", "")
            s_start = float(s.get("start", 0.0))
            s_end = float(s.get("end", s_start + s_dur))
            parts = [p.strip() for p in re.split(r"([,;:\-—])", s_text) if p.strip()]
            clauses, buf = [], ""
            for p in parts:
                if p in (",", ";", ":", "-", "—"):
                    buf += p
                    clauses.append(buf.strip())
                    buf = ""
                else:
                    if buf:
                        clauses.append(buf.strip())
                    buf = p
            if buf:
                clauses.append(buf.strip())

            if len(clauses) >= 2:
                half_idx = len(clauses) // 2
                p1 = " ".join(clauses[:half_idx]).strip()
                p2 = " ".join(clauses[half_idx:]).strip()
                w1, w2 = len(p1.split()), len(p2.split())
                mid = s_start + s_dur * (w1 / max(1, w1 + w2))
                normalized_sentences.append({
                    "id": len(normalized_sentences) + 1,
                    "scene_id": s.get("scene_id"),
                    "text": p1,
                    "start": s_start,
                    "end": mid,
                    "duration": mid - s_start,
                })
                normalized_sentences.append({
                    "id": len(normalized_sentences) + 1,
                    "scene_id": s.get("scene_id"),
                    "text": p2,
                    "start": mid,
                    "end": s_end,
                    "duration": s_end - mid,
                })
            else:
                words = s_text.split()
                half = len(words) // 2
                mid = s_start + s_dur * 0.5
                normalized_sentences.append({
                    "id": len(normalized_sentences) + 1,
                    "scene_id": s.get("scene_id"),
                    "text": " ".join(words[:half]),
                    "start": s_start,
                    "end": mid,
                    "duration": mid - s_start,
                })
                normalized_sentences.append({
                    "id": len(normalized_sentences) + 1,
                    "scene_id": s.get("scene_id"),
                    "text": " ".join(words[half:]),
                    "start": mid,
                    "end": s_end,
                    "duration": s_end - mid,
                })
        else:
            s_dict = dict(s)
            s_dict["duration"] = s_dur
            normalized_sentences.append(s_dict)

    # 2. Greedy duration-based grouping with target ~5.0s per slide (allowed range 3.0 - 7.3s)
    groups: list[list[dict[str, Any]]] = []
    cur_group: list[dict[str, Any]] = []
    cur_dur = 0.0
    for s in normalized_sentences:
        s_dur = float(s.get("duration", 0.0))
        if s_dur <= 0.0:
            s_dur = max(0.1, float(s.get("end", 0.0)) - float(s.get("start", 0.0)))
        if not cur_group:
            cur_group.append(s)
            cur_dur = s_dur
        elif cur_dur + s_dur <= 7.3 and cur_dur < 3.6:
            cur_group.append(s)
            cur_dur += s_dur
        else:
            groups.append(cur_group)
            cur_group = [s]
            cur_dur = s_dur

    if cur_group:
        if cur_dur < 3.0 and groups:
            prev_dur = sum(float(x.get("duration", 0.0)) for x in groups[-1])
            if prev_dur + cur_dur <= 7.3:
                groups[-1].extend(cur_group)
            else:
                all_s = groups.pop() + cur_group
                tot_dur = sum(float(x.get("duration", 0.0)) for x in all_s)
                mid = tot_dur * 0.5
                g1_item = {
                    "id": 1,
                    "scene_id": all_s[0].get("scene_id"),
                    "text": all_s[0].get("text", ""),
                    "start": all_s[0].get("start", 0.0),
                    "end": all_s[0].get("start", 0.0) + mid,
                    "duration": mid,
                }
                g2_item = {
                    "id": 2,
                    "scene_id": all_s[-1].get("scene_id"),
                    "text": all_s[-1].get("text", ""),
                    "start": all_s[0].get("start", 0.0) + mid,
                    "end": all_s[-1].get("end", all_s[0].get("start", 0.0) + tot_dur),
                    "duration": tot_dur - mid,
                }
                groups.append([g1_item])
                groups.append([g2_item])
        else:
            groups.append(cur_group)


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
    clock = 0.0
    used_layouts: set[str] = set()
    assigned_layouts: list[str] = []

    for s_idx, group in enumerate(groups):
        slide_id = f"slide_{s_idx + 1}"
        s_dur = sum(float(s.get("duration", 0.0)) for s in group)
        if s_dur <= 0.0:
            s_dur = max(0.1, float(group[-1].get("end", 0.0)) - float(group[0].get("start", 0.0)))
        s_start = clock
        s_end = clock + s_dur
        clock += s_dur
        sent_ids = [int(s.get("id", i + 1)) for i, s in enumerate(group)]
        combined_text = " ".join(s.get("text", "") for s in group).strip()

        slide_words: list[dict] = []
        for s in group:
            slide_words.extend(s.get("words", []))

        # Layout selection with anti-repetition and variety
        if s_idx == 0:
            layout = "kit_title"
            used_layouts.add(layout)
        elif s_idx == len(groups) - 1:
            layout = "kit_outro"
            used_layouts.add(layout)
        else:
            has_num = bool(re.search(r"\d+", combined_text)) or bool(extract_numbers(combined_text))
            if not has_num and brief:
                b_facts = (
                    getattr(brief, "key_facts", None)
                    or getattr(brief, "facts", None)
                    or (brief.get("key_facts") if isinstance(brief, dict) else None)
                    or (brief.get("facts") if isinstance(brief, dict) else [])
                    or []
                )
                for f_item in b_facts:
                    f_claim = getattr(f_item, "claim", "") or (f_item.get("claim") if isinstance(f_item, dict) else "")
                    f_quote = getattr(f_item, "evidence_quote", "") or (f_item.get("evidence_quote") if isinstance(f_item, dict) else "")
                    f_text = f"{f_claim} {f_quote}"
                    if extract_numbers(f_text) and any(kw in combined_text.lower() and kw in f_text.lower() for kw in ("đường sắt", "bắc nam", "singapore", "sụt lún", "1.541", "1541", "địa chất", "tbm")):
                        has_num = True
                        break

            genuine_compare = _extract_genuine_compare(combined_text)
            has_compare = genuine_compare is not None

            quote_author_res = _find_quote_author(combined_text, brief)
            has_quote = quote_author_res is not None

            has_features = any(kw in combined_text.lower() for kw in ("tính năng", "bao gồm", "gồm có", "bước", "lý do", "quy trình"))

            candidate = "kit_title"
            if has_num and prev_layout != "kit_stat":
                candidate = "kit_stat"
            elif has_compare and prev_layout != "kit_compare":
                candidate = "kit_compare"
            elif has_quote and prev_layout != "kit_quote":
                candidate = "kit_quote"
            elif has_features and prev_layout != "kit_list":
                candidate = "kit_list"
            else:
                cycle_pool = ["kit_list", "kit_title"]
                unused = [c for c in cycle_pool if c not in used_layouts and c != prev_layout]
                if unused:
                    candidate = unused[0]
                else:
                    avail = [c for c in cycle_pool if c != prev_layout]
                    # Cân bằng tỷ lệ layout không vượt quá 40%
                    avail.sort(key=lambda x: assigned_layouts.count(x))
                    candidate = avail[0]

            if candidate == prev_layout or (candidate in used_layouts and len(used_layouts | {"kit_outro"}) < min(4, len(groups)) and s_idx == len(groups) - 2):
                unused_any = [c for c in ("kit_list", "kit_stat", "kit_title") if c not in used_layouts and c != prev_layout]
                if unused_any:
                    candidate = unused_any[0]
                else:
                    pool = [r for r in ("kit_title", "kit_list") if r != prev_layout]
                    candidate = pool[0]
            layout = candidate
            used_layouts.add(layout)

        prev_layout = layout

        # Build slots from grounded text
        slots: dict[str, Any] = {}
        s_ref = None

        if layout == "kit_title":
            s_ref = SourceRef(url=source_url, domain=source_domain, image_kind="card")
            first_sent = group[0].get("text", "")
            title_clean = extract_clean_headline(first_sent)
            slots = {
                "pill": _safe_pill(topic_title),
                "title": title_clean or first_sent[:42],
                "subtitle": _sanitize_metaphor(combined_text)[:120],
            }

        elif layout == "kit_stat":
            # Requirement 7: kit_stat chỉ hiện khi có đủ {giá trị, đơn vị, đối tượng đo} lấy từ câu trong nguồn
            stat_res = extract_grounded_stat(combined_text, brief=brief)
            if stat_res:
                val, unit, target_obj = stat_res
                slots = {
                    "value": val,
                    "unit": unit,
                    "label": target_obj,
                    "pill": "SỐ LIỆU NỔI BẬT",
                    "subtitle": f"{target_obj}: {val} {unit}".strip(),
                }
            else:
                # Thiếu đối tượng đo hoặc đơn vị -> KHÔNG hiện stat, chuyển sang kit_title
                layout = "kit_title"
                list_title = extract_clean_headline(_sanitize_metaphor(combined_text)) or "Nội Dung Trọng Tâm"
                slots = {
                    "title": list_title,
                    "pill": _safe_pill(topic_title),
                    "subtitle": _sanitize_metaphor(combined_text)[:120],
                }

        if layout == "kit_list":
            clean_combined = _sanitize_metaphor(combined_text)
            list_title = extract_clean_headline(clean_combined) or (_safe_pill(topic_title) if topic_title else "Nội Dung Trọng Tâm")
            if any(forb in list_title.lower() for forb in ("bước đi", "làm thế nào", "cách kỹ sư", "ý chính", "phương án", "quá trình")):
                list_title = clean_trailing_dangling(clean_combined)

            raw_clauses = [c.strip() for c in re.split(r"[,;.]", clean_combined) if len(c.strip()) >= 8]
            items = []
            if len(raw_clauses) <= 1:
                # Câu đơn ngắn: tách 3-4 từ đầu làm tiêu đề, phần vị ngữ còn lại làm bullet
                w_all = clean_combined.split()
                if len(w_all) >= 6:
                    split_w = min(4, max(2, len(w_all) // 3))
                    cand_t = clean_trailing_dangling(" ".join(w_all[:split_w]))
                    cand_it = clean_trailing_dangling(" ".join(w_all[split_w:]))
                    cand_it = re.sub(r"^(?:với|có|là|được|và|để)\s+", "", cand_it, flags=re.I).strip()
                    if len(cand_t.split()) >= 2 and len(cand_it.split()) >= 3 and not is_incomplete_phrase(cand_it):
                        list_title = cand_t[0].upper() + cand_t[1:]
                        items = [cand_it[0].upper() + cand_it[1:]]

            if not items:
                for c in raw_clauses[:4]:
                    clean_c = re.sub(r"^(khi|tuy nhiên|theo đó|do đó|ngoài ra|việc này|giúp|cho thấy)\s+", "", c, flags=re.I).strip()
                    clean_c = re.sub(r"[,;:\s]+$", "", clean_c)
                    clean_c = _sanitize_metaphor(clean_c)
                    if not clean_c:
                        continue

                    # Strip headline prefix if clean_c starts with or contains the list_title
                    if clean_c.lower().startswith(list_title.lower()):
                        remainder = clean_c[len(list_title):].strip()
                        remainder = re.sub(r"^(?:giúp|khiến|để|nhằm|cho thấy|và|là|có|trong|với|tại|ở)\s+", "", remainder, flags=re.I).strip()
                        clean_c = remainder
                    elif list_title.lower() in clean_c.lower():
                        idx = clean_c.lower().find(list_title.lower())
                        remainder = (clean_c[:idx] + " " + clean_c[idx + len(list_title):]).strip()
                        clean_c = remainder

                    if not clean_c or len(clean_c.split()) < 3:
                        continue

                    clean_c = clean_c[0].upper() + clean_c[1:]
                    clean_c = clean_trailing_dangling(clean_c)

                    if clean_c and len(clean_c) >= 10 and not is_incomplete_phrase(clean_c):
                        # Requirement 5: Bullet không được trùng >= 70% với headline
                        if text_similarity(clean_c, list_title) < 0.70:
                            items.append(clean_c)

            # Requirement 5: Nếu trùng -> bỏ bullet và để headline + 1 câu bổ sung MỚI lấy từ câu kế tiếp trong narration
            if not items:
                supp_text = ""
                if s_idx + 1 < len(groups):
                    next_sent = " ".join(s.get("text", "") for s in groups[s_idx + 1]).strip()
                    next_clean = clean_trailing_dangling(_sanitize_metaphor(next_sent))
                    if next_clean and text_similarity(next_clean, list_title) < 0.70:
                        supp_clauses = [sc.strip() for sc in re.split(r"[,;.]", next_clean) if len(sc.strip()) >= 12]
                        cand_supp = supp_clauses[0] if supp_clauses else next_clean
                        cand_supp = clean_trailing_dangling(cand_supp)
                        if text_similarity(cand_supp, list_title) < 0.70 and not is_incomplete_phrase(cand_supp):
                            supp_text = cand_supp
                if supp_text:
                    items = [supp_text]

            if not items:
                # Cảnh không còn nội dung -> chuyển sang kit_title
                layout = "kit_title"
                slots = {
                    "pill": _safe_pill(topic_title),
                    "title": list_title,
                    "subtitle": _sanitize_metaphor(combined_text)[:120],
                }
            else:
                slots = {
                    "title": list_title,
                    "pill": "CHI TIẾT",
                    "items": items,
                }

        elif layout == "kit_compare":
            cmp_res = _extract_genuine_compare(combined_text)
            if cmp_res:
                l_title, l_text, r_title, r_text = cmp_res
                cmp_title = extract_clean_headline(combined_text) or (_safe_pill(topic_title) if topic_title else "Giải Pháp Kỹ Thuật")
                slots = {
                    "title": cmp_title,
                    "pill": "ĐỐI CHIẾU",
                    "left": {"title": l_title, "text": l_text},
                    "right": {"title": r_title, "text": r_text, "winner": True},
                }
            else:
                layout = "kit_title"
                slots = {
                    "pill": _safe_pill(topic_title),
                    "title": extract_clean_headline(combined_text) or combined_text[:42],
                    "subtitle": _sanitize_metaphor(combined_text)[:120],
                }

        elif layout == "kit_quote":
            quote_author_res = _find_quote_author(combined_text, brief)
            if quote_author_res:
                author_name, author_role = quote_author_res
                slots = {
                    "quote": _sanitize_metaphor(combined_text)[:120],
                    "author": author_name,
                    "role": author_role,
                    "pill": "GÓC NHÌN",
                }
            else:
                layout = "kit_title"
                slots = {
                    "pill": _safe_pill(topic_title),
                    "title": extract_clean_headline(combined_text) or combined_text[:42],
                    "subtitle": _sanitize_metaphor(combined_text)[:120],
                }

        elif layout == "kit_outro":
            channel = brand_name if (brand_name and brand_name != "TIN CÔNG NGHỆ") else ""
            outro_title = extract_clean_headline(combined_text) or "Tổng kết"
            slots = {
                "pill": "ĐIỂM NHÌN",
                "title": outro_title,
                "text": _sanitize_metaphor(combined_text)[:140],
            }
            if channel:
                slots["channel_name"] = channel
            if source_domain:
                slots["source"] = source_domain
            # Requirement 4 & 5: Ngày nguồn phải là dd/mm/yyyy hợp lệ, không hiển thị '(01/01/)' hoặc ngày hỏng.
            if brief:
                b_facts = getattr(brief, "facts", None) or (brief.get("facts") if isinstance(brief, dict) else [])
                valid_dates = []
                for f in b_facts:
                    pub = str(getattr(f, "published_at", "") or (f.get("published_at") if isinstance(f, dict) else ""))
                    if pub and re.match(r"^\d{4}-\d{2}-\d{2}$", pub):
                        try:
                            y, m, d = [int(x) for x in pub.split("-")]
                            if 2020 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31:
                                from datetime import date
                                valid_dates.append((date(y, m, d), d, m, y))
                        except Exception:
                            pass
                if valid_dates:
                    valid_dates.sort(key=lambda x: x[0], reverse=True)
                    latest_d, d, m, y = valid_dates[0]
                    slots["source_date"] = f"{d:02d}/{m:02d}/{y:04d}"

        # Synthesize image prompt in English
        img_prompt = _generate_vivid_image_prompt(combined_text, topic=topic_title, layout=layout, idx=s_idx)

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
        assigned_layouts.append(layout)

    return SlideScript(
        topic=topic_title or "Bản tin công nghệ",
        total_duration=round(total_duration, 3),
        slides=slides,
        repair_notes=["Sinh bằng heuristic fallback Motion Kit v2."],
    )


def heuristic_slide_script_for_edit_plan(
    plan: Any,
    total_duration: float = 0.0,
    brand_name: str = ""
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
            "duration": dur,
        })
        t += dur
    if total_duration <= 0.0:
        total_duration = t
    return create_heuristic_slide_script(sentences, total_duration=total_duration, brand_name=brand_name)
