"""Separate background knowledge from evidence-backed event statements."""
from typing import Literal
from pydantic import Field
from schemas.base import StrictModel,NonEmptyText

ContentMode=Literal["event_only","explainer_v2"]
SentenceType=Literal["event","explain","opinion","cta"]
InfoKind=Literal["cause","mechanism","example","comparison","consequence","metaphor","counterpoint"]


class ScriptSentence(StrictModel):
    type: SentenceType
    text: NonEmptyText
    fact_ids: list[int] = Field(default_factory=list)


class KnowledgeNote(StrictModel):
    text: NonEmptyText
    analogy: str = ""
    confidence: Literal["low","medium"] = "low"
    source: Literal["kiến thức nền"] = "kiến thức nền"


class ResearchQuestion(StrictModel):
    question: NonEmptyText
    query_vi: NonEmptyText
    query_en: NonEmptyText


class QuestionPlan(StrictModel):
    questions: list[ResearchQuestion] = Field(min_length=1,max_length=7)


class KnowledgeResponse(StrictModel):
    knowledge_notes: list[KnowledgeNote] = Field(default_factory=list,max_length=8)


class ExplainerBeat(StrictModel):
    id: int
    kind: InfoKind
    idea: NonEmptyText
    new_information: NonEmptyText
    fact_ids: list[int] = Field(default_factory=list)


class ExplainerOutline(StrictModel):
    angle: NonEmptyText
    hook: NonEmptyText
    open_loop: str = ""
    payoff: str = ""
    beats: list[ExplainerBeat] = Field(min_length=2,max_length=20)


class ShotCard(StrictModel):
    card_text: str = ""
    emphasis: list[str] = Field(default_factory=list)


class ExplainerScene(StrictModel):
    scene_id: int
    kind: InfoKind
    new_information: NonEmptyText
    sentences: list[ScriptSentence] = Field(min_length=1)
    # One distinct concept per query, aligned to successive narration segments.
    shot_queries: list[NonEmptyText] = Field(default_factory=list)
    shot_cards: list[ShotCard] = Field(default_factory=list,exclude_if=lambda v:not v)


class ExplainerScript(StrictModel):
    title: NonEmptyText
    scenes: list[ExplainerScene] = Field(min_length=2)


class WeakScene(StrictModel):
    scene_id: int
    reason: NonEmptyText


class ScriptCritic(StrictModel):
    explanation: int = Field(ge=1,le=5)
    novelty: int = Field(ge=1,le=5)
    hook: int = Field(ge=1,le=5)
    open_loop: int = Field(ge=1,le=5)
    naturalness: int = Field(ge=1,le=5)
    comments: list[str] = Field(default_factory=list)
    weak_scenes: list[WeakScene] = Field(default_factory=list)


class LoopReview(StrictModel):
    answered: bool
    reason: str = ""
    replacement_question: str = ""


class ExplainerRepairs(StrictModel):
    scenes: list[ExplainerScene]
