import unittest
from pathlib import Path

from backend.app.ingestion.indexer import build_index
from backend.app.retrieval.keyword_search import is_relevant_result, search_keyword, tokenize
from backend.app.retrieval.models import SearchResult
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

    def test_source_diverse_can_keep_only_one_chunk_per_source(self) -> None:
        first = search_keyword(self.chunks, "8080", top_k=5)
        selected = select_source_diverse(
            first,
            top_k=5,
            max_per_source=1,
            fill_repeats=False,
        )

        sources = [result.chunk.source_path for result in selected]
        self.assertEqual(len(sources), len(set(sources)))

    def test_weighted_rrf_can_prefer_keyword_rank(self) -> None:
        keyword_results = search_keyword(self.chunks, "8080", top_k=5)
        vector_results = search_keyword(self.chunks, "端口", top_k=5)
        fused = reciprocal_rank_fusion(
            [keyword_results, vector_results],
            top_k=5,
            weights=(2.0, 0.5),
        )
        self.assertTrue(fused)
        self.assertEqual(keyword_results[0].chunk.chunk_id, fused[0].chunk.chunk_id)

    def test_keyword_search_boosts_named_source_paths(self) -> None:
        results = search_keyword(self.chunks, "application.yml server.port", top_k=1)

        self.assertEqual(
            "repositories/springboot-demo/src/main/resources/application.yml",
            results[0].chunk.source_path,
        )

    def test_chinese_tokenization_keeps_phrases_and_drops_stopwords(self) -> None:
        tokens = tokenize("示例项目的用户查询相关文件")

        self.assertIn("用户", tokens)
        self.assertIn("查询", tokens)
        self.assertNotIn("的", tokens)
        self.assertNotIn("用", tokens)

    def test_relevance_filter_rejects_wrong_stack_code_evidence(self) -> None:
        result = SearchResult(
            chunk=self.chunks[0],
            score=1.0,
            matched_terms=("用户", "项目"),
        )

        self.assertFalse(
            is_relevant_result(
                result,
                "示例 Spring Boot 项目包含哪些与用户查询相关的文件？",
            )
        )


if __name__ == "__main__":
    unittest.main()
