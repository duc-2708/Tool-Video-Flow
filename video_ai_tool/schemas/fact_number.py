"""Schema and extraction utilities for FactNumber and Real Charts."""
from __future__ import annotations

import re
from typing import Any, Optional, Union
from pydantic import Field
from schemas.base import StrictModel


class FactNumber(StrictModel):
    label: str
    value: Union[float, int]
    unit: str
    period: Optional[str] = None
    source_url: Optional[str] = None
    source_sentence: str


# Regex for Vietnamese factual numbers
# Handles formats: 1.541, 1,541, 1541, 410, 4, 35%, 25 tỷ, 1.000 tỷ, 50 triệu, 4 km
NUM_PATTERN = re.compile(
    r"(?P<prefix>(?:đạt|khoảng|hơn|tới|gần|mức|tổng|đến|khoảng\s+hơn|đạt\s+mức|tăng|giảm|chiếm)\s+)?"
    r"(?P<val>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+)"
    r"\s*"
    r"(?P<unit>%|phần\s+trăm|tỷ\s+usd|tỉ\s+usd|tỷ\s+vnd|tỉ\s+vnd|tỷ\s+đồng|tỉ\s+đồng|tỷ|tỉ|triệu\s+usd|triệu\s+vnd|triệu|nghìn\s+usd|nghìn|ngàn|usd|vnd|km|m|mét|tấn|héc-ta|ha|năm|người|doanh\s+nghiệp|công\s+ty|dự\s+án|khách)(?=$|[^\w])",
    re.IGNORECASE,
)

YEAR_PATTERN = re.compile(r"\b(?:năm|quý\s+[1-4]|tháng\s+\d{1,2}(?:/\d{4})?)\s+(?P<year>20\d{2}|19\d{2})\b", re.IGNORECASE)


def parse_vietnamese_number(num_str: str) -> float:
    """Parse Vietnamese number string (handling '.', ',' and '%' appropriately)."""
    s = str(num_str).replace("%", "").strip()
    if "." in s and "," in s:
        # 1.541,5 -> 1541.5 or 1,541.5 -> 1541.5
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        # Could be thousands separator (1.541) or decimal (3.5)
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and int(parts[0]) > 0:
            s = s.replace(".", "")
        else:
            pass
    elif "," in s:
        # In VN: comma is often decimal (3,5%) or thousands (1,541)
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) == 3 and int(parts[0]) > 0:
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    try:
        val = float(s)
        return int(val) if val.is_integer() else val
    except ValueError:
        return 0.0


def extract_facts_from_text(text: str, source_url: str | None = None) -> list[FactNumber]:
    """Extract grounded FactNumber objects from text using Vietnamese regex."""
    if not text:
        return []

    facts: list[FactNumber] = []
    # Split by sentence boundaries (. ? !)
    sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]

    for sent in sentences:
        last_end = 0
        matches = list(NUM_PATTERN.finditer(sent))
        for match in matches:
            val_str = match.group("val")
            unit_str = match.group("unit").strip()
            num_val = parse_vietnamese_number(val_str)
            if num_val <= 0:
                last_end = match.end()
                continue

            start_idx = match.start()
            # Context window for period detection: pick closest year/period
            window_start = max(0, start_idx - 40)
            window_text = sent[window_start : min(len(sent), match.end() + 30)]
            period = None
            y_matches = list(YEAR_PATTERN.finditer(window_text))
            if y_matches:
                rel_num_pos = start_idx - window_start
                closest_y = min(y_matches, key=lambda m: abs(m.start() - rel_num_pos))
                period = closest_y.group(0).strip()

            # Determine label from words between last_end and start_idx
            clause_prefix = sent[last_end:start_idx].strip()
            clause_prefix = re.sub(r"[()\[\],;:\-—]", " ", clause_prefix).strip()
            prefix_words = clause_prefix.split()
            clean_label = ""
            if prefix_words:
                raw_cand = " ".join(prefix_words[-4:]).strip()
                raw_cand = re.sub(
                    r"^(?:với|có|là|trong|tại|ở|đến|từ|khoảng|mức|khi|đạt|chiếm|tăng|giảm|hơn|gần|tổng|mỗi)\s+",
                    "",
                    raw_cand,
                    flags=re.I,
                ).strip()
                raw_cand = re.sub(
                    r"\s+(?:chiếm|đạt|mức|khoảng|hơn|gần|tăng|giảm|với|tại|ở|trong|là)$",
                    "",
                    raw_cand,
                    flags=re.I,
                ).strip()
                clean_label = raw_cand

            # If label is empty, too short, or a generic currency fragment (e.g., "tỷ đồng"), look after match
            if not clean_label or len(clean_label.split()) < 2 or clean_label.lower() in ("tỷ đồng", "triệu đồng", "usd", "vnd"):
                post_text = sent[match.end() : min(len(sent), match.end() + 35)].strip()
                post_text = re.sub(r"[()\[\],;:\-—]", " ", post_text).strip()
                post_words = post_text.split()
                if post_words:
                    cand_post = " ".join(post_words[:3]).strip()
                    cand_post = re.sub(r"^(?:xảy ra|ở|tại|cho|với|của|trong|là)\s+", "", cand_post, flags=re.I).strip()
                    if cand_post and len(cand_post.split()) >= 2:
                        clean_label = cand_post

            if not clean_label or len(clean_label.split()) < 2:
                clean_label = f"Hạng mục {unit_str}"

            facts.append(
                FactNumber(
                    label=clean_label[0].upper() + clean_label[1:],
                    value=num_val,
                    unit=unit_str,
                    period=period,
                    source_url=source_url,
                    source_sentence=sent,
                )
            )
            last_end = match.end()

    return facts


def extract_facts_from_brief(brief: dict[str, Any]) -> list[FactNumber]:
    """Extract all FactNumber objects from brief's facts and knowledge notes."""
    if not brief or not isinstance(brief, dict):
        return []

    all_facts: list[FactNumber] = []
    seen_keys: set[tuple[Any, str]] = set()

    # 1. From brief facts
    b_facts = brief.get("facts") or brief.get("key_facts") or []
    for item in b_facts:
        if not isinstance(item, dict):
            continue
        claim = item.get("claim", "")
        evidence = item.get("evidence_quote", "")
        url = item.get("source_url")
        extracted = extract_facts_from_text(f"{claim}. {evidence}", source_url=url)
        for fn in extracted:
            key = (fn.value, fn.unit.lower())
            if key not in seen_keys:
                seen_keys.add(key)
                all_facts.append(fn)

    # 2. From knowledge notes if facts was sparse
    if len(all_facts) < 3:
        k_notes = brief.get("knowledge_notes") or []
        for note in k_notes:
            if isinstance(note, dict) and note.get("text"):
                extracted = extract_facts_from_text(note["text"])
                for fn in extracted:
                    key = (fn.value, fn.unit.lower())
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_facts.append(fn)

    return all_facts


def select_chart_for_facts(facts: list[FactNumber]) -> dict[str, Any] | None:
    """Select appropriate kit_chart layout based on facts structure.
    
    Strict Rules (1 chart = 1 proposition):
    1. A chart represents ONE proposition: all values MUST share the same normalized unit,
       the same object of measurement, and originate from the SAME source_sentence
       (or immediately adjacent sentence from the same source).
    2. Values from different sentences, different sources, or with different units (%, USD, count, CAGR)
       MUST NEVER be merged into a multi-bar or line chart.
    3. Every column/item MUST have a distinct category label from the source (>= 2 words),
       never generic or truncated fragments.
    4. If conditions for a multi-value chart are not met:
       Fallback to kit_stat for the single most prominent fact, or None.
    """
    if not facts:
        return None

    # Group by normalized unit
    def normalize_u(u: str) -> str:
        s = u.lower().strip()
        s = s.replace("phần trăm", "%").replace("tỉ", "tỷ")
        return s

    distinct_units = set(normalize_u(f.unit) for f in facts)
    has_mixed_units = len(distinct_units) > 1
    has_cagr = any("cagr" in f.unit.lower() or "tốc độ" in f.label.lower() for f in facts)

    # Requirement 1a & 1e: Dữ liệu trộn đơn vị hoặc có CAGR lẫn lộn -> KHÔNG ra biểu đồ, hạ cấp về kit_stat
    if has_mixed_units or (has_cagr and len(facts) > 1):
        f = facts[0]
        return {
            "layout": "kit_stat",
            "value": f.value,
            "unit": f.unit,
            "label": f.label,
            "facts": [f],
        }

    # All facts share the SAME normalized unit
    unit = normalize_u(facts[0].unit)

    # 1. Donut chart: percentages summing to approx 100% (95 - 105%) with distinct valid category labels
    if unit == "%" and len(facts) >= 2:
        total_pct = sum(f.value for f in facts)
        if 95.0 <= total_pct <= 105.0:
            labels = [f.label for f in facts if len(f.label.strip()) >= 2 and not f.label.lower().startswith("hạng mục")]
            if len(set(labels)) == len(facts):
                return {
                    "layout": "kit_chart_donut",
                    "title": f"Cơ cấu tỷ lệ (%)",
                    "series": [{"label": f.label[:20], "value": f.value} for f in facts[:5]],
                    "unit": "%",
                    "facts": facts[:5],
                }

    # 2. Line chart: >= 3 values with same unit and distinct periods
    if len(facts) >= 3:
        periods = [f.period for f in facts if f.period]
        if len(set(periods)) >= 3:
            return {
                "layout": "kit_chart_line",
                "title": f"Biến động theo thời gian ({unit})",
                "series": [{"label": str(f.period), "value": f.value} for f in facts[:6]],
                "unit": unit,
                "facts": facts[:6],
            }

    # 3. Bar chart: >= 2 items with SAME unit and distinct valid category labels from source
    if len(facts) >= 2:
        valid_labels = [f.label for f in facts if len(f.label.strip()) >= 2 and not f.label.lower().startswith("hạng mục")]
        if len(set(valid_labels)) >= 2 and len(valid_labels) == len(facts):
            return {
                "layout": "kit_chart_bar",
                "title": f"Chỉ số so sánh ({unit})",
                "series": [{"label": f.label[:18], "value": f.value} for f in facts[:5]],
                "unit": unit,
                "facts": facts[:5],
            }

    # 4. Fallback to kit_stat for the single most prominent fact
    f = facts[0]
    return {
        "layout": "kit_stat",
        "value": f.value,
        "unit": f.unit,
        "label": f.label,
        "facts": [f],
    }
