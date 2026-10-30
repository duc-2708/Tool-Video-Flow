# file: schemas/edit_plan.py
"""Schema dựng video; chỉ chứa dữ liệu, không thực thi mã từ AI."""
import re
from typing import Annotated, Literal, Self
from pydantic import AliasChoices, Field, HttpUrl, field_validator, model_validator
from config.presets import DURATION_TOLERANCE, SHOT_MAX_SECONDS, SHOT_MIN_SECONDS
from schemas.base import NonEmptyText, StrictModel
from schemas.story import StoryOutline
from schemas.validation import ValidationEvent
from schemas.style import StyleProfile, StyleRenderDefaults
from schemas.visual import Visual
from schemas.motion_scene import MotionScenePlan
from schemas.explainer import ScriptSentence,ContentMode,InfoKind,ExplainerOutline,ScriptCritic


class Music(StrictModel):
    mood: NonEmptyText
    volume: float = Field(ge=0, le=1)


class Shot(StrictModel):
    visual_plan: MotionScenePlan | None = Field(default=None,exclude_if=lambda v:v is None)
    card_text: str | None = Field(default=None,exclude_if=lambda v:v is None)
    emphasis: list[str] = Field(default_factory=list,exclude_if=lambda v:not v)
    semantic_query: bool = Field(default=False,exclude_if=lambda v:not v)
    visual: Visual | None = Field(default=None,exclude_if=lambda v:v is None)
    planning_duration: bool = Field(default=False,exclude_if=lambda v:not v)
    type: Literal["stock_video", "stock_image", "ai_image", "ai_video", "text_card"] = Field(validation_alias=AliasChoices("type","source"))
    ai_prompt: str | None = Field(default=None,exclude_if=lambda value:value is None)
    query: NonEmptyText
    duration_sec: float = Field(ge=1/30, le=600)
    effect: Literal["none", "zoom_in", "zoom_out", "pan_left", "pan_right"]
    # on_screen_text is accepted on input; renderers keep the established name.
    text_overlay: NonEmptyText | None = Field(validation_alias=AliasChoices("text_overlay", "on_screen_text"))
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)

    @field_validator("query",mode="before")
    @classmethod
    def validate_query(cls, value: str,info) -> str:
        if info.data.get("semantic_query"):
            from agents.explainer_visuals import semantic_query
            return semantic_query(value)
        from agents.broll_queries import sanitize_broll_query
        return sanitize_broll_query(value)

    @model_validator(mode="after")
    def stock_duration(self):
        if not self.planning_duration and not SHOT_MIN_SECONDS<=self.duration_sec<=SHOT_MAX_SECONDS:
            raise ValueError("Shot audio-resolved phải nằm trong 1.5–4 giây.")
        return self


class ReviewSource(StrictModel):
    fact_id: int = Field(ge=1)
    name: NonEmptyText
    url: HttpUrl
    confidence: Literal["high", "medium", "low"]


class FactReview(StrictModel):
    fact_id: int = Field(ge=1)
    source_count: int = Field(ge=1)
    confidence: Literal["high", "medium", "low"]
    sources: list[ReviewSource]


class ReviewNotes(StrictModel):
    warnings: list[str] = Field(default_factory=list,exclude_if=lambda value:not value)
    fact_ids: list[int]
    source_count: int = Field(ge=0)
    confidence: Literal["high", "medium", "low"] | None
    facts: list[FactReview]


class Scene(StrictModel):
    visual_plan: MotionScenePlan | None = Field(default=None,exclude_if=lambda v:v is None)
    sentences: list[ScriptSentence] = Field(default_factory=list,exclude_if=lambda v:not v)
    information_kind: InfoKind | None = Field(default=None,exclude_if=lambda v:v is None)
    new_information: str = Field(default="",exclude_if=lambda v:not v)
    @model_validator(mode="before")
    @classmethod
    def normalize_structure(cls,value):
        if isinstance(value,dict):
            from agents.plan_structure import normalize_plan_structure
            return normalize_plan_structure({"scenes":[value]},unique_queries=False)["scenes"][0]
        return value

    id: int = Field(ge=1)
    role: Literal["hook", "body", "transition", "cta"]
    style_purpose: str | None = Field(default=None,exclude_if=lambda v:v is None)
    narration: NonEmptyText
    pronunciation_hint: str | None = Field(default=None, exclude_if=lambda value:value is None)
    shots: Annotated[list[Shot], Field(min_length=1)]
    transition_out: Literal["cut", "fade", "zoom", "whip"]
    sfx: Literal["none", "whoosh", "pop"]
    fact_ids: list[int] = Field(default_factory=list)
    pattern_interrupt: bool = False
    # Preserve hashes of older plans that did not have this metadata field.
    review_notes: ReviewNotes | None = Field(default=None, exclude_if=lambda value: value is None)
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)

    @property
    def duration_sec(self) -> float:
        return sum(shot.duration_sec for shot in self.shots)


class EditPlan(StrictModel):
    content_mode: ContentMode = Field(default="event_only",exclude_if=lambda v:v=="event_only")
    explainer_outline: ExplainerOutline | None = Field(default=None,exclude_if=lambda v:v is None)
    script_critic: ScriptCritic | None = Field(default=None,exclude_if=lambda v:v is None)
    content_timed: bool = Field(default=False,exclude_if=lambda v:not v)
    ai_clip_limit: int = Field(default=0,ge=0,exclude_if=lambda v:not v)
    style_preset: str | None = Field(default=None, exclude_if=lambda v: v is None)
    style_profile: StyleProfile | None = Field(default=None, exclude_if=lambda v: v is None)
    render_style: StyleRenderDefaults | None = Field(default=None, exclude_if=lambda v: v is None)
    validation_events: list[ValidationEvent] = Field(default_factory=list,exclude_if=lambda v:not v)
    review_notes: list[str] = Field(default_factory=list,exclude_if=lambda v:not v)
    humanization_fallback_scene_ids: list[int] = Field(default_factory=list,exclude_if=lambda v:not v)
    adaptive: bool = Field(default=False,exclude_if=lambda v:not v)
    requested_duration_sec: float | None = Field(default=None,exclude_if=lambda v:v is None)
    creative_license: Literal["strict","balanced","story"] = Field(default="strict",exclude_if=lambda v:v=="strict")
    script_style: Literal["storytelling", "news", "explain", "review"] | None = Field(default=None, exclude_if=lambda v:v is None)
    story_outline: StoryOutline | None = Field(default=None, exclude_if=lambda v:v is None)
    title: NonEmptyText
    format: Literal["tiktok", "youtube"]
    voice: Literal["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"]
    music: Music
    scenes: Annotated[list[Scene], Field(min_length=2)]
    video_type: Literal["news", "review", "story"] | None = None
    target_duration_sec: float | None = Field(default=None, gt=0)
    brief_hash: str | None = None

    @model_validator(mode="after")
    def validate_structure(self) -> Self:
        ids = [scene.id for scene in self.scenes]
        repaired=[]
        if len(set(ids)) != len(ids):
            used=set()
            for scene in self.scenes:
                if scene.id in used: scene.id=max(ids+list(used))+1
                used.add(scene.id)
            repaired.append("Đã đánh lại ID cảnh trùng, giữ nội dung/fact.")
        if self.scenes[0].role != "hook":
            self.scenes[0].role="hook";repaired.append("Đã đặt vai trò cảnh đầu là hook.")
        if self.scenes[0].duration_sec > 3 and not self.content_timed:
            source=self.scenes[0].shots[0]
            self.scenes[0].shots=[source.model_copy(update={"duration_sec":3.})]
            repaired.append("Đã căn shot hook về 3 giây; không cắt lời đọc, audio thật sẽ được căn ở Assets.")
        if self.scenes[-1].role != "cta":
            self.scenes[-1].role="cta";repaired.append("Đã đặt vai trò cảnh cuối là cta.")
        for message in repaired:
            event=ValidationEvent(rule_id="shot_structure",group=2,action="fixed",message=message)
            if event not in self.validation_events: self.validation_events.append(event)
        return self

    @property
    def duration_sec(self) -> float:
        return sum(scene.duration_sec for scene in self.scenes)

    def validate_target_duration(self, target_sec: float) -> None:
        """Bước Director gọi thêm sau khi validate JSON."""
        if not 0 < target_sec < float("inf"):
            raise ValueError("Thời lượng yêu cầu phải là số hữu hạn lớn hơn 0.")
        if abs(self.duration_sec - target_sec) > target_sec * DURATION_TOLERANCE + 1e-8:
            from agents.validation_rules import Context,fix_duration
            from types import SimpleNamespace
            fix_duration(Context(self,None,SimpleNamespace(duration_sec=target_sec)))
