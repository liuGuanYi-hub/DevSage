"""Small graph execution contract used before the optional LangGraph runtime."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable

from .state import AgentState


AgentNode = Callable[[AgentState, dict[str, object]], str | None]


@dataclass(frozen=True)
class AgentLimits:
    """Hard limits that keep one Agent task finite and observable."""

    max_steps: int = 12
    max_tool_calls: int = 4
    max_runtime_seconds: float | None = 30.0

    def __post_init__(self) -> None:
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if self.max_runtime_seconds is not None and self.max_runtime_seconds <= 0:
            raise ValueError("max_runtime_seconds must be positive or None")


class AgentGraph:
    """Execute named nodes with explicit transitions and a hard step limit."""

    def __init__(
        self,
        nodes: dict[str, AgentNode],
        transitions: dict[str, str | None],
        limits: AgentLimits | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.nodes = nodes
        self.transitions = transitions
        self.limits = limits or AgentLimits()
        self.clock = clock

    def run(
        self,
        state: AgentState,
        context: dict[str, object] | None = None,
        start: str = "classify_question",
    ) -> AgentState:
        """Run until a node ends the task, a node returns a route, or limits stop it."""

        if self.limits.max_steps <= 0:
            state.status = "step_limit_reached"
            return state
        current = start
        node_context = context or {}
        executed_nodes = 0
        started_at = self.clock()
        while current is not None:
            if current not in self.nodes:
                raise ValueError(f"unknown Agent graph node: {current}")
            if (
                self.limits.max_runtime_seconds is not None
                and self.clock() - started_at >= self.limits.max_runtime_seconds
            ):
                state.status = "task_timeout"
                state.steps.append(_termination_step("maximum graph runtime reached"))
                break
            if executed_nodes >= self.limits.max_steps:
                state.status = "step_limit_reached"
                state.steps.append(
                    _termination_step("maximum graph steps reached")
                )
                break
            executed_nodes += 1
            next_node = self.nodes[current](state, node_context)
            if state.status != "running":
                break
            if next_node is not None:
                current = next_node
            else:
                current = self.transitions.get(current)
        return state


def _termination_step(detail: str):
    from .state import AgentStep

    return AgentStep("terminate", "limit_reached", detail)
