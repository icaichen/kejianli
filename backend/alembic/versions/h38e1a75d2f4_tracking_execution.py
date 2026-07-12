"""add tracking execution linkage and failure state

Revision ID: h38e1a75d2f4
Revises: g27d0f64c1e3
Create Date: 2026-07-12 17:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "h38e1a75d2f4"
down_revision: str | None = "g27d0f64c1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    tracking_columns = _columns("tracking_plan")
    with op.batch_alter_table("tracking_plan") as batch_op:
        if "last_error" not in tracking_columns:
            batch_op.add_column(
                sa.Column("last_error", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
            )
        if "consecutive_failures" not in tracking_columns:
            batch_op.add_column(
                sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0")
            )

    run_columns = _columns("citation_run")
    if "tracking_plan_id" not in run_columns:
        with op.batch_alter_table("citation_run") as batch_op:
            batch_op.add_column(
                sa.Column("tracking_plan_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_citation_run_tracking_plan_id",
                "tracking_plan",
                ["tracking_plan_id"],
                ["id"],
            )
            batch_op.create_index("ix_citation_run_tracking_plan_id", ["tracking_plan_id"])

    score_columns = _columns("visibility_score")
    if "tracking_plan_id" not in score_columns:
        with op.batch_alter_table("visibility_score") as batch_op:
            batch_op.add_column(
                sa.Column("tracking_plan_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_visibility_score_tracking_plan_id",
                "tracking_plan",
                ["tracking_plan_id"],
                ["id"],
            )
            batch_op.create_index("ix_visibility_score_tracking_plan_id", ["tracking_plan_id"])


def downgrade() -> None:
    with op.batch_alter_table("visibility_score") as batch_op:
        batch_op.drop_index("ix_visibility_score_tracking_plan_id")
        batch_op.drop_constraint("fk_visibility_score_tracking_plan_id", type_="foreignkey")
        batch_op.drop_column("tracking_plan_id")
    with op.batch_alter_table("citation_run") as batch_op:
        batch_op.drop_index("ix_citation_run_tracking_plan_id")
        batch_op.drop_constraint("fk_citation_run_tracking_plan_id", type_="foreignkey")
        batch_op.drop_column("tracking_plan_id")
    with op.batch_alter_table("tracking_plan") as batch_op:
        batch_op.drop_column("consecutive_failures")
        batch_op.drop_column("last_error")
