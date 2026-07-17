"""freeze research brief version on measurements

Revision ID: x94c2a6d7e08
Revises: w83b1f5c6d97
"""

import sqlalchemy as sa
from alembic import op

revision = "x94c2a6d7e08"
down_revision = "w83b1f5c6d97"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    run_columns = {column["name"] for column in inspector.get_columns("citation_run")}
    if "brief_version" not in run_columns:
        op.add_column(
            "citation_run",
            sa.Column("brief_version", sa.Integer(), nullable=False, server_default="1"),
        )
    score_columns = {
        column["name"] for column in inspector.get_columns("visibility_score")
    }
    if "brief_version" not in score_columns:
        op.add_column(
            "visibility_score",
            sa.Column("brief_version", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    score_columns = {
        column["name"] for column in inspector.get_columns("visibility_score")
    }
    if "brief_version" in score_columns:
        op.drop_column("visibility_score", "brief_version")
    run_columns = {column["name"] for column in inspector.get_columns("citation_run")}
    if "brief_version" in run_columns:
        op.drop_column("citation_run", "brief_version")
