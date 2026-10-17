"""
Candidate-facing interview endpoints. No login: access is granted by the
unguessable link token (only its hash is stored). Rate limited per IP.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, client_ip
from app.api.routes.applications import start_evaluation
from app.api.serializers import answered_questions, effective_interview_status
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.core.rate_limit import RateLimiter
from app.core.security import hash_token
from app.llm.client import LLMError
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import InterviewSession
from app.models.job import Job
from app.models.organization import Organization
from app.schemas.api import PublicInterviewOut, PublicMessageRequest, PublicMessageResponse, PublicStartRequest
from app.schemas.interview import ChatMessage, InterviewPlan
from app.services import audit, tasks
from app.services.interviews import apply_turn, decide_turn
from app.services.pipeline import run_evaluation

router = APIRouter(prefix="/public/interviews", tags=["candidate interview"],
                   dependencies=[Depends(RateLimiter(settings.rate_limit_public_per_minute, scope="public"))])


async def _session_for(db: AsyncSession, token: str, *, lock: bool = False) -> InterviewSession:
    if len(token) < 20 or len(token) > 100:
        raise NotFoundError("This interview link is invalid.")
    stmt = select(InterviewSession).where(InterviewSession.token_hash == hash_token(token))
    if lock:
        stmt = stmt.with_for_update()
    session = await db.scalar(stmt)
    if session is None or session.status == "cancelled":
        raise NotFoundError("This interview link is invalid or has been withdrawn.")
    return session


async def _view(db: AsyncSession, session: InterviewSession) -> PublicInterviewOut:
    app = await db.get(Application, session.application_id)
    job = await db.get(Job, app.job_id) if app else None
    candidate = await db.get(Candidate, app.candidate_id) if app else None
    org = await db.get(Organization, session.organization_id)
    plan = InterviewPlan.model_validate(session.plan)
    consented = session.consent_at is not None
    return PublicInterviewOut(
        organization_name=org.name if org else "the hiring team",
        job_title=job.title if job else "the role",
        candidate_first_name=((candidate.full_name or "").split(" ")[0] or None) if candidate else None,
        status=effective_interview_status(session),
        question_count=len(plan.questions),
        answered_questions=answered_questions(session),
        estimated_minutes=plan.estimated_minutes,
        expires_at=session.expires_at,
        consent_given=consented,
        # The transcript is only revealed after consent
        messages=[ChatMessage.model_validate(m) for m in session.messages] if consented else [],
    )


def _ensure_open(session: InterviewSession) -> None:
    status = effective_interview_status(session)
    if status == "expired":
        raise UnprocessableError("This interview link has expired. Please contact the recruiter for a new one.")
    if status == "completed":
        raise ConflictError("This interview is already complete. Thank you!")


@router.get("/{token}", response_model=PublicInterviewOut)
async def get_interview(token: str, db: DB) -> PublicInterviewOut:
    return await _view(db, await _session_for(db, token))


@router.post("/{token}/start", response_model=PublicInterviewOut)
async def start_interview(token: str, body: PublicStartRequest, request: Request, db: DB) -> PublicInterviewOut:
    session = await _session_for(db, token, lock=True)
    _ensure_open(session)
    if not body.consent:
        raise UnprocessableError("Please confirm you've read how your responses will be used.")
    now = datetime.now(UTC)
    if session.consent_at is None:
        session.consent_at = now
        session.started_at = now
        session.status = "in_progress"
        audit.record(db, organization_id=session.organization_id, actor_type="candidate",
                     action="interview.started", entity_type="application", entity_id=session.application_id,
                     ip_address=client_ip(request))
        await db.commit()
    return await _view(db, session)


@router.post("/{token}/messages", response_model=PublicMessageResponse)
async def send_message(token: str, body: PublicMessageRequest, request: Request, db: DB) -> PublicMessageResponse:
    # Row lock serialises concurrent submissions for the same interview
    session = await _session_for(db, token, lock=True)
    _ensure_open(session)
    if session.consent_at is None:
        raise UnprocessableError("Please start the interview first.")
    answer = body.message[: settings.interview_max_answer_chars]
    plan = InterviewPlan.model_validate(session.plan)
    messages = list(session.messages or [])

    # Idempotency: ignore an identical re-submission (double click / retry after timeout)
    last_answer = next((m for m in reversed(messages) if m["role"] == "candidate"), None)
    if last_answer and last_answer["content"] == answer and \
            datetime.fromisoformat(last_answer["timestamp"]) > datetime.now(UTC) - timedelta(minutes=2):
        tail = messages[messages.index(last_answer) + 1:]
        return PublicMessageResponse(
            new_messages=[ChatMessage.model_validate(m) for m in tail], status=session.status,
            answered_questions=answered_questions(session), question_count=len(plan.questions),
            completed=session.status == "completed",
        )

    question = plan.questions[session.current_question_index]
    try:
        decision = await decide_turn(
            question=question,
            messages=messages,
            answer=answer,
            follow_ups_remaining=max(0, plan.max_follow_ups - session.follow_up_count),
        )
    except LLMError as e:
        raise UnprocessableError(
            "The interviewer is temporarily unavailable. Your answer wasn't lost — please send it again."
        ) from e

    before = len(messages)
    messages, next_index, follow_ups, completed = apply_turn(
        plan=plan, messages=messages, current_index=session.current_question_index,
        follow_up_count=session.follow_up_count, answer=answer, decision=decision,
    )
    session.messages = messages
    session.current_question_index = next_index
    session.follow_up_count = follow_ups
    evaluation_id = None
    if completed:
        session.status = "completed"
        session.completed_at = datetime.now(UTC)
        audit.record(db, organization_id=session.organization_id, actor_type="candidate",
                     action="interview.completed", entity_type="application", entity_id=session.application_id,
                     ip_address=client_ip(request))
        evaluation = await start_evaluation(db, session, session.organization_id)
        evaluation_id = evaluation.id
    await db.commit()
    if evaluation_id:
        tasks.spawn(run_evaluation(evaluation_id), name=f"evaluation-{evaluation_id}")

    return PublicMessageResponse(
        new_messages=[ChatMessage.model_validate(m) for m in messages[before + 1:]],
        status=session.status,
        answered_questions=answered_questions(session),
        question_count=len(plan.questions),
        completed=completed,
    )
