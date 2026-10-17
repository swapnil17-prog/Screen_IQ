"""HTTP request / response models."""

import uuid
from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.schemas.evaluation import BiasAudit, FinalComponent, InterviewRubricLLM
from app.schemas.extraction import JDExtraction, ResumeExtraction
from app.schemas.fairness import JDBiasReport
from app.schemas.interview import ChatMessage, InterviewPlan
from app.schemas.organization import OrganizationSettings, ScoringWeights
from app.schemas.screening import ExperienceAnalysis, ScreeningResult

T = TypeVar("T")

Role = Literal["owner", "admin", "recruiter", "viewer"]
Stage = Literal["new", "shortlisted", "interviewing", "offer", "hired", "rejected"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


def _password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Password is too long")
    if v.isalpha() or v.isdigit():
        raise ValueError("Password must mix letters with numbers or symbols")
    return v


# ── Auth / users / organization ──────────────────────────────────────────────


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=120)
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str

    _pw = field_validator("password")(_password)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    _pw = field_validator("new_password")(_password)


class UserOut(ORM):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    last_login_at: datetime | None
    invited_at: datetime | None = None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def invite_pending(self) -> bool:
        return self.invited_at is not None and self.last_login_at is None


class OrganizationOut(ORM):
    id: uuid.UUID
    name: str
    slug: str
    settings: OrganizationSettings
    created_at: datetime

    @field_validator("settings", mode="before")
    @classmethod
    def _settings(cls, v: object) -> object:
        return OrganizationSettings.model_validate(v or {})


class SessionOut(BaseModel):
    user: UserOut
    organization: OrganizationOut
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    user: UserOut
    organization: OrganizationOut


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    role: Literal["admin", "recruiter", "viewer"] = "recruiter"
    # Omit to email them an invitation link (they choose their own password).
    # Set it to create the account directly and share the password yourself.
    temporary_password: str | None = None

    @field_validator("temporary_password")
    @classmethod
    def _temp_pw(cls, v: str | None) -> str | None:
        return None if v is None else _password(v)


class InviteUserResult(BaseModel):
    user: UserOut
    # Shown to the admin so they can share it manually if email isn't set up or fails
    invite_link: str | None = None
    invite_emailed: bool = False
    email_error: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class TokenPasswordRequest(BaseModel):
    """Reset a password or accept an invitation with the emailed token."""

    token: str = Field(min_length=20, max_length=200)
    password: str

    _pw = field_validator("password")(_password)


class InvitationOut(BaseModel):
    email: str
    full_name: str
    organization_name: str


class UpdateUserRequest(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=120)
    role: Literal["admin", "recruiter", "viewer"] | None = None
    is_active: bool | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    settings: OrganizationSettings | None = None


# ── Jobs ─────────────────────────────────────────────────────────────────────


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=50, max_length=30_000)
    department: str | None = Field(None, max_length=120)
    location: str | None = Field(None, max_length=120)
    employment_type: str | None = Field(None, max_length=60)


class CriteriaUpdate(BaseModel):
    """Recruiter override of the AI-extracted screening criteria."""

    required_skills: list[str] = Field(max_length=25)
    nice_to_have_skills: list[str] = Field(default_factory=list, max_length=20)
    min_years_experience: float | None = Field(None, ge=0, le=40)


class JobUpdate(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=200)
    description: str | None = Field(None, min_length=50, max_length=30_000)
    department: str | None = Field(None, max_length=120)
    location: str | None = Field(None, max_length=120)
    employment_type: str | None = Field(None, max_length=60)
    status: Literal["open", "paused", "closed", "archived"] | None = None
    scoring_weights: ScoringWeights | None = None
    clear_scoring_weights: bool = False
    criteria: CriteriaUpdate | None = None


class JobCounts(BaseModel):
    total: int = 0
    screened: int = 0
    processing: int = 0
    failed: int = 0
    shortlisted: int = 0
    interviewing: int = 0
    hired: int = 0
    strong: int = 0
    review: int = 0
    low: int = 0


class JobSummary(ORM):
    id: uuid.UUID
    title: str
    department: str | None
    location: str | None
    employment_type: str | None
    status: str
    extraction_status: str
    created_at: datetime
    updated_at: datetime
    counts: JobCounts = Field(default_factory=JobCounts)
    avg_score: float | None = None
    top_score: float | None = None
    inclusivity_score: int | None = None


class JobDetail(JobSummary):
    description: str
    extracted: JDExtraction | None
    extraction_error: str | None
    bias_report: JDBiasReport | None
    scoring_weights: ScoringWeights
    has_custom_weights: bool


class BiasCheckRequest(BaseModel):
    description: str = Field(min_length=1, max_length=30_000)


# ── Candidates & applications ────────────────────────────────────────────────


class CandidateRef(BaseModel):
    id: uuid.UUID
    full_name: str | None
    headline: str | None
    current_company: str | None = None
    email: str | None
    location: str | None


class SkillChip(BaseModel):
    skill: str
    importance: Literal["required", "nice_to_have"]
    status: Literal["matched", "partial", "missing"]


class ApplicationSummary(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str | None = None
    candidate: CandidateRef
    stage: Stage
    status: str
    error: str | None
    screening_score: float | None
    screening_label: str | None
    tier: Literal["strong", "review", "low"] | None = None
    one_liner: str | None = None
    skill_chips: list[SkillChip] = Field(default_factory=list)
    final_score: float | None
    recommendation: str | None
    confidence: str | None = None
    required_coverage_pct: float | None = None
    missing_required: list[str] = Field(default_factory=list)
    total_years: float | None = None
    flags: list[str] = Field(default_factory=list)
    interview_status: str | None = None
    source: Literal["upload", "careers"] = "upload"
    created_at: datetime
    updated_at: datetime


class CandidateSummary(BaseModel):
    id: uuid.UUID
    full_name: str | None
    email: str | None
    headline: str | None
    location: str | None
    status: str
    error: str | None
    skills: list[str]
    total_years: float | None
    applications_count: int = 0
    created_at: datetime
    similarity: float | None = None


class CandidateApplication(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    stage: str
    status: str
    screening_score: float | None
    final_score: float | None
    created_at: datetime


class CandidateDetail(CandidateSummary):
    phone: str | None
    filename: str
    file_size: int
    extracted: ResumeExtraction | None
    experience: ExperienceAnalysis | None
    raw_text: str
    applications: list[CandidateApplication]


class ApplyRequest(BaseModel):
    job_id: uuid.UUID


class ApplicationUpdate(BaseModel):
    stage: Stage | None = None
    notes: str | None = Field(None, max_length=10_000)


class UploadError(BaseModel):
    filename: str
    message: str


class UploadResult(BaseModel):
    created: list[ApplicationSummary]
    duplicates: list[ApplicationSummary]
    errors: list[UploadError]


# ── Interviews ───────────────────────────────────────────────────────────────


class InterviewOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    status: str
    plan: InterviewPlan
    current_question_index: int
    answered_questions: int
    messages: list[ChatMessage]
    consent_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime
    created_at: datetime
    # Only present right after creation / link regeneration (raw token isn't stored)
    link: str | None = None


class InterviewListItem(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    candidate_name: str | None
    status: str
    answered_questions: int
    total_questions: int
    created_at: datetime
    completed_at: datetime | None
    expires_at: datetime
    final_score: float | None
    recommendation: str | None


class PublicInterviewOut(BaseModel):
    organization_name: str
    job_title: str
    candidate_first_name: str | None
    status: str
    question_count: int
    answered_questions: int
    estimated_minutes: int
    expires_at: datetime
    consent_given: bool
    messages: list[ChatMessage]


class PublicStartRequest(BaseModel):
    consent: bool


class PublicMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        return v


class PublicMessageResponse(BaseModel):
    new_messages: list[ChatMessage]
    status: str
    answered_questions: int
    question_count: int
    completed: bool


# ── Evaluations ──────────────────────────────────────────────────────────────


class EvaluationOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    interview_session_id: uuid.UUID
    status: str
    error: str | None
    composite_score: float | None
    recommendation: str | None
    screening_score: float | None
    interview_score: float | None
    components: list[FinalComponent] = Field(default_factory=list)
    rubric: InterviewRubricLLM | None
    bias_audit: BiasAudit | None
    audit_trace: dict | None
    created_at: datetime
    updated_at: datetime


class ApplicationDetail(ApplicationSummary):
    notes: str | None
    filename: str
    raw_text: str
    stage_changed_by: str | None = None
    stage_changed_at: datetime | None = None
    screened_at: datetime | None = None
    screening: ScreeningResult | None
    candidate_profile: ResumeExtraction | None
    experience: ExperienceAnalysis | None
    skills: list[str]
    interview: InterviewOut | None
    evaluation: EvaluationOut | None


# ── Dashboard / fairness / audit ─────────────────────────────────────────────


class KPIs(BaseModel):
    open_jobs: int
    candidates: int
    applications: int
    screened: int
    avg_screening_score: float | None
    interviews_completed: int
    interviews_active: int
    evaluations: int
    flagged_evaluations: int


class CountBucket(BaseModel):
    key: str
    label: str
    count: int


class ActivityItem(BaseModel):
    id: uuid.UUID
    action: str
    actor_type: str
    actor_name: str | None
    entity_type: str | None
    entity_id: uuid.UUID | None
    details: dict
    created_at: datetime


class TopCandidate(BaseModel):
    application_id: uuid.UUID
    candidate_name: str | None
    job_title: str
    score: float
    label: str | None
    final_score: float | None


class Metric(BaseModel):
    value: float | None
    previous: float | None
    delta: float | None


class PeriodMetrics(BaseModel):
    days: int
    screened: Metric
    avg_score: Metric
    shortlisted: Metric
    avg_seconds_to_screen: Metric


class ReviewItem(BaseModel):
    application_id: uuid.UUID
    candidate_name: str | None
    job_title: str
    score: float
    reason: str | None


class DashboardOut(BaseModel):
    kpis: KPIs
    period: PeriodMetrics
    needs_review: list[ReviewItem]
    needs_review_total: int
    funnel: list[CountBucket]
    score_distribution: list[CountBucket]
    recent_activity: list[ActivityItem]
    top_candidates: list[TopCandidate]


class JobFairness(BaseModel):
    job_id: uuid.UUID
    title: str
    score: int
    rating: str
    gender_lean: str
    flags: int
    high_severity: int


class FlaggedEvaluation(BaseModel):
    application_id: uuid.UUID
    candidate_name: str | None
    job_title: str
    delta: float
    risk: str
    created_at: datetime


class FairnessOut(BaseModel):
    blind_screening: bool
    bias_delta_threshold: float
    avg_inclusivity: float | None
    jobs: list[JobFairness]
    evaluations_total: int
    evaluations_flagged: int
    avg_abs_delta: float | None
    risk_counts: dict[str, int]
    redactions: dict[str, int]
    screenings_blind: int
    flagged_evaluations: list[FlaggedEvaluation]
    injection_flags: int


class AuditLogOut(BaseModel):
    id: uuid.UUID
    action: str
    actor_type: str
    actor_name: str | None
    entity_type: str | None
    entity_id: uuid.UUID | None
    details: dict
    ip_address: str | None
    created_at: datetime


class MetaOut(BaseModel):
    version: str
    environment: str
    llm_provider: str
    llm_model: str
    embedding_provider: str
    email_delivery: str
    allow_public_signup: bool
    max_upload_mb: int
    max_files_per_upload: int


# ── Careers page (public) ────────────────────────────────────────────────────


class CareerJob(BaseModel):
    id: uuid.UUID
    title: str
    department: str | None
    location: str | None
    employment_type: str | None
    created_at: datetime


class CareersOut(BaseModel):
    organization_name: str
    slug: str
    jobs: list[CareerJob]


class CareerJobDetail(CareerJob):
    organization_name: str
    description: str


class ApplyResult(BaseModel):
    status: Literal["received"] = "received"
