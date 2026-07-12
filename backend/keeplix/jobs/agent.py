"""Resume due Agent work that has already received human approval."""

from __future__ import annotations

import asyncio
import json

from sqlmodel import Session

from keeplix.core.db import engine
from keeplix.services.agent_service import run_due_agent_runs


async def run() -> None:
    with Session(engine) as session:
        results = await run_due_agent_runs(session)
    print(json.dumps([result.model_dump(mode="json") for result in results], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(run())
