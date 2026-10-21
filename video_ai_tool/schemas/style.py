"""Observed style, reusable presets and renderer defaults; no executable content."""
from typing import Literal
from pydantic import Field, field_validator, model_validator
from schemas.base import StrictModel, NonEmptyText


class TranscriptPart(StrictModel):
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    summary: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("Mốc kết thúc phải sau mốc bắt đầu.")
        return self


class StyleHook(StrictModel):
    technique: NonEmptyText
    template: NonEmptyText
    word_count: int = Field(ge=0, le=150)


class StyleSection(StrictModel):
    name: NonEmptyText
    duration_sec: float = Field(gt=0)
    purpose: NonEmptyText
    transition: str


class NarrationStyle(StrictModel):
    pronouns: list[str]
    intimacy: str
    average_sentence_words: float | None = Field(default=None, gt=0, le=100)
    rhetorical_questions: str
    examples: str
    catchphrases: list[str]
    humor: str
    words_per_sec: float | None = Field(default=None, gt=0, le=10)
    voice_gender_estimate: str | None = None
    voice_age_estimate: str | None = None
    voice_emotion: str


class StylePacing(StrictModel):
    average_shot_sec: float = Field(gt=0, le=120)
    cuts_per_10_sec: float = Field(ge=0, le=100)
    pattern_interrupts: list[float]
    rhythm: str


class VisualStyle(StrictModel):
    types: list[str]
    transitions: list[str]
    camera_effects: list[str]
    aspect_ratio: str
    colors: list[str]


class CaptionStyle(StrictModel):
    enabled: bool = True
    mode: Literal["word", "phrase", "sentence"] = "phrase"
    font_description: str = "Chữ đậm dễ đọc"
    font_scale: float = Field(default=.064, ge=.03, le=.10)
    color: str = "#FFFFFF"
    highlight_color: str = "#FFD741"
    stroke_color: str = "#000000"
    stroke_width_ratio: float = Field(default=.006, ge=.001, le=.02)
    position: Literal["lower", "center", "top"] = "lower"
    emphasis: str = "Tô màu từ đang đọc"
    shadow: str = "Không rõ"

    @field_validator("color", "highlight_color", "stroke_color")
    @classmethod
    def hex_color(cls, value):
        import re
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("Màu phải là #RRGGBB.")
        return value.upper()


class AudioStyle(StrictModel):
    mood: str = "calm"
    music_volume: float = Field(default=.08, ge=0, le=.35)
    sfx_types: list[str] = Field(default_factory=list)
    sfx_per_10_sec: float = Field(default=0, ge=0, le=10)
    sfx_positions: list[float] = Field(default_factory=list)
    ducking: bool = True
    details: str = "Không đủ dữ liệu"


class StyleEnding(StrictModel):
    technique: str
    has_cta: bool


class StyleAnalysis(StrictModel):
    duration_sec: float = Field(gt=0, le=3600)
    transcript_outline: list[TranscriptPart] = Field(min_length=1, max_length=150)
    hook: StyleHook
    structure: list[StyleSection] = Field(min_length=1, max_length=40)
    narration_style: NarrationStyle
    pacing: StylePacing
    visual_style: VisualStyle
    captions: CaptionStyle
    audio: AudioStyle
    cta_ending: StyleEnding
    strengths: list[str] = Field(min_length=3, max_length=5)
    weaknesses: list[str] = Field(min_length=1, max_length=3)
    reusable_rules: list[str] = Field(min_length=8, max_length=15)

    @model_validator(mode="after")
    def timeline_bounds(self):
        if any(p.end_sec > self.duration_sec + 1 for p in self.transcript_outline):
            raise ValueError("Transcript vượt thời lượng video.")
        if any(t < 0 or t > self.duration_sec for t in self.pacing.pattern_interrupts + self.audio.sfx_positions):
            raise ValueError("Mốc hiệu ứng vượt thời lượng video.")
        return self


class AnalysisRecord(StrictModel):
    version: int = 1
    filename: str
    file_hash: str
    notes_hash: str
    model: str
    prompt_hash: str
    warnings: list[str] = Field(default_factory=list)
    analysis: StyleAnalysis


class RuleFrequency(StrictModel):
    rule: NonEmptyText
    video_count: int = Field(ge=1)


class PaceRange(StrictModel):
    mean: float = Field(gt=0)
    minimum: float = Field(gt=0)
    maximum: float = Field(gt=0)


class ProfileSection(StrictModel):
    name: str
    fraction: float = Field(gt=0, le=1)


class StyleProfile(StrictModel):
    version: int = 1
    name: NonEmptyText
    slug: NonEmptyText
    reference_hashes: list[str] = Field(min_length=1)
    reference_files: list[str]
    # Never include these in Director prompts; local comparison only.
    reference_texts: list[str]
    hook_templates: list[str]
    hook_techniques: list[str]
    structure: list[ProfileSection]
    shot_seconds: PaceRange
    speech_words_per_sec: PaceRange
    narration_rules: list[str]
    broll_patterns: list[str]
    visual_effects: list[str]
    transitions: list[str]
    captions: CaptionStyle
    audio: AudioStyle
    ending_techniques: list[str]
    reusable_rules: list[str]
    rule_frequencies: list[RuleFrequency]


class StyleRenderDefaults(StrictModel):
    captions: CaptionStyle = Field(default_factory=CaptionStyle)
    ducking: bool = True
