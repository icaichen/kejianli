"""add versioned prompt sets

Revision ID: d51a12e9f033
Revises: c44d42d9a1f1
Create Date: 2026-07-11 13:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "d51a12e9f033"
down_revision: str | None = "c44d42d9a1f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "prompt_set" not in inspector.get_table_names():
        op.create_table(
            "prompt_set",
            sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    indexes = {index["name"] for index in inspector.get_indexes("prompt_set")}
    if "ix_prompt_set_project_id" not in indexes:
        with op.batch_alter_table("prompt_set") as batch_op:
            batch_op.create_index(batch_op.f("ix_prompt_set_project_id"), ["project_id"], unique=False)
    with op.batch_alter_table("prompt") as batch_op:
        batch_op.add_column(sa.Column("prompt_set_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.create_foreign_key("fk_prompt_prompt_set", "prompt_set", ["prompt_set_id"], ["id"])
        batch_op.create_index(batch_op.f("ix_prompt_prompt_set_id"), ["prompt_set_id"], unique=False)
    with op.batch_alter_table("citation_run") as batch_op:
        batch_op.add_column(sa.Column("prompt_set_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.create_foreign_key("fk_citation_run_prompt_set", "prompt_set", ["prompt_set_id"], ["id"])
        batch_op.create_index(batch_op.f("ix_citation_run_prompt_set_id"), ["prompt_set_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("citation_run") as batch_op:
        batch_op.drop_index(batch_op.f("ix_citation_run_prompt_set_id"))
        batch_op.drop_constraint("fk_citation_run_prompt_set", type_="foreignkey")
        batch_op.drop_column("prompt_set_id")
    with op.batch_alter_table("prompt") as batch_op:
        batch_op.drop_index(batch_op.f("ix_prompt_prompt_set_id"))
        batch_op.drop_constraint("fk_prompt_prompt_set", type_="foreignkey")
        batch_op.drop_column("prompt_set_id")
    op.drop_table("prompt_set")
