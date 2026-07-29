import unittest
from pathlib import Path

from backend.app.agents.classifier import classify_question
from backend.app.agents.runner import AgentRunner
from backend.app.services.index_service import IndexService


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = AgentRunner(IndexService())

    def test_classifier_is_transparent(self) -> None:
        self.assertEqual("troubleshooting", classify_question("8080 端口被占用怎么排查"))
        self.assertEqual("code_location", classify_question("用户接口在哪个类"))
        self.assertEqual("project_summary", classify_question("总结项目技术点"))
        self.assertEqual("knowledge_write", classify_question("整理成一篇笔记"))
        self.assertEqual("git_history", classify_question("最近一次提交是什么"))
        self.assertEqual("issue_search", classify_question("这个历史故障之前出现过吗"))

    def test_code_question_uses_code_tool_and_citations(self) -> None:
        state = self.runner.run("用户接口入口在哪个类？", "sample-data")
        self.assertEqual("code_location", state.category)
        self.assertIn("search_code", state.tool_calls)
        self.assertIn("read_file", state.tool_calls)
        self.assertTrue(state.answer.citations)
        self.assertEqual("completed", state.status)

    def test_unknown_question_stops_with_insufficient_evidence(self) -> None:
        state = self.runner.run("frobulate_qzxv_731942_unindexed", "sample-data")
        self.assertEqual("insufficient_evidence", state.status)
        self.assertIn("evidence_check", [step.name for step in state.steps])

    def test_invalid_source_root_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.runner.run("端口怎么排查", "../")

    def test_troubleshooting_combines_documents_issues_and_git(self) -> None:
        state = self.runner.run("8080 端口故障之前是否出现过", "sample-data")
        self.assertEqual("troubleshooting", state.category)
        self.assertIn("search_documents", state.tool_calls)
        self.assertIn("search_issues", state.tool_calls)
        self.assertIn("get_git_history", state.tool_calls)


if __name__ == "__main__":
    unittest.main()
