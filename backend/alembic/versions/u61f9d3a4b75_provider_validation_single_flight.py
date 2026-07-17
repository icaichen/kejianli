"""allow only one running validation per engine

Revision ID: u61f9d3a4b75
Revises: t50e8c2f3a64
"""

import sqlalchemy as sa
from alembic import op

revision = "u61f9d3a4b75"
down_revision = "t50e8c2f3a64"
branch_labels = None
depends_on = None

_INDEX = "uq_engine_validation_run_one_running"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("engine_validation_run")}
    if _INDEX not in indexes:
        running = sa.text("status = 'running'")
        op.create_index(
            _INDEX,
            "engine_validation_run",
            ["engine_id"],
            unique=True,
            sqlite_where=running,
            postgresql_where=running,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("engine_validation_run")}
    if _INDEX in indexes:
        op.drop_index(_INDEX, table_name="engine_validation_run")
