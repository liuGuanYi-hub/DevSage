import unittest

from backend.app.services.answer_service import compose_evidence_answer
from backend.app.services.project_summary import compose_project_summary
from backend.app.retrieval.models import SearchResult
from backend.app.ingestion.models import ChunkRecord


class AnswerServiceTests(unittest.TestCase):
    def test_direct_evidence_is_rendered_with_citation(self) -> None:
        result = SearchResult(
            chunk=ChunkRecord(
                chunk_id="chunk-1",
                source_path="docs/example.md",
                file_type="markdown",
                content="8080 端口被占用时先查询 PID。",
                start_line=3,
                end_line=5,
            ),
            score=1.0,
            matched_terms=("8080", "端", "口"),
        )
        draft = compose_evidence_answer("8080 端口怎么排查", [result])
        self.assertTrue(draft.evidence_sufficient)
        self.assertIn("docs/example.md:3-5", draft.answer)
        self.assertEqual(("docs/example.md:3-5",), draft.citations)

    def test_no_direct_evidence_is_explicitly_insufficient(self) -> None:
        result = SearchResult(
            chunk=ChunkRecord(
                chunk_id="chunk-2",
                source_path="docs/nearest.md",
                file_type="markdown",
                content="Unrelated context.",
                start_line=1,
                end_line=1,
            ),
            score=0.2,
            matched_terms=(),
        )
        draft = compose_evidence_answer("unknown failure", [result])
        self.assertFalse(draft.evidence_sufficient)
        self.assertEqual((), draft.citations)
        self.assertIn("没有检索到足够的直接证据", draft.answer)

    def test_project_summary_groups_code_and_document_evidence(self) -> None:
        results = [
            SearchResult(
                chunk=ChunkRecord(
                    chunk_id="doc-1",
                    source_path="docs/project.md",
                    file_type="markdown",
                    content="项目使用 Spring Boot 提供用户接口。",
                    start_line=1,
                    end_line=2,
                ),
                score=1.0,
                matched_terms=("项目", "用户", "接口"),
            ),
            SearchResult(
                chunk=ChunkRecord(
                    chunk_id="code-1",
                    source_path="src/UserController.java",
                    file_type="code",
                    content="class UserController { }",
                    start_line=4,
                    end_line=6,
                ),
                score=0.9,
                matched_terms=("用户", "接口"),
            ),
        ]
        draft = compose_project_summary("总结用户接口", results)
        self.assertTrue(draft.evidence_sufficient)
        self.assertIn("文档与配置证据", draft.answer)
        self.assertIn("代码证据", draft.answer)
        self.assertEqual(2, len(draft.citations))


if __name__ == "__main__":
    unittest.main()
