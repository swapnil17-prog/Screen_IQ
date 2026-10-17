import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScoped, Timestamps, UUIDPk

INTERVIEW_STATUSES = ("pending", "in_progress", "completed", "expired", "cancelled")


class InterviewSession(UUIDPk, TenantScoped, Timestamps, Base):
    __tablename__ = "interview_sessions"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256 of the candidate's link token (the raw token is never stored)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")

    plan: Mapped[dict] = mapped_column(JSONB, nullable=False)  # InterviewPlan
    current_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    follow_up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
