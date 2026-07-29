"""Optional LangGraph adapter for the tested local Agent graph contract."""

from __future__ import annotations

from typing import Any

from .runner import AgentRunner
from .state import AgentState


class LangGraphUnavailableError(RuntimeError):
    """Raised when the optional LangGraph dependency is not installed."""


def langgraph_available() -> bool:
    """Return whether the optional runtime can be imported."""

    try:
        import langgraph.graph  # type: ignore[import-not-found]
    except ImportError:
        return False
    return True


def build_langgraph_graph(runner: AgentRunner):
    """Compile the same four-node workflow with LangGraph when available.

    The adapter intentionally consumes and returns the local ``AgentState``
    dictionary shape. This keeps the offline graph and the optional runtime
    aligned while avoiding a hard dependency during MVP development.
    """

    try:
        from langgraph.graph import END, START, StateGraph  # type: ignore[import-not-found]
    except ImportError as exc:
        raise LangGraphUnavailableError(
            "LangGraph is optional and is not installed in the current environment"
        ) from exc

    graph = StateGraph(dict)
    for node_name in (
        "classify_question",
        "retrieve_evidence",
        "evidence_check",
        "compose_answer",
    ):
        graph.add_node(node_name, _wrap_node(runner, node_name))

    graph.add_edge(START, "classify_question")
    graph.add_conditional_edges(
        "classify_question",
        _route_to("retrieve_evidence"),
        {"retrieve_evidence": "retrieve_evidence", "end": END},
    )
    graph.add_conditional_edges(
        "retrieve_evidence",
        _route_to("evidence_check"),
        {"evidence_check": "evidence_check", "end": END},
    )
    graph.add_conditional_edges(
        "evidence_check",
        _route_to("compose_answer"),
        {"compose_answer": "compose_answer", "end": END},
    )
    graph.add_edge("compose_answer", END)
    return graph.compile()


def _wrap_node(runner: AgentRunner, node_name: str):
    def node(raw_state: dict[str, Any]) -> dict[str, Any]:
        state = AgentState.from_dict(raw_state)
        context = {"top_k": int(raw_state.get("top_k", 5))}
        runner.graph.nodes[node_name](state, context)
        payload = state.to_dict()
        payload["top_k"] = context["top_k"]
        return payload

    return node


def _route_to(next_node: str):
    def route(raw_state: dict[str, Any]) -> str:
        return next_node if raw_state.get("status") == "running" else "end"

    return route
