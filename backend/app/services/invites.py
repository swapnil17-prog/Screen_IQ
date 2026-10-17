"""
Shortlist → interview invitation.

When a recruiter shortlists a candidate (and the workspace has
`auto_invite_on_shortlist` on), a background task generates the candidate's AI
interview and emails them the private link. The outcome is written to the audit
log either way, so a failed delivery is visible to the team.
"""

import asyncio
import html
import logging
import uuid
from collections import defaultdict

from sqlalchemy import select

from app.core.database import SessionLocal
from app.llm.client import LLMError
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import InterviewSession
from app.models.job import Job
from app.models.organization import Organization
from app.schemas.interview import InterviewPlan
from app.services import audit
from app.services import email as mailer
from app.services.interviews import interview_link, open_session, rotate_link
from app.services.pipeline import org_settings_of

logger = logging.getLogger(__name__)

_invite_locks: defaultdict[uuid.UUID, asyncio.Lock] = defaultdict(asyncio.Lock)


def render_invite(*, first_name: str | None, job_title: str, org_name: str, link: str, questions: int,
                  minutes: int, expires: str) -> tuple[str, str, str]:
    """Returns (subject, plain text, HTML)."""
    hello = f"Hi {first_name}," if first_name else "Hi there,"
    subject = f"Congratulations! You've been shortlisted for {job_title} at {org_name}"
    text = (
        f"{hello}\n\n"
        f"Congratulations! You have been shortlisted for the {job_title} role at {org_name}.\n\n"
        f"The next step is a short AI interview: {questions} written questions about your experience, "
        f"taking about {minutes} minutes. You can take it whenever suits you, from any device.\n\n"
        f"Start your interview:\n{link}\n\n"
        f"This link is personal to you, so please don't share it. It expires on {expires}.\n"
        "Your responses will be reviewed by a person on the hiring team.\n\n"
        f"Good luck!\nThe {org_name} hiring team\n"
    )
    e = html.escape
    body = (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;color:#1f2937;'
        'max-width:560px;margin:0 auto;padding:24px">'
        f"<p>{e(hello)}</p>"
        f"<p><strong>Congratulations!</strong> You have been shortlisted for the <strong>{e(job_title)}</strong> "
        f"role at <strong>{e(org_name)}</strong>.</p>"
        f"<p>The next step is a short AI interview: {questions} written questions about your experience, taking "
        f"about {minutes} minutes. You can take it whenever suits you, from any device.</p>"
        f'<p style="margin:28px 0"><a href="{e(link, quote=True)}" style="background:#4338ca;color:#ffffff;'
        'text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:bold;display:inline-block">'
        "Start your interview</a></p>"
        f'<p style="font-size:13px;color:#6b7280">Or paste this link into your browser:<br>{e(link)}</p>'
        f'<p style="font-size:13px;color:#6b7280">This link is personal to you, so please don\'t share it. It expires '
        f"on {e(expires)}. Your responses will be reviewed by a person on the hiring team.</p>"
        f"<p>Good luck!<br>The {e(org_name)} hiring team</p>"
        "</div>"
    )
    return subject, text, body


async def send_shortlist_invite(application_id: uuid.UUID, actor_user_id: uuid.UUID | None = None) -> None:
    async with _invite_locks[application_id], SessionLocal() as db:
        app = await db.get(Application, application_id)
        # The recruiter may have moved the candidate on again before this task ran
        if app is None or app.stage != "shortlisted":
            return
        candidate = await db.get(Candidate, app.candidate_id)
        job = await db.get(Job, app.job_id)
        org = await db.get(Organization, app.organization_id)
        if candidate is None or job is None or org is None:
            return

        def log(action: str, **details) -> None:
            audit.record(db, organization_id=app.organization_id, actor_user_id=actor_user_id,
                         actor_type="user" if actor_user_id else "system", action=action,
                         entity_type="application", entity_id=app.id, details=details)

        async def fail(reason: str) -> None:
            logger.warning("Interview invite for application %s not sent: %s", application_id, reason)
            log("interview.invite_failed", reason=reason)
            await db.commit()

        if app.status != "completed" or not app.screening:
            return await fail("Screening has not finished for this candidate.")
        if not candidate.email:
            return await fail("No email address was found on the candidate's resume.")

        session = await db.scalar(
            select(InterviewSession)
            .where(InterviewSession.application_id == app.id, InterviewSession.status != "cancelled")
            .order_by(InterviewSession.created_at.desc())
            .limit(1)
        )
        if session and (session.started_at or session.status == "completed"):
            return  # the candidate already has (or has finished) their interview

        if session is None:
            try:
                session, token = await open_session(app=app, candidate=candidate, job=job, org_name=org.name,
                                                    org_settings=org_settings_of(org))
            except (LLMError, ValueError) as e:
                return await fail(e.message if isinstance(e, LLMError) else str(e))
            db.add(session)
            log("interview.created", questions=len(session.plan["questions"]), trigger="shortlist")
        else:
            # Re-shortlisted before starting: the old token is unrecoverable, so issue a new link
            token = rotate_link(session)
            session.status = "pending"
        # Persist before sending so the link in the email is already live
        await db.commit()

        plan = InterviewPlan.model_validate(session.plan)
        subject, text, body = render_invite(
            first_name=(candidate.full_name or "").split(" ")[0] or None,
            job_title=job.title,
            org_name=org.name,
            link=interview_link(token),
            questions=len(plan.questions),
            minutes=plan.estimated_minutes,
            expires=f"{session.expires_at:%d %B %Y}",
        )
        try:
            delivery = await mailer.send_email(to=candidate.email, subject=subject, text=text, html=body,
                                               from_name=f"{org.name} Hiring")
        except mailer.EmailError as e:
            return await fail(e.message)
        log("interview.invite_sent", delivery=delivery)
        await db.commit()
