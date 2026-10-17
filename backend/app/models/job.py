import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScoped, Timestamps, UUIDPk

JOB_STATUSES = ("open", "paused", "closed", "archived")


class Job(UUIDPk, TenantScoped, Timestamps, Base):
    __tablename__ = "jobs"

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    employment_type: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")

    # JDExtraction — structured requirements parsed by the LLM
    extracted: Mapped[dict | None] = mapped_column(JSONB)
    # "pending" | "completed" | "failed"
    extraction_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    extraction_error: Mapped[str | None] = mapped_column(Text)
    # JDBiasReport — deterministic inclusive-language analysis
    bias_report: Mapped[dict | None] = mapped_column(JSONB)
    # Optional per-job override of screening weights
    scoring_weights: Mapped[dict | None] = mapped_column(JSONB)
