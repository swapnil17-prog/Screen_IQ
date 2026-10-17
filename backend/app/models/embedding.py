import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScoped, UUIDPk

# Every provider is normalised to this dimension (BGE-large = 1024 natively,
# OpenAI text-embedding-3-small is requested with dimensions=1024).
VECTOR_DIM = 1024

# owner_type values
JOB_DOC = "job"                        # full JD text
CANDIDATE_PROFILE = "candidate_profile"  # whole-profile vector, used for talent search
CANDIDATE_SECTION = "candidate_section"  # skills / experience / summary / education
CANDIDATE_CHUNK = "candidate_chunk"      # RAG retrieval units


class Embedding(UUIDPk, TenantScoped, Base):
    __tablename__ = "embeddings"

    owner_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)  # section name, e.g. "experience"
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Retrieval is always scoped to one owner (tens of rows), so an exact scan over
    # this btree index is both fast and exact. An ANN index (HNSW/IVFFlat) combined
    # with an owner filter can silently return fewer than k rows, so we don't add one.
    __table_args__ = (Index("ix_embeddings_owner", "owner_type", "owner_id"),)
