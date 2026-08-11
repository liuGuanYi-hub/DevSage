"""Index service with offline file snapshots and optional PostgreSQL storage."""

from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

from ..ingestion.indexer import IndexSnapshot, build_index
from ..ingestion.models import ChunkRecord
from ..retrieval.answer_search import (
    _expand_code_query,
    _expand_project_summary_query,
    _is_code_chunk,
    _is_document_chunk,
    search_answer_chunks,
)
from ..retrieval.hybrid_search import search_hybrid
from ..retrieval.keyword_search import search_keyword
from ..retrieval.models import SearchResult
from ..retrieval.rrf import reciprocal_rank_fusion, select_source_diverse
from ..retrieval.provider_factory import create_embedding_provider
from ..retrieval.embeddings import embed_documents
from ..retrieval.vector_search import embedding_text
from ..storage.postgres_repository import PostgresIndexRepository
from .index_snapshot_store import FileIndexSnapshotStore


PROJECT_ROOT = Path(
    os.getenv("DEVSAGE_PROJECT_ROOT", str(Path(__file__).resolve().parents[3]))
).resolve()

class SourceRootError(ValueError):
    """Raised when an API caller requests an invalid source directory."""


def resolve_source_root(source_root: str) -> Path:
    """Resolve a relative source root without allowing workspace escape."""

    requested = Path(source_root).expanduser()
    if requested.is_absolute():
        raise SourceRootError("source_root must be relative to the project root")

    resolved = (PROJECT_ROOT / requested).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise SourceRootError("source_root is outside the project root") from exc
    if not resolved.is_dir():
        raise SourceRootError(f"source_root is not a directory: {source_root}")
    return resolved


class IndexService:
    """Build local snapshots with offline file recovery or PostgreSQL persistence."""

    def __init__(
        self,
        embedding_provider=None,
        persistence=None,
        snapshot_store=None,
        external_roots: dict[str, str | Path] | None = None,
    ) -> None:
        self._snapshots: dict[str, IndexSnapshot] = {}
        self._lock = RLock()
        self.external_roots = {
            str(logical_root): Path(filesystem_root).expanduser().resolve()
            for logical_root, filesystem_root in (external_roots or {}).items()
        }
        self.embedding_provider = embedding_provider or create_embedding_provider()
        self.persistence = persistence if persistence is not None else self._create_persistence()
        if snapshot_store is not None:
            self.snapshot_store = snapshot_store
        elif self.persistence is None:
            self.snapshot_store = FileIndexSnapshotStore(
                PROJECT_ROOT / "data" / "index-snapshots"
            )
        else:
            self.snapshot_store = None
        self._persistence_initialized = False

    def _resolve_source_root(self, source_root: str) -> tuple[str, Path]:
        """Resolve a legacy workspace root or an explicitly registered external root."""

        external_root = self.external_roots.get(source_root)
        if external_root is not None:
            if not external_root.is_dir():
                raise SourceRootError(f"registered external source is not a directory: {source_root}")
            return source_root, external_root
        resolved = resolve_source_root(source_root)
        return resolved.relative_to(PROJECT_ROOT).as_posix(), resolved

    @staticmethod
    def _create_persistence():
        mode = os.getenv("DEVSAGE_STORAGE", "memory").strip().lower()
        if mode in {"", "memory", "in-memory"}:
            return None
        if mode in {"postgres", "postgresql"}:
            return PostgresIndexRepository()
        raise ValueError(f"unsupported DEVSAGE_STORAGE mode: {mode}")

    def _persist_snapshot(
        self,
        relative_root: str,
        resolved_root: Path,
        snapshot: IndexSnapshot,
    ) -> None:
        if self.persistence is None:
            return
        if not self._persistence_initialized:
            self.persistence.initialize()
            self._persistence_initialized = True
        embeddings = embed_documents(
            self.embedding_provider,
            [embedding_text(chunk) for chunk in snapshot.chunks]
        )
        self.persistence.save_snapshot(
            project_name=relative_root,
            repository_path=str(resolved_root),
            snapshot=snapshot,
            embeddings=embeddings,
        )

    def build(self, source_root: str) -> tuple[str, IndexSnapshot]:
        logical_root, resolved = self._resolve_source_root(source_root)
        key = resolved.as_posix()
        with self._lock:
            previous = self._snapshots.get(key)
        if previous is None and self.snapshot_store is not None:
            previous = self.snapshot_store.load(logical_root)
        snapshot = build_index(resolved, previous=previous)
        self._persist_snapshot(logical_root, resolved, snapshot)
        if self.snapshot_store is not None:
            self.snapshot_store.save(logical_root, snapshot)
        with self._lock:
            self._snapshots[key] = snapshot
        return logical_root, snapshot

    def get_or_build(self, source_root: str) -> tuple[str, IndexSnapshot]:
        logical_root, resolved = self._resolve_source_root(source_root)
        key = resolved.as_posix()
        with self._lock:
            snapshot = self._snapshots.get(key)
        if snapshot is None:
            return self.build(source_root)
        return logical_root, snapshot

    def search(self, source_root: str, query: str, top_k: int) -> tuple[str, list[SearchResult]]:
        relative_root, snapshot = self.get_or_build(source_root)
        if self.persistence is not None:
            return relative_root, self.persistence.search_keyword(relative_root, query, top_k)
        return relative_root, search_keyword(snapshot.chunks, query, top_k=top_k)

    def search_hybrid(
        self,
        source_root: str,
        query: str,
        top_k: int,
    ) -> tuple[str, list[SearchResult]]:
        relative_root, snapshot = self.get_or_build(source_root)
        expanded_query = _expand_code_query(query)
        if self.persistence is not None:
            return relative_root, self.persistence.search_hybrid(
                relative_root,
                expanded_query,
                top_k,
                self.embedding_provider,
            )
        return relative_root, search_hybrid(
            snapshot.chunks,
            expanded_query,
            top_k=top_k,
            provider=self.embedding_provider,
        )

    def search_for_answer(
        self,
        source_root: str,
        query: str,
        top_k: int,
    ) -> tuple[str, list[SearchResult]]:
        """Retrieve answer evidence using category-aware production routing."""

        relative_root, snapshot = self.get_or_build(source_root)
        chunks = self._retrieval_chunks(relative_root, snapshot)
        hybrid_search_fn = None
        if self.persistence is not None and chunks is not snapshot.chunks:

            def hybrid_search_fn(query_text: str, limit: int) -> list[SearchResult]:
                return self.persistence.search_hybrid(
                    relative_root,
                    query_text,
                    limit,
                    self.embedding_provider,
                )

        _, results = search_answer_chunks(
            chunks,
            query,
            top_k=top_k,
            provider=self.embedding_provider,
            hybrid_search_fn=hybrid_search_fn,
        )
        return relative_root, results

    def search_code(self, source_root: str, query: str, top_k: int) -> list[SearchResult]:
        relative_root, snapshot = self.get_or_build(source_root)
        chunks = self._retrieval_chunks(relative_root, snapshot)
        code_chunks = [
            chunk
            for chunk in chunks
            if _is_code_chunk(chunk, query)
        ]
        expanded_query = _expand_code_query(query)
        candidates = search_keyword(
            code_chunks,
            expanded_query,
            top_k=max(top_k * 4, 10),
        )
        return select_source_diverse(
            candidates,
            top_k=top_k,
            max_per_source=1,
            fill_repeats=False,
        )

    def search_project(self, source_root: str, query: str, top_k: int) -> list[SearchResult]:
        relative_root, snapshot = self.get_or_build(source_root)
        chunks = self._retrieval_chunks(relative_root, snapshot)
        document_chunks = [
            chunk
            for chunk in chunks
            if _is_document_chunk(chunk, query)
        ]
        document_results = search_hybrid(
            document_chunks,
            _expand_project_summary_query(query),
            top_k=top_k * 2,
        )
        code_chunks = [
            chunk
            for chunk in chunks
            if _is_code_chunk(chunk, query)
        ]
        code_results = search_keyword(
            code_chunks,
            _expand_code_query(query),
            top_k=top_k * 2,
        )
        fused = reciprocal_rank_fusion(
            [document_results, code_results],
            top_k=top_k * 4,
        )
        return select_source_diverse(fused, top_k=top_k, max_per_source=1)

    def _retrieval_chunks(
        self,
        relative_root: str,
        snapshot: IndexSnapshot,
    ) -> tuple[ChunkRecord, ...]:
        """Prefer persisted chunks when the configured repository exposes them."""

        load_chunks = getattr(self.persistence, "load_chunks", None)
        if self.persistence is not None and callable(load_chunks):
            return tuple(load_chunks(relative_root))
        return snapshot.chunks

    def read_file(
        self,
        source_root: str,
        source_path: str,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> str:
        """Read a bounded, source-root-relative file range safely."""

        _, root = self._resolve_source_root(source_root)
        requested = Path(source_path)
        if requested.is_absolute() or any(part in {"", ".", ".."} for part in requested.parts):
            raise SourceRootError("source_path must stay inside source_root")
        path = (root / requested).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise SourceRootError("source_path escaped source_root") from exc
        if not path.is_file():
            raise SourceRootError(f"source_path is not a file: {source_path}")
        if start_line < 1:
            raise SourceRootError("start_line must be positive")
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        bounded_end = min(end_line or len(lines), len(lines))
        if bounded_end < start_line:
            return ""
        return "\n".join(lines[start_line - 1 : bounded_end])
