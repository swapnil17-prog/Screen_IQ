from sqlalchemy import Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScoped, Timestamps, UUIDPk

# Candidate ingestion lifecycle: parse → extract → embed
CANDIDATE_STATUSES = ("processing", "ready", "failed")


class Candidate(UUIDPk, TenantScoped, Timestamps, Base):
    """A person in the talent pool, built from one parsed resume."""

    __tablename__ = "candidates"

    full_name: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(Text)

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # sha256 of the uploaded bytes — dedupes re-uploads within an organization
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    # ResumeExtraction (LLM) and ExperienceAnalysis (deterministic)
    extracted: Mapped[dict | None] = mapped_column(JSONB)
    experience: Mapped[dict | None] = mapped_column(JSONB)
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    status: Mapped[str] = mapped_column(Text, nullable=False, default="processing")
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_candidates_org_hash", "organization_id", "file_hash"),)
