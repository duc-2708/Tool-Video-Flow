"""Small schemas for the three Director passes (no unrestricted dictionaries)."""
from pydantic import Field
from schemas.base import StrictModel, NonEmptyText
from schemas.validation import ValidationEvent

class StoryPoint(StrictModel):
    id: int
    idea: NonEmptyText
    fact_ids: list[int] = Field(min_length=1)

class OutlineScene(StrictModel):
    scene_id: int
    point_id: int
    fact_ids: list[int] = Field(min_length=1)
    purpose: NonEmptyText

class OutlineRepairs(StrictModel):
    scenes: list[OutlineScene]

class StoryOutline(StrictModel):
    validation_events: list[ValidationEvent] = Field(default_factory=list,exclude_if=lambda v:not v)
    angle_index: int = Field(ge=1)
    hook: NonEmptyText
    open_loop: str = ""
    payoff: str = ""
    payoff_fact_ids: list[int] = Field(default_factory=list)
    main_points: list[StoryPoint] = Field(min_length=1,max_length=6)
    scenes: list[OutlineScene]

class SceneWords(StrictModel):
    card_texts: list[str] = Field(default_factory=list,exclude_if=lambda v:not v)
    emphasis: list[list[str]] = Field(default_factory=list,exclude_if=lambda v:not v)
    structure_warnings: list[str] = Field(default_factory=list,exclude_if=lambda v:not v)
    shot_queries: list[str] | None = Field(default=None,exclude_if=lambda v:v is None)
    shot_effects: list[str] | None = Field(default=None,exclude_if=lambda v:v is None)
    shot_types: list[str] | None = Field(default=None,exclude_if=lambda v:v is None)
    shot_sfx: list[str] | None = Field(default=None,exclude_if=lambda v:v is None)
    scene_id: int
    narration: NonEmptyText
    overlays: list[str | None]
    broll_query: NonEmptyText

class WrittenScript(StrictModel):
    title: NonEmptyText
    scenes: list[SceneWords]

class VideoTitle(StrictModel):
    title: NonEmptyText

class StoryIssue(StrictModel):
    scene_id: int
    reason: NonEmptyText

class HumanizedScript(StrictModel):
    scenes: list[SceneWords]
    approved: bool
    issues: list[StoryIssue]
