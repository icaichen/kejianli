"""measurement prompt quality

Revision ID: m83d6fca07e9
Revises: l72c5eb9f6d8
"""

import sqlalchemy as sa

from alembic import op

revision = "m83d6fca07e9"
down_revision = "l72c5eb9f6d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "citation_run",
        sa.Column("measurement_quality", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "visibility_score",
        sa.Column("measurement_quality", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.execute(
        sa.text(
            "UPDATE prompt SET intent = 'branded' WHERE EXISTS ("
            "SELECT 1 FROM brand_entity "
            "WHERE brand_entity.project_id = prompt.project_id "
            "AND instr(lower(prompt.text), lower(brand_entity.brand_name)) > 0)"
        )
    )
    op.execute(
        sa.text(
            "UPDATE prompt SET intent = 'comparison' WHERE intent IN ('category', 'branded') AND ("
            "prompt.text LIKE '%对比%' OR prompt.text LIKE '%比较%' OR "
            "prompt.text LIKE '%区别%' OR prompt.text LIKE '%哪个好%' OR "
            "lower(prompt.text) LIKE '% vs %')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE prompt SET intent = 'problem' WHERE intent = 'category' AND ("
            "prompt.text LIKE '%如何%' OR prompt.text LIKE '%怎么%' OR "
            "prompt.text LIKE '%为什么%' OR prompt.text LIKE '%提高%' OR "
            "prompt.text LIKE '%优化%')"
        )
    )


def downgrade() -> None:
    op.drop_column("visibility_score", "measurement_quality")
    op.drop_column("citation_run", "measurement_quality")
