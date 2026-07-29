import unittest

from backend.app.agents.graph import AgentGraph, AgentLimits
from backend.app.agents.state import AgentState, AgentStep


class AgentGraphTests(unittest.TestCase):
    def test_graph_stops_a_loop_at_the_step_limit(self) -> None:
        def loop_node(state: AgentState, _context: dict[str, object]) -> str:
            state.steps.append(AgentStep("loop", "running", "again"))
            return "loop"

        graph = AgentGraph(
            nodes={"loop": loop_node},
            transitions={},
            limits=AgentLimits(max_steps=2, max_tool_calls=1),
        )
        state = AgentState("task", "query", "sample-data")
        graph.run(state, start="loop")
        self.assertEqual("step_limit_reached", state.status)
        self.assertEqual("terminate", state.steps[-1].name)

    def test_graph_stops_when_runtime_budget_is_exhausted(self) -> None:
        clock_values = iter((0.0, 0.0, 2.0))

        def loop_node(state: AgentState, _context: dict[str, object]) -> str:
            state.steps.append(AgentStep("loop", "running", "again"))
            return "loop"

        graph = AgentGraph(
            nodes={"loop": loop_node},
            transitions={},
            limits=AgentLimits(max_steps=10, max_tool_calls=1, max_runtime_seconds=1.0),
            clock=lambda: next(clock_values),
        )
        state = AgentState("task", "query", "sample-data")
        graph.run(state, start="loop")
        self.assertEqual("task_timeout", state.status)
        self.assertEqual("terminate", state.steps[-1].name)


if __name__ == "__main__":
    unittest.main()
