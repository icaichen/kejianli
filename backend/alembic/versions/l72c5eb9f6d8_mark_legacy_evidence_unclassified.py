"""mark legacy evidence unclassified

Revision ID: l72c5eb9f6d8
Revises: k61b4da8e5c7
"""

import sqlalchemy as sa

from alembic import op

revision = "l72c5eb9f6d8"
down_revision = "k61b4da8e5c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE citation_run "
            "SET measurement_scope = 'legacy_unclassified', "
            "provider_acquisition = 'unknown', "
            "surface_name = engine_id || '（历史未分级）' "
            "WHERE surface_name = '' AND report_eligible = 0"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE citation_run "
            "SET measurement_scope = 'stub', provider_acquisition = 'stub', surface_name = '' "
            "WHERE measurement_scope = 'legacy_unclassified'"
        )
    )
