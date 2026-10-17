"""Careers-page applications, candidate/recruiter notification emails, password reset and email invites.

Revision ID: 0003_careers_notifications
Revises: 0002_screened_at
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_careers_notifications"
down_revision = "0002_screened_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("source", sa.Text(), nullable=False, server_default="upload"))

    op.add_column("applications", sa.Column("source", sa.Text(), nullable=False, server_default="upload"))
    op.add_column("applications", sa.Column("rejected_at", sa.DateTime(timezone=True)))
    op.add_column("applications", sa.Column("rejection_notified_at", sa.DateTime(timezone=True)))

    op.add_column("interview_sessions", sa.Column("link_version", sa.Integer()))
    op.add_column("interview_sessions", sa.Column(
        "created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.add_column("interview_sessions", sa.Column("reminder_sent_at", sa.DateTime(timezone=True)))
    op.add_column("interview_sessions", sa.Column("completion_notified_at", sa.DateTime(timezone=True)))

    op.add_column("users", sa.Column("invited_at", sa.DateTime(timezone=True)))

    op.create_table(
        "user_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_tokens_user_id", "user_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_tokens_user_id", table_name="user_tokens")
    op.drop_table("user_tokens")
    op.drop_column("users", "invited_at")
    op.drop_column("interview_sessions", "completion_notified_at")
    op.drop_column("interview_sessions", "reminder_sent_at")
    op.drop_column("interview_sessions", "created_by_id")
    op.drop_column("interview_sessions", "link_version")
    op.drop_column("applications", "rejection_notified_at")
    op.drop_column("applications", "rejected_at")
    op.drop_column("applications", "source")
    op.drop_column("candidates", "source")
