"""轻量、显式的 Agent / Workflow 抽象（无私有框架依赖）。

- Agent：有明确 input/output 的可复用工作单元。
- Workflow：把多个 agent 步骤按顺序组合，记录每步产物，便于观测与移交。
后续「自主循环」= 把现有 agent 编进一个循环 workflow，不需重写内核。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from keeplix.core.logging import get_logger

log = get_logger("agents")


class Agent[TIn, TOut](ABC):
    """所有 agent 继承此基类，实现 async run(input) -> output。"""

    name: str = "agent"

    @abstractmethod
    async def run(self, payload: TIn) -> TOut: ...


@dataclass
class WorkflowStep:
    agent_name: str
    output: Any


@dataclass
class WorkflowResult:
    outputs: dict[str, Any] = field(default_factory=dict)
    steps: list[WorkflowStep] = field(default_factory=list)


class Workflow:
    """顺序执行若干 (key, agent, input) 步骤，收集产物。"""

    def __init__(self) -> None:
        self._result = WorkflowResult()

    async def step(self, key: str, agent: Agent, payload: Any) -> Any:
        log.info("workflow step: %s (%s)", key, agent.name)
        output = await agent.run(payload)
        self._result.outputs[key] = output
        self._result.steps.append(WorkflowStep(agent_name=agent.name, output=output))
        return output

    @property
    def result(self) -> WorkflowResult:
        return self._result
