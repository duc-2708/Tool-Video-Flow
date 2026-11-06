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
            # Remove commas, semicolons
            clause_prefix = re.sub(r"[,;:\-—]", " ", clause_prefix).strip()
            prefix_words = clause_prefix.split()
            if prefix_words:
                clean_label = " ".join(prefix_words[-4:]).strip()
                clean_label = re.sub(r"^(?:với|có|là|trong|tại|ở|đến|từ|khoảng|mức|khi|đạt|chiếm|tăng|giảm)\s+", "", clean_label, flags=re.I).strip()
            else:
                clean_label = f"Chỉ số {unit_str}"

            if not clean_label or len(clean_label) < 2:
                clean_label = f"Số liệu {unit_str}"

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
    
    Rules:
    - >= 3 values with same unit and different periods -> kit_chart_line
    - Compare >= 3 items with comparable values -> kit_chart_bar
    - Percentages summing to approx 100% (95 - 105%) -> kit_chart_donut
    - 1 value -> kit_stat
    - If no valid match -> None
    """
    if not facts:
        return None

    # Group by unit
    by_unit: dict[str, list[FactNumber]] = {}
    for f in facts:
        u_norm = f.unit.lower().replace("phần trăm", "%")
        by_unit.setdefault(u_norm, []).append(f)

    # 1. Line chart: >= 3 values with same unit and different periods
    for unit, u_facts in by_unit.items():
        if len(u_facts) >= 3:
            periods = [f.period for f in u_facts if f.period]
            if len(set(periods)) >= 3:
                return {
                    "layout": "kit_chart_line",
                    "title": f"Biến động theo thời gian ({unit})",
                    "series": [{"label": str(f.period), "value": f.value} for f in u_facts[:6]],
                    "unit": unit,
                    "facts": u_facts[:6],
                }

    # 2. Donut chart: percentages summing to approx 100% (95 - 105%)
    pct_facts = by_unit.get("%", [])
    if len(pct_facts) >= 2:
        total_pct = sum(f.value for f in pct_facts)
        if 95.0 <= total_pct <= 105.0:
            return {
                "layout": "kit_chart_donut",
                "title": "Cơ cấu tỷ lệ (%)",
                "series": [{"label": f.label[:16], "value": f.value} for f in pct_facts[:5]],
                "unit": "%",
                "facts": pct_facts[:5],
            }

    # 3. Bar chart: >= 3 items with same unit
    for unit, u_facts in by_unit.items():
        if len(u_facts) >= 3:
            labels = [f.label for f in u_facts if f.label]
            if len(set(labels)) >= 3:
                return {
                    "layout": "kit_chart_bar",
                    "title": f"Chỉ số so sánh ({unit})",
                    "series": [{"label": f.label[:16], "value": f.value} for f in u_facts[:5]],
                    "unit": unit,
                    "facts": u_facts[:5],
                }

    # 4. Single number -> kit_stat
    if len(facts) >= 1:
        f = facts[0]
        return {
            "layout": "kit_stat",
            "value": f.value,
            "unit": f.unit,
            "label": f.label,
            "facts": [f],
        }

    return None
