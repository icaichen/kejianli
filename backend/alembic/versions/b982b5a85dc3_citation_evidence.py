"""store citation evidence

Revision ID: b982b5a85dc3
Revises: a44c3eb848c8
Create Date: 2026-07-11 12:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b982b5a85dc3"
down_revision: str | None = "a44c3eb848c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("citation_result") as batch_op:
        batch_op.add_column(sa.Column("raw_response", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("provider_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("citation_result") as batch_op:
        batch_op.drop_column("provider_metadata")
        batch_op.drop_column("raw_response")
