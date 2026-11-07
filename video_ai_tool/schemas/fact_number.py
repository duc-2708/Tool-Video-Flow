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
    start_offset: int = 0
    end_offset: int = 0


# Quantity Types and Unit Validity Rules
UNIT_QUANTITY_TABLE = {
    "DIMENSION": {
        "keywords": [
            "đường kính", "chiều cao", "độ sâu", "độ dày", "bề rộng", "chiều rộng",
            "bán kính", "tiết diện", "kích thước", "sâu", "rộng", "cao", "dày"
        ],
        "allowed_units": {"m", "mét", "cm", "mm"},
        "prohibited_units": {"km", "tỷ", "triệu", "usd", "vnd", "%", "kg", "tấn"},
        "description": "Kích thước hình học / đường kính / độ sâu / chiều cao",
    },
    "DISTANCE": {
        "keywords": [
            "chiều dài", "chiều dài tuyến", "chiều dài toàn tuyến", "chiều dài hầm",
            "chiều dài đoạn", "quãng đường", "cự ly", "đoạn tuyến", "hành trình", "tuyến đường",
            "tuyến metro", "đoạn hầm", "chiều dài hầm ngầm", "ống hầm dài", "hầm dài", "dài"
        ],
        "allowed_units": {"km", "m", "mét", "hải lý"},
        "prohibited_units": {"tỷ", "triệu", "usd", "vnd", "%", "kg", "tấn"},
        "description": "Chiều dài tuyến / khoảng cách / quãng đường",
    },
    "CURRENCY": {
        "keywords": [
            "vốn", "tổng vốn", "đầu tư", "tổng mức đầu tư", "chi phí", "ngân sách",
            "giá trị", "doanh thu", "lợi nhuận", "thiệt hại", "tiêu tốn", "kinh phí", "tiền",
            "tài sản", "tài sản số", "tổn thất", "rút"
        ],
        "allowed_units": {
            "tỷ đồng", "tỉ đồng", "tỷ vnd", "tỉ vnd", "tỷ usd", "tỉ usd", "tỷ", "tỉ",
            "triệu đồng", "triệu vnd", "triệu usd", "triệu", "nghìn tỷ", "nghìn usd",
            "usd", "vnd", "đồng", "$",
        },
        "prohibited_units": {"km", "m", "mét", "cm", "mm", "%", "km/h", "m/s", "tấn"},
        "description": "Tiền tệ / vốn đầu tư / chi phí",
    },
    "SPEED": {
        "keywords": ["tốc độ", "vận tốc", "tốc độ thiết kế", "vận tốc tối đa"],
        "allowed_units": {"km/h", "m/s", "hải lý/h"},
        "prohibited_units": {"km", "m", "tỷ", "%"},
        "description": "Tốc độ / vận tốc",
    },
    "RATIO": {
        "keywords": [
            "tỷ lệ", "phần trăm", "thị phần", "tăng trưởng", "tỷ trọng", "xác suất",
            "độ che phủ", "tỷ lệ nội địa hóa", "cơ cấu"
        ],
        "allowed_units": {"%", "phần trăm"},
        "prohibited_units": {"km", "m", "tỷ đồng", "triệu", "usd", "vnd"},
        "description": "Tỷ lệ / phần trăm / thị phần",
    },
    "MASS": {
        "keywords": ["trọng lượng", "khối lượng", "nặng", "tải trọng", "khối lượng máy"],
        "allowed_units": {"tấn", "kg", "tạ", "yến"},
        "prohibited_units": {"km", "m", "%", "tỷ"},
        "description": "Khối lượng / trọng lượng",
    },
    "COUNT": {
        "keywords": [
            "số lượng", "công nhân", "kỹ sư", "chuyên gia", "nhân sự", "nhân lực",
            "ga", "trạm", "nhà ga", "ống hầm", "máy đào", "sự cố", "vụ", "dự án", "tuyến",
            "lệnh", "giao dịch", "phiên", "chiếc", "cỗ"
        ],
        "allowed_units": {
            "người", "chuyên gia", "kỹ sư", "công nhân", "ga", "trạm",
            "ống hầm", "máy", "máy đào", "sự cố", "vụ", "dự án", "tuyến",
            "lệnh", "giao dịch", "phiên", "chiếc", "cỗ"
        },
        "prohibited_units": {"km", "tỷ", "%"},
        "description": "Số lượng đối tượng đếm được",
    },
}


def validate_unit_quantity(label: str, unit: str, value: float | int = 0) -> tuple[bool, str]:
    """Validate whether the unit is physically and semantically consistent with the label.
    
    Returns (True, "") if consistent, or (False, rejection_reason).
    """
    if not label or not unit:
        return False, "Thiếu label hoặc unit"

    l_low = label.lower().strip()
    u_norm = unit.lower().strip().replace("phần trăm", "%").replace("tỉ", "tỷ")

    # 1. Check DIMENSION (đường kính, chiều cao, độ sâu, độ dày)
    dim_kws = ["đường kính", "chiều cao", "độ sâu", "độ dày", "bề rộng", "chiều rộng", "bán kính", "tiết diện"]
    if any(k in l_low for k in dim_kws):
        # Strict rule: dimension cannot be km
        if u_norm in {"km", "tỷ", "triệu", "%", "usd", "vnd", "tấn"}:
            return False, f"[DIMENSION] Đại lượng kích thước/đường kính/độ sâu '{label}' không thể có đơn vị '{unit}'"
        if u_norm not in {"m", "mét", "cm", "mm"}:
            return False, f"[DIMENSION] Đại lượng kích thước '{label}' yêu cầu đơn vị m/cm/mm, không chấp nhận '{unit}'"
        return True, ""

    # 2. Check DISTANCE (chiều dài tuyến, quãng đường, cự ly)
    dist_kws = ["chiều dài tuyến", "chiều dài toàn tuyến", "chiều dài hầm", "quãng đường", "cự ly", "đoạn tuyến", "hành trình", "ống hầm dài", "hầm dài"]
    if any(k in l_low for k in dist_kws):
        if u_norm in {"tỷ", "triệu", "%", "usd", "vnd", "tấn", "kg"}:
            return False, f"[DISTANCE] Đại lượng quãng đường/chiều dài '{label}' không thể có đơn vị '{unit}'"
        if u_norm not in {"km", "m", "mét"}:
            return False, f"[DISTANCE] Đại lượng quãng đường '{label}' yêu cầu đơn vị km/m, không chấp nhận '{unit}'"
        return True, ""

    # 3. Check CURRENCY (vốn, chi phí, ngân sách, tiền, thiệt hại, tài sản)
    curr_kws = ["vốn", "đầu tư", "chi phí", "ngân sách", "giá trị", "doanh thu", "lợi nhuận", "thiệt hại", "tiêu tốn", "kinh phí", "tài sản", "tổn thất", "rút"]
    if any(k in l_low for k in curr_kws):
        # Note: % is allowed as a cost/investment proportion (e.g. chi phí chiếm 35%)
        if u_norm in {"km", "m", "mét", "cm", "mm", "km/h", "tấn", "kg"}:
            return False, f"[CURRENCY] Đại lượng tiền tệ/vốn '{label}' không thể có đơn vị đo lường '{unit}'"
        return True, ""

    # 4. Check SPEED (tốc độ, vận tốc)
    if any(k in l_low for k in ["tốc độ", "vận tốc"]):
        if u_norm not in {"km/h", "m/s", "hải lý/h"}:
            return False, f"[SPEED] Đại lượng tốc độ '{label}' không thể có đơn vị '{unit}'"
        return True, ""

    # 5. Check RATIO (tỷ lệ, thị phần, tăng trưởng)
    if any(k in l_low for k in ["tỷ lệ", "thị phần", "tăng trưởng", "tỷ trọng"]):
        if u_norm not in {"%", "phần trăm"}:
            return False, f"[RATIO] Đại lượng tỷ lệ '{label}' không thể có đơn vị '{unit}'"
        return True, ""

    # 6. Check COUNT (số lượng, máy đào, cỗ máy, thiết bị, nhân lực, lệnh...)
    count_kws = ["số lượng", "máy đào", "cỗ máy", "thiết bị", "công nhân", "kỹ sư", "nhân sự", "đoàn tàu", "ga ngầm", "nhà ga", "lệnh", "giao dịch", "phiên"]
    if any(k in l_low for k in count_kws):
        if u_norm in {"km", "m", "mét", "cm", "mm", "%", "km/h", "m/s", "usd", "vnd", "tỷ", "triệu"}:
            return False, f"[COUNT] Số lượng/thiết bị '{label}' không thể có đơn vị đo lường '{unit}'"
        return True, ""

    return True, ""


# Regex for Vietnamese factual numbers
# Handles formats: 1.541, 1,541, 1541, 410, 4, 35%, 25 tỷ, 1.000 tỷ, 50 triệu, 4 km
NUM_PATTERN = re.compile(
    r"(?P<prefix>(?:đạt|khoảng|hơn|tới|gần|mức|tổng|đến|khoảng\s+hơn|đạt\s+mức|tăng|giảm|chiếm)\s+)?"
    r"(?P<val>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+)"
    r"\s*"
    r"(?P<unit>%|phần\s+trăm|tỷ\s+usd|tỉ\s+usd|tỷ\s+vnd|tỉ\s+vnd|tỷ\s+đồng|tỉ\s+đồng|tỷ|tỉ|triệu\s+usd|triệu\s+vnd|triệu|nghìn\s+usd|nghìn|ngàn|usd|vnd|km/h|m/s|km|m|mét|tấn|héc-ta|ha|năm|người|doanh\s+nghiệp|công\s+ty|dự\s+án|khách|lệnh|giao\s+dịch|phiên|chiếc|cỗ)(?=$|[^\w])",
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
    """Extract grounded FactNumber objects from text using Vietnamese regex and semantic validation."""
    if not text:
        return []

    facts: list[FactNumber] = []
    # Split by sentence boundaries (. ? !)
    sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]

    # Patterns for ordinal / line identifiers that are not measured quantities
    ORDINAL_PREFIX_PATTERN = re.compile(
        r"(?:tuyến(?:\s+(?:metro|đường\s+sắt|xe\s+buýt))?\s+số|máy\s+số|ga\s+số|hợp\s+đồng\s+số|giai\s+đoạn|đợt|bước)\s+$",
        re.I,
    )

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

            # 1. Ignore ordinals and date/line identifiers (e.g. "tuyến metro số 3", "máy số 1")
            pre_text_close = sent[max(0, start_idx - 35) : start_idx]
            if ORDINAL_PREFIX_PATTERN.search(pre_text_close):
                last_end = match.end()
                continue

            # Context window for period detection: pick closest year/period
            window_start = max(0, start_idx - 40)
            window_text = sent[window_start : min(len(sent), match.end() + 30)]
            period = None
            y_matches = list(YEAR_PATTERN.finditer(window_text))
            if y_matches:
                rel_num_pos = start_idx - window_start
                closest_y = min(y_matches, key=lambda m: abs(m.start() - rel_num_pos))
                period = closest_y.group(0).strip()

            # 2. Identify the clause boundary within the sentence
            delims = [",", ";", ":", "-", "—", "(", ")"]
            delim_positions_before = [sent.rfind(d, 0, start_idx) for d in delims if sent.rfind(d, 0, start_idx) != -1]
            clause_start = max(delim_positions_before) + 1 if delim_positions_before else 0

            delim_positions_after = [sent.find(d, match.end()) for d in delims if sent.find(d, match.end()) != -1]
            clause_end = min(delim_positions_after) if delim_positions_after else len(sent)

            clause_text = sent[clause_start:clause_end].strip()

            # 3. Determine label from words in this clause before the number
            pre_in_clause = sent[clause_start:start_idx].strip()
            pre_in_clause = re.sub(r"[()\[\],;:\-—]", " ", pre_in_clause).strip()
            prefix_words = pre_in_clause.split()

            clean_label = ""
            label_start_pos = start_idx

            # Check for explicit keywords inside this clause:
            # đường kính, chiều dài, độ sâu, chiều cao, vốn đầu tư, tốc độ, tỷ lệ...
            kw_match = None
            for q_type, q_info in UNIT_QUANTITY_TABLE.items():
                for kw in q_info["keywords"]:
                    if re.search(rf"\b{re.escape(kw)}\b", pre_in_clause, re.I):
                        kw_match = kw
                        break
                if kw_match:
                    break

            if kw_match:
                # Find start of keyword or subject in clause
                kw_idx = pre_in_clause.lower().find(kw_match.lower())
                raw_cand = pre_in_clause[kw_idx:].strip()
                # If there's a subject before the keyword (e.g. "máy đào hầm đường kính"), include subject
                pre_subject = pre_in_clause[:kw_idx].strip()
                sub_words = pre_subject.split()
                if sub_words and len(sub_words) <= 4:
                    raw_cand = f"{' '.join(sub_words[-3:])} {raw_cand}".strip()

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
                pos_in_sent = sent.find(clean_label, clause_start)
                if pos_in_sent != -1:
                    label_start_pos = pos_in_sent
            elif prefix_words:
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
                pos_in_sent = sent.find(clean_label, clause_start)
                if pos_in_sent != -1:
                    label_start_pos = pos_in_sent

            # If label is empty, too short, or a generic currency fragment (e.g., "tỷ đồng"), look after match
            if not clean_label or len(clean_label.split()) < 2 or clean_label.lower() in ("tỷ đồng", "triệu đồng", "usd", "vnd"):
                post_text = sent[match.end() : clause_end].strip()
                post_text = re.sub(r"[()\[\],;:\-—]", " ", post_text).strip()
                post_words = post_text.split()
                if post_words:
                    cand_post = " ".join(post_words[:3]).strip()
                    cand_post = re.sub(r"^(?:xảy ra|ở|tại|cho|với|của|trong|là)\s+", "", cand_post, flags=re.I).strip()
                    if cand_post and len(cand_post.split()) >= 2:
                        clean_label = cand_post
                        label_start_pos = match.start()

            if not clean_label or len(clean_label.split()) < 2:
                clean_label = f"Chỉ số {unit_str}"
                label_start_pos = match.start()

            # 4. Semantic consistency check (Unit vs Quantity type)
            is_valid, err_reason = validate_unit_quantity(clean_label, unit_str, num_val)
            if not is_valid:
                # Inconsistent quantity and unit: log reason and reject fact
                last_end = match.end()
                continue

            # Calculate span offsets (value, unit, and label MUST be in the same span)
            fact_start = min(label_start_pos, match.start())
            fact_end = max(match.end(), fact_start + len(clean_label))

            facts.append(
                FactNumber(
                    label=clean_label[0].upper() + clean_label[1:],
                    value=num_val,
                    unit=unit_str,
                    period=period,
                    source_url=source_url,
                    source_sentence=sent,
                    start_offset=fact_start,
                    end_offset=fact_end,
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
