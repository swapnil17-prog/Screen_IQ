"""ORM rows → API models. Kept in one place so every endpoint renders consistently."""

from datetime import UTC, datetime

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.evaluation import Evaluation
from app.models.interview import InterviewSession
from app.models.job import Job
from app.schemas.api import (
    ApplicationSummary,
    CandidateRef,
    CandidateSummary,
    EvaluationOut,
    InterviewOut,
    SkillChip,
)
from app.schemas.evaluation import BiasAudit, FinalComponent, InterviewRubricLLM
from app.schemas.interview import ChatMessage, InterviewPlan
from app.services.scoring import tier_for


def candidate_ref(c: Candidate) -> CandidateRef:
    return CandidateRef(
        id=c.id,
        full_name=c.full_name,
        headline=c.headline,
        current_company=(c.experience or {}).get("current_company"),
        email=c.email,
        location=c.location,
    )


def _one_liner(screening: dict) -> str | None:
    if screening.get("one_liner"):
        return screening["one_liner"]
    summary = screening.get("summary") or ""
    first = summary.split(". ")[0].strip().rstrip(".")
    return (first[:120] + ("…" if len(first) > 120 else "")) or None


def _skill_chips(screening: dict) -> list[SkillChip]:
    """Every criterion skill in criteria order (must-haves first) with its match status."""
    matches = (screening.get("skill_gap") or {}).get("matches", [])
    return [SkillChip(skill=m["skill"], importance=m["importance"], status=m["status"]) for m in matches]


def application_summary(
    app: Application, candidate: Candidate, job: Job | None = None, interview_status: str | None = None
) -> ApplicationSummary:
    s = app.screening or {}
    gap = s.get("skill_gap") or {}
    exp = (candidate.experience or {}) if candidate else {}
    return ApplicationSummary(
        id=app.id,
        job_id=app.job_id,
        job_title=job.title if job else None,
        candidate=candidate_ref(candidate),
        stage=app.stage,  # type: ignore[arg-type]
        status=app.status,
        error=app.error,
        screening_score=app.screening_score,
        screening_label=app.screening_label,
        tier=tier_for(app.screening_score) if app.status == "completed" else None,  # type: ignore[arg-type]
        one_liner=_one_liner(s) if s else None,
        skill_chips=_skill_chips(s) if s else [],
        final_score=app.final_score,
        recommendation=app.recommendation,
        confidence=s.get("confidence"),
        required_coverage_pct=gap.get("required_coverage_pct") if s else None,
        missing_required=gap.get("missing_required", []),
        total_years=exp.get("total_years"),
        flags=s.get("flags", []),
        interview_status=interview_status,
        source=app.source,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


def candidate_summary(c: Candidate, applications_count: int = 0, similarity: float | None = None) -> CandidateSummary:
    return CandidateSummary(
        id=c.id,
        full_name=c.full_name,
        email=c.email,
        headline=c.headline,
        location=c.location,
        status=c.status,
        error=c.error,
        skills=(c.skills or [])[:12],
        total_years=(c.experience or {}).get("total_years"),
        applications_count=applications_count,
        created_at=c.created_at,
        similarity=similarity,
    )


def effective_interview_status(s: InterviewSession) -> str:
    if s.status in ("pending", "in_progress") and s.expires_at < datetime.now(UTC):
        return "expired"
    return s.status


def answered_questions(s: InterviewSession) -> int:
    answered = {m.get("question_id") for m in (s.messages or []) if m.get("role") == "candidate"}
    return len(answered)


def interview_out(s: InterviewSession, link: str | None = None) -> InterviewOut:
    return InterviewOut(
        id=s.id,
        application_id=s.application_id,
        status=effective_interview_status(s),
        plan=InterviewPlan.model_validate(s.plan),
        current_question_index=s.current_question_index,
        answered_questions=answered_questions(s),
        messages=[ChatMessage.model_validate(m) for m in s.messages or []],
        consent_at=s.consent_at,
        started_at=s.started_at,
        completed_at=s.completed_at,
        expires_at=s.expires_at,
        created_at=s.created_at,
        link=link,
    )


def evaluation_out(e: Evaluation) -> EvaluationOut:
    trace = e.audit_trace or {}
    return EvaluationOut(
        id=e.id,
        application_id=e.application_id,
        interview_session_id=e.interview_session_id,
        status=e.status,
        error=e.error,
        composite_score=e.composite_score,
        recommendation=e.recommendation,
        screening_score=e.screening_score,
        interview_score=e.interview_score,
        components=[FinalComponent.model_validate(c) for c in trace.get("components", [])],
        rubric=InterviewRubricLLM.model_validate(e.rubric) if e.rubric else None,
        bias_audit=BiasAudit.model_validate(e.bias_audit) if e.bias_audit else None,
        audit_trace=e.audit_trace,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )
