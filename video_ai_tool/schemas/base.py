# file: schemas/base.py
"""Chính sách validate thống nhất cho JSON từ AI."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True, allow_inf_nan=False)
