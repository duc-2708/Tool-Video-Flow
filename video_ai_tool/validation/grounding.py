"""
validation/grounding.py - Unified grounding & provenance verification module.

Single source of truth across the pipeline for:
- Numeric normalization, conversion, scaling, and comparison.
- Entity normalization, acronyms, and permutation-invariant matching.
- Claim classification (event claim vs question vs CTA vs opinion vs background).
- Provenance matching against ResearchBrief facts.
- Multi-step self-repair ladder (Fix -> Neutralize -> Drop, never block unless 0 scenes).
- GROUNDING_MODE control: 'fix' (default), 'warn', 'block'.
"""
import os
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, NamedTuple
from urllib.parse import urlsplit


# -----------------------------------------------------------------------------
# Configuration: GROUNDING_MODE
# -----------------------------------------------------------------------------

def get_grounding_mode(settings=None) -> str:
    """Return grounding mode: 'fix' (default), 'warn', or 'block'."""
    mode = ""
    if settings is not None and hasattr(settings, "grounding_mode"):
        mode = getattr(settings, "grounding_mode", "")
    if not mode:
        mode = os.environ.get("GROUNDING_MODE", "").strip().lower()
    return mode if mode in ("fix", "warn", "block") else "fix"


# -----------------------------------------------------------------------------
# 1. Numeric Normalization and Comparison
# -----------------------------------------------------------------------------

VI_DIGIT_WORDS = {
    "không": 0, "mot": 1, "mốt": 1, "một": 1,
    "hai": 2, "ba": 3, "bốn": 4, "tư": 4,
    "năm": 5, "lăm": 5, "sáu": 6, "bảy": 7, "bẩy": 7,
    "tám": 8, "chín": 9,
}

MAGNITUDES = {
    "tỷ": Decimal("1000000000"),
    "tỉ": Decimal("1000000000"),
    "billion": Decimal("1000000000"),
    "b": Decimal("1000000000"),
    "triệu": Decimal("1000000"),
    "million": Decimal("1000000"),
    "m": Decimal("1000000"),
    "nghìn": Decimal("1000"),
    "ngàn": Decimal("1000"),
    "thousand": Decimal("1000"),
    "k": Decimal("1000"),
}


class NormalizedNumber:
    """Structured representation of a parsed number with unit, magnitude and range."""
    def __init__(
        self,
        value: Decimal | None = None,
        unit: str | None = None,
        raw: str = "",
        multiplier: Decimal = Decimal(1),
        is_range: bool = False,
        range_min: Decimal | None = None,
        range_max: Decimal | None = None,
        relational_multiplier: float | None = None,
    ):
        self.value = value
        self.unit = unit
        self.raw = raw
        self.multiplier = multiplier
        self.is_range = is_range
        self.range_min = range_min
        self.range_max = range_max
        self.relational_multiplier = relational_multiplier

    @property
    def effective_value(self) -> Decimal | None:
        if self.value is not None:
            return self.value * self.multiplier
        return None

    def canonical_str(self) -> str:
        u = "%" if self.unit == "%" else ""
        if self.is_range and self.range_min is not None and self.range_max is not None:
            return f"{format(self.range_min.normalize(), 'f')}-{format(self.range_max.normalize(), 'f')}{u}"
        if self.effective_value is not None:
            val_str = format(self.effective_value.normalize(), "f")
            return f"{val_str}{u}"
        return self.raw

    def __repr__(self) -> str:
        return f"NormalizedNumber(val={self.effective_value}, unit={self.unit!r}, raw={self.raw!r})"


def _clean_thousand_decimal(val_str: str) -> str:
    """Convert European / Vietnamese / US punctuation to standard decimal '.'"""
    val = val_str.strip()
    if "," in val and "." in val:
        dec = "," if val.rfind(",") > val.rfind(".") else "."
        val = val.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif re.fullmatch(r"[1-9]\d{0,2}(?:[.,]\d{3})+", val):
        val = val.replace(".", "").replace(",", "")
    else:
        val = val.replace(",", ".")
    return val


def _parse_vietnamese_spoken_number(text: str) -> Decimal | None:
    """Parse Vietnamese number words like 'hai mươi bốn' -> Decimal(24)."""
    words = text.casefold().strip().split()
    if not words:
        return None

    total = Decimal(0)
    current_group = Decimal(0)
    current_digit = Decimal(0)
    has_any = False

    i = 0
    while i < len(words):
        w = words[i]
        if w in VI_DIGIT_WORDS:
            current_digit = Decimal(VI_DIGIT_WORDS[w])
            has_any = True
        elif w in ("mười", "mươi"):
            if current_digit == Decimal(0):
                current_group += Decimal(10)
            else:
                current_group += current_digit * Decimal(10)
            current_digit = Decimal(0)
            has_any = True
        elif w == "trăm":
            current_group += current_digit * Decimal(100)
            current_digit = Decimal(0)
            has_any = True
        elif w in ("nghìn", "ngàn"):
            group_val = current_group + current_digit
            if group_val == Decimal(0):
                group_val = Decimal(1)
            total += group_val * Decimal(1000)
            current_group = Decimal(0)
            current_digit = Decimal(0)
            has_any = True
        elif w == "triệu":
            group_val = current_group + current_digit
            if group_val == Decimal(0):
                group_val = Decimal(1)
            total += group_val * Decimal(1000000)
            current_group = Decimal(0)
            current_digit = Decimal(0)
            has_any = True
        elif w in ("tỷ", "tỉ"):
            group_val = current_group + current_digit
            if group_val == Decimal(0):
                group_val = Decimal(1)
            total += group_val * Decimal(1000000000)
            current_group = Decimal(0)
            current_digit = Decimal(0)
            has_any = True
        elif w in ("lẻ", "linh"):
            pass
        else:
            return None
        i += 1

    if not has_any:
        return None
    return total + current_group + current_digit


def normalize_number(val: Any) -> NormalizedNumber | None:
    """
    Parse and normalize a single number, string with number/unit, range, or word.
    Handles %, $, đ, VND, multipliers (k, tr, tỷ, million, billion), and Vietnamese words.
    """
    if val is None:
        return None

    if isinstance(val, (int, float, Decimal)):
        try:
            d = Decimal(str(val))
            return NormalizedNumber(value=d, raw=str(val))
        except (InvalidOperation, ValueError):
            return None

    raw_text = str(val).strip()
    if not raw_text:
        return None

    # Relational phrases
    if re.search(r"\bgấp đôi\b", raw_text, re.I):
        return NormalizedNumber(value=Decimal(2), relational_multiplier=2.0, raw=raw_text)
    if re.search(r"\bmột nửa\b", raw_text, re.I):
        return NormalizedNumber(value=Decimal("0.5"), relational_multiplier=0.5, raw=raw_text)
    if re.search(r"\bgấp ba\b", raw_text, re.I):
        return NormalizedNumber(value=Decimal(3), relational_multiplier=3.0, raw=raw_text)

    # Range check (e.g. "10-15", "10 - 15", "10 đến 15")
    range_match = re.search(
        r"(?<!\d)(\d+(?:[.,]\d+)*)\s*(?:-|–|—|đến|to)\s*(\d+(?:[.,]\d+)*)\s*(triệu|tỷ|tỉ|nghìn|ngàn|k|m|b|%|usd|\$|đồng|vnd)?",
        raw_text,
        re.I,
    )
    if range_match:
        try:
            r1 = Decimal(_clean_thousand_decimal(range_match.group(1)))
            r2 = Decimal(_clean_thousand_decimal(range_match.group(2)))
            unit = range_match.group(3) or None
            mult = Decimal(1)
            if unit:
                u_lower = unit.lower()
                if u_lower in MAGNITUDES:
                    mult = MAGNITUDES[u_lower]
                    unit = None
            return NormalizedNumber(
                is_range=True,
                range_min=min(r1, r2) * mult,
                range_max=max(r1, r2) * mult,
                unit=unit,
                raw=raw_text,
            )
        except (InvalidOperation, ValueError):
            pass

    # Clean currency / percent signs
    has_percent = bool(re.search(r"%\s*|phần trăm", raw_text, re.I))
    has_usd = bool(re.search(r"\$|\busd\b|đô la", raw_text, re.I))
    has_vnd = bool(re.search(r"đ|\bvnd\b|\bvnđ\b|đồng", raw_text, re.I))

    clean = re.sub(r"[\$%đ]|phần trăm|\busd\b|\bvnd\b|\bvnđ\b|đô la|đồng", " ", raw_text, flags=re.I)

    # Magnitude suffix detection
    mag_match = re.search(r"(?<=\d|\s)(triệu|tỷ|tỉ|nghìn|ngàn|million|billion|thousand|[kmb])\b", clean, re.I)
    mult = Decimal(1)
    if mag_match:
        m_word = mag_match.group(1).lower()
        mult = MAGNITUDES.get(m_word, Decimal(1))
        clean = clean[:mag_match.start()] + clean[mag_match.end():]

    clean = clean.strip()

    # Attempt direct decimal parse
    num_match = re.search(r"(?<!\w)(\d+(?:[.,]\d+)*)(?!\w)", clean)
    if num_match:
        try:
            clean_str = _clean_thousand_decimal(num_match.group(1))
            d = Decimal(clean_str)
            unit = "%" if has_percent else "USD" if has_usd else "VND" if has_vnd else None
            return NormalizedNumber(value=d, unit=unit, multiplier=mult, raw=raw_text)
        except (InvalidOperation, ValueError):
            pass

    # Attempt Vietnamese spoken word number parse
    spoken_val = _parse_vietnamese_spoken_number(clean)
    if spoken_val is not None:
        unit = "%" if has_percent else "USD" if has_usd else "VND" if has_vnd else None
        return NormalizedNumber(value=spoken_val, unit=unit, multiplier=mult, raw=raw_text)

    return None


def extract_numbers(text: str, *, ignore_current_year: bool = True) -> list[NormalizedNumber]:
    """
    Extract all distinct numbers, magnitudes, and ranges from a sentence or paragraph.
    Handles Vietnamese spoken numbers, currencies, percentages, and avoids date token concatenation.
    """
    if not text:
        return []

    # Preserve and protect date boundaries (e.g. 'tháng 1 năm 2026', '01/2026')
    # Never concatenate month and year into '12026'
    calendar_protected = re.sub(
        r"(?<!\d)(?:(\d{1,2})\s*[./-]\s*)?(\d{1,2})\s*[./-]\s*(\d{4})(?!\d)",
        lambda m: f" {m.group(1) or ''} tháng {m.group(2)} năm {m.group(3)} ",
        text,
    )

    # Lowercase m / mét in article lengths is not financial suffix M
    calendar_protected = re.sub(r"(\d+(?:[.,]\d+)*)\s*m\b", r"\1 mét", calendar_protected)

    from agents.vietnamese_tts import spoken_to_digits
    converted_text = spoken_to_digits(calendar_protected.casefold()).replace("phần trăm", "%")
    converted_text = re.sub(r"\b(?:cảnh|scene|bước|thứ|mục|phần|stt|số thứ tự)\s*#?\s*\d+\b", "", converted_text)

    current_year = datetime.now().year
    results: list[NormalizedNumber] = []
    seen_effective: set[Decimal] = set()

    # Pattern for numbers with optional magnitude and optional percent/currency
    pattern = re.compile(
        r"(?<!\d)(\d+(?:[.,]\d+)*)(?:\s*(triệu|tỷ|tỉ|nghìn|ngàn|million|billion|thousand|[mkb])(?!\w))?\s*(%|\$|đ|usd|vnd)?",
        re.I,
    )

    for m in pattern.finditer(converted_text):
        val_str, mag_str, unit_str = m.groups()
        try:
            cleaned = _clean_thousand_decimal(val_str)
            val = Decimal(cleaned)
            multiplier = Decimal(1)
            if mag_str:
                multiplier = MAGNITUDES.get(mag_str.lower(), Decimal(1))

            unit = None
            if unit_str:
                u = unit_str.lower()
                unit = "%" if "%" in u else "$" if ("$" in u or "usd" in u) else "đ" if ("đ" in u or "vnd" in u) else None

            num = NormalizedNumber(value=val, unit=unit, multiplier=multiplier, raw=m.group(0).strip())
            eff = num.effective_value

            if ignore_current_year and eff == Decimal(current_year) and not mag_str and not unit:
                continue

            if eff not in seen_effective:
                seen_effective.add(eff)
                results.append(num)
        except (InvalidOperation, ValueError):
            continue

    return results


def numbers_match(n1: Any, n2: Any, tolerance: float = 0.01) -> bool:
    """
    Check if two numbers match by numeric value and compatible unit.
    Tolerance defaults to 1% (0.01).
    Example: 51.8 matches 51.8% (compatible unit).
    25 tỷ matches 25 billion and matches 25000000000.
    """
    norm1 = normalize_number(n1) if not isinstance(n1, NormalizedNumber) else n1
    norm2 = normalize_number(n2) if not isinstance(n2, NormalizedNumber) else n2

    if norm1 is None or norm2 is None:
        return False

    # Range matching
    if norm1.is_range and not norm2.is_range:
        v2 = norm2.effective_value
        if v2 is not None and norm1.range_min is not None and norm1.range_max is not None:
            return norm1.range_min <= v2 <= norm1.range_max
    if norm2.is_range and not norm1.is_range:
        v1 = norm1.effective_value
        if v1 is not None and norm2.range_min is not None and norm2.range_max is not None:
            return norm2.range_min <= v1 <= norm2.range_max
    if norm1.is_range and norm2.is_range:
        return (
            norm1.range_min == norm2.range_min
            and norm1.range_max == norm2.range_max
        )

    # Value comparison
    v1 = norm1.effective_value
    v2 = norm2.effective_value
    if v1 is None or v2 is None:
        return False

    diff = abs(v1 - v2)
    max_val = max(abs(v1), abs(v2))

    # Exact or within tolerance
    if max_val == 0:
        val_match = diff == 0
    else:
        val_match = diff <= (max_val * Decimal(str(tolerance))) or diff < Decimal("0.000001")

    if not val_match:
        # Check scale discrepancy (e.g. 51.8 vs 0.518 for percentages)
        if norm1.unit == "%" or norm2.unit == "%":
            scaled_v1 = v1 / Decimal(100) if norm1.unit == "%" else v1
            scaled_v2 = v2 / Decimal(100) if norm2.unit == "%" else v2
            scaled_diff = abs(scaled_v1 - scaled_v2)
            scaled_max = max(abs(scaled_v1), abs(scaled_v2))
            if scaled_max > 0 and scaled_diff <= (scaled_max * Decimal(str(tolerance))):
                val_match = True

    if not val_match:
        return False

    # Unit compatibility: None is compatible with anything; matching units are compatible
    if norm1.unit is None or norm2.unit is None:
        return True
    return norm1.unit.lower() == norm2.unit.lower()


def normalized_numbers(text: str, *, ignore_current_year: bool = True) -> set[str]:
    """
    Drop-in compatibility function matching the signature of agents/director_numbers.py.
    Returns string set of normalized numbers (including % if present).
    """
    extracted = extract_numbers(text, ignore_current_year=ignore_current_year)
    return {n.canonical_str() for n in extracted}


# -----------------------------------------------------------------------------
# 2. Entity Normalization and Permutation-Invariant Matching
# -----------------------------------------------------------------------------

COMMON_VI_WORDS = set("""trải nghiệm nhiều khi nếu vì mỗi hầu thực giả sử như vậy nên nhưng
và hoặc hay với thì là của trong trên dưới này đó những các một hai ba bốn năm
sáu bảy tám chín mười không có thể sẽ đã đang còn chỉ cũng rất hơn nhất người
dùng mình bạn họ chúng ta tôi nó đây đâu đầu sau trước cuối phần việc điều cách
bước cảnh câu nguồn thông tin nền số dữ liệu hình ảnh ví dụ thường nói nhìn
thử hãy đừng mặt khác tuy dù bởi do từ đến tại ở cho để về qua cùng lại chính
thật tế quy trình hệ thống máy công nghệ nhân sự giải thích phân tích đánh giá
sản phẩm công ty ngân hàng vụ kiện mất thay đổi kiểm tra chọn giữ lấy đưa tạo
thêm bỏ tránh kết mở chào cảm ơn giới thiệu nhờ chẳng hạn đồng thời ngoài ra
toàn bộ bất kỳ vài khoảng ước chừng ước tính xấp xỉ hàng chục trăm nghìn triệu
tỷ giây phút giờ ngày tháng năm hôm nay chiều tối sáng bắt đầu tiếp theo
nhẹ nhanh chậm lớn nhỏ mạnh yếu tốt xấu rõ ràng mới cũ kinh doanh học làm
nghĩ tưởng tượng giống khác biệt bằng tức bếp bánh chiếc cỗ tấm bức hồ sơ
giấy tờ trách nhiệm lợi ích tác động kết luận nhận định dù sao vốn và vốn dĩ
đặc biệt bối nội dung trực tuyến vâng nhé thật sự tất cả sắp xếp chủ đề
ai api cpu gpu tts video công cụ gợi ý ý nghĩa miễn là dẫu tuy nhiên liệu
bình luận theo dõi kênh chia sẻ quan điểm tin tức
""".split())

GENERIC_ENTITY_PREFIXES = set("""vụ vụ_kiện kiện công_ty tập_đoàn doanh_nghiệp ngân_hàng
hãng tổ_chức quỹ báo tạp_chí kênh đài trang ứng_dụng nền_tảng dịch_vụ sản_phẩm
hệ_thống mô_hình dự_án hiệp_hội liên_minh toà_án viện chính_phủ bộ ban ngành
""".split())


def _strip_accents(text: str) -> str:
    """Strip Vietnamese diacritics into plain ASCII-like lowercase."""
    nfkd = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return without_accents.replace("đ", "d").replace("Đ", "d").casefold()


class NormalizedEntity:
    """Normalized entity representation with core token set for permutation invariance."""
    def __init__(self, raw: str):
        self.raw = raw.strip()
        self.canonical = re.sub(r"\s+", " ", _strip_accents(self.raw)).strip()
        # Extract core tokens (strip generic prefixes and common words)
        words = self.canonical.split()
        core: list[str] = []
        for w in words:
            clean_w = re.sub(r"[^\w-]", "", w)
            if clean_w and clean_w not in GENERIC_ENTITY_PREFIXES and clean_w not in COMMON_VI_WORDS:
                core.append(clean_w)
        self.core_tokens = tuple(sorted(set(core)))
        self.is_acronym = bool(re.fullmatch(r"[A-Z0-9-]{2,10}", self.raw))
        self.is_foreign = bool(re.search(r"[a-z][A-Z]|\b[A-Za-z]+(?:'[A-Za-z]+)?\b", self.raw) and not any(w in COMMON_VI_WORDS for w in words))

    def __repr__(self) -> str:
        return f"NormalizedEntity(raw={self.raw!r}, core={self.core_tokens})"


def normalize_entity(text: str) -> NormalizedEntity:
    return NormalizedEntity(text)


def entity_matches(e1: Any, e2: Any) -> bool:
    """
    Check if two entities match, accounting for:
    - Permutations: 'Cambridge Analytica Vụ' matches 'Vụ Cambridge Analytica'
    - Casing, diacritics and punctuation
    - Acronym expansion / containment
    """
    norm1 = normalize_entity(e1) if not isinstance(e1, NormalizedEntity) else e1
    norm2 = normalize_entity(e2) if not isinstance(e2, NormalizedEntity) else e2

    if not norm1.raw or not norm2.raw:
        return False

    # Exact canonical match
    if norm1.canonical == norm2.canonical:
        return True

    # Core token set match (permutation invariant)
    if norm1.core_tokens and norm2.core_tokens:
        s1 = set(norm1.core_tokens)
        s2 = set(norm2.core_tokens)
        if s1 == s2:
            return True
        # Subset match if all core tokens of one are in the other and size >= 1
        if len(s1) >= 2 and len(s2) >= 2 and (s1.issubset(s2) or s2.issubset(s1)):
            return True

    return False


def proper_names(text: str):
    """
    Drop-in compatibility generator function matching agents/proper_names.py.
    Preserves regex match objects and offsets for span replacement.
    """
    from agents.proper_names import proper_names as _orig_proper_names
    return _orig_proper_names(text)


def extract_entities(text: str, *, sentence_boundary: bool = True) -> list[NormalizedEntity]:
    """Extract candidate entities from text avoiding common words and sentence starts."""
    matches = list(proper_names(text))
    results: list[NormalizedEntity] = []
    seen: set[str] = set()
    for m in matches:
        name = m.group(0).strip()
        ne = NormalizedEntity(name)
        if ne.canonical not in seen and ne.core_tokens:
            seen.add(ne.canonical)
            results.append(ne)
    return results


# -----------------------------------------------------------------------------
# 3. Claim Classification
# -----------------------------------------------------------------------------

def classify_claim(text: str, sentence_type: str = "event") -> dict[str, Any]:
    """
    Distinguish event assertions from questions, CTA invitations, opinions, and background examples.
    Returns:
    {
        'category': 'question' | 'cta_invitation' | 'opinion' | 'background_example' | 'event_claim',
        'is_assertion': bool,
        'assertion_part': str,
        'cta_part': str,
        'numbers': list[NormalizedNumber],
        'entities': list[NormalizedEntity],
    }
    """
    raw = (text or "").strip()
    if not raw:
        return {
            "category": "opinion",
            "is_assertion": False,
            "assertion_part": "",
            "cta_part": "",
            "numbers": [],
            "entities": [],
        }

    # 1. Background illustrative example
    if re.match(r"^\s*(?:ví dụ|chẳng hạn|minh họa|đơn cử)\b", raw, re.I):
        return {
            "category": "background_example",
            "is_assertion": False,
            "assertion_part": "",
            "cta_part": "",
            "numbers": extract_numbers(raw),
            "entities": extract_entities(raw),
        }

    # 2. Pure question
    is_q = raw.endswith("?") or bool(
        re.match(r"^(?:liệu|phải chăng|theo bạn|bạn nghĩ sao|ai sẽ|khi nào|đâu là|tại sao|vì sao|có nên|có phải)\b", raw, re.I)
    )
    nums = extract_numbers(raw)
    ents = extract_entities(raw)

    if is_q and not nums:
        return {
            "category": "question",
            "is_assertion": False,
            "assertion_part": "",
            "cta_part": raw,
            "numbers": nums,
            "entities": ents,
        }

    # 3. Pure CTA invitation
    is_invitation = bool(
        re.search(
            r"\b(?:hãy để lại|hãy bình luận|để lại ý kiến|bình luận bên dưới|theo dõi kênh|bạn nghĩ sao|chia sẻ góc nhìn|ấn theo dõi|đăng ký kênh)\b",
            raw,
            re.I,
        )
    )
    if is_invitation and not nums and not ents:
        return {
            "category": "cta_invitation",
            "is_assertion": False,
            "assertion_part": "",
            "cta_part": raw,
            "numbers": nums,
            "entities": ents,
        }

    # 4. Soft opinion
    is_opinion = bool(
        re.search(r"\b(?:theo mình|quan điểm|tôi nghĩ|tin rằng|đánh giá|cảm thấy|dường như)\b", raw, re.I)
    )
    if is_opinion and not nums and sentence_type in ("opinion", "explain", "cta"):
        return {
            "category": "opinion",
            "is_assertion": False,
            "assertion_part": raw,
            "cta_part": "",
            "numbers": nums,
            "entities": ents,
        }

    # Split assertion vs CTA question if compound sentence
    assertion_part, cta_part = raw, ""
    split_match = re.search(
        r"\s*[,;–—]\s*(?=(?:bạn nghĩ sao|theo bạn|hãy để lại|hãy bình luận|đừng quên|liệu\b)\b)",
        raw,
        re.I,
    )
    if split_match:
        assertion_part = raw[:split_match.start()].strip()
        cta_part = raw[split_match.end():].strip()

    has_event_action = bool(
        re.search(
            r"\b(?:bị kiện|nộp đơn|đệ đơn|bị phạt|thông báo|tuyên bố|ký kết|ra mắt|công bố|phán quyết|kết luận|khởi kiện|xử phạt)\b",
            assertion_part,
            re.I,
        )
    )

    is_claim = bool(nums or has_event_action or ents)

    return {
        "category": "event_claim" if is_claim else "opinion" if is_opinion else "cta_invitation" if is_invitation else "event_claim",
        "is_assertion": is_claim,
        "assertion_part": assertion_part,
        "cta_part": cta_part,
        "numbers": nums,
        "entities": ents,
    }


# -----------------------------------------------------------------------------
# 4. Fact Provenance Matching
# -----------------------------------------------------------------------------

class GroundingMatch(NamedTuple):
    matched: bool
    matched_fact_id: int | None
    canonical_value: str | None
    confidence: float
    match_type: str
    reason: str


def match_to_facts(item: Any, facts: list[Any], tolerance: float = 0.01) -> GroundingMatch:
    """
    Match a candidate value (number, entity, phrase) to a list of Fact objects / dicts.
    Returns GroundingMatch with matched_fact_id, canonical_value, confidence, match_type.
    """
    if not facts:
        return GroundingMatch(False, None, None, 0.0, "none", "Brief facts rỗng")

    # 1. Attempt Number Match
    cand_num = normalize_number(item)
    if cand_num is not None:
        best_match: GroundingMatch | None = None
        for idx, fact in enumerate(facts, 1):
            f_text = f"{getattr(fact, 'fact_vi', '') or getattr(fact, 'claim', '')} {getattr(fact, 'claim', '')} {getattr(fact, 'evidence_quote', '')}"
            fact_nums = extract_numbers(f_text, ignore_current_year=False)
            for fn in fact_nums:
                if numbers_match(cand_num, fn, tolerance=tolerance):
                    # Check exact vs compatible unit
                    if cand_num.effective_value == fn.effective_value and cand_num.unit == fn.unit:
                        return GroundingMatch(True, idx, fn.canonical_str(), 1.0, "exact_number", f"Khớp chính xác fact #{idx}")
                    match = GroundingMatch(True, idx, fn.canonical_str(), 0.95, "compatible_unit_number", f"Khớp giá trị/đơn vị tương thích fact #{idx}: '{cand_num.canonical_str()}' ↔ '{fn.canonical_str()}'")
                    if best_match is None or match.confidence > best_match.confidence:
                        best_match = match
        if best_match is not None:
            return best_match

    # 2. Attempt Entity Match
    cand_entity = normalize_entity(str(item))
    if cand_entity.core_tokens:
        for idx, fact in enumerate(facts, 1):
            f_text = f"{getattr(fact, 'fact_vi', '') or getattr(fact, 'claim', '')} {getattr(fact, 'claim', '')} {getattr(fact, 'source_name', '')}"
            fact_entities = extract_entities(f_text, sentence_boundary=False)
            for fe in fact_entities:
                if entity_matches(cand_entity, fe):
                    return GroundingMatch(True, idx, fe.raw, 0.95, "entity_core_match", f"Khớp thực thể cốt lõi fact #{idx}: '{cand_entity.raw}' ↔ '{fe.raw}'")

    # 3. Attempt Textkey Overlap
    from agents.validation_rules import textkey
    cand_key = textkey(str(item))
    if cand_key:
        for idx, fact in enumerate(facts, 1):
            f_key = textkey(f"{getattr(fact, 'fact_vi', '') or getattr(fact, 'claim', '')} {getattr(fact, 'claim', '')}")
            if cand_key in f_key:
                return GroundingMatch(True, idx, str(item), 0.9, "textkey_contained", f"Chứa trong fact #{idx}")

    return GroundingMatch(False, None, None, 0.0, "none", "Không tìm thấy căn cứ khớp trong facts")


# -----------------------------------------------------------------------------
# 5. Self-Repair Ladder (Visual & Sentence Grounding)
# -----------------------------------------------------------------------------

def repair_visual_grounding(scene: Any, shot: Any, brief: Any, settings: Any = None) -> tuple[bool, str | None]:
    """
    Apply self-repair ladder to shot.visual:
    (i) Match after normalization -> replace with canonical fact value (e.g. '51.8' -> '51.8%').
    (ii) Near match within tolerance -> use closest fact value, log note.
    (iii) No match -> convert element to qualitative / neutral version (strip number/name).
    (iv) Drop element; never halt unless no visual possible.
    """
    visual = getattr(shot, "visual", None)
    if visual is None or visual.template == "stock":
        return False, None

    data = getattr(visual, "data", None)
    if data is None:
        return False, None

    facts = getattr(brief, "facts", [])
    if not facts:
        return False, None

    mode = get_grounding_mode(settings)
    repaired = False
    notes: list[str] = []

    # 1. Repair numeric values in visual data
    if data.value is not None:
        # Check against facts
        v_num = normalize_number(f"{data.value:.8f}".rstrip("0").rstrip(".") + (data.unit or ""))
        match = match_to_facts(v_num, facts)
        if match.matched:
            # (i) Exact/compatible match: adopt canonical fact representation
            canon = match.canonical_value or ""
            parsed_canon = normalize_number(canon)
            if parsed_canon and parsed_canon.unit and data.unit != parsed_canon.unit:
                data.unit = parsed_canon.unit
                repaired = True
                notes.append(f"'{v_num.canonical_str()}' -> '{parsed_canon.canonical_str()}' (fact #{match.matched_fact_id})")
        else:
            # (iii) No match: convert to qualitative / neutral version
            if mode != "block":
                from agents.visual_policy import neutral_visual
                neutral = neutral_visual(scene, shot)
                shot.visual = neutral
                repaired = True
                notes.append(f"số liệu '{v_num.canonical_str()}' không có căn cứ -> chuyển sang đồ họa định tính trung tính")

    # 2. Repair comparison bars
    if getattr(data, "bars", None):
        valid_bars = []
        for b in data.bars:
            b_num = normalize_number(f"{b.value:.8f}".rstrip("0").rstrip(".") + (b.unit or ""))
            b_match = match_to_facts(b_num, facts)
            if b_match.matched:
                p_c = normalize_number(b_match.canonical_value)
                if p_c and p_c.unit and b.unit != p_c.unit:
                    b.unit = p_c.unit
                    repaired = True
                    notes.append(f"bar '{b.label}': '{b_num.canonical_str()}' -> '{p_c.canonical_str()}' (fact #{b_match.matched_fact_id})")
                valid_bars.append(b)
            else:
                if mode != "block":
                    repaired = True
                    notes.append(f"bỏ bar '{b.label}' không có căn cứ fact")
                else:
                    valid_bars.append(b)
        if len(valid_bars) != len(data.bars):
            data.bars = valid_bars
            if not data.bars and mode != "block":
                from agents.visual_policy import neutral_visual
                shot.visual = neutral_visual(scene, shot)

    # 3. Repair text/label names
    for field in ("text", "label", "title"):
        val = getattr(data, field, None)
        if not val:
            continue
        from agents.validation_rules import textkey, proper_names, ORDINARY
        for m in proper_names(val):
            name = m.group(0)
            clean_name = re.sub(r"^(?:Vụ(?: kiện)?|Công ty|Ngân hàng|Sản phẩm)\s+", "", name)
            if all(w in ORDINARY for w in clean_name.split()):
                continue
            e_match = match_to_facts(clean_name, facts)
            if not e_match.matched and mode != "block":
                # Convert to neutral term
                setattr(data, field, re.sub(re.escape(name), "đối tượng liên quan", val))
                repaired = True
                notes.append(f"tên '{name}' không có trong brief -> đổi sang cụm chung")

    if repaired and notes:
        summary = f"[grounding, tự sửa] Cảnh {scene.id}, shot {getattr(shot, 'id', 1)}: " + "; ".join(notes)
        return True, summary
    return False, None


def repair_cta_grounding(plan: Any, brief: Any, settings: Any = None) -> list[tuple[int, str]]:
    """Self-repair CTA sentences containing empirical event assertions."""
    from agents.explainer_guard import is_v2, sync_narration
    if not is_v2(plan):
        return []

    fixed: list[tuple[int, str]] = []
    review_notes = getattr(plan, "review_notes", None)
    if review_notes is None:
        review_notes = []
        setattr(plan, "review_notes", review_notes)

    facts = getattr(brief, "facts", [])

    for scene in plan.scenes:
        if not getattr(scene, "sentences", None):
            continue
        new_sentences = []
        scene_modified = False

        for index, sentence in enumerate(scene.sentences, 1):
            if sentence.type != "cta":
                new_sentences.append(sentence)
                continue

            claim_info = classify_claim(sentence.text, sentence_type="cta")
            if not claim_info["is_assertion"]:
                new_sentences.append(sentence)
                continue

            assert_part = claim_info["assertion_part"]
            cta_part = claim_info["cta_part"]

            # (i) Match fact in brief
            matched_fact_ids: list[int] = []
            for num in claim_info["numbers"]:
                m = match_to_facts(num, facts)
                if m.matched and m.matched_fact_id:
                    matched_fact_ids.append(m.matched_fact_id)
            for ent in claim_info["entities"]:
                m = match_to_facts(ent.raw, facts)
                if m.matched and m.matched_fact_id:
                    matched_fact_ids.append(m.matched_fact_id)

            matched_fact_ids = sorted(set(matched_fact_ids))

            if matched_fact_ids:
                # 1(a) Re-label to event with fact_ids
                ev_text = assert_part.rstrip(".!?, ").strip() + "."
                ev_sent = type(sentence)(text=ev_text, type="event", fact_ids=matched_fact_ids)
                new_sentences.append(ev_sent)
                scene_modified = True
                msg = f"[grounding, tự sửa] Cảnh {scene.id}: Câu {index} CTA chứa khẳng định sự kiện khớp fact #{matched_fact_ids}; tách/chuyển nhãn sang event."
                fixed.append((scene.id, msg))
                review_notes.append(msg)
                if cta_part:
                    new_sentences.append(type(sentence)(text=cta_part, type="cta", fact_ids=[]))
                elif scene.role == "cta" or scene == plan.scenes[-1]:
                    new_sentences.append(type(sentence)(text="Bạn nghĩ sao về điều này? Hãy để lại ý kiến dưới phần bình luận nhé.", type="cta", fact_ids=[]))
                continue

            # 1(b) Soft opinion or general explanation
            is_opinion = claim_info["category"] == "opinion" or re.search(r"\b(?:nghĩ|tin|quan điểm|đánh giá|theo mình)\b", assert_part, re.I)
            if is_opinion:
                new_type = "opinion"
                op_sent = type(sentence)(text=assert_part.rstrip(".!?, ").strip() + ".", type=new_type, fact_ids=[])
                new_sentences.append(op_sent)
                scene_modified = True
                msg = f"[grounding, tự sửa] Cảnh {scene.id}: Câu {index} CTA là nhận định chung; chuyển nhãn sang '{new_type}'."
                fixed.append((scene.id, msg))
                review_notes.append(msg)
                if cta_part:
                    new_sentences.append(type(sentence)(text=cta_part, type="cta", fact_ids=[]))
                continue

            # 1(c) Cut ungrounded assertion, retain pure CTA invitation/question
            cta_final = cta_part if cta_part else "Bạn nghĩ sao về chuyện này? Hãy để lại ý kiến dưới phần bình luận nhé."
            new_sentences.append(type(sentence)(text=cta_final, type="cta", fact_ids=[]))
            scene_modified = True
            msg = f"[grounding, tự sửa] Cảnh {scene.id}: Cắt bỏ khẳng định không có căn cứ trong CTA, bảo lưu câu hỏi tương tác."
            fixed.append((scene.id, msg))
            review_notes.append(msg)

        if scene_modified and new_sentences:
            scene.sentences = new_sentences

    if fixed:
        sync_narration(plan)
    return fixed


def repair_sentence_grounding(plan: Any, brief: Any, settings: Any = None) -> list[tuple[int, str]]:
    """Auto-repair event names and CTA claims across plan scenes."""
    from agents.explainer_guard import repair_event_names
    mode = get_grounding_mode(settings)
    if mode == "block":
        return []
    ev_fixed = repair_event_names(plan, brief)
    cta_fixed = repair_cta_grounding(plan, brief, settings=settings)
    return [*ev_fixed, *cta_fixed]


def repair_grounding(plan: Any, brief: Any, settings: Any = None) -> list[str]:
    """Execute complete self-repair ladder across all scenes and shots."""
    changes: list[str] = []
    review_notes = getattr(plan, "review_notes", None)
    if review_notes is None:
        review_notes = []
        setattr(plan, "review_notes", review_notes)

    # 1. Sentence level repairs
    sent_fixes = repair_sentence_grounding(plan, brief, settings=settings)
    for sid, msg in sent_fixes:
        changes.append(f"Cảnh {sid}: {msg}")

    # 2. Visual level repairs
    for scene in getattr(plan, "scenes", []):
        for shot in getattr(scene, "shots", []):
            rep, note = repair_visual_grounding(scene, shot, brief, settings=settings)
            if rep and note:
                changes.append(note)
                review_notes.append(note)

    return changes
