"""Optional PostgreSQL + pgvector persistence adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..ingestion.indexer import IndexSnapshot


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

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", "").strip()

    @staticmethod
    def migration_sql() -> str:
        return MIGRATION_PATH.read_text(encoding="utf-8")

    def _connect(self):
        if not self.database_url:
            raise PostgresRepositoryError("DATABASE_URL is not configured")
        try:
            import psycopg
        except ImportError as exc:
            raise PostgresRepositoryError(
                "psycopg is required only when PostgreSQL persistence is enabled"
            ) from exc
        try:
            return psycopg.connect(self.database_url)
        except Exception as exc:  # psycopg exposes provider-specific exceptions
            raise PostgresRepositoryError("PostgreSQL connection failed") from exc

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
