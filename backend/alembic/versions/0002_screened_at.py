"""Add applications.screened_at for time-to-screen and period metrics.

Revision ID: 0002_screened_at
Revises: 0001_v2
Create Date: 2026-09-28
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_screened_at"
down_revision = "0001_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("screened_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE applications SET screened_at = updated_at WHERE status = 'completed'")
    op.create_index("ix_applications_org_screened", "applications", ["organization_id", "screened_at"])


def downgrade() -> None:
    op.drop_index("ix_applications_org_screened", table_name="applications")
    op.drop_column("applications", "screened_at")
