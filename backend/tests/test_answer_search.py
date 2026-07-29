import unittest
from pathlib import Path

from backend.app.ingestion.chunkers import split_document
from backend.app.ingestion.indexer import build_index
from backend.app.ingestion.loaders import load_document
from backend.app.retrieval.answer_search import search_answer_chunks


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AnswerSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        snapshot = build_index(PROJECT_ROOT / "sample-data")
        config_document = load_document(PROJECT_ROOT / ".env.example", PROJECT_ROOT)
        cls.chunks = (*snapshot.chunks, *split_document(config_document))

    def test_code_location_prioritises_controller_evidence(self) -> None:
        category, results = search_answer_chunks(
            self.chunks,
            "示例 Spring Boot 项目的用户接口入口在哪个类？",
        )

        self.assertEqual("code_location", category)
        sources = {result.chunk.source_path for result in results}
        self.assertIn(
            "repositories/springboot-demo/src/main/java/com/example/devsage/UserController.java",
            sources,
        )
        self.assertNotIn(".env.example", sources)

    def test_project_summary_keeps_multiple_expected_sources(self) -> None:
        category, results = search_answer_chunks(
            self.chunks,
            "示例 Spring Boot 项目包含哪些与用户查询相关的文件？",
        )

        self.assertEqual("project_summary", category)
        sources = {result.chunk.source_path for result in results}
        self.assertTrue(
            {
                "repositories/springboot-demo/README.md",
                "repositories/springboot-demo/src/main/java/com/example/devsage/UserController.java",
                "repositories/springboot-demo/src/main/java/com/example/devsage/UserService.java",
            }.issubset(sources)
        )

    def test_security_boundary_includes_env_template_evidence(self) -> None:
        category, results = search_answer_chunks(
            self.chunks,
            "样例项目为什么不能把真实数据库密码写入配置模板？",
        )

        self.assertEqual("knowledge_write", category)
        sources = {result.chunk.source_path for result in results}
        self.assertIn(".env.example", sources)
        self.assertIn("README.md", sources)


if __name__ == "__main__":
    unittest.main()
