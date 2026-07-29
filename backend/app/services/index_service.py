"""In-memory index service for the first DevMind API milestone."""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from ..ingestion.indexer import IndexSnapshot, build_index
from ..retrieval.hybrid_search import search_hybrid
from ..retrieval.keyword_search import search_keyword
from ..retrieval.models import SearchResult
from ..retrieval.rrf import reciprocal_rank_fusion


PROJECT_ROOT = Path(__file__).resolve().parents[3]

CODE_QUERY_EXPANSIONS = {
    "用户": "user UserController UserService",
    "接口": "controller Controller endpoint",
    "登录": "login AuthController",
    "认证": "auth Authenticate middleware",
    "令牌": "token Bearer Sanctum",
    "路由": "route Route routes",
    "方法": "method function",
    "调用链": "Controller Service",
}


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

    def search_hybrid(
        self,
        source_root: str,
        query: str,
        top_k: int,
    ) -> tuple[str, list[SearchResult]]:
        relative_root, snapshot = self.get_or_build(source_root)
        return relative_root, search_hybrid(snapshot.chunks, query, top_k=top_k)

    def search_code(self, source_root: str, query: str, top_k: int) -> list[SearchResult]:
        _, snapshot = self.get_or_build(source_root)
        code_chunks = [chunk for chunk in snapshot.chunks if chunk.file_type == "code"]
        expansions = " ".join(
            expansion
            for term, expansion in CODE_QUERY_EXPANSIONS.items()
            if term in query
        )
        expanded_query = f"{query} {expansions}".strip()
        return search_keyword(code_chunks, expanded_query, top_k=top_k)

    def search_project(self, source_root: str, query: str, top_k: int) -> list[SearchResult]:
        _, snapshot = self.get_or_build(source_root)
        document_results = search_hybrid(snapshot.chunks, query, top_k=top_k * 2)
        code_chunks = [chunk for chunk in snapshot.chunks if chunk.file_type == "code"]
        code_results = search_keyword(code_chunks, query, top_k=top_k * 2)
        return reciprocal_rank_fusion([document_results, code_results], top_k=top_k)

    def read_file(
        self,
        source_root: str,
        source_path: str,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> str:
        """Read a bounded, source-root-relative file range safely."""

        root = resolve_source_root(source_root)
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
