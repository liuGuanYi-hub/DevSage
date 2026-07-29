import os
import unittest
from unittest.mock import patch

from backend.app.retrieval.embeddings import (
    EmbeddingProviderError,
    HashEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)
from backend.app.retrieval.provider_factory import create_embedding_provider
from backend.app.storage.postgres_repository import (
    PostgresIndexRepository,
    PostgresRepositoryError,
    vector_literal,
)


class ProviderAdapterTests(unittest.TestCase):
    def test_remote_provider_requires_explicit_configuration(self) -> None:
        provider = OpenAICompatibleEmbeddingProvider(
            endpoint="https://example.test/v1",
            model="demo-model",
            api_key_env="DEVSAGE_TEST_MISSING_KEY",
        )
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEVSAGE_TEST_MISSING_KEY", None)
            with self.assertRaises(EmbeddingProviderError):
                provider.embed(["test"])

    def test_remote_provider_parses_ordered_vectors_without_network(self) -> None:
        provider = OpenAICompatibleEmbeddingProvider(
            endpoint="https://example.test/v1",
            model="demo-model",
        )
        vectors = provider._parse_embeddings(
            {
                "data": [
                    {"index": 1, "embedding": [0.2, 0.3]},
                    {"index": 0, "embedding": [0.1, 0.4]},
                ]
            },
            expected_count=2,
        )
        self.assertEqual([[0.1, 0.4], [0.2, 0.3]], vectors)
        self.assertEqual(2, provider.dimension)

    def test_vector_literal_validates_migration_dimension(self) -> None:
        with self.assertRaises(ValueError):
            vector_literal([0.1, 0.2], expected_dimension=3)
        self.assertTrue(vector_literal([0.1, 0.2, 0.3], expected_dimension=3).startswith("["))

    def test_default_hash_embedding_matches_pgvector_dimension(self) -> None:
        vector = HashEmbeddingProvider().embed(["8080 端口"])[0]
        self.assertEqual(1024, len(vector))
        self.assertTrue(vector_literal(vector).startswith("["))

    def test_non_matching_embedding_dimension_is_rejected_before_connection(self) -> None:
        repository = PostgresIndexRepository(
            database_url="postgresql://example.invalid/devsage"
        )
        with self.assertRaises(PostgresRepositoryError):
            repository.search_vector(
                "sample-data",
                "query",
                top_k=1,
                provider=HashEmbeddingProvider(dimension=8),
            )

    def test_postgres_repository_fails_clearly_without_database_url(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=False):
            repository = PostgresIndexRepository(database_url="")
            with self.assertRaises(PostgresRepositoryError):
                repository.initialize()

    def test_postgres_repository_exposes_checked_in_migration(self) -> None:
        migration = PostgresIndexRepository.migration_sql()
        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector", migration)
        self.assertIn("projects_name_idx", migration)
        self.assertIn("embedding vector(1024)", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS agent_tasks", migration)

    def test_postgres_repository_reconstructs_chunk_rows(self) -> None:
        chunk = PostgresIndexRepository._chunk_from_row(
            ("chunk-1", "docs/example.md", "markdown", "content", 2, 5, {"title": "Example"})
        )
        self.assertEqual("docs/example.md", chunk.source_path)
        self.assertEqual(2, chunk.start_line)
        self.assertEqual(5, chunk.end_line)
        self.assertEqual({"title": "Example"}, chunk.metadata)

    def test_provider_factory_defaults_to_offline_hash(self) -> None:
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "hash"}, clear=False):
            provider = create_embedding_provider()
        self.assertEqual("HashEmbeddingProvider", type(provider).__name__)

    def test_provider_factory_rejects_unknown_mode(self) -> None:
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "unknown"}, clear=False):
            with self.assertRaises(EmbeddingProviderError):
                create_embedding_provider()


if __name__ == "__main__":
    unittest.main()
