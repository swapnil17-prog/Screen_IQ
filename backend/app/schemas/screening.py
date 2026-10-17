"""Explainable screening result: skill gap, experience analysis, RAG evidence and weighted score."""

from typing import Literal

from pydantic import BaseModel, Field

# ── Skill gap ────────────────────────────────────────────────────────────────


class SkillMatch(BaseModel):
    skill: str
    importance: Literal["required", "nice_to_have"]
    status: Literal["matched", "partial", "missing"]
    # How the match was established — surfaced in the UI for explainability
    method: Literal["exact", "alias", "related", "semantic", "mentioned", "none"]
    matched_to: str | None = None
    similarity: float | None = None


class SkillGapResult(BaseModel):
    matches: list[SkillMatch] = Field(default_factory=list)
    matched_required: list[str] = Field(default_factory=list)
    partial_required: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    matched_nice_to_have: list[str] = Field(default_factory=list)
    missing_nice_to_have: list[str] = Field(default_factory=list)
    bonus_skills: list[str] = Field(default_factory=list)
    required_coverage_pct: float = 0.0
    nice_to_have_coverage_pct: float = 0.0


# ── Experience ───────────────────────────────────────────────────────────────


class ExperienceRole(BaseModel):
    company: str
    title: str
    start: str | None = None  # YYYY-MM
    end: str | None = None  # YYYY-MM, None when current
    months: int | None = None
    is_current: bool = False
    seniority: str | None = None


class EmploymentGap(BaseModel):
    start: str
    end: str
    months: int


class ExperienceAnalysis(BaseModel):
    total_years: float | None = None
    role_count: int = 0
    roles: list[ExperienceRole] = Field(default_factory=list)
    average_tenure_months: float | None = None
    longest_tenure_months: int | None = None
    gaps: list[EmploymentGap] = Field(default_factory=list)
    current_title: str | None = None
    current_company: str | None = None
    seniority_estimate: str | None = None
    progression: Literal["ascending", "stable", "mixed", "unknown"] = "unknown"
    flags: list[str] = Field(default_factory=list)


class RelevantRole(BaseModel):
    title: str
    company: str
    relevance: float  # 0-100, calibrated similarity to the job


class ExperienceFit(BaseModel):
    candidate_years: float | None = None
    required_years: float | None = None
    expected_seniority: str | None = None
    estimated_seniority: str | None = None
    relevant_roles: list[RelevantRole] = Field(default_factory=list)


# ── RAG evidence ─────────────────────────────────────────────────────────────


class EvidenceChunk(BaseModel):
    id: str
    section: str
    text: str
    similarity: float


class RequirementAssessment(BaseModel):
    id: str
    requirement: str
    kind: Literal["skill", "responsibility", "experience", "education"]
    importance: Literal["required", "nice_to_have"]
    verdict: Literal["met", "partial", "not_met"]
    reasoning: str
    evidence_quote: str | None = None
    # True when the quoted text was found in the retrieved resume chunks —
    # guards against hallucinated citations.
    quote_verified: bool = False
    evidence: list[EvidenceChunk] = Field(default_factory=list)


class SemanticSection(BaseModel):
    section: str
    similarity: float
    calibrated: float


class SemanticMatch(BaseModel):
    score: float  # 0-100 calibrated
    sections: list[SemanticSection] = Field(default_factory=list)


# ── Scoring ──────────────────────────────────────────────────────────────────

ComponentKey = Literal["skills", "experience", "semantic", "assessment"]


class ScoreComponent(BaseModel):
    key: ComponentKey
    label: str
    score: float  # 0-100
    weight: float  # normalised 0-1
    contribution: float  # score * weight
    reasons: list[str] = Field(default_factory=list)


class ScreeningResult(BaseModel):
    version: str = "screening-v2"
    overall_score: float
    label: Literal["strong_match", "good_match", "potential", "weak_match"]
    confidence: Literal["high", "medium", "low"]
    components: list[ScoreComponent]
    summary: str
    one_liner: str = ""
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    skill_gap: SkillGapResult
    experience_fit: ExperienceFit
    semantic: SemanticMatch
    requirements: list[RequirementAssessment] = Field(default_factory=list)

    blind_screening: bool = True
    redactions: dict[str, int] = Field(default_factory=dict)

    llm_provider: str
    llm_model: str
    embedding_provider: str
    generated_at: str


# ── LLM contract for the RAG assessment step ─────────────────────────────────


class LLMRequirementVerdict(BaseModel):
    requirement_id: str = Field(description="The id given for the requirement, e.g. 'R3'")
    verdict: Literal["met", "partial", "not_met"]
    evidence_quote: str | None = Field(
        description="Short verbatim quote from the provided resume excerpts, or null if none supports it"
    )
    reasoning: str = Field(description="One or two sentences explaining the verdict")


class ScreeningAssessmentLLM(BaseModel):
    fit_score: int = Field(description="Holistic fit from 0 to 100; 85+ only for exceptional matches")
    summary: str = Field(description="2-4 sentence evidence-based assessment")
    one_liner: str = Field(
        description="One short phrase (max ~12 words) a recruiter can scan in a table, e.g. "
        "'Led a design-system rebuild used across 40+ teams.'"
    )
    strengths: list[str] = Field(description="Up to 4 specific strengths grounded in the excerpts")
    concerns: list[str] = Field(description="Up to 4 genuine gaps or risks")
    requirements: list[LLMRequirementVerdict]
