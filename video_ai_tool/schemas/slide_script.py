"""Pydantic schema for Slide Script (Motion Kit v2 presentation flow)."""
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


def wrap_text_greedy(text: str, max_chars_per_line: int = 14, max_lines: int = 3) -> list[str]:
    """Wrap text at word boundaries without breaking words.
    
    Ensures no orphaned words on lines when possible.
    """
    if not text:
        return []
    words = str(text).strip().split()
    if not words:
        return []
    
    lines: list[str] = []
    current_line = ""
    for w in words:
        candidate = f"{current_line} {w}".strip() if current_line else w
        if len(candidate) <= max_chars_per_line:
            current_line = candidate
        else:
            if current_line:
                lines.append(current_line)
            current_line = w
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

    return lines[:max_lines]


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

        # Pill limit <= 28 chars
        for pill_key in ("pill", "badge", "chip", "kicker", "sub_pill"):
            if pill_key in cleaned and cleaned[pill_key]:
                val = str(cleaned[pill_key]).strip()
                if len(val) > 28:
                    wrapped = wrap_text_greedy(val, max_chars_per_line=28, max_lines=1)
                    cleaned[pill_key] = wrapped[0] if wrapped else val[:28]

        # Headline / title: max 3 lines x 14 chars/line
        for title_key in ("title", "headline"):
            if title_key in cleaned and cleaned[title_key]:
                val = str(cleaned[title_key]).strip()
                lines = wrap_text_greedy(val, max_chars_per_line=14, max_lines=3)
                cleaned[title_key] = " ".join(lines) if lines else val[:42]

        # Features items: max 4 items, each <= 40 chars
        if "items" in cleaned and isinstance(cleaned["items"], list):
            items_list = []
            for item in cleaned["items"][:4]:
                item_str = str(item).strip()
                if len(item_str) > 40:
                    wrapped = wrap_text_greedy(item_str, max_chars_per_line=40, max_lines=1)
                    item_str = wrapped[0] if wrapped else item_str[:40]
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
                            side_dict[k] = " ".join(w) if w else s_val[:28]
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
