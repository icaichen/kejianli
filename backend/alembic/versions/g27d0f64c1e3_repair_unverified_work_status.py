"""repair work completed without implementation evidence

Revision ID: g27d0f64c1e3
Revises: f16c9e53b0d2
Create Date: 2026-07-12 16:30:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "g27d0f64c1e3"
down_revision: str | None = "f16c9e53b0d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE work_item SET status = 'in_progress', completed_at = NULL "
            "WHERE status = 'done' AND EXISTS ("
            "SELECT 1 FROM optimization_artifact artifact "
            "WHERE artifact.work_item_id = work_item.id "
            "AND artifact.status NOT IN ('implemented', 'superseded'))"
        )
    )


def downgrade() -> None:
    pass
