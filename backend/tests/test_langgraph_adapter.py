import unittest

from backend.app.agents.langgraph_adapter import (
    LangGraphUnavailableError,
    build_langgraph_graph,
    langgraph_available,
)
from backend.app.services.index_service import IndexService
from backend.app.agents.runner import AgentRunner


class LangGraphAdapterTests(unittest.TestCase):
    def test_optional_runtime_reports_current_environment(self) -> None:
        if langgraph_available():
            self.skipTest("LangGraph is installed; optional adapter smoke belongs to integration tests")
        with self.assertRaises(LangGraphUnavailableError):
            build_langgraph_graph(AgentRunner(IndexService()))


if __name__ == "__main__":
    unittest.main()
