"""Run due post-delivery GEO cycle retests once.

Production schedulers can invoke `python -m keeplix.jobs.retests` at a fixed interval.
The database keeps the due time and execution state for every cycle.
"""

from __future__ import annotations

import asyncio
import json

from sqlmodel import Session

from keeplix.core.db import engine
from keeplix.services.project_service import run_due_cycle_retests


async def run() -> None:
    with Session(engine) as session:
        result = await run_due_cycle_retests(session)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(run())
