"""version research briefs and prompt scopes

Revision ID: w83b1f5c6d97
Revises: v72a0e4b5c86
"""

import sqlalchemy as sa
from alembic import op

revision = "w83b1f5c6d97"
down_revision = "v72a0e4b5c86"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    project_columns = {column["name"] for column in inspector.get_columns("project")}
    if "brief_version" not in project_columns:
        op.add_column(
            "project",
            sa.Column("brief_version", sa.Integer(), nullable=False, server_default="1"),
        )
    prompt_set_columns = {
        column["name"] for column in inspector.get_columns("prompt_set")
    }
    if "brief_version" not in prompt_set_columns:
        op.add_column(
            "prompt_set",
            sa.Column("brief_version", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    prompt_set_columns = {
        column["name"] for column in inspector.get_columns("prompt_set")
    }
    if "brief_version" in prompt_set_columns:
        op.drop_column("prompt_set", "brief_version")
    project_columns = {column["name"] for column in inspector.get_columns("project")}
    if "brief_version" in project_columns:
        op.drop_column("project", "brief_version")
