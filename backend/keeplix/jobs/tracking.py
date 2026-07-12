"""Run all due tracking plans once.

Production schedulers can invoke `python -m keeplix.jobs.tracking` at a fixed interval.
The database stores due times, so repeated invocations are idempotent at the plan level.
"""

from __future__ import annotations

import asyncio
import json

from sqlmodel import Session

from keeplix.core.db import engine
from keeplix.services.project_service import run_due_tracking_plans


async def run() -> None:
    with Session(engine) as session:
        result = await run_due_tracking_plans(session)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(run())
