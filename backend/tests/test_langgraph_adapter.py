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

    def test_installed_runtime_executes_the_local_agent_contract(self) -> None:
        if not langgraph_available():
            self.skipTest("LangGraph is not installed in the current environment")

        graph = build_langgraph_graph(AgentRunner(IndexService()))
        result = graph.invoke(
            {
                "task_id": "langgraph-test-001",
                "query": "8080 端口占用怎么排查？",
                "source_root": "sample-data",
                "top_k": 5,
            }
        )

        self.assertEqual("completed", result["status"])
        self.assertEqual("troubleshooting", result["category"])
        self.assertTrue(result["answer"]["citations"])

    def test_installed_runtime_can_store_completed_state_in_a_checkpoint(self) -> None:
        if not langgraph_available():
            self.skipTest("LangGraph is not installed in the current environment")

        from langgraph.checkpoint.memory import MemorySaver

        config = {"configurable": {"thread_id": "langgraph-checkpoint-001"}}
        graph = build_langgraph_graph(
            AgentRunner(IndexService()),
            checkpointer=MemorySaver(),
        )
        graph.invoke(
            {
                "task_id": "langgraph-checkpoint-001",
                "query": "8080 端口占用怎么排查？",
                "source_root": "sample-data",
                "top_k": 5,
            },
            config,
        )

        checkpoint = graph.get_state(config)
        self.assertEqual("completed", checkpoint.values["status"])
        self.assertTrue(checkpoint.values["answer"]["citations"])


if __name__ == "__main__":
    unittest.main()
