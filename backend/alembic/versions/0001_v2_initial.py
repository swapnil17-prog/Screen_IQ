"""ScreenIQ 2.0 schema: multi-tenant orgs/users, jobs, candidates, applications,
embeddings (pgvector), interviews, evaluations and audit log.

Revision ID: 0001_v2
Revises:
Create Date: 2026-09-27
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0001_v2"
down_revision = None
branch_labels = None
depends_on = None

VECTOR_DIM = 1024


def _id() -> sa.Column:
    return sa.Column("id", pg.UUID(as_uuid=True), primary_key=True)


def _org() -> sa.Column:
    return sa.Column(
        "organization_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "organizations",
        _id(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False, unique=True),
        sa.Column("settings", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "users",
        _id(),
        _org(),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False, server_default="recruiter"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("role IN ('owner','admin','recruiter','viewer')", name="ck_users_role"),
    )

    op.create_table(
        "jobs",
        _id(),
        _org(),
        sa.Column("created_by_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("department", sa.Text),
        sa.Column("location", sa.Text),
        sa.Column("employment_type", sa.Text),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="open"),
        sa.Column("extracted", pg.JSONB),
        sa.Column("extraction_status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("extraction_error", sa.Text),
        sa.Column("bias_report", pg.JSONB),
        sa.Column("scoring_weights", pg.JSONB),
        *_ts(),
        sa.CheckConstraint("status IN ('open','paused','closed','archived')", name="ck_jobs_status"),
    )

    op.create_table(
        "candidates",
        _id(),
        _org(),
        sa.Column("full_name", sa.Text),
        sa.Column("email", sa.Text),
        sa.Column("phone", sa.Text),
        sa.Column("location", sa.Text),
        sa.Column("headline", sa.Text),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("content_type", sa.Text),
        sa.Column("file_size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("file_hash", sa.Text, nullable=False),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("extracted", pg.JSONB),
        sa.Column("experience", pg.JSONB),
        sa.Column("skills", pg.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.Text, nullable=False, server_default="processing"),
        sa.Column("error", sa.Text),
        *_ts(),
    )
    op.create_index("ix_candidates_org_hash", "candidates", ["organization_id", "file_hash"])

    op.create_table(
        "applications",
        _id(),
        _org(),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("candidate_id", pg.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("stage", sa.Text, nullable=False, server_default="new"),
        sa.Column("status", sa.Text, nullable=False, server_default="queued"),
        sa.Column("error", sa.Text),
        sa.Column("screening", pg.JSONB),
        sa.Column("screening_score", sa.Float),
        sa.Column("screening_label", sa.Text),
        sa.Column("final_score", sa.Float),
        sa.Column("recommendation", sa.Text),
        sa.Column("notes", sa.Text),
        *_ts(),
        sa.UniqueConstraint("job_id", "candidate_id", name="uq_applications_job_candidate"),
        sa.CheckConstraint("stage IN ('new','shortlisted','interviewing','offer','hired','rejected')",
                           name="ck_applications_stage"),
    )
    op.create_index("ix_applications_job_score", "applications", ["job_id", "screening_score"])

    op.create_table(
        "embeddings",
        _id(),
        _org(),
        sa.Column("owner_type", sa.Text, nullable=False),
        sa.Column("owner_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("vector", Vector(VECTOR_DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    # Retrieval is always filtered to one owner, so a btree on the owner gives exact,
    # fast scans. (An ANN index + owner filter can silently return fewer than k rows.)
    op.create_index("ix_embeddings_owner", "embeddings", ["owner_type", "owner_id"])

    op.create_table(
        "interview_sessions",
        _id(),
        _org(),
        sa.Column("application_id", pg.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("token_hash", sa.Text, nullable=False, unique=True),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("plan", pg.JSONB, nullable=False),
        sa.Column("current_question_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("follow_up_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("messages", pg.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("consent_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_ts(),
    )

    op.create_table(
        "evaluations",
        _id(),
        _org(),
        sa.Column("application_id", pg.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("interview_session_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        sa.Column("error", sa.Text),
        sa.Column("composite_score", sa.Float),
        sa.Column("recommendation", sa.Text),
        sa.Column("screening_score", sa.Float),
        sa.Column("interview_score", sa.Float),
        sa.Column("rubric", pg.JSONB),
        sa.Column("bias_audit", pg.JSONB),
        sa.Column("audit_trace", pg.JSONB),
        *_ts(),
    )

    op.create_table(
        "audit_logs",
        _id(),
        _org(),
        sa.Column("actor_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_type", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("entity_type", sa.Text),
        sa.Column("entity_id", pg.UUID(as_uuid=True)),
        sa.Column("details", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip_address", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_logs_org_created", "audit_logs", ["organization_id", "created_at"])


def downgrade() -> None:
    for table in ("audit_logs", "evaluations", "interview_sessions", "embeddings", "applications", "candidates",
                  "jobs", "users", "organizations"):
        op.drop_table(table)
