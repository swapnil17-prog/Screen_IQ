import uuid

from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy import String, cast, delete, func, or_, select

from app.api.deps import DB, Admin, Auth, Writer, client_ip, get_owned
from app.api.serializers import application_summary, candidate_summary
from app.core.errors import ConflictError, UnprocessableError
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.embedding import Embedding
from app.models.job import Job
from app.schemas.api import (
    ApplicationSummary,
    ApplyRequest,
    CandidateApplication,
    CandidateDetail,
    CandidateSummary,
    Page,
)
from app.schemas.extraction import ResumeExtraction
from app.schemas.screening import ExperienceAnalysis
from app.services import audit, tasks
from app.services.embeddings import get_embedder
from app.services.pipeline import run_application, run_candidate_ingestion
from app.services.retrieval import search_candidates

router = APIRouter(prefix="/candidates", tags=["candidates"])


async def _app_counts(db: DB, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    rows = await db.execute(
        select(Application.candidate_id, func.count()).where(Application.candidate_id.in_(ids))
        .group_by(Application.candidate_id)
    )
    return {cid: n for cid, n in rows}


@router.get("", response_model=Page[CandidateSummary])
async def list_candidates(
    auth: Auth,
    db: DB,
    q: str | None = None,
    semantic: bool = False,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[CandidateSummary]:
    """Talent pool. `semantic=true` ranks by embedding similarity to the query (RAG-style search)."""
    if q and semantic:
        [qv] = await get_embedder().embed_queries([q.strip()])
        hits = await search_candidates(db, organization_id=auth.org_id, query_vector=qv, limit=limit)
        by_id = {c.id: c for c in await db.scalars(select(Candidate).where(Candidate.id.in_([h[0] for h in hits])))}
        counts = await _app_counts(db, list(by_id))
        cal = get_embedder().calibration
        items = [
            candidate_summary(by_id[cid], counts.get(cid, 0), similarity=cal.to_score(sim))
            for cid, sim in hits if cid in by_id
        ]
        return Page(items=items, total=len(items), limit=limit, offset=0)

    stmt = select(Candidate).where(Candidate.organization_id == auth.org_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            Candidate.full_name.ilike(like), Candidate.email.ilike(like), Candidate.headline.ilike(like),
            cast(Candidate.skills, String).ilike(like),
        ))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(await db.scalars(stmt.order_by(Candidate.created_at.desc()).limit(limit).offset(offset)))
    counts = await _app_counts(db, [c.id for c in rows])
    return Page(items=[candidate_summary(c, counts.get(c.id, 0)) for c in rows], total=total, limit=limit,
                offset=offset)


@router.get("/{candidate_id}", response_model=CandidateDetail)
async def get_candidate(candidate_id: uuid.UUID, auth: Auth, db: DB) -> CandidateDetail:
    c = await get_owned(db, Candidate, candidate_id, auth.org_id, "Candidate")
    rows = await db.execute(
        select(Application, Job.title).join(Job, Job.id == Application.job_id)
        .where(Application.candidate_id == c.id).order_by(Application.created_at.desc())
    )
    apps = [
        CandidateApplication(id=a.id, job_id=a.job_id, job_title=title, stage=a.stage, status=a.status,
                             screening_score=a.screening_score, final_score=a.final_score, created_at=a.created_at)
        for a, title in rows
    ]
    base = candidate_summary(c, len(apps))
    return CandidateDetail(
        **base.model_dump(exclude={"skills"}),
        skills=c.skills or [],
        phone=c.phone,
        filename=c.filename,
        file_size=c.file_size,
        extracted=ResumeExtraction.model_validate(c.extracted) if c.extracted else None,
        experience=ExperienceAnalysis.model_validate(c.experience) if c.experience else None,
        raw_text=c.raw_text,
        applications=apps,
    )


@router.post("/{candidate_id}/applications", response_model=ApplicationSummary, status_code=status.HTTP_201_CREATED)
async def apply_to_job(candidate_id: uuid.UUID, body: ApplyRequest, auth: Writer, request: Request,
                       db: DB) -> ApplicationSummary:
    """Screen an existing talent-pool candidate against another job."""
    c = await get_owned(db, Candidate, candidate_id, auth.org_id, "Candidate")
    job = await get_owned(db, Job, body.job_id, auth.org_id, "Job")
    if job.status in ("closed", "archived"):
        raise UnprocessableError("This job is closed.")
    if await db.scalar(select(Application.id).where(Application.job_id == job.id, Application.candidate_id == c.id)):
        raise ConflictError("This candidate is already in that job's pipeline.")
    app = Application(organization_id=auth.org_id, job_id=job.id, candidate_id=c.id, status="queued", stage="new")
    db.add(app)
    await db.flush()
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="application.created",
                 entity_type="application", entity_id=app.id, details={"job_id": str(job.id)},
                 ip_address=client_ip(request))
    await db.commit()
    await db.refresh(app)
    tasks.spawn(run_application(app.id), name=f"application-{app.id}")
    return application_summary(app, c, job)


@router.post("/{candidate_id}/reprocess", response_model=dict)
async def reprocess_candidate(candidate_id: uuid.UUID, auth: Writer, db: DB) -> dict:
    """Re-run extraction + embeddings, then re-screen all of the candidate's applications."""
    c = await get_owned(db, Candidate, candidate_id, auth.org_id, "Candidate")
    c.status, c.error = "processing", None
    apps = list(await db.scalars(select(Application).where(Application.candidate_id == c.id)))
    for a in apps:
        a.status, a.error = "queued", None
    await db.commit()
    if not apps:
        tasks.spawn(run_candidate_ingestion(c.id), name=f"candidate-{c.id}")
    for a in apps:
        tasks.spawn(run_application(a.id), name=f"application-{a.id}")
    return {"queued": len(apps)}


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(candidate_id: uuid.UUID, auth: Admin, request: Request, db: DB) -> Response:
    """Right-to-erasure: removes the candidate, resume text, vectors, applications, interviews and evaluations."""
    c = await get_owned(db, Candidate, candidate_id, auth.org_id, "Candidate")
    await db.execute(delete(Embedding).where(Embedding.owner_id == c.id))
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="candidate.erased",
                 entity_type="candidate", entity_id=c.id, ip_address=client_ip(request))
    await db.delete(c)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
