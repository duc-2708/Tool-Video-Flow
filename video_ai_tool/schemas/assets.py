# file: schemas/assets.py
"""Manifest Assets và kế hoạch resolved, tách khỏi EditPlan gốc."""
from typing import Literal
from pydantic import Field, model_validator
from schemas.base import NonEmptyText, StrictModel
from schemas.edit_plan import EditPlan


class ResolvedEditPlan(EditPlan):
    source_plan_hash: NonEmptyText
    timing_basis: Literal["audio"] = "audio"
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_structure(self):
        # Giọng thật có thể làm hook >3s; giữ cảnh và ghi cảnh báo, không cắt lời.
        ids = [scene.id for scene in self.scenes]
        if len(ids) != len(set(ids)) or self.scenes[0].role != "hook" or self.scenes[-1].role != "cta":
            raise ValueError("Resolved plan phải có ID duy nhất, hook đầu và CTA cuối.")
        return self


class ShotAsset(StrictModel):
    shot_id: int = Field(ge=1)
    query: str
    media_type: Literal["video", "image", "color"]
    path: NonEmptyText
    provider: Literal["pixabay", "pexels", "generated"]
    asset_id: str | None = None
    author: str | None = None
    source_url: str | None = None
    fallback: bool
    fallback_reason: str | None = None
    media_duration_sec: float | None = None
    requires_loop: bool = False


class SceneAssets(StrictModel):
    scene_id: int = Field(ge=1)
    audio_path: str | None
    audio_duration_sec: float | None = Field(default=None, gt=0)
    audio_error: str | None = None
    audio_silent: bool = False
    audio_voice: str | None = None
    audio_warnings: list[str] = Field(default_factory=list)
    shots: list[ShotAsset]


class AssetsManifest(StrictModel):
    source_plan_hash: NonEmptyText
    resolved_plan_hash: NonEmptyText
    status: Literal["complete", "partial"]
    scenes: list[SceneAssets]
    warnings: list[str]
    # Dependency-separated hashes
    audio_hash: str | None = None
    clip_hash: str | None = None
    visual_hash: str | None = None
    scene_audio_hashes: dict[str, str] = Field(default_factory=dict)
    scene_clip_hashes: dict[str, str] = Field(default_factory=dict)
