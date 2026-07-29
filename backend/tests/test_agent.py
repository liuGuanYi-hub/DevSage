import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.agents.classifier import classify_question
from backend.app.agents.issue_tools import IssueToolError
from backend.app.agents.runner import AgentRunner
from backend.app.agents.state import AgentState
from backend.app.ingestion.models import ChunkRecord
from backend.app.retrieval.models import SearchResult
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

    def test_classifier_routes_code_details_before_generic_troubleshooting(self) -> None:
        self.assertEqual(
            "code_location",
            classify_question("示例 Spring Boot 项目当前配置的服务端口是多少？"),
        )
        self.assertEqual(
            "code_location",
            classify_question("Laravel 示例项目的任务列表接口使用了什么中间件？"),
        )
        self.assertEqual(
            "code_location",
            classify_question("AuthController 的 login 方法首先校验哪个凭据字段？"),
        )
        self.assertEqual(
            "code_location",
            classify_question("UserController 获取用户时调用了哪个业务方法？"),
        )
        self.assertEqual(
            "code_location",
            classify_question("Laravel Authenticate 中间件如何判断 Bearer Token 不是空值？"),
        )

    def test_code_question_uses_code_tool_and_citations(self) -> None:
        state = self.runner.run("用户接口入口在哪个类？", "sample-data")
        self.assertEqual("code_location", state.category)
        self.assertIn("search_code", state.tool_calls)
        self.assertIn("read_file", state.tool_calls)
        self.assertTrue(state.answer.citations)
        self.assertEqual("completed", state.status)

    def test_code_location_can_retrieve_config_and_supporting_documents(self) -> None:
        state = self.runner.run("Spring Boot 示例配置中的 server.port 是多少？", "sample-data")

        sources = {result.chunk.source_path for result in state.evidence}
        self.assertEqual("code_location", state.category)
        self.assertIn("search_code", state.tool_calls)
        self.assertIn("search_documents", state.tool_calls)
        self.assertIn(
            "repositories/springboot-demo/src/main/resources/application.yml",
            sources,
        )

    def test_project_summary_uses_document_and_code_evidence_contract(self) -> None:
        state = self.runner.run("总结用户接口项目技术点", "sample-data")
        self.assertEqual("project_summary", state.category)
        self.assertIsNotNone(state.answer)
        self.assertTrue(state.answer.evidence_sufficient)
        self.assertIn("项目总结", state.answer.answer)
        self.assertTrue(state.answer.citations)

    def test_project_summary_uses_a_wider_multi_source_evidence_budget(self) -> None:
        state = self.runner.run(
            "请总结 Spring Boot 示例项目的用户查询调用链和端口配置。",
            "sample-data",
        )

        sources = {result.chunk.source_path for result in state.evidence}
        self.assertGreaterEqual(len(state.evidence), 4)
        self.assertIn(
            "repositories/springboot-demo/src/main/java/com/example/devsage/UserController.java",
            sources,
        )
        self.assertIn(
            "repositories/springboot-demo/src/main/java/com/example/devsage/UserService.java",
            sources,
        )
        self.assertIn(
            "repositories/springboot-demo/src/main/resources/application.yml",
            sources,
        )

    def test_knowledge_write_uses_preview_tool_without_approval(self) -> None:
        state = self.runner.run("整理成一篇端口排查笔记", "sample-data")
        self.assertEqual("knowledge_write", state.category)
        self.assertIn("create_knowledge_note_preview", state.tool_calls)
        self.assertNotIn("approve_knowledge_note", state.tool_calls)

    def test_security_boundary_agent_respects_source_root_boundary(self) -> None:
        state = self.runner.run(
            "样例项目为什么不能把真实数据库密码写入配置模板？",
            "sample-data",
        )

        sources = {result.chunk.source_path for result in state.evidence}
        self.assertIn("README.md", sources)
        self.assertNotIn(".env.example", sources)

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

    def test_issue_tool_retries_once_and_records_the_failed_attempt(self) -> None:
        runner = AgentRunner(IndexService(), max_tool_retries=1)

        with patch(
            "backend.app.agents.runner.search_issues",
            side_effect=[IssueToolError("temporary read failure"), []],
        ):
            state = runner.run("这个历史故障之前出现过吗", "sample-data")

        self.assertEqual(1, state.tool_retry_count)
        self.assertEqual(["search_issues", "search_issues"], state.tool_calls)
        self.assertIn("tool_retry", [step.name for step in state.steps])
        self.assertEqual("insufficient_evidence", state.status)

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
        self.assertEqual(state.usage.total_token_estimate, restored.usage.total_token_estimate)
        self.assertEqual(state.usage.tool_calls, len(state.tool_calls))
        self.assertGreaterEqual(state.usage.runtime_ms, 0)

    def test_agent_usage_is_logged_without_query_content(self) -> None:
        with self.assertLogs("devsage.agent", level="INFO") as logs:
            state = self.runner.run("用户接口入口在哪里", "sample-data")

        self.assertTrue(any("agent_run_completed" in message for message in logs.output))
        self.assertTrue(all("用户接口入口在哪里" not in message for message in logs.output))
        self.assertGreater(state.usage.total_token_estimate, 0)

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

    def test_query_rewrite_retries_once_with_transparent_terms(self) -> None:
        class RewriteIndexService:
            def search_hybrid(self, _source_root: str, query: str, _top_k: int):
                if "login" not in query:
                    return "sample-data", []
                result = SearchResult(
                    chunk=ChunkRecord(
                        chunk_id="rewrite-1",
                        source_path="docs/auth.md",
                        file_type="markdown",
                        content="login requires auth middleware.",
                        start_line=1,
                        end_line=1,
                    ),
                    score=1.0,
                    matched_terms=("login", "auth"),
                )
                return "sample-data", [result]

            def read_file(self, *_args, **_kwargs):
                return "login requires auth middleware."

        runner = AgentRunner(RewriteIndexService())
        state = runner.run("登录流程", "sample-data")
        self.assertEqual("completed", state.status)
        self.assertEqual(1, state.retry_count)
        self.assertIn("login", state.rewritten_query)
        self.assertIn("query_rewrite", [step.name for step in state.steps])


if __name__ == "__main__":
    unittest.main()
