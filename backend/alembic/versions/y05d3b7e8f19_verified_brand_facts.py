"""add verified brand facts

Revision ID: y05d3b7e8f19
Revises: x94c2a6d7e08
"""

import sqlalchemy as sa
from alembic import op

revision = "y05d3b7e8f19"
down_revision = "x94c2a6d7e08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "brand_fact" in inspector.get_table_names():
        return
    op.create_table(
        "brand_fact",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("fact_type", sa.String(), nullable=False, server_default="product"),
        sa.Column("claim", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="verified"),
        sa.Column("created_by", sa.String(), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_brand_fact_project_id", "brand_fact", ["project_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "brand_fact" not in inspector.get_table_names():
        return
    op.drop_index("ix_brand_fact_project_id", table_name="brand_fact")
    op.drop_table("brand_fact")
