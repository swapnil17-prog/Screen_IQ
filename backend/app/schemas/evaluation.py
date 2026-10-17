"""LLM-as-a-judge rubric contract, counterfactual bias audit and final evaluation."""

from typing import Literal

from pydantic import BaseModel, Field

Recommendation = Literal["strong_hire", "hire", "lean_hire", "lean_no_hire", "no_hire"]


class CriterionScore(BaseModel):
    criterion: str
    met: bool
    evidence_quote: str | None = Field(description="Verbatim quote from the candidate's answer, or null")
    score: int = Field(description="0-10")


class QuestionScore(BaseModel):
    question_id: str
    technical_depth: int = Field(description="0-10")
    communication: int = Field(description="0-10: structure and clarity")
    problem_solving: int = Field(description="0-10: reasoning and trade-off awareness")
    score: int = Field(description="0-100 overall for this question")
    criteria: list[CriterionScore]
    strengths: list[str]
    improvements: list[str]


class InterviewRubricLLM(BaseModel):
    overall_score: int = Field(description="0-100 holistic interview performance")
    summary: str = Field(description="2-4 sentence evidence-backed summary of the interview")
    question_scores: list[QuestionScore]
    key_strengths: list[str]
    key_risks: list[str]


class QuestionDelta(BaseModel):
    question_id: str
    unmasked: float
    masked: float
    delta: float


class BiasAudit(BaseModel):
    method: str = "counterfactual_masking"
    unmasked_score: float
    masked_score: float
    delta: float
    threshold: float
    risk: Literal["low", "medium", "high"]
    flagged: bool
    entities_masked: dict[str, int] = Field(default_factory=dict)
    per_question: list[QuestionDelta] = Field(default_factory=list)
    explanation: str
    notes: list[str] = Field(default_factory=list)


class FinalComponent(BaseModel):
    key: Literal["screening", "interview"]
    label: str
    score: float
    weight: float
    contribution: float
