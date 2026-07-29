import json
import unittest
from pathlib import Path

from backend.app.agents.classifier import classify_question
from backend.app.agents.runner import AgentRunner
from backend.app.agents.state import AgentState
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

    def test_project_summary_uses_document_and_code_evidence_contract(self) -> None:
        state = self.runner.run("总结用户接口项目技术点", "sample-data")
        self.assertEqual("project_summary", state.category)
        self.assertIsNotNone(state.answer)
        self.assertTrue(state.answer.evidence_sufficient)
        self.assertIn("项目总结", state.answer.answer)
        self.assertTrue(state.answer.citations)

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

    def test_git_diff_question_is_classified_separately(self) -> None:
        self.assertEqual("git_diff", classify_question("最近一次提交改了什么"))

    def test_git_diff_question_uses_read_only_diff_tool(self) -> None:
        state = self.runner.run("最近一次提交改了什么", "sample-data")
        self.assertEqual("git_diff", state.category)
        self.assertIn("get_commit_diff", state.tool_calls)
        self.assertTrue(state.answer.evidence_sufficient)

    def test_state_snapshot_round_trip_is_json_safe(self) -> None:
        state = self.runner.run("用户接口入口在哪里", "sample-data")
        snapshot = state.to_dict()
        json.dumps(snapshot, ensure_ascii=False)
        restored = AgentState.from_dict(snapshot)
        self.assertEqual(state.task_id, restored.task_id)
        self.assertEqual(state.status, restored.status)
        self.assertEqual(state.tool_calls, restored.tool_calls)
        self.assertEqual(state.answer.citations, restored.answer.citations)

    def test_tool_limit_stops_before_unbounded_read(self) -> None:
        runner = AgentRunner(IndexService(), max_tool_calls=1)
        state = runner.run("用户接口入口在哪里", "sample-data")
        self.assertEqual("tool_limit_reached", state.status)
        self.assertIsNotNone(state.answer)

    def test_bounded_task_can_resume_with_a_new_budget(self) -> None:
        runner = AgentRunner(IndexService(), max_tool_calls=1)
        state = runner.run("用户接口入口在哪里", "sample-data")
        self.assertEqual("tool_limit_reached", state.status)
        runner.max_tool_calls = 2
        resumed = runner.resume(state)
        self.assertEqual("completed", resumed.status)
        self.assertIn("resume", [step.name for step in resumed.steps])


if __name__ == "__main__":
    unittest.main()
