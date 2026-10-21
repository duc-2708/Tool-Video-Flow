"""Serializable editorial decisions, never narration or factual evidence."""
from typing import Literal
from pydantic import Field
from schemas.base import StrictModel

class ValidationEvent(StrictModel):
    rule_id: str
    group: Literal[1,2,3]
    scene_id: int | None = None
    phase: str = "plan"
    action: Literal["fixed","warning","error"]
    message: str

