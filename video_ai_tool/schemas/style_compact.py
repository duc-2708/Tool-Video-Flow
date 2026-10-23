"""Small transport schema for a single compact retry, not a second full report."""
from pydantic import Field,field_validator
from schemas.style import CategoryGuess,SceneTransition
from schemas.style_normalize import StyleObservation,EMPTY


class CompactStyleScene(StyleObservation):
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    purpose: str
    narration_summary: str = ""
    shot_count: int | None = Field(default=None,ge=1)
    transition_to_next: SceneTransition | None = None

    @field_validator("transition_to_next",mode="before")
    @classmethod
    def no_next(cls,value):
        return None if isinstance(value,str) and value.strip().casefold() in EMPTY else value

    @field_validator("purpose","narration_summary")
    @classmethod
    def short(cls,value):
        return " ".join(value.split()[:20])

    @field_validator("transition_to_next")
    @classmethod
    def short_transition(cls,value):
        if value:
            value.type=" ".join(value.type.split()[:20])
            value.connective_template=" ".join(value.connective_template.split()[:20])
        return value


class CompactStyleAnalysis(StyleObservation):
    entities_in_video: list[str] = Field(default_factory=list)
    scenes: list[CompactStyleScene] = Field(min_length=1,max_length=12)
    duration_sec: float | None = Field(default=None,gt=0)
    category_guess: CategoryGuess | None = None
    narrative_flow: str = ""
    reusable_rules: list[str] = Field(default_factory=list,max_length=12)

    @field_validator("category_guess")
    @classmethod
    def short_category_reason(cls,value):
        if value:
            value.reason=" ".join(value.reason.split()[:20])
        return value

    @field_validator("narrative_flow")
    @classmethod
    def short(cls,value):
        return " ".join(value.split()[:20])

    @field_validator("reusable_rules")
    @classmethod
    def short_rules(cls,value):
        return [" ".join(v.split()[:20]) for v in value]
