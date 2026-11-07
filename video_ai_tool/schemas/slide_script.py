"""Pydantic schema for Slide Script (Motion Kit v2 presentation flow)."""
import re
from typing import Annotated, Any, Literal
from pydantic import Field, field_validator, model_validator
from schemas.base import StrictModel, NonEmptyText


ALLOWED_LAYOUTS = (
    "kit_title",
    "kit_stat",
    "kit_chart_bar",
    "kit_chart_line",
    "kit_chart_donut",
    "kit_photo",
    "kit_list",
    "kit_compare",
    "kit_quote",
    "kit_timeline",
    "kit_outro",
    # Legacy aliases mapped to kit equivalents
    "lg_source_headline",
    "lg_stat_hero",
    "lg_shot_features",
    "lg_vs_compare",
    "lg_note_card",
    "lg_cta_profile",
)

LayoutType = Literal[
    "kit_title",
    "kit_stat",
    "kit_chart_bar",
    "kit_chart_line",
    "kit_chart_donut",
    "kit_photo",
    "kit_list",
    "kit_compare",
    "kit_quote",
    "kit_timeline",
    "kit_outro",
    "lg_source_headline",
    "lg_stat_hero",
    "lg_shot_features",
    "lg_vs_compare",
    "lg_note_card",
    "lg_cta_profile",
]

ImageKindType = Literal["screenshot", "og", "card", "photo"]
EmphasisKindType = Literal["term", "number", "name"]

LEGACY_TO_KIT_LAYOUT = {
    "lg_source_headline": "kit_title",
    "lg_stat_hero": "kit_stat",
    "lg_shot_features": "kit_list",
    "lg_vs_compare": "kit_compare",
    "lg_note_card": "kit_title",
    "lg_cta_profile": "kit_outro",
}

def normalize_kit_layout(layout: str) -> str:
    return LEGACY_TO_KIT_LAYOUT.get(layout, layout)


class ChartSeriesItem(StrictModel):
    label: NonEmptyText
    value: float
    unit: str | None = None


class ChartSlot(StrictModel):
    type: Literal["bar", "line", "donut"] = "bar"
    series: list[ChartSeriesItem] = Field(default_factory=list, max_length=6)
    unit: str | None = None
    title: str | None = None


class PhotoSlot(StrictModel):
    path: str | None = None
    name: str | None = None
    role: str | None = None
    credit: str | None = None


class SourceRef(StrictModel):
    url: str | None = None
    domain: str | None = None
    image_kind: ImageKindType = "card"
    image_path: str | None = None
    title: str | None = None


class EmphasisItem(StrictModel):
    phrase: NonEmptyText
    kind: EmphasisKindType = "term"
    start_sec: float | None = None
    end_sec: float | None = None


VIETNAMESE_COMPOUND_WORDS = {
    "cốt lõi", "mục tiêu", "tự hành", "tự chủ", "nhân lực", "nhân tạo", "đồng bộ",
    "hạ tầng", "tính toán", "công cụ", "sai sót", "chất lượng", "địa chất", "thi công",
    "tiêu chuẩn", "kinh nghiệm", "năng suất", "giải pháp", "phát triển", "nghiên cứu",
    "chiến lược", "hệ thống", "quốc gia", "hành động", "phân chia", "kết quả", "định hướng",
    "hỗ trợ", "tối ưu", "công việc", "trợ lý", "ngày hội", "trí tuệ", "thu hút", "quan tâm",
    "bối cảnh", "văn hóa", "dài hạn", "đầu tư", "kỹ thuật", "sụt lún", "công trình", "nền đất",
    "khảo sát", "xử lý", "địa kỹ", "kỹ sư", "vận hành", "độc quyền", "thiết kế", "quan sát",
    "liên tục", "chướng ngại", "ngôn ngữ", "nhận biết", "điều chỉnh", "biện pháp", "thực tế",
    "đáp ứng", "yêu cầu", "đòi hỏi", "khác biệt", "thích ứng", "kế hoạch", "hiện đại",
    "đơn giản", "phần mềm", "phần cứng", "dữ liệu", "mô hình", "thuật toán", "năng lực",
    "tiến bộ", "nâng cao", "toàn diện", "chuyên môn", "đội ngũ", "nhà thầu", "chủ đầu",
    "vấn đề", "thách thức", "cơ hội", "tiềm năng", "đột phá", "bước đi", "tầm nhìn", "vai trò",
    "phương án", "phương pháp", "thực hiện", "triển khai", "đảm bảo", "bảo đảm", "an toàn",
    "chính xác", "hiệu quả", "linh hoạt", "độc lập", "tự lập", "tự động", "chủ động", "nhiệm vụ",
    "quy trình", "nguyên tắc", "nguyên nhân", "bài học", "bước ngoặt", "thời điểm", "tương lai",
    "hiện tại", "quá khứ", "tổng thể", "cơ sở", "nền tảng", "công nghệ", "thiết bị", "vật liệu",
    "môi trường", "đô thị", "ngầm hóa", "đường hầm", "hầm ngầm", "tuyến metro", "đường sắt",
    "cao tốc", "tốc độ", "tường vây", "cọc khoan", "áp lực", "cân bằng", "địa tầng", "đất yếu",
    "sỏi cuội", "cát chảy", "bùn lỏng", "nước ngầm", "xuyên suốt", "chuỗi việc", "ranh giới",
    "nội địa", "nguồn lực", "máy móc", "chủ thể", "quyết định", "con người", "nhúng tay",
    "nhân lên", "bước đầu", "khâu đầu", "cuối cùng", "nghiên cứu", "phức tạp",
    "hoàn toàn", "hoàn chỉnh", "hoàn thành", "hoàn mỹ", "mở rộng", "dẫn đầu", "từng bước",
    "dựa trên", "nguồn dữ", "dữ liệu", "khác biệt", "dường như"
}

COMPOUND_WORD_FIRST_SYLLABLES = {
    p.split()[0] for p in VIETNAMESE_COMPOUND_WORDS
} | {
    "cốt", "mục", "tự", "nhân", "đồng", "hạ", "tính", "công", "sai", "chất",
    "địa", "thi", "tiêu", "kinh", "năng", "giải", "phát", "nghiên", "chiến",
    "hệ", "quốc", "hành", "phân", "kết", "định", "hỗ", "tối", "trợ", "trí",
    "thu", "quan", "bối", "văn", "dài", "đầu", "kỹ", "sụt", "khảo", "xử",
    "vận", "độc", "thiết", "chướng", "ngôn", "nhận", "điều", "biện", "thực",
    "đáp", "tiến", "chuyên", "thách", "tiềm", "đột", "bước", "tầm", "vai",
    "phương", "triển", "đảm", "bảo", "an", "chính", "hiệu", "linh", "nhiệm",
    "quy", "nguyên", "tổng", "cơ", "nền", "tuyến", "cao", "tốc", "tường", "cọc",
    "áp", "cân", "sỏi", "cát", "bùn", "nước", "xuyên", "chuỗi", "ranh", "nội",
    "máy", "quyết", "con", "nhúng", "phức", "hoàn", "mở", "dẫn", "dường"
}

COMPOUND_WORD_SECOND_SYLLABLES = {
    p.split()[1] for p in VIETNAMESE_COMPOUND_WORDS
} | {
    "lõi", "tiêu", "hành", "chủ", "lực", "tạo", "bộ", "tầng", "toán", "cụ",
    "sót", "lượng", "chất", "chuẩn", "nghiệm", "suất", "pháp", "triển", "cứu",
    "lược", "thống", "gia", "động", "chia", "quả", "hướng", "trợ", "ưu", "việc",
    "lý", "hội", "tuệ", "hút", "tâm", "cảnh", "hóa", "hạn", "tư", "thuật", "lún",
    "trình", "đất", "sát", "quyền", "kế", "tục", "ngại", "ngữ", "biết", "chỉnh",
    "tế", "ứng", "cầu", "hỏi", "biệt", "hoạch", "đại", "giản", "mềm", "cứng",
    "liệu", "hình", "toán", "bộ", "cao", "môn", "ngũ", "thầu", "đề", "thức",
    "năng", "phá", "đi", "nhìn", "trò", "án", "hiện", "khai", "toàn", "xác",
    "hoạt", "lập", "vụ", "tắc", "nhân", "học", "ngoặt", "điểm", "lai", "tại",
    "khứ", "thể", "sở", "tảng", "nghệ", "bị", "trường", "thị", "hầm", "ngầm",
    "sắt", "độ", "vây", "khoan", "bằng", "yếu", "cuội", "chảy", "lỏng", "suốt",
    "việc", "giới", "địa", "lực", "móc", "thể", "định", "người", "tay", "lên", "cùng", "tạp", "chỉnh", "như"
}


def is_compound_pair(w1: str, w2: str) -> bool:
    """Check whether two consecutive words form a Vietnamese compound word that cannot be split."""
    c1 = re.sub(r"[^\w]", "", w1.lower()).strip()
    c2 = re.sub(r"[^\w]", "", w2.lower()).strip()
    if not c1 or not c2:
        return False
    if f"{c1} {c2}" in VIETNAMESE_COMPOUND_WORDS:
        return True
    return c1 in COMPOUND_WORD_FIRST_SYLLABLES and c2 in COMPOUND_WORD_SECOND_SYLLABLES


DANGLING_END_WORDS = {
    "đòi", "kỹ", "của", "và", "là", "để", "với", "cho", "trong", "khi", "tại", "từ",
    "ở", "về", "có", "các", "những", "làm", "được", "bị", "do", "bởi", "ra",
    "vào", "lên", "xuống", "đầu", "như", "theo", "giúp", "rằng", "thì", "mà", "bằng",
    "hay", "hoặc", "tới", "đến", "qua", "sau", "trước", "cùng", "nhất", "rất", "quá",
    "tầm", "mức", "chủ", "hỏi", "nhận", "đặt", "tạo", "mang", "coi", "tính", "biết",
    "thấy", "khiến", "nhằm", "gồm", "thuộc", "cần", "phía", "vận", "độ", "bậc", "đằng",
    "nhưng", "song", "tuy", "dù", "nếu", "vì",
    "thể", "nhiều", "ít", "đang", "sẽ", "đã", "tự", "bộ", "điều", "này", "kia", "đó", "nguồn", "lõi", "tiêu", "dường",
    "phẫu", "triển", "khéo", "léo", "vỡ", "số", "con"
}


def clean_trailing_dangling(text: str) -> str:
    """Trim any trailing dangling words, orphan numbers, or incomplete particles from text."""
    if not text:
        return ""
    stripped = text.strip()
    words = stripped.split()
    while words:
        if len(words) >= 2 and is_compound_pair(words[-2], words[-1]):
            break
        clean_last = re.sub(r"[^\w]", "", words[-1].lower()).strip()
        # Orphan number at the end of phrase (e.g. "tiêu tốn 83", "triển khai 5")
        if re.match(r"^\d+$", clean_last):
            words.pop()
            continue
        if clean_last in DANGLING_END_WORDS or clean_last in COMPOUND_WORD_FIRST_SYLLABLES:
            if words[-1][-1] in (".", "?", "!") and clean_last not in {"và", "là", "để", "với", "cho", "của", "trong", "khi", "tại", "nhưng", "vì", "phẫu", "triển", "khéo", "léo"}:
                break
            words.pop()
        else:
            break
    return " ".join(words).strip()


def wrap_text_greedy(text: str, max_chars_per_line: int = 14, max_lines: int = 3) -> list[str]:
    """Wrap text at word boundaries without breaking words or cutting compound pairs.
    
    Ensures no orphaned words on lines when possible, and trims trailing
    dangling words/prepositions/particles when text is truncated.
    """
    if not text:
        return []
    words = str(text).strip().split()
    if not words:
        return []
    
    lines: list[str] = []
    current_line = ""
    words_consumed = 0
    i = 0
    while i < len(words):
        w = words[i]
        # Check if next word forms a compound pair with current word
        if i + 1 < len(words) and is_compound_pair(w, words[i + 1]):
            pair = f"{w} {words[i + 1]}"
            candidate = f"{current_line} {pair}".strip() if current_line else pair
            if len(candidate) <= max_chars_per_line or not current_line:
                current_line = candidate
                words_consumed += 2
                i += 2
            else:
                lines.append(current_line)
                current_line = pair
                words_consumed += 2
                i += 2
                if len(lines) >= max_lines:
                    break
        else:
            candidate = f"{current_line} {w}".strip() if current_line else w
            if len(candidate) <= max_chars_per_line:
                current_line = candidate
                words_consumed += 1
                i += 1
            else:
                if current_line:
                    lines.append(current_line)
                current_line = w
                words_consumed += 1
                i += 1
                if len(lines) >= max_lines:
                    break

    if current_line and len(lines) < max_lines:
        lines.append(current_line)

    # Balance lines to prevent orphan single word at the end if lines > 1
    if len(lines) >= 2 and len(lines[-1].split()) == 1:
        prev_words = lines[-2].split()
        if len(prev_words) >= 2:
            moved = prev_words.pop()
            new_prev = " ".join(prev_words)
            new_last = f"{moved} {lines[-1]}"
            if len(new_last) <= max_chars_per_line:
                lines[-2] = new_prev
                lines[-1] = new_last

    # If text was truncated (not all words consumed), ensure the ending is not a dangling word or compound first syllable
    if words_consumed < len(words) and lines:
        while lines:
            line_words = lines[-1].split()
            if len(line_words) >= 2 and is_compound_pair(line_words[-2], line_words[-1]):
                break
            if line_words:
                last_w = re.sub(r"[^\w]", "", line_words[-1].lower()).strip()
                if last_w in DANGLING_END_WORDS or last_w in COMPOUND_WORD_FIRST_SYLLABLES:
                    line_words.pop()
                    if line_words:
                        lines[-1] = " ".join(line_words)
                        break
                    else:
                        lines.pop()
                else:
                    break
            else:
                break

    return lines[:max_lines]


INCOMPLETE_HEADLINE_PATTERNS = [
    r"^làm\s+(?:thế\s+nào|sao)(?:\s+để)?$",
    r"^cách\s+(?:các\s+)?kỹ\s+sư(?:\s+việt)?$",
    r"^cách\s+[a-zđáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ\s]{2,18}$",
    r"^(?:đây|đó)\s+là(?:\s+bước\s+đi(?:\s+thiết\s+thực)?)?$",
    r"^quá\s+trình\s+này$",
    r"^phương\s+án(?:\s+\d+|\s+1/2)?$",
    r"^ý\s+chính(?:\s+cần\s+nhớ)?$",
    r"^điều\s+này(?:\s+dường(?:\s+như)?)?$",
    r"^sự\s+khéo\s+léo$",
    r"^triển\s+khai(?:\s+\d+)?$",
    r"^bác\s+sĩ\s+phẫu$",
    r"^con\s+số\s+này$",
    r"^việc\s+này$",
    r".*tiêu\s+tốn\s+\d+$",
]


def is_incomplete_phrase(phrase: str) -> bool:
    """Check if a phrase is grammatically incomplete or a prohibited cut-off template fragment."""
    p_clean = re.sub(r"[^\w\s]", "", phrase.lower()).strip()
    for pat in INCOMPLETE_HEADLINE_PATTERNS:
        if re.match(pat, p_clean):
            return True
    return False


def extract_clean_headline(sentence: str, max_chars: int = 96) -> str:
    """Extract a complete, grammatically sound headline phrase from a sentence without cutting words.
    
    If text cannot be cleanly shortened to a complete grammatical clause, returns the full sentence.
    """
    if not sentence:
        return ""
    clean = re.sub(r"\s+", " ", sentence.strip())

    # 0. If multiple sentences exist, extract headline from the first complete sentence
    sents = [s.strip() for s in re.split(r"(?<=[.?!])\s+", clean) if s.strip()]
    if len(sents) > 1:
        first_s = sents[0]
        first_h = extract_clean_headline(first_s, max_chars=max_chars)
        if first_h and len(first_h.split()) >= 3 and not is_incomplete_phrase(first_h):
            return first_h
        return clean_trailing_dangling(first_s)

    # Strip dangling demonstrative clause prefixes so titles are substantive independent statements
    m_dem = re.match(
        r"^(?:con\s+số\s+này|điều\s+này|việc\s+này|điều\s+đó|này|đó)\s+(?:dường\s+như|có\s+thể|sẽ)?\s*(?:cho\s+thấy|chứng\s+minh|khẳng\s+định|là|khiến|giúp|làm\s+cho|đưa\s+đến|dẫn\s+đến)?\s*(.+)",
        clean,
        re.I,
    )
    if m_dem and len(m_dem.group(1).strip().split()) >= 3:
        clean = m_dem.group(1).strip()
        clean = clean[0].upper() + clean[1:]

    # Special handling for questions: "Làm sao để ... giúp Việt Nam tự chủ hạ tầng hoàn toàn?"
    if re.search(r"làm sao để|làm thế nào để", clean, re.I):
        m_goal = re.search(r"giúp\s+([^?]+)", clean, re.I)
        if m_goal:
            goal_text = clean_trailing_dangling(m_goal.group(1).strip())
            if 10 <= len(goal_text) <= max_chars and not is_incomplete_phrase(goal_text):
                return goal_text[0].upper() + goal_text[1:]
        m_q = re.search(r"(tự chủ [^?]+)", clean, re.I)
        if m_q:
            q_text = clean_trailing_dangling(m_q.group(1).strip())
            if 8 <= len(q_text) <= max_chars and not is_incomplete_phrase(q_text):
                return q_text[0].upper() + q_text[1:]

    # Special handling for "Cách ... làm chủ ...": ensure we keep the complete predicate
    m_cach = re.search(r"(cách\s+[^,;:\-—.]+?\s+làm\s+chủ\s+[^,;:\-—.]+)", clean, re.I)
    if m_cach:
        cach_cand = clean_trailing_dangling(m_cach.group(1).strip())
        if len(cach_cand) <= max_chars:
            return cach_cand[0].upper() + cach_cand[1:]

    # Helper to validate a candidate headline
    def is_valid_headline(cand: str) -> bool:
        if not cand or len(cand) > max_chars:
            return False
        w = cand.split()
        if len(w) < 3:
            return False
        if is_incomplete_phrase(cand):
            return False
        # Cannot begin with a subordinate conjunction, preposition, or dangling demonstrative
        if re.match(r"^(?:này|đó|điều này|con số này|việc này|điều đó|khi|nếu|dù|mặc dù|trong khi|bởi vì|với|tại|theo|do|bởi)\b", cand, re.I):
            return False
        first_clean = re.sub(r"[^\w]", "", w[0].lower()).strip()
        last_clean = re.sub(r"[^\w]", "", w[-1].lower()).strip()
        # Cannot end with a bare number (orphan number)
        if re.match(r"^\d+$", last_clean):
            return False
        if len(w) >= 2 and is_compound_pair(w[0], w[1]):
            pass
        elif first_clean in COMPOUND_WORD_SECOND_SYLLABLES or cand[0].islower():
            return False
        if cand[-1] in (".", "?", "!") and last_clean not in {"và", "là", "để", "với", "cho", "của", "trong", "khi", "tại", "nhưng", "vì", "cốt", "mục", "đồng", "tự", "hạ", "phẫu", "triển", "khéo", "léo"}:
            pass
        elif len(w) >= 2 and is_compound_pair(w[-2], w[-1]):
            pass
        elif last_clean in DANGLING_END_WORDS or last_clean in COMPOUND_WORD_FIRST_SYLLABLES:
            return False
        return True

    # 1. Check natural punctuation clause boundary (do not split on comma between digits like 83,2)
    parts = re.split(r"(?<!\d)[,;:\-—](?!\d)", clean)
    if parts:
        first_part = clean_trailing_dangling(parts[0].strip())
        if first_part:
            first_part = first_part[0].upper() + first_part[1:]
        if is_valid_headline(first_part):
            return first_part
        elif len(parts) > 1:
            second_part = clean_trailing_dangling(parts[1].strip())
            if second_part:
                second_part = second_part[0].upper() + second_part[1:]
            if is_valid_headline(second_part):
                return second_part

    # 2. Split on common predicate/verb connectors to extract full subject noun phrase
    verb_parts = re.split(r"\s+(?:đòi hỏi|yêu cầu|cho thấy|đóng vai trò|giúp|khiến|nhằm|mang lại)\s+", clean, flags=re.I)
    if verb_parts:
        subj = clean_trailing_dangling(verb_parts[0].strip())
        if subj:
            subj = subj[0].upper() + subj[1:]
        if is_valid_headline(subj):
            return subj

    # 3. Split on common subordinate connectors (nhưng, và, để, vì, khi, nếu, trong khi, cho thấy, nhằm, giúp)
    sub_parts = re.split(r"\s+(?:nhưng|cho thấy|nhằm|để|giúp|khiến|trong khi)\s+", clean, flags=re.I)
    if sub_parts:
        cand = clean_trailing_dangling(sub_parts[0].strip())
        if cand:
            cand = cand[0].upper() + cand[1:]
        if is_valid_headline(cand):
            return cand

    # If shortening breaks clause completeness or yields a cut-off phrase, USE THE FULL SENTENCE!
    full_clean = clean_trailing_dangling(clean)
    if full_clean:
        return full_clean[0].upper() + full_clean[1:]
    return clean


class SlideItem(StrictModel):
    id: str = "slide_1"
    layout: LayoutType = "kit_title"
    sentence_ids: list[int] = Field(default_factory=lambda: [1])
    slots: dict[str, Any] = Field(default_factory=dict)
    chart: ChartSlot | None = None
    photo: PhotoSlot | None = None
    source_ref: SourceRef | None = None
    emphasis: list[EmphasisItem] = Field(default_factory=list, max_length=5)
    t_start: float = 0.0
    t_end: float = 0.0
    duration: float = 0.0
    narration: str = ""
    image_prompt: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_layout(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Compatibility with scene_idx, start_ms, end_ms
            if "scene_idx" in data:
                val = data.pop("scene_idx")
                if "id" not in data:
                    data["id"] = f"slide_{val}"
            if "start_ms" in data:
                val = data.pop("start_ms")
                if "t_start" not in data:
                    data["t_start"] = float(val) / 1000.0
            if "end_ms" in data:
                val = data.pop("end_ms")
                if "t_end" not in data:
                    data["t_end"] = float(val) / 1000.0
                    if "duration" not in data:
                        data["duration"] = data["t_end"] - data.get("t_start", 0.0)
            # Slot shortcuts: title, subtitle, stat_value, stat_label, bullets, etc.
            slots = data.setdefault("slots", {})
            for k in ("title", "subtitle", "stat_value", "stat_label", "value", "unit", "label", "bullets"):
                if k in data:
                    val = data.pop(k)
                    if k not in slots:
                        slots[k] = val

            layout = data.get("layout")
            if layout and layout in LEGACY_TO_KIT_LAYOUT:
                data["layout"] = LEGACY_TO_KIT_LAYOUT[layout]
        return data

    @field_validator("slots")
    @classmethod
    def validate_slot_limits(cls, slots: dict[str, Any]) -> dict[str, Any]:
        """Validate and clamp slot limits according to layout rules."""
        cleaned = dict(slots)

        # Pill limit <= 28 chars, trimmed of trailing dangling words and incomplete phrases
        for pill_key in ("pill", "badge", "chip", "kicker", "sub_pill"):
            if pill_key in cleaned and cleaned[pill_key]:
                val = str(cleaned[pill_key]).strip()
                if len(val) > 28:
                    wrapped = wrap_text_greedy(val, max_chars_per_line=28, max_lines=1)
                    val = clean_trailing_dangling(wrapped[0] if wrapped else val[:28])
                else:
                    val = clean_trailing_dangling(val)
                if is_incomplete_phrase(val):
                    val = "TIÊU ĐIỂM"
                cleaned[pill_key] = val

        # Headline / title: max 3 lines x 32 chars/line (<= 96 chars), trimmed of dangling words and compound cuts
        for title_key in ("title", "headline"):
            if title_key in cleaned and cleaned[title_key]:
                val = str(cleaned[title_key]).strip()
                sents = [s.strip() for s in re.split(r"(?<=[.?!])\s+", val) if s.strip()]
                if len(sents) > 1 and len(val) > 96:
                    first_s = sents[0]
                    if len(first_s) <= 96:
                        val = first_s
                    else:
                        val = extract_clean_headline(first_s, max_chars=96)
                if len(val) > 96:
                    val_h = extract_clean_headline(val, max_chars=96)
                    if val_h and len(val_h) <= 96:
                        val = val_h
                    else:
                        lines = wrap_text_greedy(val, max_chars_per_line=32, max_lines=3)
                        val = clean_trailing_dangling(" ".join(lines) if lines else val[:96])
                else:
                    val = clean_trailing_dangling(val)
                if val:
                    val = val[0].upper() + val[1:]
                cleaned[title_key] = val

        # Subtitle: trimmed of dangling words and ensures starts uppercase
        for sub_key in ("subtitle", "sub"):
            if sub_key in cleaned and cleaned[sub_key]:
                s_val = str(cleaned[sub_key]).strip()
                s_val = clean_trailing_dangling(s_val)
                if s_val:
                    s_val = s_val[0].upper() + s_val[1:]
                cleaned[sub_key] = s_val

        # Features items: max 4 items, each <= 90 chars, full clause without premature cutting
        if "items" in cleaned and isinstance(cleaned["items"], list):
            items_list = []
            for item in cleaned["items"][:4]:
                item_str = str(item).strip()
                if len(item_str) > 90:
                    cand = extract_clean_headline(item_str, max_chars=90)
                    if cand and len(cand) <= 90 and not is_incomplete_phrase(cand):
                        item_str = cand
                    else:
                        wrapped = wrap_text_greedy(item_str, max_chars_per_line=45, max_lines=2)
                        item_str = clean_trailing_dangling(" ".join(wrapped) if wrapped else item_str[:90])
                else:
                    item_str = clean_trailing_dangling(item_str)
                if item_str:
                    item_str = item_str[0].upper() + item_str[1:]
                items_list.append(item_str)
            cleaned["items"] = items_list

        # Compare: left & right labels / text <= 2 lines of 14 chars each (<= 28 chars)
        for side in ("left", "right"):
            if side in cleaned and isinstance(cleaned[side], dict):
                side_dict = dict(cleaned[side])
                for k in ("title", "text", "label"):
                    if k in side_dict and side_dict[k]:
                        s_val = str(side_dict[k]).strip()
                        if len(s_val) > 28:
                            w = wrap_text_greedy(s_val, max_chars_per_line=14, max_lines=2)
                            s_val = clean_trailing_dangling(" ".join(w) if w else s_val[:28])
                        else:
                            s_val = clean_trailing_dangling(s_val)
                        if s_val:
                            s_val = s_val[0].upper() + s_val[1:]
                        side_dict[k] = s_val
                cleaned[side] = side_dict

        return cleaned


class SlideScript(StrictModel):
    topic: str = ""
    total_duration: float = 0.0
    slides: list[SlideItem] = Field(default_factory=list)
    repair_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_scenes_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "scenes" in data and "slides" not in data:
                data["slides"] = data.pop("scenes")
        return data

    @property
    def scenes(self) -> list[SlideItem]:
        return self.slides


SlideScene = SlideItem
