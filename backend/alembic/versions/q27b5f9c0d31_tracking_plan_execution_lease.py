"""tracking plan execution lease

Revision ID: q27b5f9c0d31
Revises: p16a4e8b9c20
"""

import sqlalchemy as sa

from alembic import op

revision = "q27b5f9c0d31"
down_revision = "p16a4e8b9c20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("tracking_plan")}
    if "lease_token" not in columns:
        op.add_column("tracking_plan", sa.Column("lease_token", sa.String(), nullable=True))
    if "lease_expires_at" not in columns:
        op.add_column(
            "tracking_plan",
            sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("tracking_plan")}
    if "lease_expires_at" in columns:
        op.drop_column("tracking_plan", "lease_expires_at")
    if "lease_token" in columns:
        op.drop_column("tracking_plan", "lease_token")
