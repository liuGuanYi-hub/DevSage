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


if __name__ == "__main__":
    unittest.main()
