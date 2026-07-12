"""add unified project activities

Revision ID: e712d0c49b2a
Revises: d51a12e9f033
Create Date: 2026-07-11 22:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "e712d0c49b2a"
down_revision: str | None = "d51a12e9f033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "project_activity" not in inspector.get_table_names():
        op.create_table(
            "project_activity",
            sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("triggered_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sa.Enum("pending", "running", "done", "failed", name="runstatus"), nullable=False),
            sa.Column("input_snapshot", sa.JSON(), nullable=True),
            sa.Column("output_summary", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    inspector = sa.inspect(bind)
    activity_indexes = {index["name"] for index in inspector.get_indexes("project_activity")}
    if "ix_project_activity_project_id" not in activity_indexes:
        with op.batch_alter_table("project_activity") as batch_op:
            batch_op.create_index(batch_op.f("ix_project_activity_project_id"), ["project_id"], unique=False)

    for table_name in ("citation_run", "audit_run"):
        inspector = sa.inspect(bind)
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "activity_id" not in columns:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(sa.Column("activity_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
                batch_op.create_foreign_key(f"fk_{table_name}_activity", "project_activity", ["activity_id"], ["id"])
                batch_op.create_index(batch_op.f(f"ix_{table_name}_activity_id"), ["activity_id"], unique=False)

    metadata = sa.MetaData()
    activity_table = sa.Table("project_activity", metadata, autoload_with=bind)
    run_table = sa.Table("citation_run", metadata, autoload_with=bind)
    result_table = sa.Table("citation_result", metadata, autoload_with=bind)
    legacy_runs = bind.execute(sa.select(run_table).where(run_table.c.activity_id.is_(None))).mappings().all()
    for run in legacy_runs:
        results = bind.execute(
            sa.select(result_table).where(result_table.c.citation_run_id == run["id"])
        ).mappings().all()
        questions = list(dict.fromkeys(result["prompt_text"] for result in results if result.get("prompt_text")))
        activity_id = str(uuid4())
        bind.execute(activity_table.insert().values(
            id=activity_id,
            project_id=run["project_id"],
            kind="visibility",
            title="运行 AI 可见度检测",
            triggered_by="user",
            status=run["status"],
            input_snapshot={
                "questions": questions,
                "engine_ids": [run["engine_id"]],
                "samples_per_question": run["samples"],
                "legacy": True,
            },
            output_summary={
                "question_count": len(questions),
                "sample_count": len(results),
                "brand_mention_count": sum(bool(result["brand_mentioned"]) for result in results),
                "own_domain_citation_count": sum(bool(result["own_domain_cited"]) for result in results),
            },
            started_at=run["started_at"],
            finished_at=run["finished_at"],
        ))
        bind.execute(run_table.update().where(run_table.c.id == run["id"]).values(activity_id=activity_id))


def downgrade() -> None:
    for table_name in ("audit_run", "citation_run"):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_index(batch_op.f(f"ix_{table_name}_activity_id"))
            batch_op.drop_constraint(f"fk_{table_name}_activity", type_="foreignkey")
            batch_op.drop_column("activity_id")
    op.drop_table("project_activity")
