import unittest
from pathlib import Path

from backend.app.ingestion.indexer import build_index
from backend.app.retrieval.keyword_search import search_keyword
from backend.app.retrieval.rrf import reciprocal_rank_fusion, select_source_diverse


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        snapshot = build_index(PROJECT_ROOT / "sample-data")
        cls.chunks = snapshot.chunks

    def test_rrf_deduplicates_chunks_and_keeps_sources(self) -> None:
        first = search_keyword(self.chunks, "8080", top_k=5)
        second = search_keyword(self.chunks, "端口", top_k=5)
        fused = reciprocal_rank_fusion([first, second], top_k=5)

        self.assertTrue(fused)
        chunk_ids = [result.chunk.chunk_id for result in fused]
        self.assertEqual(len(chunk_ids), len(set(chunk_ids)))
        self.assertTrue(any("springboot-errors.md" in result.citation for result in fused))

    def test_rrf_rejects_invalid_smoothing(self) -> None:
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([], smoothing=0)

    def test_source_diverse_selection_prefers_distinct_files(self) -> None:
        first = search_keyword(self.chunks, "8080", top_k=5)
        second = search_keyword(self.chunks, "端口", top_k=5)
        fused = reciprocal_rank_fusion([first, second], top_k=10)
        selected = select_source_diverse(fused, top_k=3, max_per_source=1)

        sources = [result.chunk.source_path for result in selected]
        self.assertEqual(len(sources), len(set(sources)))


if __name__ == "__main__":
    unittest.main()
