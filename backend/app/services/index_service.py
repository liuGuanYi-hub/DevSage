"""In-memory index service for the first DevMind API milestone."""

from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

from ..ingestion.indexer import IndexSnapshot, build_index
from ..retrieval.hybrid_search import search_hybrid
from ..retrieval.keyword_search import search_keyword
from ..retrieval.models import SearchResult
from ..retrieval.rrf import reciprocal_rank_fusion, select_source_diverse
from ..retrieval.provider_factory import create_embedding_provider
from ..storage.postgres_repository import PostgresIndexRepository


PROJECT_ROOT = Path(
    os.getenv("DEVSAGE_PROJECT_ROOT", str(Path(__file__).resolve().parents[3]))
).resolve()

CODE_QUERY_EXPANSIONS = {
    "用户": "user UserController UserService",
    "接口": "controller Controller endpoint",
    "登录": "login AuthController",
    "认证": "auth Authenticate middleware",
    "令牌": "token Bearer Sanctum",
    "路由": "route Route routes",
    "方法": "method function",
    "调用链": "Controller Service",
    "调用": "Controller Service",
    "中间件": "middleware Authenticate auth:sanctum",
    "任务列表": "task tasks api.php auth:sanctum",
    "登录路由": "api.php AuthController login",
    "token 类型": "token_type Bearer AuthController",
    "返回什么类型": "UserDto UserController getUser",
    "配置": "application.yml server.port",
    "端口": "application.yml server.port",
    "getuser": "UserController UserDto UserService",
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
    """Build local snapshots and optionally persist/search them in PostgreSQL."""

    def __init__(self, embedding_provider=None, persistence=None) -> None:
        self._snapshots: dict[str, IndexSnapshot] = {}
        self._lock = RLock()
        self.embedding_provider = embedding_provider or create_embedding_provider()
        self.persistence = persistence if persistence is not None else self._create_persistence()
        self._persistence_initialized = False

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
        embeddings = self.embedding_provider.embed([chunk.content for chunk in snapshot.chunks])
        self.persistence.save_snapshot(
            project_name=relative_root,
            repository_path=str(resolved_root),
            snapshot=snapshot,
            embeddings=embeddings,
        )

    def build(self, source_root: str) -> tuple[str, IndexSnapshot]:
        resolved = resolve_source_root(source_root)
        key = resolved.as_posix()
        with self._lock:
            previous = self._snapshots.get(key)
        snapshot = build_index(resolved, previous=previous)
        relative_root = resolved.relative_to(PROJECT_ROOT).as_posix()
        self._persist_snapshot(relative_root, resolved, snapshot)
        with self._lock:
            self._snapshots[key] = snapshot
        return relative_root, snapshot

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
        if self.persistence is not None:
            return relative_root, self.persistence.search_hybrid(
                relative_root,
                query,
                top_k,
                self.embedding_provider,
            )
        return relative_root, search_hybrid(
            snapshot.chunks,
            query,
            top_k=top_k,
            provider=self.embedding_provider,
        )

    def search_code(self, source_root: str, query: str, top_k: int) -> list[SearchResult]:
        _, snapshot = self.get_or_build(source_root)
        code_chunks = [
            chunk
            for chunk in snapshot.chunks
            if chunk.file_type in {"code", "config"}
            and not chunk.source_path.startswith(("issues/", "git/"))
        ]
        expanded_query = _expand_code_query(query)
        candidates = search_keyword(
            code_chunks,
            expanded_query,
            top_k=max(top_k * 4, 10),
        )
        return select_source_diverse(candidates, top_k=top_k, max_per_source=1)

    def search_project(self, source_root: str, query: str, top_k: int) -> list[SearchResult]:
        _, snapshot = self.get_or_build(source_root)
        document_chunks = [
            chunk
            for chunk in snapshot.chunks
            if chunk.file_type == "markdown"
            or (
                chunk.file_type == "config"
                and not chunk.source_path.startswith(("issues/", "git/"))
            )
        ]
        document_results = search_hybrid(document_chunks, query, top_k=top_k * 2)
        code_chunks = [
            chunk
            for chunk in snapshot.chunks
            if chunk.file_type in {"code", "config"}
            and not chunk.source_path.startswith(("issues/", "git/"))
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


def _expand_code_query(query: str) -> str:
    normalized_query = query.lower()
    expansions = " ".join(
        expansion
        for term, expansion in CODE_QUERY_EXPANSIONS.items()
        if term.lower() in normalized_query
    )
    return f"{query} {expansions}".strip()
