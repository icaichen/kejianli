"""store citation prompt text

Revision ID: c44d42d9a1f1
Revises: b982b5a85dc3
Create Date: 2026-07-11 12:30:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c44d42d9a1f1"
down_revision: str | None = "b982b5a85dc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("citation_result") as batch_op:
        batch_op.add_column(sa.Column("prompt_text", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("citation_result") as batch_op:
        batch_op.drop_column("prompt_text")
