import unittest

from backend.app.services.index_service import IndexService
from backend.app.retrieval.embeddings import HashEmbeddingProvider


class RecordingPersistence:
    def __init__(self) -> None:
        self.initialize_calls = 0
        self.saved = []
        self.keyword_calls = []
        self.hybrid_calls = []

    def initialize(self) -> None:
        self.initialize_calls += 1

    def save_snapshot(self, **kwargs) -> None:
        self.saved.append(kwargs)

    def search_keyword(self, project_name, query, top_k):
        self.keyword_calls.append((project_name, query, top_k))
        return []

    def search_hybrid(self, project_name, query, top_k, provider):
        self.hybrid_calls.append((project_name, query, top_k, provider))
        return []


class IndexPersistenceTests(unittest.TestCase):
    def test_build_initializes_and_saves_snapshot_once_per_build(self) -> None:
        persistence = RecordingPersistence()
        service = IndexService(
            embedding_provider=HashEmbeddingProvider(dimension=8),
            persistence=persistence,
        )

        source_root, snapshot = service.build("sample-data")
        second_root, second_snapshot = service.build("sample-data")

        self.assertEqual("sample-data", source_root)
        self.assertEqual(source_root, second_root)
        self.assertEqual(len(snapshot.chunks), len(persistence.saved[0]["embeddings"]))
        self.assertEqual(len(second_snapshot.chunks), len(persistence.saved[1]["embeddings"]))
        self.assertEqual(1, persistence.initialize_calls)
        self.assertEqual(2, len(persistence.saved))
        self.assertEqual("sample-data", persistence.saved[0]["project_name"])

    def test_search_delegates_to_persisted_retrieval_when_enabled(self) -> None:
        persistence = RecordingPersistence()
        service = IndexService(
            embedding_provider=HashEmbeddingProvider(dimension=8),
            persistence=persistence,
        )

        service.search("sample-data", "8080", top_k=3)
        service.search_hybrid("sample-data", "8080", top_k=4)

        self.assertEqual([("sample-data", "8080", 3)], persistence.keyword_calls)
        self.assertEqual("sample-data", persistence.hybrid_calls[0][0])
        self.assertEqual("8080", persistence.hybrid_calls[0][1])
        self.assertEqual(4, persistence.hybrid_calls[0][2])


if __name__ == "__main__":
    unittest.main()
