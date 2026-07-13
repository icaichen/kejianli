"""competitor visibility

Revision ID: n94e70db18fa
Revises: m83d6fca07e9
"""

import sqlalchemy as sa

from alembic import op

revision = "n94e70db18fa"
down_revision = "m83d6fca07e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "citation_result",
        sa.Column("competitor_mentions", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "visibility_score",
        sa.Column("competitor_sov", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column("visibility_score", sa.Column("relative_sov", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("visibility_score", "relative_sov")
    op.drop_column("visibility_score", "competitor_sov")
    op.drop_column("citation_result", "competitor_mentions")
