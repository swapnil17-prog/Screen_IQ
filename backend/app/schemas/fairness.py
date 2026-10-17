from typing import Literal

from pydantic import BaseModel, Field

BiasCategory = Literal[
    "masculine_coded", "feminine_coded", "age", "exclusionary", "ableist", "jargon", "requirements"
]


class BiasFlag(BaseModel):
    category: BiasCategory
    phrase: str
    count: int = 1
    severity: Literal["low", "medium", "high"]
    suggestion: str


class JDBiasReport(BaseModel):
    score: int  # 0-100, higher = more inclusive
    rating: Literal["inclusive", "needs_review", "biased"]
    gender_lean: Literal["masculine", "feminine", "neutral"]
    masculine_count: int = 0
    feminine_count: int = 0
    word_count: int = 0
    flags: list[BiasFlag] = Field(default_factory=list)
    summary: str
