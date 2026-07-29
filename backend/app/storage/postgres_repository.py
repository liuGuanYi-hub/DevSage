"""Optional PostgreSQL + pgvector persistence adapter."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..ingestion.indexer import IndexSnapshot
from ..ingestion.models import ChunkRecord
from ..retrieval.embeddings import EmbeddingProvider
from ..retrieval.keyword_search import search_keyword as search_keyword_chunks
from ..retrieval.models import SearchResult
from ..retrieval.rrf import reciprocal_rank_fusion, select_source_diverse


VECTOR_DIMENSION = 1024
MIGRATION_PATH = Path(__file__).resolve().parents[2] / "migrations/001_initial_schema.sql"


class PostgresRepositoryError(RuntimeError):
    """Raised when PostgreSQL persistence is not configured or unavailable."""


def vector_literal(values: list[float], expected_dimension: int = VECTOR_DIMENSION) -> str:
    """Format a vector for pgvector without exposing any external secrets."""

    if len(values) != expected_dimension:
        raise ValueError(
            f"embedding dimension must be {expected_dimension}, got {len(values)}"
        )
    return "[" + ",".join(f"{float(value):.12g}" for value in values) + "]"


class PostgresIndexRepository:
    """Persist index snapshots when psycopg and a database URL are available."""

    def __init__(
        self,
        database_url: str | None = None,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", "").strip()
        self._connection_factory = connection_factory

    @staticmethod
    def migration_sql() -> str:
        return MIGRATION_PATH.read_text(encoding="utf-8")

    def _connect(self):
        if self._connection_factory is not None:
            return self._connection_factory()
        if not self.database_url:
            raise PostgresRepositoryError("DATABASE_URL is not configured")
        database_url = self.database_url.replace(
            "postgresql+psycopg://", "postgresql://", 1
        )
        try:
            import psycopg
        except ImportError as exc:
            raise PostgresRepositoryError(
                "psycopg is required only when PostgreSQL persistence is enabled"
            ) from exc
        try:
            return psycopg.connect(database_url)
        except Exception as exc:  # psycopg exposes provider-specific exceptions
            raise PostgresRepositoryError("PostgreSQL connection failed") from exc

    @staticmethod
    def _chunk_from_row(row: tuple[Any, ...]) -> ChunkRecord:
        metadata = row[6] if len(row) > 6 else {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        return ChunkRecord(
            chunk_id=str(row[0]),
            source_path=str(row[1]),
            file_type=str(row[2]),
            content=str(row[3]),
            start_line=int(row[4]),
            end_line=int(row[5]),
            metadata={str(key): str(value) for key, value in metadata.items()},
        )

    def _fetch_chunks(self, project_name: str) -> list[ChunkRecord]:
        """Load persisted chunks for the keyword and project tools."""

        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT c.chunk_id, d.file_path, d.file_type, c.content,
                           c.start_line, c.end_line, c.metadata
                    FROM chunks AS c
                    JOIN documents AS d ON d.id = c.document_id
                    JOIN projects AS p ON p.id = d.project_id
                    WHERE p.name = %s
                    ORDER BY d.file_path, c.start_line
                    """,
                    (project_name,),
                )
                rows = cursor.fetchall()
            return [self._chunk_from_row(row) for row in rows]
        except Exception as exc:
            raise PostgresRepositoryError("PostgreSQL chunk query failed") from exc
        finally:
            connection.close()

    def load_chunks(self, project_name: str) -> list[ChunkRecord]:
        """Load persisted chunks for category-aware answer routing."""

        return self._fetch_chunks(project_name)

    def search_keyword(
        self,
        project_name: str,
        query: str,
        top_k: int,
    ) -> list[SearchResult]:
        """Run the deterministic keyword ranker over persisted chunks."""

        return search_keyword_chunks(self._fetch_chunks(project_name), query, top_k=top_k)

    def search_vector(
        self,
        project_name: str,
        query: str,
        top_k: int,
        provider: EmbeddingProvider,
    ) -> list[SearchResult]:
        """Run pgvector cosine search over the persisted embedding column."""

        if top_k <= 0:
            return []
        query_vector = provider.embed([query])[0]
        try:
            vector = vector_literal(query_vector)
        except ValueError as exc:
            raise PostgresRepositoryError(
                "embedding dimension does not match pgvector schema"
            ) from exc
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT c.chunk_id, d.file_path, d.file_type, c.content,
                           c.start_line, c.end_line, c.metadata,
                           1 - (c.embedding <=> %s::vector) AS score
                    FROM chunks AS c
                    JOIN documents AS d ON d.id = c.document_id
                    JOIN projects AS p ON p.id = d.project_id
                    WHERE p.name = %s AND c.embedding IS NOT NULL
                    ORDER BY c.embedding <=> %s::vector, d.file_path, c.start_line
                    LIMIT %s
                    """,
                    (vector, project_name, vector, top_k),
                )
                rows = cursor.fetchall()
            results: list[SearchResult] = []
            for row in rows:
                chunk = self._chunk_from_row(row[:7])
                results.append(SearchResult(chunk=chunk, score=float(row[7]), matched_terms=()))
            return results
        except Exception as exc:
            raise PostgresRepositoryError("PostgreSQL vector query failed") from exc
        finally:
            connection.close()

    def search_hybrid(
        self,
        project_name: str,
        query: str,
        top_k: int,
        provider: EmbeddingProvider,
    ) -> list[SearchResult]:
        """Fuse persisted keyword and pgvector candidates with RRF."""

        candidate_k = max(top_k * 4, 10)
        fused = reciprocal_rank_fusion(
            [
                self.search_keyword(project_name, query, candidate_k),
                self.search_vector(project_name, query, candidate_k, provider),
            ],
            top_k=candidate_k,
        )
        return select_source_diverse(fused, top_k=top_k, max_per_source=1)

    def initialize(self) -> None:
        """Apply the checked-in migration to the configured database."""

        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(self.migration_sql())
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise PostgresRepositoryError("PostgreSQL migration failed") from exc
        finally:
            connection.close()

    def save_snapshot(
        self,
        project_name: str,
        repository_path: str,
        snapshot: IndexSnapshot,
        embeddings: list[list[float]],
    ) -> None:
        """Replace the project documents and Chunks in one transaction."""

        if len(embeddings) != len(snapshot.chunks):
            raise ValueError("embeddings must match snapshot chunk count")
        if any(len(embedding) != VECTOR_DIMENSION for embedding in embeddings):
            raise PostgresRepositoryError(
                "embedding dimension does not match pgvector schema"
            )
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO projects (name, description, repository_path)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO UPDATE
                    SET repository_path = EXCLUDED.repository_path
                    RETURNING id
                    """,
                    (project_name, "", repository_path),
                )
                project_id = cursor.fetchone()[0]
                document_paths = [document.source_path for document in snapshot.documents]
                if document_paths:
                    cursor.execute(
                        """
                        DELETE FROM documents
                        WHERE project_id = %s AND NOT (file_path = ANY(%s))
                        """,
                        (project_id, document_paths),
                    )
                else:
                    cursor.execute("DELETE FROM documents WHERE project_id = %s", (project_id,))
                chunks_by_source: dict[str, list[tuple[Any, list[float]]]] = {}
                for chunk, embedding in zip(snapshot.chunks, embeddings):
                    chunks_by_source.setdefault(chunk.source_path, []).append((chunk, embedding))

                for document in snapshot.documents:
                    cursor.execute(
                        """
                        INSERT INTO documents (project_id, file_path, file_type, content_hash)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (project_id, file_path) DO UPDATE
                        SET file_type = EXCLUDED.file_type,
                            content_hash = EXCLUDED.content_hash,
                            updated_at = NOW()
                        RETURNING id
                        """,
                        (project_id, document.source_path, document.file_type, document.content_hash),
                    )
                    document_id = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
                    for chunk, embedding in chunks_by_source.get(document.source_path, []):
                        cursor.execute(
                            """
                            INSERT INTO chunks
                                (document_id, chunk_id, content, embedding, start_line, end_line, metadata)
                            VALUES (%s, %s, %s, %s::vector, %s, %s, %s::jsonb)
                            """,
                            (
                                document_id,
                                chunk.chunk_id,
                                chunk.content,
                                vector_literal(embedding),
                                chunk.start_line,
                                chunk.end_line,
                                json.dumps(chunk.metadata, ensure_ascii=False),
                            ),
                        )
            connection.commit()
        except ValueError:
            connection.rollback()
            raise
        except Exception as exc:  # psycopg exposes provider-specific exceptions
            connection.rollback()
            raise PostgresRepositoryError("PostgreSQL snapshot save failed") from exc
        finally:
            connection.close()
