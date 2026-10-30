"""Small structured-output friendly visual payload; no executable expressions."""
from typing import Literal
from pydantic import Field
from schemas.base import StrictModel


class VisualBar(StrictModel):
    label: str = ""
    value: float = 0
    unit: str = ""
    fact_id: int | None = None


class VisualBeat(StrictModel):
    # Word indexes are zero based in scene_N.words.json; seconds are scene local.
    at_word_index: int | None = Field(default=None,exclude_if=lambda v:v is None)
    at_sec: float | None = Field(default=None,exclude_if=lambda v:v is None)
    action: str = "reveal"


class VisualData(StrictModel):
    text: str = ""
    highlight: list[str] = Field(default_factory=list)
    value: float | None = None
    number_text: str = ""
    label: str = ""
    unit: str = ""
    source: str = ""
    source_url: str = ""
    date: str = ""
    title: str = ""
    items: list[str] = Field(default_factory=list)
    bars: list[VisualBar] = Field(default_factory=list)
    fact_ids: list[int] = Field(default_factory=list)
    status: str = ""
    left_label: str = ""
    right_label: str = ""
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


class Visual(StrictModel):
    beats: list[VisualBeat] = Field(default_factory=list,exclude_if=lambda v:not v)
    # One-based sentence association survives Assets shot duplication/resolution.
    sentence_index: int | None = Field(default=None,ge=1,exclude_if=lambda v:v is None)
    content_type: Literal["event","explain","opinion","cta"] = Field(default="event",exclude_if=lambda v:v=="event")
    auto_generated: bool = Field(default=False,exclude_if=lambda v:not v)
    template: Literal["hook_card", "stat_card", "steps_list", "compare_bars", "source_card", "text_focus", "stock",
        "progress_tracker", "ring_percent", "line_growth", "strike_replace", "quote_card", "timeline", "versus", "icon_card", "cta_card"] = "stock"
    data: VisualData = Field(default_factory=VisualData)
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
