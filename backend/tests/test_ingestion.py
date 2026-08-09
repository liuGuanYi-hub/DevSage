import unittest
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


if __name__ == "__main__":
    unittest.main()
