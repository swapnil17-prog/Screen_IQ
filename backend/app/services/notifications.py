"""
Candidate and recruiter notification emails.

Immediate ones (application received, interview completed) run as background
tasks. Timed ones (rejections after a grace period, expiry reminders) are picked
up by `notification_sweeper`, which runs in the app lifespan. Each row records when
it was handled, and rows are claimed with SKIP LOCKED, so nothing is sent twice even
across instances or restarts. Every send or failure lands in the audit log.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.evaluation import Evaluation
from app.models.interview import InterviewSession
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User
from app.schemas.interview import InterviewPlan
from app.schemas.organization import OrganizationSettings
from app.services import audit
from app.services import email as mailer
from app.services.email_templates import Email, compose, first_name_of, hello
from app.services.interviews import current_link

logger = logging.getLogger(__name__)

RECOMMENDATION_LABELS = {
    "strong_hire": "Strong hire",
    "hire": "Hire",
    "lean_hire": "Lean hire",
    "lean_no_hire": "Lean no hire",
    "no_hire": "No hire",
}


def _org_settings(org: Organization) -> OrganizationSettings:
    return OrganizationSettings.model_validate(org.settings or {})


def app_url(application_id: uuid.UUID) -> str:
    return f"{settings.frontend_url.rstrip('/')}/app/applications/{application_id}"


async def _send(db: AsyncSession, *, org: Organization, entity_id: uuid.UUID, to: str, message: Email,
                kind: str, from_name: str | None = None) -> bool:
    """Send one email and audit the outcome (`notification.sent` / `notification.failed`). Returns success."""
    try:
        delivery = await mailer.send_email(to=to, subject=message.subject, text=message.text, html=message.html,
                                           from_name=from_name or f"{org.name} Hiring")
    except mailer.EmailError as e:
        logger.warning("%s email for %s not sent: %s", kind, entity_id, e.message)
        audit.record(db, organization_id=org.id, actor_type="system", action="notification.failed",
                     entity_type="application", entity_id=entity_id, details={"kind": kind, "reason": e.message})
        return False
    audit.record(db, organization_id=org.id, actor_type="system", action="notification.sent",
                 entity_type="application", entity_id=entity_id, details={"kind": kind, "delivery": delivery})
    return True


# ── Application received (careers page) ──────────────────────────────────────


def render_application_received(*, first_name: str | None, job_title: str, org_name: str) -> Email:
    return compose(
        subject=f"We received your application for {job_title}",
        greeting=hello(first_name),
        paragraphs=[
            f"Thank you for applying for the {job_title} role at {org_name}. We've received your application "
            "and our hiring team will review it.",
            "If your experience is a good match, we'll email you about next steps, which may include a short "
            "online interview you can take at a time that suits you.",
        ],
        footnotes=["You don't need to reply to this email."],
        signoff=f"Best wishes,\nThe {org_name} hiring team",
    )


async def send_application_received(application_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        app = await db.get(Application, application_id)
        if app is None:
            return
        candidate = await db.get(Candidate, app.candidate_id)
        job = await db.get(Job, app.job_id)
        org = await db.get(Organization, app.organization_id)
        if not (candidate and candidate.email and job and org):
            return
        message = render_application_received(first_name=first_name_of(candidate.full_name), job_title=job.title,
                                              org_name=org.name)
        await _send(db, org=org, entity_id=app.id, to=candidate.email, message=message, kind="application_received")
        await db.commit()


# ── Rejections ───────────────────────────────────────────────────────────────


def render_rejection(*, first_name: str | None, job_title: str, org_name: str) -> Email:
    return compose(
        subject=f"Your application for {job_title} at {org_name}",
        greeting=hello(first_name),
        paragraphs=[
            f"Thank you for your interest in the {job_title} role at {org_name}, and for the time you put into "
            "your application.",
            "After careful consideration, we've decided not to move forward with your application for this "
            "position. This was a difficult decision, and it isn't a reflection of your potential.",
            f"We'd be glad to see your application for future roles at {org_name}. We wish you every success "
            "in your search.",
        ],
        signoff=f"Kind regards,\nThe {org_name} hiring team",
    )


async def _rejection_eligible(db: AsyncSession, app: Application) -> bool:
    """Only people who applied themselves or were invited to interview hear back — not sourced resumes."""
    if app.source == "careers":
        return True
    return bool(await db.scalar(select(exists().where(InterviewSession.application_id == app.id))))


async def send_due_rejections(limit: int = 50) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.rejection_email_delay_minutes)
    sent = 0
    async with SessionLocal() as db:
        apps = list(await db.scalars(
            select(Application)
            .where(Application.stage == "rejected", Application.rejected_at <= cutoff,
                   Application.rejection_notified_at.is_(None))
            .order_by(Application.rejected_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ))
        # Claim the batch first (handled whether or not an email goes out), so a crash or a second
        # instance can never send twice
        for app in apps:
            app.rejection_notified_at = datetime.now(UTC)
        await db.commit()
        for app in apps:
            org = await db.get(Organization, app.organization_id)
            candidate = await db.get(Candidate, app.candidate_id)
            job = await db.get(Job, app.job_id)
            if not (org and candidate and candidate.email and job) or not _org_settings(org).email_rejections \
                    or not await _rejection_eligible(db, app):
                continue
            message = render_rejection(first_name=first_name_of(candidate.full_name), job_title=job.title,
                                       org_name=org.name)
            sent += await _send(db, org=org, entity_id=app.id, to=candidate.email, message=message, kind="rejection")
            await db.commit()
        await db.commit()
    return sent


# ── Interview expiry reminders ───────────────────────────────────────────────


def render_reminder(*, first_name: str | None, job_title: str, org_name: str, link: str, expires: str,
                    started: bool) -> Email:
    lead = ("You've started your AI interview" if started else "You haven't started your AI interview yet") + \
        f" for the {job_title} role at {org_name}."
    return compose(
        subject=f"Reminder: your {job_title} interview link expires on {expires}",
        greeting=hello(first_name),
        paragraphs=[
            lead,
            f"Your interview link expires on {expires}. "
            + ("You can pick up where you left off." if started else "It only takes a few minutes to complete."),
        ],
        button=("Continue your interview" if started else "Start your interview", link),
        footnotes=["This link is personal to you, so please don't share it. If you're no longer interested, "
                   "you can ignore this email."],
        signoff=f"Best wishes,\nThe {org_name} hiring team",
    )


async def send_due_reminders(limit: int = 50) -> int:
    now = datetime.now(UTC)
    sent = 0
    async with SessionLocal() as db:
        sessions = list(await db.scalars(
            select(InterviewSession)
            .where(InterviewSession.status.in_(("pending", "in_progress")),
                   InterviewSession.reminder_sent_at.is_(None),
                   InterviewSession.expires_at > now,
                   InterviewSession.expires_at <= now + timedelta(hours=settings.interview_reminder_hours),
                   # Don't nag someone who was invited moments ago
                   InterviewSession.created_at <= now - timedelta(hours=24))
            .order_by(InterviewSession.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ))
        for session in sessions:
            session.reminder_sent_at = now
        await db.commit()
        for session in sessions:
            link = current_link(session)
            app = await db.get(Application, session.application_id)
            org = await db.get(Organization, session.organization_id)
            candidate = await db.get(Candidate, app.candidate_id) if app else None
            job = await db.get(Job, app.job_id) if app else None
            if not (link and app and app.stage != "rejected" and org and candidate and candidate.email and job) \
                    or not _org_settings(org).interview_reminders:
                continue
            message = render_reminder(first_name=first_name_of(candidate.full_name), job_title=job.title,
                                      org_name=org.name, link=link, expires=f"{session.expires_at:%d %B %Y}",
                                      started=session.started_at is not None)
            sent += await _send(db, org=org, entity_id=app.id, to=candidate.email, message=message,
                                kind="interview_reminder")
            await db.commit()
        await db.commit()
    return sent


# ── Recruiter alert: interview completed ─────────────────────────────────────


def render_completion(*, recipient_first_name: str | None, candidate_name: str, job_title: str, url: str,
                      questions: int, evaluation: Evaluation | None) -> Email:
    if evaluation and evaluation.status == "completed" and evaluation.composite_score is not None:
        rec = RECOMMENDATION_LABELS.get(evaluation.recommendation or "", evaluation.recommendation or "—")
        result = (f"The AI evaluation is ready: final score {evaluation.composite_score:.0f}/100, "
                  f"recommendation: {rec}.")
        if (evaluation.bias_audit or {}).get("risk") in ("medium", "high"):
            result += " The bias audit flagged this evaluation for human review."
    else:
        result = "The AI evaluation couldn't be completed automatically. You can re-run it from the candidate's page."
    return compose(
        subject=f"{candidate_name} completed their AI interview for {job_title}",
        greeting=hello(recipient_first_name),
        paragraphs=[f"{candidate_name} has finished the {questions}-question AI interview for {job_title}.", result],
        button=("Review the interview", url),
        signoff="— ScreenIQ",
    )


async def notify_interview_completed(session_id: uuid.UUID) -> None:
    """Email the recruiter who set up the interview (or the workspace admins) once it's evaluated. Sent once."""
    async with SessionLocal() as db:
        session = await db.scalar(select(InterviewSession).where(InterviewSession.id == session_id)
                                  .with_for_update(skip_locked=True))
        if session is None or session.status != "completed" or session.completion_notified_at is not None:
            return
        session.completion_notified_at = datetime.now(UTC)
        app = await db.get(Application, session.application_id)
        org = await db.get(Organization, session.organization_id)
        if not (app and org) or not _org_settings(org).notify_on_interview_complete:
            await db.commit()
            return
        candidate = await db.get(Candidate, app.candidate_id)
        job = await db.get(Job, app.job_id)
        evaluation = await db.scalar(select(Evaluation).where(Evaluation.interview_session_id == session.id))

        owner = await db.get(User, session.created_by_id) if session.created_by_id else None
        if owner and owner.is_active:
            recipients = [owner]
        else:
            recipients = list(await db.scalars(select(User).where(
                User.organization_id == org.id, User.is_active.is_(True), User.role.in_(("owner", "admin")))))
        for user in recipients:
            message = render_completion(
                recipient_first_name=first_name_of(user.full_name),
                candidate_name=(candidate.full_name if candidate else None) or "A candidate",
                job_title=job.title if job else "the role",
                url=app_url(app.id),
                questions=len(InterviewPlan.model_validate(session.plan).questions),
                evaluation=evaluation,
            )
            await _send(db, org=org, entity_id=app.id, to=user.email, message=message, kind="interview_completed",
                        from_name=settings.app_name)
        await db.commit()


# ── Sweeper ──────────────────────────────────────────────────────────────────


async def notification_sweeper() -> None:
    """Long-running loop started from the app lifespan."""
    while True:
        for job in (send_due_rejections, send_due_reminders):
            try:
                await job()
            except Exception:
                logger.exception("Notification sweep %s failed", job.__name__)
        await asyncio.sleep(settings.notification_sweep_seconds)
