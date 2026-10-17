import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScoped, Timestamps, UUIDPk

# Recruiter-controlled hiring stage
STAGES = ("new", "shortlisted", "interviewing", "offer", "hired", "rejected")

# System-controlled pipeline status, mirroring the screening pipeline:
# Resume → Parser → Skill Extraction → Experience Analysis → JD Matching → Candidate Score
PIPELINE_STATUSES = (
    "queued",
    "parsing",
    "extracting",
    "analyzing",
    "matching",
    "scoring",
    "completed",
    "failed",
)


class Application(UUIDPk, TenantScoped, Timestamps, Base):
    """A candidate applying to a job — holds the screening result for that pair."""

    __tablename__ = "applications"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    stage: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text)

    # Screening outcome (ScreeningResult) + denormalised headline numbers for sorting
    screening: Mapped[dict | None] = mapped_column(JSONB)
    screening_score: Mapped[float | None] = mapped_column(Float)
    screening_label: Mapped[str | None] = mapped_column(Text)
    # When the latest screening finished (drives time-to-screen and period metrics)
    screened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Final (screening + interview) score once evaluated
    final_score: Mapped[float | None] = mapped_column(Float)
    recommendation: Mapped[str | None] = mapped_column(Text)

    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_applications_job_candidate"),
        Index("ix_applications_job_score", "job_id", "screening_score"),
        Index("ix_applications_org_screened", "organization_id", "screened_at"),
    )
