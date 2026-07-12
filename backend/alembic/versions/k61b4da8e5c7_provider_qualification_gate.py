"""provider qualification gate

Revision ID: k61b4da8e5c7
Revises: j50a3c97f4b6
"""

import sqlalchemy as sa

from alembic import op

revision = "k61b4da8e5c7"
down_revision = "j50a3c97f4b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "engine_qualification" not in inspector.get_table_names():
        op.create_table(
            "engine_qualification",
            sa.Column("engine_id", sa.String(), nullable=False),
            sa.Column("surface_name", sa.String(), nullable=False),
            sa.Column("expected_acquisition", sa.String(), nullable=False),
            sa.Column("network_enabled", sa.Boolean(), nullable=False),
            sa.Column("region_language", sa.String(), nullable=False),
            sa.Column("auth_mode", sa.String(), nullable=False),
            sa.Column("citation_availability", sa.String(), nullable=False),
            sa.Column("measurement_scope", sa.String(), nullable=False),
            sa.Column("validation_status", sa.String(), nullable=False),
            sa.Column("report_eligible", sa.Boolean(), nullable=False),
            sa.Column("last_validated_at", sa.DateTime(), nullable=True),
            sa.Column("validation_notes", sa.String(), nullable=False),
            sa.Column("cost_note", sa.String(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["engine_id"], ["engine.id"]),
            sa.PrimaryKeyConstraint("engine_id"),
        )
    citation_columns = {column["name"] for column in inspector.get_columns("citation_run")}
    visibility_columns = {column["name"] for column in inspector.get_columns("visibility_score")}
    additions = (
        ("citation_run", citation_columns, "surface_name", sa.String(), ""),
        ("citation_run", citation_columns, "provider_acquisition", sa.String(), "stub"),
        ("citation_run", citation_columns, "measurement_scope", sa.String(), "stub"),
        ("citation_run", citation_columns, "report_eligible", sa.Boolean(), sa.false()),
        ("visibility_score", visibility_columns, "surface_name", sa.String(), ""),
        (
            "visibility_score",
            visibility_columns,
            "report_eligible",
            sa.Boolean(),
            sa.false(),
        ),
    )
    for table, existing, name, column_type, default in additions:
        if name not in existing:
            op.add_column(
                table,
                sa.Column(name, column_type, nullable=False, server_default=default),
            )


def downgrade() -> None:
    op.drop_column("visibility_score", "report_eligible")
    op.drop_column("visibility_score", "surface_name")
    op.drop_column("citation_run", "report_eligible")
    op.drop_column("citation_run", "measurement_scope")
    op.drop_column("citation_run", "provider_acquisition")
    op.drop_column("citation_run", "surface_name")
    op.drop_table("engine_qualification")
