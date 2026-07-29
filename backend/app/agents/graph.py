"""Small graph execution contract used before the optional LangGraph runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .state import AgentState


AgentNode = Callable[[AgentState, dict[str, object]], str | None]


@dataclass(frozen=True)
class AgentLimits:
    """Hard limits that keep one Agent task finite and observable."""

    max_steps: int = 12
    max_tool_calls: int = 4


class AgentGraph:
    """Execute named nodes with explicit transitions and a hard step limit."""

    def __init__(
        self,
        nodes: dict[str, AgentNode],
        transitions: dict[str, str | None],
        limits: AgentLimits | None = None,
    ) -> None:
        self.nodes = nodes
        self.transitions = transitions
        self.limits = limits or AgentLimits()

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
        while current is not None:
            if current not in self.nodes:
                raise ValueError(f"unknown Agent graph node: {current}")
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
