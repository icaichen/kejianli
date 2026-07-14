"""engine runtime status

Revision ID: p16a4e8b9c20
Revises: o05f81ec29ab
"""

import sqlalchemy as sa

from alembic import op

revision = "p16a4e8b9c20"
down_revision = "o05f81ec29ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "engine_runtime_status" in inspector.get_table_names():
        return
    op.create_table(
        "engine_runtime_status",
        sa.Column("engine_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["engine_id"], ["engine.id"]),
        sa.PrimaryKeyConstraint("engine_id"),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "engine_runtime_status" not in inspector.get_table_names():
        return
    op.drop_table("engine_runtime_status")
