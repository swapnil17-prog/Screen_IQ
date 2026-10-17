"""
Vector storage and retrieval on pgvector.

All similarity math runs in Postgres via the `<=>` cosine-distance operator.
"""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import (
    CANDIDATE_CHUNK,
    CANDIDATE_PROFILE,
    CANDIDATE_SECTION,
    JOB_DOC,
    Embedding,
)
from app.schemas.extraction import JDExtraction, ResumeExtraction
from app.schemas.screening import EvidenceChunk
from app.services.chunking import build_profile_text, build_resume_chunks, build_section_texts
from app.services.embeddings import Embedder


async def store_candidate_embeddings(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    candidate_id: uuid.UUID,
    resume: ResumeExtraction,
    raw_text: str,
    embedder: Embedder,
) -> int:
    """(Re)build every vector for a candidate: RAG chunks, sections and whole profile."""
    await db.execute(
        delete(Embedding).where(
            Embedding.owner_id == candidate_id,
            Embedding.owner_type.in_([CANDIDATE_CHUNK, CANDIDATE_SECTION, CANDIDATE_PROFILE]),
        )
    )
    rows: list[tuple[str, str, int, str]] = []  # (owner_type, label, index, content)
    per_section: dict[str, int] = {}
    for chunk in build_resume_chunks(resume, raw_text):
        idx = per_section.get(chunk.section, 0)
        per_section[chunk.section] = idx + 1
        rows.append((CANDIDATE_CHUNK, chunk.section, idx, chunk.text))
    for section, text in build_section_texts(resume).items():
        rows.append((CANDIDATE_SECTION, section, 0, text))
    profile = build_profile_text(resume) or raw_text[:4000]
    rows.append((CANDIDATE_PROFILE, "profile", 0, profile))

    vectors = await embedder.embed_documents([r[3] for r in rows])
    for (owner_type, label, idx, content), vector in zip(rows, vectors, strict=True):
        db.add(
            Embedding(
                organization_id=organization_id,
                owner_type=owner_type,
                owner_id=candidate_id,
                label=label,
                chunk_index=idx,
                content=content,
                provider=embedder.name,
                vector=vector,
            )
        )
    return len(rows)


def job_embedding_text(title: str, description: str, jd: JDExtraction | None) -> str:
    if jd is None:
        return f"{title}\n{description}"[:6000]
    parts = [jd.role_title or title]
    if jd.required_skills:
        parts.append("Required: " + ", ".join(jd.required_skills))
    if jd.nice_to_have_skills:
        parts.append("Preferred: " + ", ".join(jd.nice_to_have_skills))
    parts += jd.responsibilities
    return "\n".join(parts)[:6000]


async def store_job_embedding(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    job_id: uuid.UUID,
    text: str,
    embedder: Embedder,
) -> None:
    await db.execute(delete(Embedding).where(Embedding.owner_id == job_id, Embedding.owner_type == JOB_DOC))
    [vector] = await embedder.embed_documents([text])
    db.add(
        Embedding(
            organization_id=organization_id,
            owner_type=JOB_DOC,
            owner_id=job_id,
            label="job",
            content=text,
            provider=embedder.name,
            vector=vector,
        )
    )


async def get_job_vector(db: AsyncSession, job_id: uuid.UUID) -> list[float] | None:
    row = await db.scalar(
        select(Embedding.vector).where(Embedding.owner_type == JOB_DOC, Embedding.owner_id == job_id)
    )
    return None if row is None else [float(x) for x in row]


async def retrieve_evidence(
    db: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    query_vectors: list[list[float]],
    top_k: int,
) -> list[list[EvidenceChunk]]:
    """Top-k resume chunks per query (one query per JD requirement)."""
    results: list[list[EvidenceChunk]] = []
    for qv in query_vectors:
        distance = Embedding.vector.cosine_distance(qv)
        rows = await db.execute(
            select(Embedding.id, Embedding.label, Embedding.content, (1 - distance).label("similarity"))
            .where(Embedding.owner_type == CANDIDATE_CHUNK, Embedding.owner_id == candidate_id)
            .order_by(distance)
            .limit(top_k)
        )
        results.append(
            [
                EvidenceChunk(id=str(r.id), section=r.label, text=r.content, similarity=round(float(r.similarity), 4))
                for r in rows
            ]
        )
    return results


async def section_similarities(
    db: AsyncSession, *, candidate_id: uuid.UUID, job_vector: list[float]
) -> dict[str, float]:
    distance = Embedding.vector.cosine_distance(job_vector)
    rows = await db.execute(
        select(Embedding.label, (1 - distance).label("similarity")).where(
            Embedding.owner_type == CANDIDATE_SECTION, Embedding.owner_id == candidate_id
        )
    )
    return {r.label: float(r.similarity) for r in rows}


async def search_candidates(
    db: AsyncSession, *, organization_id: uuid.UUID, query_vector: list[float], limit: int
) -> list[tuple[uuid.UUID, float]]:
    """Semantic talent-pool search over whole-profile vectors."""
    distance = Embedding.vector.cosine_distance(query_vector)
    rows = await db.execute(
        select(Embedding.owner_id, func.max(1 - distance).label("similarity"))
        .where(Embedding.organization_id == organization_id, Embedding.owner_type == CANDIDATE_PROFILE)
        .group_by(Embedding.owner_id)
        .order_by(func.max(1 - distance).desc())
        .limit(limit)
    )
    return [(r.owner_id, float(r.similarity)) for r in rows]
