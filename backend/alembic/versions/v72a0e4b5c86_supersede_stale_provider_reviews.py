"""supersede stale provider validation reviews

Revision ID: v72a0e4b5c86
Revises: u61f9d3a4b75
"""

import sqlalchemy as sa
from alembic import op

revision = "v72a0e4b5c86"
down_revision = "u61f9d3a4b75"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE engine_validation_run AS old "
            "SET review_status = 'rejected', "
            "reviewed_at = COALESCE(old.finished_at, old.started_at), "
            "review_notes = '已被更新的 Provider 验证替代。' "
            "WHERE old.review_status = 'pending' "
            "AND EXISTS ("
            "SELECT 1 FROM engine_validation_run AS newer "
            "WHERE newer.engine_id = old.engine_id "
            "AND newer.started_at > old.started_at "
            "AND newer.review_status IN ('accepted', 'rejected')"
            ")"
        )
    )


def downgrade() -> None:
    # Supersession is an audit decision and must not be silently undone.
    pass
