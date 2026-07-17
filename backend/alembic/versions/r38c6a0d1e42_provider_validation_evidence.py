"""provider validation evidence and human review

Revision ID: r38c6a0d1e42
Revises: q27b5f9c0d31
"""

import sqlalchemy as sa
from alembic import op

revision = "r38c6a0d1e42"
down_revision = "q27b5f9c0d31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "engine_validation_run" not in inspector.get_table_names():
        op.create_table(
            "engine_validation_run",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("engine_id", sa.String(), nullable=False),
            sa.Column("profile_version", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("review_status", sa.String(), nullable=False),
            sa.Column("provider_acquisition", sa.String(), nullable=False),
            sa.Column("measurement_scope", sa.String(), nullable=False),
            sa.Column("checks", sa.JSON(), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("error_summary", sa.String(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("review_notes", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["engine_id"], ["engine.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_engine_validation_run_engine_id",
            "engine_validation_run",
            ["engine_id"],
        )

    if "engine_qualification" in inspector.get_table_names():
        legacy_notes = (
            "'已对照真实联网回答、引用 URL、请求 ID 与原始 SSE 事件。',"
            "'已验收两阶段联网搜索事件、来源 URL 与请求 ID。',"
            "'已验收联网回答、结构化 references 与请求 ID。',"
            "'仅验收普通模型回答采样，不具备搜索引用报告资格。'"
        )
        op.execute(
            sa.text(
                "UPDATE engine_qualification "
                "SET validation_status = 'pending', report_eligible = false, "
                "last_validated_at = NULL, "
                "validation_notes = '尚未完成带证据的 Provider 验证与人工审核。' "
                f"WHERE validation_notes IN ({legacy_notes})"
            )
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "engine_validation_run" in inspector.get_table_names():
        op.drop_index("ix_engine_validation_run_engine_id", table_name="engine_validation_run")
        op.drop_table("engine_validation_run")
