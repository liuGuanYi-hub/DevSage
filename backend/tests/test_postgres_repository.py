import unittest

from backend.app.ingestion.indexer import IndexSnapshot
from backend.app.ingestion.models import ChunkRecord, DocumentRecord
from backend.app.retrieval.embeddings import HashEmbeddingProvider
from backend.app.storage.postgres_repository import PostgresIndexRepository


class FakePostgresCursor:
    """Small in-memory cursor for the PostgreSQL adapter contract smoke."""

    def __init__(self, connection: "FakePostgresConnection") -> None:
        self.connection = connection
        self.rows: list[tuple] = []

    def __enter__(self) -> "FakePostgresCursor":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def execute(self, sql: str, params=None) -> None:
        normalized = " ".join(sql.split())
        lowered = normalized.lower()
        self.connection.statements.append(normalized)
        self.rows = []

        if lowered.startswith("insert into projects"):
            project_name, _, repository_path = params
            project_id = self.connection.projects.setdefault(
                project_name,
                {
                    "id": self.connection.next_project_id,
                    "repository_path": repository_path,
                },
            )["id"]
            self.connection.next_project_id = max(
                self.connection.next_project_id, project_id + 1
            )
            self.rows = [(project_id,)]
            return

        if lowered.startswith("delete from documents"):
            project_id = params[0]
            allowed_paths = set(params[1]) if len(params) > 1 else set()
            for key, document in list(self.connection.documents.items()):
                if document["project_id"] != project_id:
                    continue
                if len(params) > 1 and document["file_path"] in allowed_paths:
                    continue
                self.connection.documents.pop(key)
                self.connection.chunks.pop(document["id"], None)
            return

        if lowered.startswith("insert into documents"):
            project_id, file_path, file_type, content_hash = params
            key = (project_id, file_path)
            document = self.connection.documents.get(key)
            if document is None:
                document = {
                    "id": self.connection.next_document_id,
                    "project_id": project_id,
                    "file_path": file_path,
                    "file_type": file_type,
                    "content_hash": content_hash,
                }
                self.connection.next_document_id += 1
                self.connection.documents[key] = document
            else:
                document.update(file_type=file_type, content_hash=content_hash)
            self.rows = [(document["id"],)]
            return

        if lowered.startswith("delete from chunks"):
            self.connection.chunks[params[0]] = []
            return

        if lowered.startswith("insert into chunks"):
            document_id, chunk_id, content, embedding, start_line, end_line, metadata = params
            self.connection.chunks.setdefault(document_id, []).append(
                {
                    "chunk_id": chunk_id,
                    "content": content,
                    "embedding": embedding,
                    "start_line": start_line,
                    "end_line": end_line,
                    "metadata": metadata,
                }
            )
            return

        if lowered.startswith("select c.chunk_id") and "1 - (c.embedding" not in lowered:
            project_name = params[0]
            self.rows = self.connection.chunk_rows(project_name)
            return

        if lowered.startswith("select c.chunk_id") and "1 - (c.embedding" in lowered:
            project_name = params[1]
            limit = int(params[3])
            self.rows = [
                (*row, max(0.1, 0.95 - index * 0.1))
                for index, row in enumerate(self.connection.chunk_rows(project_name)[:limit])
            ]

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class FakePostgresConnection:
    """Stateful fake matching the cursor boundary used by the repository."""

    def __init__(self) -> None:
        self.projects: dict[str, dict] = {}
        self.documents: dict[tuple[int, str], dict] = {}
        self.chunks: dict[int, list[dict]] = {}
        self.statements: list[str] = []
        self.next_project_id = 1
        self.next_document_id = 1
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0

    def cursor(self) -> FakePostgresCursor:
        return FakePostgresCursor(self)

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.close_count += 1

    def chunk_rows(self, project_name: str) -> list[tuple]:
        project = self.projects[project_name]
        document_rows = sorted(
            (
                document
                for document in self.documents.values()
                if document["project_id"] == project["id"]
            ),
            key=lambda document: document["file_path"],
        )
        rows: list[tuple] = []
        for document in document_rows:
            for chunk in sorted(
                self.chunks.get(document["id"], []),
                key=lambda item: item["start_line"],
            ):
                rows.append(
                    (
                        chunk["chunk_id"],
                        document["file_path"],
                        document["file_type"],
                        chunk["content"],
                        chunk["start_line"],
                        chunk["end_line"],
                        chunk["metadata"],
                    )
                )
        return rows


def make_snapshot() -> IndexSnapshot:
    guide = DocumentRecord(
        source_path="docs/guide.md",
        file_type="markdown",
        content_hash="guide-hash",
        content="# Retry guide\nUse pgvector for semantic search.",
        line_count=2,
    )
    service = DocumentRecord(
        source_path="src/retry.py",
        file_type="code",
        content_hash="service-hash",
        content="def retry_connection():\n    return True",
        line_count=2,
    )
    chunks = (
        ChunkRecord(
            chunk_id="guide-1",
            source_path=guide.source_path,
            file_type=guide.file_type,
            content=guide.content,
            start_line=1,
            end_line=2,
            metadata={"heading": "Retry guide"},
        ),
        ChunkRecord(
            chunk_id="service-1",
            source_path=service.source_path,
            file_type=service.file_type,
            content=service.content,
            start_line=1,
            end_line=2,
            metadata={"structure": "def retry_connection():"},
        ),
    )
    return IndexSnapshot(documents=(guide, service), chunks=chunks)


class PostgresRepositoryContractTests(unittest.TestCase):
    def test_migration_snapshot_and_search_contract(self) -> None:
        connection = FakePostgresConnection()
        repository = PostgresIndexRepository(connection_factory=lambda: connection)
        snapshot = make_snapshot()
        provider = HashEmbeddingProvider()
        embeddings = provider.embed([chunk.content for chunk in snapshot.chunks])

        repository.initialize()
        repository.save_snapshot("demo-project", "sample-data", snapshot, embeddings)

        keyword_results = repository.search_keyword("demo-project", "retry windows", top_k=5)
        vector_results = repository.search_vector(
            "demo-project", "database", top_k=2, provider=provider
        )
        hybrid_results = repository.search_hybrid(
            "demo-project", "retry", top_k=2, provider=provider
        )

        self.assertTrue(any("CREATE EXTENSION IF NOT EXISTS vector" in statement for statement in connection.statements))
        self.assertEqual(2, len(connection.documents))
        self.assertEqual(2, sum(len(chunks) for chunks in connection.chunks.values()))
        self.assertEqual("docs/guide.md:1-2", keyword_results[0].citation)
        self.assertEqual(2, len(vector_results))
        self.assertGreater(vector_results[0].score, 0.0)
        self.assertGreaterEqual(len(hybrid_results), 1)
        self.assertEqual(
            len(hybrid_results),
            len({result.chunk.source_path for result in hybrid_results}),
        )
        self.assertEqual(2, connection.commit_count)
        self.assertEqual(0, connection.rollback_count)
        self.assertGreaterEqual(connection.close_count, 5)


if __name__ == "__main__":
    unittest.main()
