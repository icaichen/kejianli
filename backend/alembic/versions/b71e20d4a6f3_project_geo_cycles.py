"""add project geo cycles and shared work queue

Revision ID: b71e20d4a6f3
Revises: a62d4f09c8e1
Create Date: 2026-07-12 13:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "b71e20d4a6f3"
down_revision: str | None = "a62d4f09c8e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()
    if "geo_cycle" not in tables:
        op.create_table(
            "geo_cycle",
            sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("objective", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("stage", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_geo_cycle_project_id", "geo_cycle", ["project_id"])

    activity_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("project_activity")
    }
    if "cycle_id" not in activity_columns:
        with op.batch_alter_table("project_activity") as batch_op:
            batch_op.add_column(
                sa.Column("cycle_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_project_activity_cycle_id_geo_cycle", "geo_cycle", ["cycle_id"], ["id"]
            )
            batch_op.create_index("ix_project_activity_cycle_id", ["cycle_id"])

    if "work_item" not in tables:
        op.create_table(
            "work_item",
            sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("cycle_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("source_activity_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("recommendation_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("detail", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("priority", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("execution_mode", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("evidence_snapshot", sa.JSON(), nullable=True),
            sa.Column("output_snapshot", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
            sa.ForeignKeyConstraint(["cycle_id"], ["geo_cycle.id"]),
            sa.ForeignKeyConstraint(["source_activity_id"], ["project_activity.id"]),
            sa.ForeignKeyConstraint(["recommendation_id"], ["recommendation.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_work_item_project_id", "work_item", ["project_id"])
        op.create_index("ix_work_item_cycle_id", "work_item", ["cycle_id"])
        op.create_index("ix_work_item_source_activity_id", "work_item", ["source_activity_id"])

    deliverable_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("deliverable")
    }
    if "cycle_id" not in deliverable_columns:
        with op.batch_alter_table("deliverable") as batch_op:
            batch_op.add_column(
                sa.Column("cycle_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_deliverable_cycle_id_geo_cycle", "geo_cycle", ["cycle_id"], ["id"]
            )
            batch_op.create_index("ix_deliverable_cycle_id", ["cycle_id"])


def downgrade() -> None:
    with op.batch_alter_table("deliverable") as batch_op:
        batch_op.drop_index("ix_deliverable_cycle_id")
        batch_op.drop_constraint("fk_deliverable_cycle_id_geo_cycle", type_="foreignkey")
        batch_op.drop_column("cycle_id")
    op.drop_table("work_item")
    with op.batch_alter_table("project_activity") as batch_op:
        batch_op.drop_index("ix_project_activity_cycle_id")
        batch_op.drop_constraint("fk_project_activity_cycle_id_geo_cycle", type_="foreignkey")
        batch_op.drop_column("cycle_id")
    op.drop_table("geo_cycle")
