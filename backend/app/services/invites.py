"""
Shortlist → interview invitation.

When a recruiter shortlists a candidate (and the workspace has
`auto_invite_on_shortlist` on), a background task generates the candidate's AI
interview and emails them the private link. The outcome is written to the audit
log either way, so a failed delivery is visible to the team.
"""

import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime

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
from app.services.email_templates import Email, compose, first_name_of, hello
from app.services.interviews import current_link, interview_link, open_session, rotate_link
from app.services.pipeline import org_settings_of

logger = logging.getLogger(__name__)

_invite_locks: defaultdict[uuid.UUID, asyncio.Lock] = defaultdict(asyncio.Lock)


def render_invite(*, first_name: str | None, job_title: str, org_name: str, link: str, questions: int,
                  minutes: int, expires: str) -> Email:
    return compose(
        subject=f"Congratulations! You've been shortlisted for {job_title} at {org_name}",
        greeting=hello(first_name),
        paragraphs=[
            f"Congratulations! You have been shortlisted for the {job_title} role at {org_name}.",
            f"The next step is a short AI interview: {questions} written questions about your experience, "
            f"taking about {minutes} minutes. You can take it whenever suits you, from any device.",
        ],
        button=("Start your interview", link),
        footnotes=[f"This link is personal to you, so please don't share it. It expires on {expires}.",
                   "Your responses will be reviewed by a person on the hiring team."],
        signoff=f"Good luck!\nThe {org_name} hiring team",
    )


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
                                                    org_settings=org_settings_of(org), created_by_id=actor_user_id)
            except (LLMError, ValueError) as e:
                return await fail(e.message if isinstance(e, LLMError) else str(e))
            db.add(session)
            log("interview.created", questions=len(session.plan["questions"]), trigger="shortlist")
            link = interview_link(token)
        else:
            # Re-shortlisted before starting: resend the live link. Expired links and legacy
            # (non-derivable) tokens get a fresh one instead.
            link = current_link(session)
            if link is None or session.expires_at < datetime.now(UTC):
                link = interview_link(rotate_link(session))
            session.status = "pending"
        # Persist before sending so the link in the email is already live
        await db.commit()

        plan = InterviewPlan.model_validate(session.plan)
        message = render_invite(
            first_name=first_name_of(candidate.full_name),
            job_title=job.title,
            org_name=org.name,
            link=link,
            questions=len(plan.questions),
            minutes=plan.estimated_minutes,
            expires=f"{session.expires_at:%d %B %Y}",
        )
        try:
            delivery = await mailer.send_email(to=candidate.email, subject=message.subject, text=message.text,
                                               html=message.html, from_name=f"{org.name} Hiring")
        except mailer.EmailError as e:
            return await fail(e.message)
        log("interview.invite_sent", delivery=delivery)
        await db.commit()
