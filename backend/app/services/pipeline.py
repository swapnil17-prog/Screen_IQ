"""
Background pipelines. Each opens its own DB session and persists progress so
the UI can show a live stepper:

  Resume → Parser → Skill Extraction → Experience Analysis → JD Matching → Candidate Score
                                                        → AI Interview → Final Evaluation
"""

import asyncio
import contextlib
import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.llm.client import LLMError
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.evaluation import Evaluation
from app.models.interview import InterviewSession
from app.models.job import Job
from app.models.organization import Organization
from app.schemas.extraction import ResumeExtraction
from app.schemas.interview import InterviewPlan
from app.schemas.organization import OrganizationSettings
from app.services import audit
from app.services.embeddings import get_embedder
from app.services.evaluation import evaluate
from app.services.experience import analyze_experience
from app.services.extraction import extract_job, extract_resume
from app.services.fairness import RedactionContext, analyze_job_description
from app.services.retrieval import job_embedding_text, store_candidate_embeddings, store_job_embedding
from app.services.screening import screen

logger = logging.getLogger(__name__)

_candidate_locks: defaultdict[uuid.UUID, asyncio.Lock] = defaultdict(asyncio.Lock)
_job_locks: defaultdict[uuid.UUID, asyncio.Lock] = defaultdict(asyncio.Lock)

def org_settings_of(org: Organization | None) -> OrganizationSettings:
    return OrganizationSettings.model_validate((org.settings if org else None) or {})


def _user_error(exc: Exception) -> str:
    if isinstance(exc, LLMError):
        return exc.message
    if isinstance(exc, ValueError):
        return str(exc)
    return "An unexpected error occurred while processing. Please retry."


# ── Jobs ─────────────────────────────────────────────────────────────────────


async def prepare_job(db: AsyncSession, job: Job) -> None:
    """Extract requirements, run the inclusive-language report and embed the JD."""
    async with _job_locks[job.id]:
        await db.refresh(job)
        if job.extraction_status == "completed" and job.extracted:
            return
        try:
            jd = await extract_job(job.title, job.description)
            job.extracted = jd.model_dump()
            job.bias_report = analyze_job_description(job.description, len(jd.required_skills)).model_dump()
            await store_job_embedding(
                db,
                organization_id=job.organization_id,
                job_id=job.id,
                text=job_embedding_text(job.title, job.description, jd),
                embedder=get_embedder(),
            )
            job.extraction_status, job.extraction_error = "completed", None
        except Exception as e:
            logger.exception("Job %s preparation failed", job.id)
            await db.rollback()
            await db.refresh(job)
            job.extraction_status, job.extraction_error = "failed", _user_error(e)
            await db.commit()
            raise
        await db.commit()


async def run_job_preparation(job_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        job = await db.get(Job, job_id)
        if job:
            with contextlib.suppress(Exception):  # failure status is already persisted
                await prepare_job(db, job)


# ── Candidates ───────────────────────────────────────────────────────────────


async def ingest_candidate(db: AsyncSession, candidate: Candidate) -> None:
    """Skill extraction → experience analysis → embeddings (idempotent, locked per candidate)."""
    async with _candidate_locks[candidate.id]:
        await db.refresh(candidate)
        if candidate.status == "ready":
            return
        try:
            resume = await extract_resume(candidate.raw_text)
            experience = analyze_experience(resume.work_history)
            candidate.extracted = resume.model_dump()
            candidate.experience = experience.model_dump()
            candidate.skills = resume.skills
            candidate.full_name = resume.full_name
            candidate.email = resume.email
            candidate.phone = resume.phone
            candidate.location = resume.location
            candidate.headline = resume.headline or experience.current_title
            await store_candidate_embeddings(
                db,
                organization_id=candidate.organization_id,
                candidate_id=candidate.id,
                resume=resume,
                raw_text=candidate.raw_text,
                embedder=get_embedder(),
            )
            candidate.status, candidate.error = "ready", None
            await db.commit()
        except Exception as e:
            logger.exception("Candidate %s ingestion failed", candidate.id)
            await db.rollback()
            await db.refresh(candidate)
            candidate.status, candidate.error = "failed", _user_error(e)
            await db.commit()
            raise


async def run_candidate_ingestion(candidate_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        candidate = await db.get(Candidate, candidate_id)
        if candidate:
            with contextlib.suppress(Exception):  # failure status is already persisted
                await ingest_candidate(db, candidate)


# ── Applications (screening) ─────────────────────────────────────────────────


async def _set_status(db: AsyncSession, app: Application, status: str) -> None:
    app.status = status
    app.error = None
    await db.commit()


async def run_application(application_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        app = await db.get(Application, application_id)
        if app is None:
            return
        job = await db.get(Job, app.job_id)
        candidate = await db.get(Candidate, app.candidate_id)
        org = await db.get(Organization, app.organization_id)
        if job is None or candidate is None:
            return
        try:
            await _set_status(db, app, "extracting")
            if candidate.status != "ready":
                await ingest_candidate(db, candidate)
            await _set_status(db, app, "analyzing")
            if job.extraction_status != "completed":
                await prepare_job(db, job)
            await _set_status(db, app, "matching")
            result = await screen(db, job=job, candidate=candidate, org_settings=org_settings_of(org))
            await _set_status(db, app, "scoring")
            app.screening = result.model_dump()
            app.screening_score = result.overall_score
            app.screening_label = result.label
            app.screened_at = datetime.now(UTC)
            app.status = "completed"
            audit.record(
                db,
                organization_id=app.organization_id,
                actor_type="system",
                action="application.screened",
                entity_type="application",
                entity_id=app.id,
                details={"score": result.overall_score, "label": result.label, "confidence": result.confidence},
            )
            await db.commit()
        except Exception as e:
            logger.exception("Application %s screening failed", application_id)
            await db.rollback()
            app = await db.get(Application, application_id)
            if app:
                app.status, app.error = "failed", _user_error(e)
                await db.commit()


# ── Evaluations ──────────────────────────────────────────────────────────────


async def run_evaluation(evaluation_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        ev = await db.get(Evaluation, evaluation_id)
        if ev is None:
            return
        session = await db.get(InterviewSession, ev.interview_session_id)
        app = await db.get(Application, ev.application_id)
        if session is None or app is None:
            return
        job = await db.get(Job, app.job_id)
        candidate = await db.get(Candidate, app.candidate_id)
        org = await db.get(Organization, app.organization_id)
        try:
            resume = ResumeExtraction.model_validate(candidate.extracted) if candidate and candidate.extracted else None
            result = await evaluate(
                job_title=job.title if job else "the role",
                plan=InterviewPlan.model_validate(session.plan),
                messages=session.messages or [],
                redaction=RedactionContext(
                    full_name=resume.full_name if resume else None,
                    email=resume.email if resume else None,
                    phone=resume.phone if resume else None,
                    location=resume.location if resume else None,
                    institutions=[e.institution for e in resume.education] if resume else [],
                ),
                candidate_name=candidate.full_name if candidate else None,
                screening_score=app.screening_score,
                org_settings=org_settings_of(org),
            )
            ev.composite_score = result["composite_score"]
            ev.recommendation = result["recommendation"]
            ev.interview_score = result["interview_score"]
            ev.screening_score = result["screening_score"]
            ev.rubric = result["rubric"]
            ev.bias_audit = result["bias_audit"]
            ev.audit_trace = result["audit_trace"]
            ev.status, ev.error = "completed", None
            app.final_score = result["composite_score"]
            app.recommendation = result["recommendation"]
            audit.record(
                db,
                organization_id=app.organization_id,
                actor_type="system",
                action="evaluation.completed",
                entity_type="application",
                entity_id=app.id,
                details={
                    "composite_score": result["composite_score"],
                    "recommendation": result["recommendation"],
                    "bias_risk": result["bias_audit"]["risk"],
                },
            )
            await db.commit()
        except Exception as e:
            logger.exception("Evaluation %s failed", evaluation_id)
            await db.rollback()
            ev = await db.get(Evaluation, evaluation_id)
            if ev:
                ev.status, ev.error = "failed", _user_error(e)
                await db.commit()


# ── Stale-work recovery ──────────────────────────────────────────────────────

INTERRUPTED = "Processing was interrupted (server restart or timeout). Use Retry to run it again."
STALE_AFTER = timedelta(minutes=20)  # every pipeline step persists progress well within this
SWEEP_INTERVAL_SECONDS = 300


async def recover_interrupted_work() -> int:
    """
    Mark in-flight work that hasn't progressed for STALE_AFTER as failed/retryable.

    Staleness (not mere "in flight" status) is the criterion, so a restarting
    instance never fails work another live instance is still processing.
    """
    cutoff = datetime.now(UTC) - STALE_AFTER
    in_flight = ("queued", "parsing", "extracting", "analyzing", "matching", "scoring")
    async with SessionLocal() as db:
        results = [
            await db.execute(
                update(Application)
                .where(Application.status.in_(in_flight), Application.updated_at < cutoff)
                .values(status="failed", error=INTERRUPTED)
            ),
            await db.execute(
                update(Candidate)
                .where(Candidate.status == "processing", Candidate.updated_at < cutoff)
                .values(status="failed", error=INTERRUPTED)
            ),
            await db.execute(
                update(Evaluation)
                .where(Evaluation.status == "running", Evaluation.updated_at < cutoff)
                .values(status="failed", error=INTERRUPTED)
            ),
            await db.execute(
                update(Job)
                .where(Job.extraction_status == "pending", Job.updated_at < cutoff)
                .values(extraction_status="failed", extraction_error=INTERRUPTED)
            ),
        ]
        await db.commit()
    total = sum(r.rowcount or 0 for r in results)
    if total:
        logger.warning("Marked %d stale in-flight records as failed/retryable", total)
    return total


async def stale_work_sweeper() -> None:
    """Long-running loop started from the app lifespan."""
    while True:
        try:
            await recover_interrupted_work()
        except Exception:
            logger.exception("Stale-work sweep failed")
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
