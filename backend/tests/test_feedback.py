import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.feedback_store import FeedbackStore


class FeedbackStoreTests(unittest.TestCase):
    def test_approved_feedback_is_appended_as_an_evaluation_case(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "feedback"
            evaluation_path = root / "confirmed-evaluation.jsonl"
            store = FeedbackStore(root, evaluation_path)

            created = store.create(
                {
                    "task_id": "task-123456",
                    "project_id": "sample-data",
                    "query": "8080 端口被占用怎么办？",
                    "rating": "needs_revision",
                    "comment": "引用需要更精确",
                    "incorrect_citations": ["docs/old.md:1-2"],
                    "citation_corrections": [
                        {
                            "citation": "docs/old.md:1-2",
                            "corrected_citation": "docs/springboot-errors.md:3-13",
                            "note": "实际根因在启动失败记录",
                        }
                    ],
                },
                "local-demo",
            )

            approved = store.approve(
                created["feedback_id"],
                "local-demo",
                "先检查占用 8080 端口的进程，再确认服务配置。",
                ["sample-data/docs/springboot-errors.md"],
                ["classify_question", "search_documents"],
                "人工确认后纳入回归集",
            )

            self.assertEqual("approved", approved["status"])
            self.assertTrue(approved["evaluation_case_id"].startswith("feedback-"))
            cases = [json.loads(line) for line in evaluation_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(1, len(cases))
            self.assertEqual("human_feedback", cases[0]["category"])
            self.assertEqual(created["feedback_id"], cases[0]["feedback_id"])

    def test_feedback_api_queues_and_approves_without_touching_vault(self) -> None:
        with TemporaryDirectory() as temporary:
            store = FeedbackStore(
                Path(temporary) / "feedback",
                Path(temporary) / "feedback" / "confirmed-evaluation.jsonl",
            )
            with patch("backend.app.main.feedback_store", store):
                client = TestClient(app)
                headers = {"X-DevSage-Actor": "local-demo"}
                created = client.post(
                    "/api/feedback",
                    headers=headers,
                    json={
                        "task_id": "task-123456",
                        "project_id": "sample-data",
                        "query": "8080 端口被占用怎么办？",
                        "rating": "helpful",
                    },
                )
                self.assertEqual(200, created.status_code)
                feedback_id = created.json()["feedback_id"]

                pending = client.get(
                    "/api/feedback?project_id=sample-data&status=pending",
                    headers=headers,
                )
                self.assertEqual(200, pending.status_code)
                self.assertEqual(1, pending.json()["total"])
                viewer_queue = client.get(
                    "/api/feedback",
                    headers={"X-DevSage-Actor": "local-viewer"},
                )
                self.assertEqual(403, viewer_queue.status_code)

                approved = client.post(
                    f"/api/feedback/{feedback_id}/approve",
                    headers=headers,
                    json={
                        "reference_answer": "先检查占用端口的进程。",
                        "expected_sources": ["sample-data/docs/springboot-errors.md"],
                        "expected_tools": ["search_documents"],
                        "reviewer_comment": "通过人工确认",
                    },
                )
                self.assertEqual(200, approved.status_code)
                self.assertEqual("approved", approved.json()["status"])
                self.assertTrue(store.evaluation_path.is_file())


if __name__ == "__main__":
    unittest.main()
