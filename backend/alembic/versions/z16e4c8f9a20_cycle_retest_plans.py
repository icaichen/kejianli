"""add durable cycle retest plans

Revision ID: z16e4c8f9a20
Revises: y05d3b7e8f19
"""

import sqlalchemy as sa
from alembic import op

revision = "z16e4c8f9a20"
down_revision = "y05d3b7e8f19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "cycle_retest_plan" in inspector.get_table_names():
        return
    op.create_table(
        "cycle_retest_plan",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("cycle_id", sa.String(), nullable=False),
        sa.Column("source_delivery_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="scheduled"),
        sa.Column("scheduled_for", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["geo_cycle.id"]),
        sa.ForeignKeyConstraint(["source_delivery_id"], ["delivery_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cycle_retest_plan_project_id", "cycle_retest_plan", ["project_id"])
    op.create_index("ix_cycle_retest_plan_cycle_id", "cycle_retest_plan", ["cycle_id"])
    op.create_index(
        "ix_cycle_retest_plan_source_delivery_id",
        "cycle_retest_plan",
        ["source_delivery_id"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "cycle_retest_plan" not in inspector.get_table_names():
        return
    op.drop_index("ix_cycle_retest_plan_source_delivery_id", table_name="cycle_retest_plan")
    op.drop_index("ix_cycle_retest_plan_cycle_id", table_name="cycle_retest_plan")
    op.drop_index("ix_cycle_retest_plan_project_id", table_name="cycle_retest_plan")
    op.drop_table("cycle_retest_plan")
