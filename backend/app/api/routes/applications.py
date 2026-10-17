import uuid

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, Auth, Writer, client_ip, get_owned
from app.api.serializers import (
    application_summary,
    effective_interview_status,
    evaluation_out,
    interview_out,
)
from app.core.errors import ConflictError, UnprocessableError
from app.llm.client import LLMError
from app.models.application import Application
from app.models.audit import AuditLog
from app.models.candidate import Candidate
from app.models.evaluation import Evaluation
from app.models.interview import InterviewSession
from app.models.job import Job
from app.models.user import User
from app.schemas.api import ApplicationDetail, ApplicationUpdate, EvaluationOut, InterviewOut
from app.schemas.extraction import ResumeExtraction
from app.schemas.screening import ExperienceAnalysis, ScreeningResult
from app.services import audit, tasks
from app.services.interviews import interview_link, open_session, rotate_link
from app.services.invites import send_shortlist_invite
from app.services.pipeline import org_settings_of, run_application, run_evaluation

router = APIRouter(prefix="/applications", tags=["applications"])


async def _load(db: AsyncSession, application_id: uuid.UUID, org_id: uuid.UUID) -> tuple[Application, Candidate, Job]:
    app = await get_owned(db, Application, application_id, org_id, "Application")
    candidate = await db.get(Candidate, app.candidate_id)
    job = await db.get(Job, app.job_id)
    return app, candidate, job  # type: ignore[return-value]


async def _latest_session(db: AsyncSession, application_id: uuid.UUID) -> InterviewSession | None:
    return await db.scalar(
        select(InterviewSession)
        .where(InterviewSession.application_id == application_id, InterviewSession.status != "cancelled")
        .order_by(InterviewSession.created_at.desc())
        .limit(1)
    )


@router.get("/{application_id}", response_model=ApplicationDetail)
async def get_application(application_id: uuid.UUID, auth: Auth, db: DB) -> ApplicationDetail:
    app, candidate, job = await _load(db, application_id, auth.org_id)
    session = await _latest_session(db, app.id)
    evaluation = await db.scalar(
        select(Evaluation).where(Evaluation.interview_session_id == session.id)
    ) if session else None
    summary = application_summary(app, candidate, job, effective_interview_status(session) if session else None)
    last_move = (await db.execute(
        select(AuditLog.created_at, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.entity_id == app.id, AuditLog.action == "application.stage_changed")
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )).first()
    return ApplicationDetail(
        **summary.model_dump(),
        notes=app.notes,
        filename=candidate.filename,
        raw_text=candidate.raw_text,
        stage_changed_by=last_move.full_name if last_move else None,
        stage_changed_at=last_move.created_at if last_move else None,
        screened_at=app.screened_at,
        screening=ScreeningResult.model_validate(app.screening) if app.screening else None,
        candidate_profile=ResumeExtraction.model_validate(candidate.extracted) if candidate.extracted else None,
        experience=ExperienceAnalysis.model_validate(candidate.experience) if candidate.experience else None,
        skills=candidate.skills or [],
        interview=interview_out(session) if session else None,
        evaluation=evaluation_out(evaluation) if evaluation else None,
    )


@router.patch("/{application_id}", response_model=ApplicationDetail)
async def update_application(application_id: uuid.UUID, body: ApplicationUpdate, auth: Writer, request: Request,
                             db: DB) -> ApplicationDetail:
    app, _, _ = await _load(db, application_id, auth.org_id)
    details: dict = {}
    if body.stage is not None and body.stage != app.stage:
        details = {"from": app.stage, "to": body.stage}
        app.stage = body.stage
    if body.notes is not None:
        app.notes = body.notes
    if details:
        audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="application.stage_changed",
                     entity_type="application", entity_id=app.id, details=details, ip_address=client_ip(request))
    await db.commit()
    if details.get("to") == "shortlisted" and org_settings_of(auth.org).auto_invite_on_shortlist:
        tasks.spawn(send_shortlist_invite(app.id, auth.user.id), name=f"invite-{app.id}")
    return await get_application(application_id, auth, db)


@router.post("/{application_id}/rescreen", response_model=ApplicationDetail)
async def rescreen(application_id: uuid.UUID, auth: Writer, db: DB) -> ApplicationDetail:
    """Retry a failed screening, or re-run a completed one (e.g. after changing weights)."""
    app, _, _ = await _load(db, application_id, auth.org_id)
    if app.status not in ("completed", "failed"):
        raise ConflictError("Screening is already in progress.")
    app.status, app.error = "queued", None
    await db.commit()
    tasks.spawn(run_application(app.id), name=f"application-{app.id}")
    return await get_application(application_id, auth, db)


@router.post("/{application_id}/interview", response_model=InterviewOut)
async def create_interview(application_id: uuid.UUID, auth: Writer, request: Request, db: DB,
                           replace: bool = False) -> InterviewOut:
    """Generate a candidate-specific, gap-aware interview and a private candidate link."""
    app, candidate, job = await _load(db, application_id, auth.org_id)
    if app.status != "completed" or not app.screening:
        raise UnprocessableError("Screening must finish before an interview can be generated.")
    existing = await _latest_session(db, app.id)
    if existing and effective_interview_status(existing) in ("pending", "in_progress"):
        if not replace:
            raise ConflictError("An interview is already open for this candidate.")
        existing.status = "cancelled"

    try:
        session, token = await open_session(app=app, candidate=candidate, job=job, org_name=auth.org.name,
                                            org_settings=org_settings_of(auth.org))
    except LLMError as e:
        raise UnprocessableError(e.message) from e
    except ValueError as e:
        raise UnprocessableError(str(e)) from e

    db.add(session)
    if app.stage in ("new", "shortlisted"):
        app.stage = "interviewing"
    await db.flush()
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="interview.created",
                 entity_type="application", entity_id=app.id,
                 details={"questions": len(session.plan["questions"]), "replaced": bool(existing and replace)},
                 ip_address=client_ip(request))
    await db.commit()
    await db.refresh(session)
    return interview_out(session, link=interview_link(token))


@router.post("/{application_id}/interview/link", response_model=InterviewOut)
async def regenerate_link(application_id: uuid.UUID, auth: Writer, request: Request, db: DB) -> InterviewOut:
    """Issue a fresh candidate link (old link stops working) and extend the expiry."""
    app, _, _ = await _load(db, application_id, auth.org_id)
    session = await _latest_session(db, app.id)
    if session is None:
        raise UnprocessableError("No interview exists for this candidate yet.")
    if session.status == "completed":
        raise ConflictError("This interview is already complete.")
    token = rotate_link(session)
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="interview.link_regenerated",
                 entity_type="application", entity_id=app.id, ip_address=client_ip(request))
    await db.commit()
    await db.refresh(session)
    return interview_out(session, link=interview_link(token))


@router.post("/{application_id}/interview/cancel", response_model=ApplicationDetail)
async def cancel_interview(application_id: uuid.UUID, auth: Writer, request: Request, db: DB) -> ApplicationDetail:
    app, _, _ = await _load(db, application_id, auth.org_id)
    session = await _latest_session(db, app.id)
    if session is None or session.status == "completed":
        raise UnprocessableError("There is no open interview to cancel.")
    session.status = "cancelled"
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="interview.cancelled",
                 entity_type="application", entity_id=app.id, ip_address=client_ip(request))
    await db.commit()
    return await get_application(application_id, auth, db)


async def start_evaluation(db: AsyncSession, session: InterviewSession, org_id: uuid.UUID) -> Evaluation:
    evaluation = await db.scalar(select(Evaluation).where(Evaluation.interview_session_id == session.id))
    if evaluation is None:
        evaluation = Evaluation(organization_id=org_id, application_id=session.application_id,
                                interview_session_id=session.id, status="running")
        db.add(evaluation)
    else:
        evaluation.status, evaluation.error = "running", None
    await db.flush()
    return evaluation


@router.post("/{application_id}/evaluation", response_model=EvaluationOut)
async def run_final_evaluation(application_id: uuid.UUID, auth: Writer, request: Request, db: DB) -> EvaluationOut:
    """(Re)run the LLM-as-a-judge rubric, counterfactual bias audit and composite scoring."""
    app, _, _ = await _load(db, application_id, auth.org_id)
    session = await _latest_session(db, app.id)
    if session is None or not any(m.get("role") == "candidate" for m in session.messages or []):
        raise UnprocessableError("The candidate hasn't answered any interview questions yet.")
    existing = await db.scalar(select(Evaluation).where(Evaluation.interview_session_id == session.id))
    if existing and existing.status == "running":
        raise ConflictError("An evaluation is already running.")
    evaluation = await start_evaluation(db, session, auth.org_id)
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="evaluation.requested",
                 entity_type="application", entity_id=app.id, ip_address=client_ip(request))
    await db.commit()
    await db.refresh(evaluation)
    tasks.spawn(run_evaluation(evaluation.id), name=f"evaluation-{evaluation.id}")
    return evaluation_out(evaluation)
