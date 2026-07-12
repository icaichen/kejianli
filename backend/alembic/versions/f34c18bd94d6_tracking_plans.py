"""add tracking plans

Revision ID: f34c18bd94d6
Revises: e712d0c49b2a
Create Date: 2026-07-12 01:30:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "f34c18bd94d6"
down_revision: str | None = "e712d0c49b2a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tracking_plan" not in inspector.get_table_names():
        op.create_table(
            "tracking_plan",
            sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("prompt_set_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("engine_ids", sa.JSON(), nullable=True),
            sa.Column("samples", sa.Integer(), nullable=False),
            sa.Column("cadence", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("next_run_at", sa.DateTime(), nullable=True),
            sa.Column("last_run_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
            sa.ForeignKeyConstraint(["prompt_set_id"], ["prompt_set.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    indexes = {index["name"] for index in inspector.get_indexes("tracking_plan")}
    if "ix_tracking_plan_project_id" not in indexes:
        with op.batch_alter_table("tracking_plan") as batch_op:
            batch_op.create_index(
                batch_op.f("ix_tracking_plan_project_id"),
                ["project_id"],
                unique=False,
            )


def downgrade() -> None:
    op.drop_table("tracking_plan")
