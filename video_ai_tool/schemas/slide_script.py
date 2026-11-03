"""Pydantic schema for Slide Script (Light Glass style presentation flow)."""
from typing import Annotated, Any, Literal
from pydantic import Field, field_validator
from schemas.base import StrictModel, NonEmptyText


ALLOWED_LAYOUTS = (
    "lg_source_headline",
    "lg_stat_hero",
    "lg_shot_features",
    "lg_vs_compare",
    "lg_note_card",
    "lg_cta_profile",
)
LayoutType = Literal[
    "lg_source_headline",
    "lg_stat_hero",
    "lg_shot_features",
    "lg_vs_compare",
    "lg_note_card",
    "lg_cta_profile",
]

ImageKindType = Literal["screenshot", "og", "card"]
EmphasisKindType = Literal["term", "number", "name"]


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
    id: NonEmptyText
    layout: LayoutType
    sentence_ids: list[int] = Field(min_length=1)
    slots: dict[str, Any] = Field(default_factory=dict)
    source_ref: SourceRef | None = None
    emphasis: list[EmphasisItem] = Field(default_factory=list, max_length=5)
    t_start: float = 0.0
    t_end: float = 0.0
    duration: float = 0.0
    narration: str = ""
    image_prompt: str = ""

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
                    # Cut at word boundary if possible
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
