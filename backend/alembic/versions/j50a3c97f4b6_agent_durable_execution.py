"""agent durable execution

Revision ID: j50a3c97f4b6
Revises: i49f2b86e3a5
"""

from alembic import op
import sqlalchemy as sa

revision = "j50a3c97f4b6"
down_revision = "i49f2b86e3a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_policy", sa.Column("auto_plan_on_tracking", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("agent_run", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("agent_run", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("agent_run", sa.Column("heartbeat_at", sa.DateTime(), nullable=True))
    op.add_column("agent_run", sa.Column("next_attempt_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_run", "next_attempt_at")
    op.drop_column("agent_run", "heartbeat_at")
    op.drop_column("agent_run", "max_attempts")
    op.drop_column("agent_run", "attempt_count")
    op.drop_column("agent_policy", "auto_plan_on_tracking")
