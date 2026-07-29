import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


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


if __name__ == "__main__":
    unittest.main()
