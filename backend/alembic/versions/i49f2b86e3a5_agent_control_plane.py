"""add agent policy runs and actions

Revision ID: i49f2b86e3a5
Revises: h38e1a75d2f4
Create Date: 2026-07-12 18:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "i49f2b86e3a5"
down_revision: str | None = "h38e1a75d2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_policy",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("generation_engine", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("max_actions_per_run", sa.Integer(), nullable=False),
        sa.Column("per_run_budget", sa.Float(), nullable=False),
        sa.Column("monthly_budget", sa.Float(), nullable=False),
        sa.Column("allow_direct_publish", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
    )
    op.create_index("ix_agent_policy_project_id", "agent_policy", ["project_id"], unique=True)
    op.create_table(
        "agent_run",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("cycle_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("activity_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("trigger", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("goal", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("actual_cost", sa.Float(), nullable=False),
        sa.Column("error_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["geo_cycle.id"]),
        sa.ForeignKeyConstraint(["activity_id"], ["project_activity.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_run_project_id", "agent_run", ["project_id"])
    op.create_index("ix_agent_run_cycle_id", "agent_run", ["cycle_id"])
    op.create_index("ix_agent_run_activity_id", "agent_run", ["activity_id"])
    op.create_table(
        "agent_action",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("agent_run_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("cycle_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("work_item_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source_artifact_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("action_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("rationale", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("output_artifact_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("error_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_run.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["geo_cycle.id"]),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_item.id"]),
        sa.ForeignKeyConstraint(["source_artifact_id"], ["optimization_artifact.id"]),
        sa.ForeignKeyConstraint(["output_artifact_id"], ["optimization_artifact.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_action_agent_run_id", "agent_action", ["agent_run_id"])
    op.create_index("ix_agent_action_project_id", "agent_action", ["project_id"])
    op.create_index("ix_agent_action_cycle_id", "agent_action", ["cycle_id"])
    op.create_index("ix_agent_action_work_item_id", "agent_action", ["work_item_id"])


def downgrade() -> None:
    op.drop_table("agent_action")
    op.drop_table("agent_run")
    op.drop_table("agent_policy")
