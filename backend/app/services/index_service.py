"""In-memory index service for the first DevMind API milestone."""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from ..ingestion.indexer import IndexSnapshot, build_index
from ..retrieval.keyword_search import search_keyword
from ..retrieval.models import SearchResult


PROJECT_ROOT = Path(__file__).resolve().parents[3]


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
    """Cache deterministic snapshots until persistence is introduced."""

    def __init__(self) -> None:
        self._snapshots: dict[str, IndexSnapshot] = {}
        self._lock = RLock()

    def build(self, source_root: str) -> tuple[str, IndexSnapshot]:
        resolved = resolve_source_root(source_root)
        key = resolved.as_posix()
        with self._lock:
            previous = self._snapshots.get(key)
        snapshot = build_index(resolved, previous=previous)
        with self._lock:
            self._snapshots[key] = snapshot
        return resolved.relative_to(PROJECT_ROOT).as_posix(), snapshot

    def get_or_build(self, source_root: str) -> tuple[str, IndexSnapshot]:
        resolved = resolve_source_root(source_root)
        key = resolved.as_posix()
        with self._lock:
            snapshot = self._snapshots.get(key)
        if snapshot is None:
            return self.build(source_root)
        return resolved.relative_to(PROJECT_ROOT).as_posix(), snapshot

    def search(self, source_root: str, query: str, top_k: int) -> tuple[str, list[SearchResult]]:
        relative_root, snapshot = self.get_or_build(source_root)
        return relative_root, search_keyword(snapshot.chunks, query, top_k=top_k)
