"""Read-only aggregate views: dashboard, fairness center, interview list, audit log."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DB, Admin, Auth
from app.api.serializers import answered_questions, effective_interview_status
from app.models.application import Application
from app.models.audit import AuditLog
from app.models.candidate import Candidate
from app.models.evaluation import Evaluation
from app.models.interview import InterviewSession
from app.models.job import Job
from app.models.user import User
from app.schemas.api import (
    ActivityItem,
    AuditLogOut,
    CountBucket,
    DashboardOut,
    FairnessOut,
    FlaggedEvaluation,
    InterviewListItem,
    JobFairness,
    KPIs,
    Metric,
    Page,
    PeriodMetrics,
    ReviewItem,
    TopCandidate,
)
from app.schemas.interview import InterviewPlan
from app.services.pipeline import org_settings_of
from app.services.scoring import TIER_REVIEW, TIER_STRONG

router = APIRouter(tags=["insights"])

STAGE_LABELS = [("new", "New"), ("shortlisted", "Shortlisted"), ("interviewing", "Interviewing"),
                ("offer", "Offer"), ("hired", "Hired"), ("rejected", "Rejected")]
BUCKETS = [(0, 40, "0–39"), (40, 50, "40–49"), (50, 65, "50–64"), (65, 80, "65–79"), (80, 101, "80–100")]


async def _activity(db: DB, org_id, limit: int) -> list[ActivityItem]:
    rows = await db.execute(
        select(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.organization_id == org_id, AuditLog.action != "user.login")
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return [
        ActivityItem(id=a.id, action=a.action, actor_type=a.actor_type, actor_name=name, entity_type=a.entity_type,
                     entity_id=a.entity_id, details=a.details or {}, created_at=a.created_at)
        for a, name in rows
    ]


def _metric(value: float | None, previous: float | None) -> Metric:
    delta = None if value is None or previous is None else round(value - previous, 1)
    return Metric(value=value, previous=previous, delta=delta)


async def _period(db: DB, org_id, start: datetime, end: datetime) -> tuple[float, float | None, float, float | None]:
    """(screened, avg score, shortlisted, avg seconds to screen) for applications screened in [start, end)."""
    row = (await db.execute(
        select(
            func.count(),
            func.avg(Application.screening_score),
            func.avg(func.extract("epoch", Application.screened_at - Application.created_at)),
        ).where(Application.organization_id == org_id, Application.status == "completed",
                Application.screened_at >= start, Application.screened_at < end)
    )).one()
    shortlisted = await db.scalar(
        select(func.count()).where(
            AuditLog.organization_id == org_id, AuditLog.action == "application.stage_changed",
            AuditLog.details["to"].astext == "shortlisted", AuditLog.created_at >= start, AuditLog.created_at < end,
        )
    ) or 0
    avg = round(float(row[1]), 1) if row[1] is not None else None
    secs = round(float(row[2]), 1) if row[2] is not None else None
    return float(row[0]), avg, float(shortlisted), secs


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(auth: Auth, db: DB, days: int = Query(7, ge=1, le=365)) -> DashboardOut:
    org = auth.org_id
    open_jobs = await db.scalar(select(func.count()).where(Job.organization_id == org, Job.status == "open")) or 0
    candidates = await db.scalar(select(func.count()).where(Candidate.organization_id == org)) or 0
    apps = await db.execute(
        select(
            func.count(),
            func.count().filter(Application.status == "completed"),
            func.avg(Application.screening_score),
        ).where(Application.organization_id == org)
    )
    total_apps, screened, avg_score = apps.one()
    now = datetime.now(UTC)
    interviews = await db.execute(
        select(
            func.count().filter(InterviewSession.status == "completed"),
            func.count().filter(InterviewSession.status.in_(("pending", "in_progress")),
                                InterviewSession.expires_at > now),
        ).where(InterviewSession.organization_id == org)
    )
    completed_iv, active_iv = interviews.one()
    evals = await db.execute(
        select(
            func.count().filter(Evaluation.status == "completed"),
            func.count().filter(Evaluation.bias_audit["flagged"].as_boolean().is_(True)),
        ).where(Evaluation.organization_id == org)
    )
    eval_count, flagged = evals.one()

    stage_counts = dict((await db.execute(
        select(Application.stage, func.count()).where(Application.organization_id == org).group_by(Application.stage)
    )).all())
    funnel = [CountBucket(key=k, label=label, count=stage_counts.get(k, 0)) for k, label in STAGE_LABELS]

    scores = [s for (s,) in (await db.execute(
        select(Application.screening_score).where(Application.organization_id == org,
                                                  Application.screening_score.is_not(None))
    )).all()]
    distribution = [
        CountBucket(key=f"{lo}", label=label, count=sum(1 for s in scores if lo <= s < hi))
        for lo, hi, label in BUCKETS
    ]

    top_rows = await db.execute(
        select(Application, Candidate.full_name, Job.title)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Application.organization_id == org, Application.screening_score.is_not(None),
               Application.stage != "rejected", Job.status == "open")
        .order_by(func.coalesce(Application.final_score, Application.screening_score).desc())
        .limit(6)
    )
    top = [
        TopCandidate(application_id=a.id, candidate_name=name, job_title=title, score=a.screening_score,
                     label=a.screening_label, final_score=a.final_score)
        for a, name, title in top_rows
    ]
    cur = await _period(db, org, now - timedelta(days=days), now)
    prev = await _period(db, org, now - timedelta(days=2 * days), now - timedelta(days=days))
    period = PeriodMetrics(
        days=days,
        screened=_metric(cur[0], prev[0]),
        avg_score=_metric(cur[1], prev[1]),
        shortlisted=_metric(cur[2], prev[2]),
        avg_seconds_to_screen=_metric(cur[3], prev[3]),
    )

    # Screened, un-actioned candidates in the "needs review" band on open jobs
    review_filter = (
        Application.organization_id == org, Application.status == "completed", Application.stage == "new",
        Application.screening_score >= TIER_REVIEW, Application.screening_score < TIER_STRONG, Job.status == "open",
    )
    review_total = await db.scalar(
        select(func.count()).select_from(Application).join(Job, Job.id == Application.job_id).where(*review_filter)
    ) or 0
    review_rows = await db.execute(
        select(Application, Candidate.full_name, Job.title)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(*review_filter)
        .order_by(Application.screening_score.desc())
        .limit(6)
    )
    needs_review = []
    for a, name, title in review_rows:
        s = a.screening or {}
        missing = (s.get("skill_gap") or {}).get("missing_required") or []
        reason = (f"Missing must-have: {missing[0]}" if missing else None) or s.get("one_liner") or             (s.get("concerns") or [None])[0]
        needs_review.append(ReviewItem(application_id=a.id, candidate_name=name, job_title=title,
                                       score=a.screening_score, reason=reason))

    return DashboardOut(
        period=period,
        needs_review=needs_review,
        needs_review_total=review_total,
        kpis=KPIs(open_jobs=open_jobs, candidates=candidates, applications=total_apps, screened=screened,
                  avg_screening_score=round(float(avg_score), 1) if avg_score is not None else None,
                  interviews_completed=completed_iv, interviews_active=active_iv, evaluations=eval_count,
                  flagged_evaluations=flagged),
        funnel=funnel,
        score_distribution=distribution,
        recent_activity=await _activity(db, org, 12),
        top_candidates=top,
    )


@router.get("/fairness", response_model=FairnessOut)
async def fairness(auth: Auth, db: DB) -> FairnessOut:
    org = auth.org_id
    org_settings = org_settings_of(auth.org)
    jobs = list(await db.scalars(
        select(Job).where(Job.organization_id == org, Job.status != "archived").order_by(Job.created_at.desc())
    ))
    job_rows = []
    for j in jobs:
        report = j.bias_report or {}
        if not report:
            continue
        flags = report.get("flags", [])
        job_rows.append(JobFairness(
            job_id=j.id, title=j.title, score=report.get("score", 0), rating=report.get("rating", "inclusive"),
            gender_lean=report.get("gender_lean", "neutral"), flags=len(flags),
            high_severity=sum(1 for f in flags if f.get("severity") == "high"),
        ))

    eval_rows = (await db.execute(
        select(Evaluation, Candidate.full_name, Job.title)
        .join(Application, Application.id == Evaluation.application_id)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Evaluation.organization_id == org, Evaluation.status == "completed")
        .order_by(Evaluation.updated_at.desc())
    )).all()
    risk_counts = {"low": 0, "medium": 0, "high": 0}
    deltas: list[float] = []
    flagged: list[FlaggedEvaluation] = []
    for ev, name, title in eval_rows:
        audit = ev.bias_audit or {}
        risk = audit.get("risk", "low")
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
        deltas.append(abs(float(audit.get("delta", 0))))
        if risk != "low":
            flagged.append(FlaggedEvaluation(application_id=ev.application_id, candidate_name=name, job_title=title,
                                             delta=float(audit.get("delta", 0)), risk=risk, created_at=ev.updated_at))

    redactions: dict[str, int] = {}
    blind = 0
    injection = 0
    for (screening,) in (await db.execute(
        select(Application.screening).where(Application.organization_id == org, Application.screening.is_not(None))
    )).all():
        if screening.get("blind_screening"):
            blind += 1
        for k, v in (screening.get("redactions") or {}).items():
            redactions[k] = redactions.get(k, 0) + int(v)
        if any("instructions to AI" in f for f in screening.get("flags", [])):
            injection += 1

    return FairnessOut(
        blind_screening=org_settings.blind_screening,
        bias_delta_threshold=org_settings.bias_delta_threshold,
        avg_inclusivity=round(sum(j.score for j in job_rows) / len(job_rows), 1) if job_rows else None,
        jobs=job_rows,
        evaluations_total=len(eval_rows),
        evaluations_flagged=risk_counts.get("high", 0),
        avg_abs_delta=round(sum(deltas) / len(deltas), 2) if deltas else None,
        risk_counts=risk_counts,
        redactions=dict(sorted(redactions.items(), key=lambda kv: -kv[1])),
        screenings_blind=blind,
        flagged_evaluations=flagged[:20],
        injection_flags=injection,
    )


@router.get("/interviews", response_model=list[InterviewListItem])
async def list_interviews(auth: Auth, db: DB, status: str | None = None) -> list[InterviewListItem]:
    rows = (await db.execute(
        select(InterviewSession, Application, Candidate.full_name, Job.title)
        .join(Application, Application.id == InterviewSession.application_id)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(InterviewSession.organization_id == auth.org_id, InterviewSession.status != "cancelled")
        .order_by(InterviewSession.created_at.desc())
        .limit(200)
    )).all()
    items = []
    for s, app, name, title in rows:
        eff = effective_interview_status(s)
        if status and eff != status:
            continue
        items.append(InterviewListItem(
            id=s.id, application_id=app.id, job_id=app.job_id, job_title=title, candidate_name=name, status=eff,
            answered_questions=answered_questions(s), total_questions=len(InterviewPlan.model_validate(s.plan).questions),
            created_at=s.created_at, completed_at=s.completed_at, expires_at=s.expires_at,
            final_score=app.final_score, recommendation=app.recommendation,
        ))
    return items


@router.get("/audit-logs", response_model=Page[AuditLogOut])
async def audit_logs(
    auth: Admin,
    db: DB,
    action: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[AuditLogOut]:
    conditions = [AuditLog.organization_id == auth.org_id]
    if action:
        conditions.append(AuditLog.action.ilike(f"{action}%"))
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0
    rows = await db.execute(
        select(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        AuditLogOut(id=a.id, action=a.action, actor_type=a.actor_type, actor_name=name, entity_type=a.entity_type,
                    entity_id=a.entity_id, details=a.details or {}, ip_address=a.ip_address, created_at=a.created_at)
        for a, name in rows
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)
