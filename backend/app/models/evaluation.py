import uuid

from sqlalchemy import Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScoped, Timestamps, UUIDPk


class Evaluation(UUIDPk, TenantScoped, Timestamps, Base):
    """Final, auditable hiring evaluation for one completed interview."""

    __tablename__ = "evaluations"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interview_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")  # running|completed|failed
    error: Mapped[str | None] = mapped_column(Text)

    composite_score: Mapped[float | None] = mapped_column(Float)
    recommendation: Mapped[str | None] = mapped_column(Text)
    screening_score: Mapped[float | None] = mapped_column(Float)
    interview_score: Mapped[float | None] = mapped_column(Float)

    rubric: Mapped[dict | None] = mapped_column(JSONB)       # InterviewRubric
    bias_audit: Mapped[dict | None] = mapped_column(JSONB)   # BiasAudit
    audit_trace: Mapped[dict | None] = mapped_column(JSONB)  # explainability trace
