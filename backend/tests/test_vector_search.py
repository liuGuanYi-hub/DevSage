import unittest
from pathlib import Path

from backend.app.ingestion.indexer import build_index
from backend.app.retrieval.embeddings import HashEmbeddingProvider
from backend.app.retrieval.hybrid_search import search_hybrid
from backend.app.retrieval.vector_search import cosine_similarity, embedding_text, search_vector


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class VectorSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.chunks = build_index(PROJECT_ROOT / "sample-data").chunks

    def test_hash_embedding_is_deterministic(self) -> None:
        provider = HashEmbeddingProvider(dimension=32)
        self.assertEqual(provider.embed(["hello"]), provider.embed(["hello"]))
        self.assertEqual(32, len(provider.embed(["hello"])[0]))

    def test_cosine_similarity_rejects_different_dimensions(self) -> None:
        with self.assertRaises(ValueError):
            cosine_similarity([1.0], [1.0, 0.0])

    def test_vector_search_returns_ranked_results(self) -> None:
        results = search_vector(self.chunks, "8080 端口占用", top_k=3)
        self.assertEqual(3, len(results))
        self.assertGreaterEqual(results[0].score, results[-1].score)

    def test_hybrid_search_returns_citations(self) -> None:
        results = search_hybrid(self.chunks, "8080 端口占用", top_k=5)
        self.assertTrue(results)
        self.assertTrue(all(result.citation for result in results))

    def test_vector_embedding_text_includes_source_responsibility_metadata(self) -> None:
        controller = next(
            chunk for chunk in self.chunks if chunk.source_path.endswith("UserController.java")
        )
        text = embedding_text(controller)
        self.assertIn("document_role: api-entry", text)
        self.assertIn("source: repositories/springboot-demo", text)


if __name__ == "__main__":
    unittest.main()
