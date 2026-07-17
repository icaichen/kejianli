"""persist visibility measurement scope

Revision ID: t50e8c2f3a64
Revises: s49d7b1e2f53
"""

import sqlalchemy as sa
from alembic import op

revision = "t50e8c2f3a64"
down_revision = "s49d7b1e2f53"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("visibility_score")}
    for name in ("provider_acquisition", "measurement_scope"):
        if name not in columns:
            op.add_column(
                "visibility_score",
                sa.Column(
                    name,
                    sa.String(),
                    nullable=False,
                    server_default="legacy_unclassified",
                ),
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("visibility_score")}
    for name in ("measurement_scope", "provider_acquisition"):
        if name in columns:
            op.drop_column("visibility_score", name)
