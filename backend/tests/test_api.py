import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual("ok", response.json()["status"])

    def test_index_and_search_endpoints_return_citations(self) -> None:
        index_response = self.client.post(
            "/api/index",
            json={"source_root": "sample-data"},
        )
        self.assertEqual(200, index_response.status_code)
        self.assertGreater(index_response.json()["document_count"], 0)

        second_index_response = self.client.post(
            "/api/index",
            json={"source_root": "sample-data"},
        )
        self.assertEqual(200, second_index_response.status_code)
        self.assertGreater(second_index_response.json()["unchanged_documents"], 0)

        search_response = self.client.post(
            "/api/search",
            json={
                "source_root": "sample-data",
                "query": "8080 端口占用",
                "top_k": 5,
            },
        )
        self.assertEqual(200, search_response.status_code)
        results = search_response.json()["results"]
        self.assertTrue(results)
        self.assertTrue(any("springboot-errors.md" in result["source_path"] for result in results))
        self.assertTrue(all(result["citation"] for result in results))

    def test_api_rejects_source_root_escape(self) -> None:
        response = self.client.post(
            "/api/index",
            json={"source_root": "../"},
        )
        self.assertEqual(400, response.status_code)

    def test_knowledge_note_preview_requires_safe_path(self) -> None:
        response = self.client.post(
            "/api/knowledge-notes/preview",
            json={
                "title": "端口排查",
                "content": "# 端口排查",
                "target_path": "SpringBoot/端口排查.md",
                "source_citations": ["sample-data/docs/springboot-errors.md:1-8"],
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("pending", response.json()["status"])

        unsafe_response = self.client.post(
            "/api/knowledge-notes/preview",
            json={
                "title": "Unsafe",
                "content": "content",
                "target_path": "../outside.md",
            },
        )
        self.assertEqual(400, unsafe_response.status_code)

    def test_answer_endpoint_returns_evidence_grounded_response(self) -> None:
        response = self.client.post(
            "/api/answer",
            json={
                "source_root": "sample-data",
                "query": "8080 端口被占用怎么排查？",
                "top_k": 5,
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["evidence_sufficient"])
        self.assertTrue(payload["citations"])
        self.assertIn("springboot-errors.md", payload["answer"])

    def test_answer_endpoint_refuses_unsupported_conclusion(self) -> None:
        response = self.client.post(
            "/api/answer",
            json={
                "source_root": "sample-data",
                "query": "frobulate_qzxv_731942_unindexed",
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertFalse(payload["evidence_sufficient"])
        self.assertEqual([], payload["citations"])

    def test_answer_stream_returns_sse_events(self) -> None:
        response = self.client.post(
            "/api/answer/stream",
            json={
                "source_root": "sample-data",
                "query": "8080 端口被占用怎么排查？",
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertIn("event: meta", response.text)
        self.assertIn("event: done", response.text)

    def test_agent_endpoint_reports_tools_and_steps(self) -> None:
        response = self.client.post(
            "/api/agent/run",
            json={
                "source_root": "sample-data",
                "query": "用户接口入口在哪个类？",
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("code_location", payload["category"])
        self.assertIn("search_code", payload["tool_calls"])
        self.assertIn("read_file", payload["tool_calls"])
        self.assertTrue(payload["steps"])
        self.assertTrue(payload["citations"])

    def test_agent_endpoint_supports_issue_search(self) -> None:
        response = self.client.post(
            "/api/agent/run",
            json={
                "source_root": "sample-data",
                "query": "Laravel 认证 401 之前出现过吗",
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("issue_search", payload["category"])
        self.assertIn("search_issues", payload["tool_calls"])
        self.assertTrue(any("ISSUE-002" in citation for citation in payload["citations"]))

    def test_agent_task_can_be_explicitly_persisted_and_loaded(self) -> None:
        response = self.client.post(
            "/api/agent/run",
            json={
                "source_root": "sample-data",
                "query": "用户接口入口在哪个类？",
                "persist": True,
            },
        )
        self.assertEqual(200, response.status_code)
        task_id = response.json()["task_id"]
        try:
            loaded = self.client.get(f"/api/agent/tasks/{task_id}")
            self.assertEqual(200, loaded.status_code)
            self.assertEqual(task_id, loaded.json()["task_id"])
        finally:
            task_path = PROJECT_ROOT / "data" / "task-state" / f"{task_id}.json"
            if task_path.is_file():
                task_path.unlink()
            task_directory = task_path.parent
            if task_directory.is_dir() and not any(task_directory.iterdir()):
                task_directory.rmdir()

    def test_agent_endpoint_returns_structured_troubleshooting_report(self) -> None:
        response = self.client.post(
            "/api/agent/run",
            json={
                "source_root": "sample-data",
                "query": "8080 端口故障之前是否出现过",
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("troubleshooting", payload["category"])
        self.assertIsNotNone(payload["report"])
        self.assertTrue(payload["report"]["findings"])
        self.assertTrue(payload["report"]["citations"])


if __name__ == "__main__":
    unittest.main()
