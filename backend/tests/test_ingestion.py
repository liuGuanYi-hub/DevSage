import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.ingestion.chunkers import split_document
from backend.app.ingestion.indexer import build_index
from backend.app.ingestion.loaders import load_document
from backend.app.retrieval.keyword_search import search_keyword


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_ROOT = PROJECT_ROOT / "sample-data"


class IngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = build_index(SAMPLE_ROOT)

    def test_index_contains_documents_and_chunks(self) -> None:
        self.assertGreaterEqual(len(self.snapshot.documents), 8)
        self.assertGreaterEqual(len(self.snapshot.chunks), len(self.snapshot.documents))

    def test_documents_have_stable_hashes_and_relative_paths(self) -> None:
        springboot = next(
            document
            for document in self.snapshot.documents
            if document.source_path.endswith("springboot-errors.md")
        )
        self.assertEqual(64, len(springboot.content_hash))
        self.assertFalse(Path(springboot.source_path).is_absolute())
        self.assertGreater(springboot.line_count, 1)

    def test_markdown_chunk_keeps_heading_metadata_and_line_range(self) -> None:
        chunks = [
            chunk
            for chunk in self.snapshot.chunks
            if chunk.source_path.endswith("springboot-errors.md")
        ]
        self.assertTrue(any(chunk.metadata.get("heading") == "8080 端口被占用" for chunk in chunks))
        self.assertTrue(all(chunk.start_line <= chunk.end_line for chunk in chunks))
        port_chunk = next(chunk for chunk in chunks if chunk.metadata.get("heading") == "8080 端口被占用")
        self.assertEqual("knowledge-document", port_chunk.metadata["document_role"])
        self.assertEqual("markdown-section", port_chunk.metadata["chunk_role"])
        self.assertIn("8080 端口被占用", port_chunk.metadata["heading_path"])
        self.assertRegex(port_chunk.metadata["line_range"], r"^\d+-\d+$")

    def test_code_chunk_exposes_symbol_and_file_responsibility_metadata(self) -> None:
        controller = next(
            chunk
            for chunk in self.snapshot.chunks
            if chunk.source_path.endswith("UserController.java")
            and chunk.metadata.get("symbol") == "UserController"
        )
        self.assertEqual("api-entry", controller.metadata["document_role"])
        self.assertEqual("class", controller.metadata["symbol_kind"])
        self.assertEqual("code-structure", controller.metadata["chunk_role"])

    def test_code_search_returns_expected_source(self) -> None:
        results = search_keyword(self.snapshot.chunks, "UserController getUser", top_k=5)
        self.assertTrue(results)
        self.assertTrue(
            any(result.chunk.source_path.endswith("UserController.java") for result in results)
        )
        self.assertTrue(all(result.citation for result in results))

    def test_keyword_search_returns_port_document(self) -> None:
        results = search_keyword(self.snapshot.chunks, "8080 端口占用", top_k=5)
        self.assertTrue(results)
        self.assertTrue(
            any(result.chunk.source_path.endswith("springboot-errors.md") for result in results)
        )

    def test_keyword_search_normalizes_chinese_incident_aliases(self) -> None:
        results = search_keyword(self.snapshot.chunks, "服务启动失败，8080 已经被占用", top_k=5)
        self.assertTrue(results)
        self.assertTrue(
            any(result.chunk.source_path.endswith("springboot-errors.md") for result in results)
        )
        self.assertTrue(any("alias:port-conflict" in result.matched_terms for result in results))

    def test_keyword_search_matches_http_error_code_aliases(self) -> None:
        results = search_keyword(self.snapshot.chunks, "登录成功后接口返回未认证 401", top_k=5)
        self.assertTrue(results)
        self.assertTrue(
            any(result.chunk.source_path.endswith("issues.json") for result in results)
        )
        self.assertTrue(any("alias:http-401" in result.matched_terms for result in results))

    def test_loader_rejects_file_outside_source_root(self) -> None:
        with self.assertRaises(ValueError):
            load_document(PROJECT_ROOT / "README.md", SAMPLE_ROOT)

    def test_example_config_is_supported(self) -> None:
        env_template = load_document(PROJECT_ROOT / ".env.example", PROJECT_ROOT)
        self.assertEqual("config", env_template.file_type)

    def test_three_code_language_extensions_load_and_split(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            samples = {
                "Controller.java": "public class Controller {\n    public void run() {}\n}\n",
                "Controller.php": "<?php\nclass Controller {\n    public function run() {}\n}\n",
                "health.ts": "export function health(): string {\n    return \"ok\";\n}\n",
            }
            for filename, content in samples.items():
                (root / filename).write_text(content, encoding="utf-8")

            documents = [load_document(root / filename, root) for filename in samples]

            self.assertTrue(all(document.file_type == "code" for document in documents))
            self.assertTrue(all(split_document(document) for document in documents))
            self.assertEqual(
                {"Controller.java", "Controller.php", "health.ts"},
                {document.source_path for document in documents},
            )

    def test_obsidian_and_cache_directories_are_excluded(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Keep.md").write_text("# Keep\n\nsearchable note\n", encoding="utf-8")
            for directory in (".obsidian", ".cache", "Cache", "__pycache__"):
                ignored = root / directory
                ignored.mkdir()
                (ignored / "ignored.md").write_text("should not be indexed", encoding="utf-8")

            snapshot = build_index(root)

            self.assertEqual({"Keep.md"}, {document.source_path for document in snapshot.documents})

    def test_incremental_index_reuses_unchanged_chunks(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "note.md"
            source.write_text("# First\n\nOriginal content\n", encoding="utf-8")
            first = build_index(root)
            source.write_text("# First\n\nOriginal content\n", encoding="utf-8")
            second = build_index(root, previous=first)

            self.assertIsNotNone(second.stats)
            assert second.stats is not None
            self.assertEqual(1, second.stats.unchanged_documents)
            self.assertEqual(0, second.stats.changed_documents)
            self.assertEqual(first.chunks[0].chunk_id, second.chunks[0].chunk_id)

    def test_incremental_index_refreshes_legacy_chunk_metadata(self) -> None:
        legacy = replace(
            self.snapshot,
            chunks=tuple(replace(chunk, metadata={}) for chunk in self.snapshot.chunks),
        )

        refreshed = build_index(SAMPLE_ROOT, previous=legacy)

        assert refreshed.stats is not None
        self.assertGreater(refreshed.stats.changed_documents, 0)
        self.assertTrue(
            all(chunk.metadata.get("metadata_version") == "2" for chunk in refreshed.chunks)
        )


if __name__ == "__main__":
    unittest.main()
