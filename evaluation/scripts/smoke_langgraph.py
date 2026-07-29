"""Run an optional LangGraph integration smoke against the local Agent contract."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agents.langgraph_adapter import (  # noqa: E402
    build_langgraph_graph,
    langgraph_available,
)
from backend.app.agents.runner import AgentRunner  # noqa: E402
from backend.app.agents.state import AgentState  # noqa: E402
from backend.app.services.index_service import IndexService  # noqa: E402


def main() -> None:
    if not langgraph_available():
        print("LangGraph smoke skipped: optional dependency is unavailable")
        return

    graph = build_langgraph_graph(AgentRunner(IndexService()))
    initial = AgentState(
        "langgraph-smoke-001",
        "8080 端口占用怎么排查？",
        "sample-data",
    ).to_dict()
    initial["top_k"] = 5
    result = graph.invoke(initial)
    answer = result.get("answer") or {}
    citations = answer.get("citations", [])
    if result.get("status") != "completed":
        raise RuntimeError(f"LangGraph graph did not complete: {result.get('status')}")
    if not citations:
        raise RuntimeError("LangGraph graph returned no citations")
    print(
        "LangGraph smoke passed: "
        f"status={result.get('status')}, "
        f"category={result.get('category')}, "
        f"tool_calls={len(result.get('tool_calls', []))}, "
        f"citations={len(citations)}"
    )


if __name__ == "__main__":
    main()
