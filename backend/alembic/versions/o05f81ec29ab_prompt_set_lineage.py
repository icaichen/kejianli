"""prompt set lineage

Revision ID: o05f81ec29ab
Revises: n94e70db18fa
"""

import sqlalchemy as sa

from alembic import op

revision = "o05f81ec29ab"
down_revision = "n94e70db18fa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prompt_set",
        sa.Column("source_prompt_set_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_prompt_set_source_prompt_set_id",
        "prompt_set",
        ["source_prompt_set_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_prompt_set_source_prompt_set_id", table_name="prompt_set")
    op.drop_column("prompt_set", "source_prompt_set_id")
