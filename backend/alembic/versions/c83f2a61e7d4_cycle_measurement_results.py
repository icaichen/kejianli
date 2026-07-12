"""add cycle measurement configuration and results

Revision ID: c83f2a61e7d4
Revises: b71e20d4a6f3
Create Date: 2026-07-12 14:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c83f2a61e7d4"
down_revision: str | None = "b71e20d4a6f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("geo_cycle")
    }
    with op.batch_alter_table("geo_cycle") as batch_op:
        for name in (
            "measurement_config",
            "baseline_summary",
            "verification_summary",
        ):
            if name not in existing:
                batch_op.add_column(sa.Column(name, sa.JSON(), nullable=True))


def downgrade() -> None:
    existing = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("geo_cycle")
    }
    with op.batch_alter_table("geo_cycle") as batch_op:
        for name in (
            "verification_summary",
            "baseline_summary",
            "measurement_config",
        ):
            if name in existing:
                batch_op.drop_column(name)
