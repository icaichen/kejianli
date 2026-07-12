"""backfill artifacts for existing cycle work items

Revision ID: e05b8d42a9c1
Revises: d94a7c30f8b2
Create Date: 2026-07-12 15:30:00
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "e05b8d42a9c1"
down_revision: str | None = "d94a7c30f8b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    work_items = bind.execute(
        sa.text(
            "SELECT id, project_id, cycle_id, title, detail, evidence_snapshot, "
            "output_snapshot FROM work_item WHERE id NOT IN "
            "(SELECT work_item_id FROM optimization_artifact)"
        )
    ).mappings()
    now = datetime.now(UTC)
    for item in work_items:
        output = item["output_snapshot"] or {}
        evidence = item["evidence_snapshot"] or {}
        if isinstance(output, str):
            output = json.loads(output)
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        candidates: list[tuple[str, str, str, dict]] = []
        if output.get("generated_content"):
            candidates.append(
                ("content", f"{item['title']}·内容草稿", output["generated_content"], {})
            )
        if output.get("jsonld"):
            candidates.append(("jsonld", f"{item['title']}·JSON-LD", "", output["jsonld"]))
        if not candidates:
            candidates.append(("instructions", f"{item['title']}·执行说明", item["detail"], {}))
        for kind, title, content, structured in candidates:
            bind.execute(
                sa.text(
                    "INSERT INTO optimization_artifact "
                    "(id, project_id, cycle_id, work_item_id, kind, title, version, status, "
                    "content, structured_content, source_snapshot, created_by, created_at, "
                    "updated_at, approved_at, implemented_at) VALUES "
                    "(:id, :project_id, :cycle_id, :work_item_id, :kind, :title, 1, 'draft', "
                    ":content, :structured_content, :source_snapshot, 'system', :created_at, "
                    ":updated_at, NULL, NULL)"
                ),
                {
                    "id": str(uuid4()),
                    "project_id": item["project_id"],
                    "cycle_id": item["cycle_id"],
                    "work_item_id": item["id"],
                    "kind": kind,
                    "title": title,
                    "content": content,
                    "structured_content": json.dumps(structured, ensure_ascii=False),
                    "source_snapshot": json.dumps(evidence, ensure_ascii=False),
                    "created_at": now,
                    "updated_at": now,
                },
            )


def downgrade() -> None:
    # Backfilled rows are indistinguishable from legitimate system-created v1 artifacts.
    # Keep user data intact on downgrade.
    pass
