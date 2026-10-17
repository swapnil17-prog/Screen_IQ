"""
Public careers page: a workspace's open jobs and an apply form. No login.

Applications enter the same pipeline as recruiter uploads (parse → screen), tagged
`source="careers"`. Rate limited per IP, with a honeypot field for naive bots.
"""

import asyncio
import hashlib
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, client_ip
from app.core.config import settings
from app.core.errors import NotFoundError, UnprocessableError
from app.core.rate_limit import RateLimiter
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.organization import Organization
from app.schemas.api import ApplyResult, CareerJob, CareerJobDetail, CareersOut
from app.services import audit, tasks
from app.services.notifications import send_application_received
from app.services.parsing import SUPPORTED_EXTENSIONS, ParseError, parse_resume
from app.services.pipeline import org_settings_of, run_application

router = APIRouter(prefix="/public/careers", tags=["careers"])
browse_limit = Depends(RateLimiter(settings.rate_limit_public_per_minute, scope="careers"))
apply_limit = Depends(RateLimiter(settings.rate_limit_apply_per_minute, scope="apply"))

_email = TypeAdapter(EmailStr)


async def _org(db: AsyncSession, slug: str) -> Organization:
    org = await db.scalar(select(Organization).where(Organization.slug == slug.lower()))
    if org is None or not org_settings_of(org).careers_page_enabled:
        raise NotFoundError("This careers page doesn't exist.")
    return org


async def _open_job(db: AsyncSession, org: Organization, job_id: uuid.UUID) -> Job:
    job = await db.get(Job, job_id)
    if job is None or job.organization_id != org.id or job.status != "open":
        raise NotFoundError("This job isn't open for applications.")
    return job


def _career_job(job: Job) -> CareerJob:
    return CareerJob(id=job.id, title=job.title, department=job.department, location=job.location,
                     employment_type=job.employment_type, created_at=job.created_at)


@router.get("/{slug}", response_model=CareersOut, dependencies=[browse_limit])
async def careers(slug: str, db: DB) -> CareersOut:
    org = await _org(db, slug)
    jobs = await db.scalars(
        select(Job).where(Job.organization_id == org.id, Job.status == "open").order_by(Job.created_at.desc())
    )
    return CareersOut(organization_name=org.name, slug=org.slug, jobs=[_career_job(j) for j in jobs])


@router.get("/{slug}/jobs/{job_id}", response_model=CareerJobDetail, dependencies=[browse_limit])
async def career_job(slug: str, job_id: uuid.UUID, db: DB) -> CareerJobDetail:
    org = await _org(db, slug)
    job = await _open_job(db, org, job_id)
    return CareerJobDetail(**_career_job(job).model_dump(), organization_name=org.name, description=job.description)


@router.post("/{slug}/jobs/{job_id}/apply", response_model=ApplyResult, status_code=status.HTTP_201_CREATED,
             dependencies=[apply_limit])
async def apply(
    slug: str,
    job_id: uuid.UUID,
    request: Request,
    db: DB,
    full_name: Annotated[str, Form(min_length=1, max_length=120)],
    email: Annotated[str, Form(max_length=254)],
    resume: Annotated[UploadFile, File(description="PDF, DOCX or TXT resume")],
    consent: Annotated[bool, Form()] = False,
    phone: Annotated[str | None, Form(max_length=40)] = None,
    website: Annotated[str | None, Form()] = None,  # honeypot: hidden from people, filled by bots
) -> ApplyResult:
    org = await _org(db, slug)
    job = await _open_job(db, org, job_id)
    if website:
        return ApplyResult()  # look successful to the bot, store nothing
    if not consent:
        raise UnprocessableError("Please agree to the privacy notice to apply.")
    try:
        email = _email.validate_python(email.strip()).lower()
    except ValidationError as e:
        raise UnprocessableError("Enter a valid email address.") from e
    full_name = full_name.strip()
    if not full_name:
        raise UnprocessableError("Enter your full name.")

    name = Path(resume.filename or "resume").name[:200]
    if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UnprocessableError("Upload your resume as a PDF, DOCX or TXT file.")
    data = await resume.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise UnprocessableError(f"Your resume must be under {settings.max_upload_mb} MB.")
    if not data:
        raise UnprocessableError("That file is empty.")

    file_hash = hashlib.sha256(data).hexdigest()
    candidate = await db.scalar(
        select(Candidate).where(Candidate.organization_id == org.id, Candidate.file_hash == file_hash)
    )
    if candidate is None:
        try:
            raw_text = await asyncio.to_thread(parse_resume, data, name)
        except ParseError as e:
            raise UnprocessableError(str(e)) from e
        candidate = Candidate(
            organization_id=org.id, source="careers", full_name=full_name, email=email,
            phone=(phone or "").strip() or None, filename=name, content_type=resume.content_type,
            file_size=len(data), file_hash=file_hash, raw_text=raw_text, status="processing", skills=[],
        )
        db.add(candidate)
        await db.flush()
    elif await db.scalar(select(Application.id).where(Application.job_id == job.id,
                                                      Application.candidate_id == candidate.id)):
        # Already applied: same response, so this can't be used to probe who has applied
        return ApplyResult()
    # An existing candidate keeps their stored contact details: a re-used resume file must not
    # redirect another person's emails.

    application = Application(organization_id=org.id, job_id=job.id, candidate_id=candidate.id,
                              status="queued", stage="new", source="careers")
    db.add(application)
    await db.flush()
    audit.record(db, organization_id=org.id, actor_type="candidate", action="application.applied",
                 entity_type="application", entity_id=application.id, details={"job_id": str(job.id)},
                 ip_address=client_ip(request))
    await db.commit()
    tasks.spawn(run_application(application.id), name=f"application-{application.id}")
    tasks.spawn(send_application_received(application.id), name=f"received-{application.id}")
    return ApplyResult()
