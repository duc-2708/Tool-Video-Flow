"""Small structured-output friendly visual payload; no executable expressions."""
from typing import Any, Literal
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


class VisualCompareSide(StrictModel):
    label: str = ""
    sub: str = ""
    points: list[str] = Field(default_factory=list)


class VisualSeriesItem(StrictModel):
    label: str = ""
    value: float = 0.0
    unit: str = ""


class VisualPhoto(StrictModel):
    path: str = ""
    name: str = ""
    role: str = ""
    credit: str = ""


class VisualData(StrictModel):
    text: str = ""
    highlight: list[str] = Field(default_factory=list)
    value: float | int | str | None = None
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
    pill: str = ""
    headline: str = ""
    badge: str = ""
    winner: str | int = ""
    repo_name: str = ""
    repo_desc: str = ""
    neon_stat: str = ""
    stat_box_1: str = ""
    stat_box_2: str = ""
    stat_box_3: str = ""
    author: str = ""
    channel_name: str = ""
    channel_handle: str = ""
    image_url: str = ""
    image_prompt: str = ""
    subtext: str = ""
    note: str = ""
    sub_pill: str = ""
    statement: str = ""
    quote: str = ""
    mockup_type: str = ""
    subtitle: str = ""
    sub: str = ""
    series: list[VisualSeriesItem] = Field(default_factory=list)
    left: VisualCompareSide = Field(default_factory=VisualCompareSide)
    right: VisualCompareSide = Field(default_factory=VisualCompareSide)
    role: str = ""
    call_to_action: str = ""
    button_text: str = ""
    chart_type: str = ""
    icon: str = ""
    icon_reason: str = ""
    photo: VisualPhoto = Field(default_factory=VisualPhoto)
    path: str = ""
    image: str = ""
    thumbnail: str = ""
    delta: str = ""
    delta_type: str = ""
    delta_dir: str = ""
    source_date: str = ""
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


class Visual(StrictModel):
    beats: list[VisualBeat] = Field(default_factory=list,exclude_if=lambda v:not v)
    # One-based sentence association survives Assets shot duplication/resolution.
    sentence_index: int | None = Field(default=None,ge=1,exclude_if=lambda v:v is None)
    content_type: Literal["event","explain","opinion","cta"] = Field(default="event",exclude_if=lambda v:v=="event")
    auto_generated: bool = Field(default=False,exclude_if=lambda v:not v)
    template: Literal["hook_card", "stat_card", "steps_list", "compare_bars", "source_card", "text_focus", "stock",
        "progress_tracker", "ring_percent", "line_growth", "strike_replace", "quote_card", "timeline", "versus", "icon_card", "cta_card",
        "kit_title", "kit_stat", "kit_chart_bar", "kit_chart_line", "kit_chart_donut",
        "kit_photo", "kit_list", "kit_compare", "kit_quote", "kit_timeline", "kit_outro",
        "lg_source_headline", "lg_stat_hero", "lg_shot_features", "lg_vs_compare", "lg_note_card", "lg_cta_profile"] = "stock"
    data: VisualData = Field(default_factory=VisualData)
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
