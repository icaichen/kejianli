"""add versioned optimization artifacts

Revision ID: d94a7c30f8b2
Revises: c83f2a61e7d4
Create Date: 2026-07-12 15:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "d94a7c30f8b2"
down_revision: str | None = "c83f2a61e7d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "optimization_artifact" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "optimization_artifact",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("cycle_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("work_item_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("structured_content", sa.JSON(), nullable=True),
        sa.Column("source_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("implemented_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["geo_cycle.id"]),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_item.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_optimization_artifact_project_id", "optimization_artifact", ["project_id"])
    op.create_index("ix_optimization_artifact_cycle_id", "optimization_artifact", ["cycle_id"])
    op.create_index(
        "ix_optimization_artifact_work_item_id",
        "optimization_artifact",
        ["work_item_id"],
    )


def downgrade() -> None:
    op.drop_table("optimization_artifact")
