"""add visibility confidence intervals

Revision ID: a62d4f09c8e1
Revises: f34c18bd94d6
Create Date: 2026-07-12 11:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a62d4f09c8e1"
down_revision: str | None = "f34c18bd94d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("visibility_score")
    }
    additions = (
        "entity_ci_low",
        "entity_ci_high",
        "citation_ci_low",
        "citation_ci_high",
    )
    with op.batch_alter_table("visibility_score") as batch_op:
        for name in additions:
            if name not in existing:
                batch_op.add_column(sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    existing = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("visibility_score")
    }
    with op.batch_alter_table("visibility_score") as batch_op:
        for name in (
            "citation_ci_high",
            "citation_ci_low",
            "entity_ci_high",
            "entity_ci_low",
        ):
            if name in existing:
                batch_op.drop_column(name)
