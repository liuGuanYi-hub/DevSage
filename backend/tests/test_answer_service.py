import unittest
from unittest.mock import patch

from backend.app.services.answer_generation import GeneratedAnswer
from backend.app.services.answer_service import compose_evidence_answer, compose_routed_answer
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
        self.assertTrue(draft.key_steps)

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

    def test_code_location_starts_with_a_direct_controller_conclusion(self) -> None:
        results = [
            SearchResult(
                chunk=ChunkRecord(
                    chunk_id="controller-1",
                    source_path="repositories/demo/UserController.java",
                    file_type="code",
                    content="public class UserController {\n    private final UserService userService;\n}",
                    start_line=4,
                    end_line=7,
                ),
                score=1.0,
                matched_terms=("usercontroller", "userservice"),
            ),
            SearchResult(
                chunk=ChunkRecord(
                    chunk_id="service-1",
                    source_path="repositories/demo/UserService.java",
                    file_type="code",
                    content="public class UserService { public UserController.UserDto findUser(long id) { } }",
                    start_line=4,
                    end_line=6,
                ),
                score=0.9,
                matched_terms=("userservice", "finduser"),
            ),
            SearchResult(
                chunk=ChunkRecord(
                    chunk_id="controller-2",
                    source_path="repositories/demo/UserController.java",
                    file_type="code",
                    content="public UserDto getUser(long id) { return userService.findUser(id); }",
                    start_line=9,
                    end_line=11,
                ),
                score=0.8,
                matched_terms=("getuser", "finduser"),
            ),
        ]

        draft = compose_evidence_answer(
            "示例项目的用户接口入口在哪个类？",
            results,
        )

        self.assertIn("直接结论", draft.answer)
        self.assertIn("UserController", draft.answer)
        self.assertIn("UserService.findUser", draft.answer)
        self.assertEqual(2, len(draft.evidence))
        self.assertEqual(2, len(draft.citations))

    def test_directory_question_prefers_the_vault_responsibility_table(self) -> None:
        result = SearchResult(
            chunk=ChunkRecord(
                chunk_id="vault-readme-1",
                source_path="README.md",
                file_type="markdown",
                content=(
                    "## 核心目录\n\n"
                    "| 目录 | 用途 |\n|---|---|\n"
                    "| `00-Inbox` | 网页剪藏、下载、清理和收集流程 |\n"
                    "| `04-Research` | 研究资料、领域分类和 Topic Hub |"
                ),
                start_line=12,
                end_line=18,
            ),
            score=0.8,
            matched_terms=("目录", "核心"),
        )

        draft = compose_evidence_answer("Obsidian 知识库的核心目录分别负责什么？", [result])

        self.assertIn("00-Inbox", draft.answer)
        self.assertIn("04-Research", draft.answer)
        self.assertIn("新内容放进", draft.answer)

    def test_routed_answer_uses_ai_result_after_evidence_is_ready(self) -> None:
        result = SearchResult(
            chunk=ChunkRecord(
                chunk_id="ai-1",
                source_path="docs/example.md",
                file_type="markdown",
                content="8080 端口被占用时先查询 PID。",
                start_line=3,
                end_line=5,
            ),
            score=1.0,
            matched_terms=("8080", "PID"),
        )
        generated = GeneratedAnswer(
            answer="先查询占用 8080 端口的 PID。[E1]",
            key_steps=("执行端口查询命令。",),
            model="qwen-test",
            provider="qwen",
        )
        with patch(
            "backend.app.services.answer_service.get_answer_generation_config"
        ) as config_mock, patch(
            "backend.app.services.answer_service.generate_grounded_answer",
            return_value=generated,
        ):
            config_mock.return_value.enabled = True
            config_mock.return_value.model = "qwen-test"
            draft = compose_routed_answer("8080 端口怎么排查？", [result])

        self.assertEqual("ai", draft.generation_mode)
        self.assertEqual("qwen-test", draft.generation_model)
        self.assertIn("[E1]", draft.answer)
        self.assertEqual(("执行端口查询命令。",), draft.key_steps)

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
        self.assertIn("文件职责", draft.answer)
        self.assertIn("知识说明文档", draft.answer)
        self.assertIn("用户接口入口", draft.answer)
        self.assertEqual(2, len(draft.citations))


if __name__ == "__main__":
    unittest.main()
