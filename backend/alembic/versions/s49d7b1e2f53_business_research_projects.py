"""business research project context

Revision ID: s49d7b1e2f53
Revises: r38c6a0d1e42
"""

import sqlalchemy as sa
from alembic import op

revision = "s49d7b1e2f53"
down_revision = "r38c6a0d1e42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("project")}
    additions = (
        ("market", "中国"),
        ("category", ""),
        ("research_objective", ""),
    )
    for name, default in additions:
        if name not in columns:
            op.add_column(
                "project",
                sa.Column(name, sa.String(), nullable=False, server_default=default),
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("project")}
    for name in ("research_objective", "category", "market"):
        if name in columns:
            op.drop_column("project", name)
