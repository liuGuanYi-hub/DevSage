import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class StorageSchemaTests(unittest.TestCase):
    def test_initial_migration_contains_core_vector_tables(self) -> None:
        migration = (
            PROJECT_ROOT / "backend/migrations/001_initial_schema.sql"
        ).read_text(encoding="utf-8")
        for required in (
            "CREATE EXTENSION IF NOT EXISTS vector",
            "CREATE TABLE IF NOT EXISTS projects",
            "CREATE TABLE IF NOT EXISTS documents",
            "CREATE TABLE IF NOT EXISTS chunks",
            "embedding vector(1024)",
            "chunks_embedding_hnsw_idx",
        ):
            self.assertIn(required, migration)


if __name__ == "__main__":
    unittest.main()

