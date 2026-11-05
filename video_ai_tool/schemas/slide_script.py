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


DANGLING_END_WORDS = {
    "đòi", "kỹ", "của", "và", "là", "để", "với", "cho", "trong", "khi", "tại", "từ",
    "ở", "về", "có", "các", "những", "làm", "được", "bị", "do", "bởi", "ra",
    "vào", "lên", "xuống", "đầu", "như", "theo", "giúp", "rằng", "thì", "mà", "bằng",
    "hay", "hoặc", "tới", "đến", "qua", "sau", "trước", "cùng", "nhất", "rất", "quá",
    "tầm", "mức", "chủ", "hỏi", "nhận", "đặt", "tạo", "mang", "coi", "tính", "biết",
    "thấy", "khiến", "nhằm", "gồm", "thuộc", "cần", "phía", "vận", "độ", "bậc", "đằng",
}


def clean_trailing_dangling(text: str) -> str:
    """Trim any trailing dangling words or incomplete particles from text."""
    if not text:
        return ""
    words = text.strip().split()
    while words and words[-1].lower().strip(".,;:?!\"'") in DANGLING_END_WORDS:
        words.pop()
    return " ".join(words).strip()


def wrap_text_greedy(text: str, max_chars_per_line: int = 14, max_lines: int = 3) -> list[str]:
    """Wrap text at word boundaries without breaking words.
    
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
    for w in words:
        candidate = f"{current_line} {w}".strip() if current_line else w
        if len(candidate) <= max_chars_per_line:
            current_line = candidate
            words_consumed += 1
        else:
            if current_line:
                lines.append(current_line)
            current_line = w
            if len(lines) >= max_lines:
                break
            words_consumed += 1
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

    # If text was truncated (not all words consumed), ensure the ending is not a dangling word
    if words_consumed < len(words) and lines:
        while lines:
            line_words = lines[-1].split()
            if line_words and line_words[-1].lower().strip(".,;:—?!") in DANGLING_END_WORDS:
                line_words.pop()
                if line_words:
                    lines[-1] = " ".join(line_words)
                    break
                else:
                    lines.pop()
            else:
                break

    return lines[:max_lines]


def extract_clean_headline(sentence: str, max_chars: int = 56) -> str:
    """Extract a complete, grammatically sound headline phrase from a sentence without cutting words."""
    if not sentence:
        return ""
    clean = re.sub(r"\s+", " ", sentence.strip())

    # Special handling for questions: "Làm sao để ... giúp Việt Nam tự chủ hạ tầng hoàn toàn?"
    if re.search(r"làm sao để|làm thế nào để", clean, re.I):
        m_goal = re.search(r"giúp\s+([^?]+)", clean, re.I)
        if m_goal:
            goal_text = clean_trailing_dangling(m_goal.group(1).strip())
            if 10 <= len(goal_text) <= max_chars:
                return goal_text[0].upper() + goal_text[1:]
        m_q = re.search(r"(tự chủ [^?]+)", clean, re.I)
        if m_q:
            q_text = clean_trailing_dangling(m_q.group(1).strip())
            if 8 <= len(q_text) <= max_chars:
                return q_text[0].upper() + q_text[1:]

    # 1. Check natural punctuation clause boundary (comma, semicolon, dash, colon)
    parts = re.split(r"[,;:\-—]", clean)
    if parts:
        first_part = parts[0].strip()
        words = first_part.split()
        if 3 <= len(words) <= 8 and len(first_part) <= max_chars:
            cleaned = clean_trailing_dangling(first_part)
            if len(cleaned.split()) >= 3:
                return cleaned

    # 2. Split on common predicate/verb connectors to extract full subject noun phrase
    verb_parts = re.split(r"\s+(?:đòi hỏi|yêu cầu|cho thấy|đóng vai trò|giúp|khiến|nhằm|mang lại)\s+", clean, flags=re.I)
    if verb_parts:
        subj = clean_trailing_dangling(verb_parts[0].strip())
        w_subj = subj.split()
        if 3 <= len(w_subj) <= 8 and len(subj) <= max_chars:
            return subj

    # 3. Split on common subordinate connectors (cho thấy, nhằm, để, giúp, khiến)
    sub_parts = re.split(r"\s+(?:cho thấy|nhằm|để|giúp|khiến)\s+", clean, flags=re.I)
    if sub_parts and len(sub_parts[0].split()) >= 3 and len(sub_parts[0].strip()) <= max_chars:
        cand = clean_trailing_dangling(sub_parts[0].strip())
        if len(cand.split()) >= 3:
            return cand

    # 4. Otherwise wrap greedily and join lines respecting max_chars
    max_lines = 1 if max_chars <= 30 else 2
    chars_per_line = min(max_chars, 24)
    lines = wrap_text_greedy(clean, max_chars_per_line=chars_per_line, max_lines=max_lines)
    joined = clean_trailing_dangling(" ".join(lines).strip())
    if len(joined) > max_chars:
        joined = clean_trailing_dangling(joined[:max_chars])
    return joined


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

        # Pill limit <= 28 chars, trimmed of trailing dangling words
        for pill_key in ("pill", "badge", "chip", "kicker", "sub_pill"):
            if pill_key in cleaned and cleaned[pill_key]:
                val = str(cleaned[pill_key]).strip()
                if len(val) > 28:
                    wrapped = wrap_text_greedy(val, max_chars_per_line=28, max_lines=1)
                    cleaned[pill_key] = clean_trailing_dangling(wrapped[0] if wrapped else val[:28])
                else:
                    cleaned[pill_key] = clean_trailing_dangling(val)

        # Headline / title: max 2 lines x 24 chars/line, trimmed of dangling words
        for title_key in ("title", "headline"):
            if title_key in cleaned and cleaned[title_key]:
                val = str(cleaned[title_key]).strip()
                lines = wrap_text_greedy(val, max_chars_per_line=24, max_lines=2)
                cleaned[title_key] = clean_trailing_dangling(" ".join(lines) if lines else val[:48])

        # Features items: max 4 items, each <= 40 chars, no dangling words
        if "items" in cleaned and isinstance(cleaned["items"], list):
            items_list = []
            for item in cleaned["items"][:4]:
                item_str = str(item).strip()
                if len(item_str) > 40:
                    wrapped = wrap_text_greedy(item_str, max_chars_per_line=40, max_lines=1)
                    item_str = wrapped[0] if wrapped else item_str[:40]
                item_str = clean_trailing_dangling(item_str)
                if item_str:
                    items_list.append(item_str)
            cleaned["items"] = items_list

        # Compare: left & right labels / text <= 2 lines of 18 chars each (<= 36 chars)
        for side in ("left", "right"):
            if side in cleaned and isinstance(cleaned[side], dict):
                side_dict = dict(cleaned[side])
                for k in ("title", "text", "label"):
                    if k in side_dict and side_dict[k]:
                        s_val = str(side_dict[k]).strip()
                        if len(s_val) > 36:
                            w = wrap_text_greedy(s_val, max_chars_per_line=18, max_lines=2)
                            side_dict[k] = clean_trailing_dangling(" ".join(w) if w else s_val[:36])
                        else:
                            side_dict[k] = clean_trailing_dangling(s_val)
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
