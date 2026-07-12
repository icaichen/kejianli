"""add delivery records

Revision ID: f16c9e53b0d2
Revises: e05b8d42a9c1
Create Date: 2026-07-12 16:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "f16c9e53b0d2"
down_revision: str | None = "e05b8d42a9c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "delivery_record" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "delivery_record",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("cycle_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("work_item_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("artifact_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("method", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["geo_cycle.id"]),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_item.id"]),
        sa.ForeignKeyConstraint(["artifact_id"], ["optimization_artifact.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_delivery_record_project_id", "delivery_record", ["project_id"])
    op.create_index("ix_delivery_record_cycle_id", "delivery_record", ["cycle_id"])
    op.create_index("ix_delivery_record_work_item_id", "delivery_record", ["work_item_id"])
    op.create_index("ix_delivery_record_artifact_id", "delivery_record", ["artifact_id"])


def downgrade() -> None:
    op.drop_table("delivery_record")
