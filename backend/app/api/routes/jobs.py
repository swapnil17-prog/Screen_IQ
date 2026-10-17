import asyncio
import hashlib
import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, Query, Request, Response, UploadFile, status
from sqlalchemy import delete, func, or_, select

from app.api.deps import DB, Admin, Auth, Writer, client_ip, get_owned
from app.api.serializers import application_summary
from app.core.config import settings
from app.core.errors import UnprocessableError
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.embedding import JOB_DOC, Embedding
from app.models.interview import InterviewSession
from app.models.job import Job
from app.schemas.api import (
    ApplicationSummary,
    BiasCheckRequest,
    JobCounts,
    JobCreate,
    JobDetail,
    JobSummary,
    JobUpdate,
    UploadError,
    UploadResult,
)
from app.schemas.extraction import JDExtraction
from app.schemas.fairness import JDBiasReport
from app.schemas.organization import ScoringWeights
from app.services import audit, tasks
from app.services.embeddings import get_embedder
from app.services.fairness import analyze_job_description
from app.services.parsing import SUPPORTED_EXTENSIONS, ParseError, parse_resume
from app.services.pipeline import org_settings_of, run_application, run_job_preparation
from app.services.retrieval import job_embedding_text, store_job_embedding
from app.services.scoring import TIER_REVIEW, TIER_STRONG
from app.services.skills import dedupe_skills

router = APIRouter(prefix="/jobs", tags=["jobs"])

PROCESSING = ("queued", "parsing", "extracting", "analyzing", "matching", "scoring")


async def _job_stats(db: DB, org_id: uuid.UUID, job_ids: list[uuid.UUID] | None = None) -> dict:
    stmt = select(
        Application.job_id,
        func.count().label("total"),
        func.count().filter(Application.status == "completed").label("screened"),
        func.count().filter(Application.status.in_(PROCESSING)).label("processing"),
        func.count().filter(Application.status == "failed").label("failed"),
        func.count().filter(Application.stage == "shortlisted").label("shortlisted"),
        func.count().filter(Application.stage == "interviewing").label("interviewing"),
        func.count().filter(Application.stage == "hired").label("hired"),
        func.count().filter(Application.screening_score >= TIER_STRONG, Application.status == "completed")
        .label("strong"),
        func.count().filter(Application.screening_score >= TIER_REVIEW, Application.screening_score < TIER_STRONG,
                            Application.status == "completed").label("review"),
        func.count().filter(Application.screening_score < TIER_REVIEW, Application.status == "completed")
        .label("low"),
        func.avg(Application.screening_score).label("avg"),
        func.max(Application.screening_score).label("top"),
    ).where(Application.organization_id == org_id).group_by(Application.job_id)
    if job_ids is not None:
        stmt = stmt.where(Application.job_id.in_(job_ids))
    return {r.job_id: r for r in await db.execute(stmt)}


def _summary(job: Job, stats) -> dict:
    counts = JobCounts()
    avg = top = None
    if stats is not None:
        counts = JobCounts(total=stats.total, screened=stats.screened, processing=stats.processing,
                           failed=stats.failed, shortlisted=stats.shortlisted, interviewing=stats.interviewing,
                           hired=stats.hired, strong=stats.strong, review=stats.review, low=stats.low)
        avg = round(float(stats.avg), 1) if stats.avg is not None else None
        top = round(float(stats.top), 1) if stats.top is not None else None
    return {
        "id": job.id, "title": job.title, "department": job.department, "location": job.location,
        "employment_type": job.employment_type, "status": job.status, "extraction_status": job.extraction_status,
        "created_at": job.created_at, "updated_at": job.updated_at, "counts": counts, "avg_score": avg,
        "top_score": top, "inclusivity_score": (job.bias_report or {}).get("score"),
    }


async def _detail(db: DB, job: Job, auth) -> JobDetail:
    stats = (await _job_stats(db, auth.org_id, [job.id])).get(job.id)
    weights = ScoringWeights.model_validate(job.scoring_weights) if job.scoring_weights \
        else org_settings_of(auth.org).scoring_weights
    return JobDetail(
        **_summary(job, stats),
        description=job.description,
        extracted=JDExtraction.model_validate(job.extracted) if job.extracted else None,
        extraction_error=job.extraction_error,
        bias_report=JDBiasReport.model_validate(job.bias_report) if job.bias_report else None,
        scoring_weights=weights,
        has_custom_weights=job.scoring_weights is not None,
    )


@router.get("", response_model=list[JobSummary])
async def list_jobs(
    auth: Auth,
    db: DB,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    q: str | None = None,
) -> list[JobSummary]:
    stmt = select(Job).where(Job.organization_id == auth.org_id)
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    else:
        stmt = stmt.where(Job.status != "archived")
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Job.title.ilike(like), Job.department.ilike(like), Job.location.ilike(like)))
    jobs = list(await db.scalars(stmt.order_by(Job.created_at.desc())))
    stats = await _job_stats(db, auth.org_id, [j.id for j in jobs])
    return [JobSummary(**_summary(j, stats.get(j.id))) for j in jobs]


@router.post("", response_model=JobDetail, status_code=status.HTTP_201_CREATED)
async def create_job(body: JobCreate, auth: Writer, request: Request, db: DB) -> JobDetail:
    job = Job(
        organization_id=auth.org_id,
        created_by_id=auth.user.id,
        title=body.title.strip(),
        description=body.description.strip(),
        department=body.department,
        location=body.location,
        employment_type=body.employment_type,
        extraction_status="pending",
        # Instant, deterministic report; refined with the skill count after extraction
        bias_report=analyze_job_description(body.description).model_dump(),
    )
    db.add(job)
    await db.flush()
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="job.created",
                 entity_type="job", entity_id=job.id, details={"title": job.title}, ip_address=client_ip(request))
    await db.commit()
    await db.refresh(job)
    tasks.spawn(run_job_preparation(job.id), name=f"job-prepare-{job.id}")
    return await _detail(db, job, auth)


@router.post("/bias-check", response_model=JDBiasReport)
async def bias_check(body: BiasCheckRequest, auth: Auth) -> JDBiasReport:
    """Live inclusive-language analysis for the job editor (no persistence, no LLM)."""
    return analyze_job_description(body.description)


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(job_id: uuid.UUID, auth: Auth, db: DB) -> JobDetail:
    job = await get_owned(db, Job, job_id, auth.org_id, "Job")
    return await _detail(db, job, auth)


@router.patch("/{job_id}", response_model=JobDetail)
async def update_job(job_id: uuid.UUID, body: JobUpdate, auth: Writer, request: Request, db: DB) -> JobDetail:
    job = await get_owned(db, Job, job_id, auth.org_id, "Job")
    changes = body.model_dump(exclude_unset=True, exclude={"scoring_weights", "clear_scoring_weights", "criteria"})
    content_changed = any(k in changes and changes[k] != getattr(job, k) for k in ("title", "description"))
    for field, value in changes.items():
        setattr(job, field, value.strip() if isinstance(value, str) else value)
    if body.clear_scoring_weights:
        job.scoring_weights = None
        changes["scoring_weights"] = "organization default"
    elif body.scoring_weights is not None:
        job.scoring_weights = body.scoring_weights.model_dump()
        changes["scoring_weights"] = job.scoring_weights
    if content_changed:
        job.extraction_status, job.extracted = "pending", None
        job.bias_report = analyze_job_description(job.description).model_dump()
    criteria_changed = False
    if body.criteria is not None and not content_changed:
        if not job.extracted:
            raise UnprocessableError("Criteria can be edited once the job description has been analyzed.")
        jd = JDExtraction.model_validate(job.extracted)
        jd.required_skills = dedupe_skills(body.criteria.required_skills)
        required_keys = {s.lower() for s in jd.required_skills}
        jd.nice_to_have_skills = [s for s in dedupe_skills(body.criteria.nice_to_have_skills)
                                  if s.lower() not in required_keys]
        jd.min_years_experience = body.criteria.min_years_experience
        job.extracted = jd.model_dump()
        job.bias_report = analyze_job_description(job.description, len(jd.required_skills)).model_dump()
        await store_job_embedding(db, organization_id=job.organization_id, job_id=job.id,
                                  text=job_embedding_text(job.title, job.description, jd), embedder=get_embedder())
        changes["criteria"] = body.criteria.model_dump()
        criteria_changed = True
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="job.updated",
                 entity_type="job", entity_id=job.id, details={k: v for k, v in changes.items() if k != "description"},
                 ip_address=client_ip(request))
    await db.commit()
    await db.refresh(job)
    if content_changed:
        tasks.spawn(run_job_preparation(job.id), name=f"job-prepare-{job.id}")
    if criteria_changed:
        await _queue_rescore(db, job.id)
    return await _detail(db, job, auth)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: uuid.UUID, auth: Admin, request: Request, db: DB) -> Response:
    job = await get_owned(db, Job, job_id, auth.org_id, "Job")
    await db.execute(delete(Embedding).where(Embedding.owner_type == JOB_DOC, Embedding.owner_id == job.id))
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="job.deleted",
                 entity_type="job", entity_id=job.id, details={"title": job.title}, ip_address=client_ip(request))
    await db.delete(job)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{job_id}/retry-extraction", response_model=JobDetail)
async def retry_extraction(job_id: uuid.UUID, auth: Writer, db: DB) -> JobDetail:
    job = await get_owned(db, Job, job_id, auth.org_id, "Job")
    job.extraction_status, job.extraction_error = "pending", None
    await db.commit()
    tasks.spawn(run_job_preparation(job.id), name=f"job-prepare-{job.id}")
    return await _detail(db, job, auth)


@router.get("/{job_id}/applications", response_model=list[ApplicationSummary])
async def list_applications(
    job_id: uuid.UUID,
    auth: Auth,
    db: DB,
    stage: str | None = None,
    tier: Literal["strong", "review", "low"] | None = None,
    sort: Literal["score", "recent", "name", "final"] = "score",
) -> list[ApplicationSummary]:
    job = await get_owned(db, Job, job_id, auth.org_id, "Job")
    stmt = (
        select(Application, Candidate)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .where(Application.job_id == job.id, Application.organization_id == auth.org_id)
    )
    if stage:
        stmt = stmt.where(Application.stage == stage)
    if tier:
        stmt = stmt.where(Application.status == "completed")
        stmt = stmt.where({
            "strong": Application.screening_score >= TIER_STRONG,
            "review": (Application.screening_score >= TIER_REVIEW) & (Application.screening_score < TIER_STRONG),
            "low": Application.screening_score < TIER_REVIEW,
        }[tier])
    order = {
        "score": (Application.screening_score.desc().nulls_last(), Application.created_at.desc()),
        "final": (Application.final_score.desc().nulls_last(), Application.screening_score.desc().nulls_last()),
        "recent": (Application.created_at.desc(),),
        "name": (Candidate.full_name.asc().nulls_last(),),
    }[sort]
    rows = (await db.execute(stmt.order_by(*order))).all()

    app_ids = [a.id for a, _ in rows]
    latest: dict[uuid.UUID, str] = {}
    if app_ids:
        sessions = await db.execute(
            select(InterviewSession.application_id, InterviewSession.status)
            .where(InterviewSession.application_id.in_(app_ids), InterviewSession.status != "cancelled")
            .order_by(InterviewSession.created_at)
        )
        latest = {r.application_id: r.status for r in sessions}
    return [application_summary(a, c, job, latest.get(a.id)) for a, c in rows]


@router.post("/{job_id}/applications/upload", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
async def upload_resumes(
    job_id: uuid.UUID,
    auth: Writer,
    request: Request,
    db: DB,
    files: Annotated[list[UploadFile], File(description="PDF, DOCX or TXT resumes")],
) -> UploadResult:
    job = await get_owned(db, Job, job_id, auth.org_id, "Job")
    if job.status in ("closed", "archived"):
        raise UnprocessableError("This job is closed. Reopen it to add candidates.")
    if not files:
        raise UnprocessableError("Attach at least one resume.")
    if len(files) > settings.max_files_per_upload:
        raise UnprocessableError(f"Upload at most {settings.max_files_per_upload} files at a time.")

    created: list[tuple[Application, Candidate]] = []
    duplicates: list[tuple[Application, Candidate]] = []
    errors: list[UploadError] = []

    for upload in files:
        name = Path(upload.filename or "resume").name[:200]
        ext = Path(name).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS and ext != ".doc":
            errors.append(UploadError(filename=name, message="Unsupported file type. Use PDF, DOCX or TXT."))
            continue
        data = await upload.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            errors.append(UploadError(filename=name, message=f"File exceeds {settings.max_upload_mb} MB."))
            continue
        if not data:
            errors.append(UploadError(filename=name, message="File is empty."))
            continue

        file_hash = hashlib.sha256(data).hexdigest()
        candidate = await db.scalar(
            select(Candidate).where(Candidate.organization_id == auth.org_id, Candidate.file_hash == file_hash)
        )
        if candidate is None:
            try:
                raw_text = await asyncio.to_thread(parse_resume, data, name)
            except ParseError as e:
                errors.append(UploadError(filename=name, message=str(e)))
                continue
            candidate = Candidate(
                organization_id=auth.org_id, filename=name, content_type=upload.content_type,
                file_size=len(data), file_hash=file_hash, raw_text=raw_text, status="processing", skills=[],
            )
            db.add(candidate)
            await db.flush()
        else:
            existing = await db.scalar(
                select(Application).where(Application.job_id == job.id, Application.candidate_id == candidate.id)
            )
            if existing:
                duplicates.append((existing, candidate))
                continue

        application = Application(organization_id=auth.org_id, job_id=job.id, candidate_id=candidate.id,
                                  status="queued", stage="new")
        db.add(application)
        await db.flush()
        created.append((application, candidate))

    if created:
        audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="applications.uploaded",
                     entity_type="job", entity_id=job.id,
                     details={"created": len(created), "duplicates": len(duplicates), "errors": len(errors)},
                     ip_address=client_ip(request))
    await db.commit()
    for application, _ in created:
        tasks.spawn(run_application(application.id), name=f"application-{application.id}")

    return UploadResult(
        created=[application_summary(a, c, job) for a, c in created],
        duplicates=[application_summary(a, c, job) for a, c in duplicates],
        errors=errors,
    )


@router.post("/{job_id}/rescore", response_model=dict)
async def rescore_job(job_id: uuid.UUID, auth: Writer, request: Request, db: DB) -> dict:
    """Re-run screening for every settled application (e.g. after changing weights or the JD)."""
    job = await get_owned(db, Job, job_id, auth.org_id, "Job")
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="job.rescored",
                 entity_type="job", entity_id=job.id, ip_address=client_ip(request))
    return {"queued": await _queue_rescore(db, job.id)}


async def _queue_rescore(db: DB, job_id: uuid.UUID) -> int:
    """Re-run screening for every settled application of a job; returns how many were queued."""
    apps = list(await db.scalars(
        select(Application).where(Application.job_id == job_id, Application.status.in_(("completed", "failed")))
    ))
    for a in apps:
        a.status, a.error = "queued", None
    await db.commit()
    for a in apps:
        tasks.spawn(run_application(a.id), name=f"application-{a.id}")
    return len(apps)
