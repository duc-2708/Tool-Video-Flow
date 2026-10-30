"""Schema definitions for Scene Director and Hybrid Rendering (Phase 8).
Validates scene-by-scene presentation decisions: motion, ai_clip, or hybrid.
"""
from __future__ import annotations

import re
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


SceneMode = Literal["motion", "ai_clip", "hybrid"]
EmphasisKind = Literal["new_term", "number", "contrast", "warning", "cta"]
EmphasisIntensity = Literal["subtle", "normal", "hero"]
EmphasisPlace = Literal["caption", "center", "label"]
EmphasisSFX = Literal["pop", "whoosh", "click", "chime", "none"]

EMPHASIS_EFFECTS = {
    "underline_draw", "marker_highlight", "color_flip", "bold_pop",
    "scale_punch", "glow_pulse", "gradient_sweep", "shine_glint",
    "box_draw", "circle_scribble", "bracket_focus", "stamp_hit",
    "strike_replace", "typewriter_reveal", "letter_spread", "spotlight_dim",
    "zoom_to_word", "term_card", "badge_tag", "arrow_point"
}


class KeyBeatBrief(BaseModel):
    at_phrase: str = Field(default="", description="2-3 từ nguyên văn trong lời đọc, không dấu câu")
    event: str = Field(default="", description="Điều xảy ra trên hình")

    @field_validator("at_phrase", mode="before")
    @classmethod
    def clean_at_phrase(cls, v: Any) -> str:
        s = str(v or "").strip()
        return re.sub(r"[.,!?;:\"']+", "", s).strip()


class MotionBrief(BaseModel):
    visual_idea: str = Field(default="", description="Động từ hình ảnh + vật thể")
    recipe_candidates: list[str] = Field(default_factory=list, description="Danh sách recipe đề xuất")
    metaphor_link: str = Field(default="", description="Liên hệ với ẩn dụ chủ đạo của video")
    key_beats: list[KeyBeatBrief] = Field(default_factory=list, description="Các nhịp chuyển động chính")


class EmphasisItem(BaseModel):
    at_phrase: str = Field(default="", description="2-3 từ nguyên văn trong lời đọc")
    text: str = Field(default="", description="Cụm cần nhấn mạnh, <= 4 từ, chép nguyên văn")
    kind: str = Field(default="new_term")
    effect: str = Field(default="bold_pop")
    intensity: str = Field(default="normal")
    place: str = Field(default="caption")
    sfx: str = Field(default="none")

    @field_validator("at_phrase", mode="before")
    @classmethod
    def clean_at_phrase(cls, v: Any) -> str:
        s = str(v or "").strip()
        return re.sub(r"[.,!?;:\"']+", "", s).strip()

    @field_validator("effect", mode="before")
    @classmethod
    def validate_effect(cls, v: Any) -> str:
        eff = str(v or "").strip().lower()
        if eff not in EMPHASIS_EFFECTS:
            return "bold_pop"
        return eff


class AiClipBrief(BaseModel):
    prompt_en: str = Field(default="", description="Prompt mô tả cảnh quay AI bằng tiếng Anh")
    negative_en: str = Field(
        default="text, watermark, logo, deformed, letters, typography, readable screens, face close-up, celebrity, famous person",
        description="Negative prompt bằng tiếng Anh"
    )
    duration_sec: int = Field(default=4, ge=1, le=30)
    camera: str = Field(default="slow push-in", description="Chuyển động camera")
    overlay_safe: str = Field(default="", description="Gợi ý vùng an toàn cho lớp đồ họa")
    fallback_recipe: str = Field(default="text_focus", description="Recipe thay thế nếu clip AI gặp sự cố")
    extend: str = Field(default="slowmo", description="Cách kéo dài clip: slowmo | loop | hold")


class ScenePlanItem(BaseModel):
    scene_id: int = Field(ge=1)
    mode: SceneMode = Field(default="motion")
    rationale: str = Field(default="")
    motion_brief: MotionBrief = Field(default_factory=MotionBrief)
    emphasis: list[EmphasisItem] = Field(default_factory=list)
    ai_clip: Optional[AiClipBrief] = None

    @model_validator(mode="after")
    def ensure_fallback_and_mode_consistency(self) -> "ScenePlanItem":
        if self.mode in ("ai_clip", "hybrid"):
            if not self.ai_clip:
                self.ai_clip = AiClipBrief(fallback_recipe="text_focus")
            elif not self.ai_clip.fallback_recipe:
                self.ai_clip.fallback_recipe = (
                    self.motion_brief.recipe_candidates[0]
                    if self.motion_brief.recipe_candidates
                    else "text_focus"
                )
        return self


class ScenePlanResponse(BaseModel):
    style_prefix_en: str = Field(
        default="cinematic, deep navy and cyan neon accents, soft volumetric light, shallow depth of field",
        description="Phong cách hình ảnh thống nhất cho mọi clip AI"
    )
    ai_label_required: bool = Field(default=True)
    scenes: list[ScenePlanItem] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)
