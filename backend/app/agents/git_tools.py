"""Read-only Git history tool for local repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..ingestion.models import ChunkRecord
from ..retrieval.keyword_search import tokenize
from ..retrieval.models import SearchResult


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class GitToolError(RuntimeError):
    """Raised when a local repository cannot be queried safely."""


def _resolve_repository(repository_path: str | Path | None) -> Path:
    requested = Path(repository_path or ".")
    if requested.is_absolute():
        raise GitToolError("repository_path must be relative to the project root")
    repository = (PROJECT_ROOT / requested).resolve()
    try:
        repository.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise GitToolError("repository_path escaped the project root") from exc
    if not repository.is_dir():
        raise GitToolError("repository_path is not a directory")
    return repository


def get_git_history(
    query: str = "",
    repository_path: str | Path | None = None,
    limit: int = 5,
) -> list[SearchResult]:
    """Return recent matching commits from a local repository."""

    if limit <= 0:
        return []
    repository = _resolve_repository(repository_path)
    command = [
        "git",
        "-C",
        str(repository),
        "log",
        "--all",
        f"-n{max(limit * 3, limit)}",
        "--date=iso-strict",
        "--pretty=format:%H%x1f%aI%x1f%s",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GitToolError("git history query failed") from exc

    query_terms = tokenize(query)
    commits: list[SearchResult] = []
    unmatched_commits: list[SearchResult] = []
    for line in completed.stdout.splitlines():
        fields = line.split("\x1f", 2)
        if len(fields) != 3:
            continue
        commit_hash, authored_at, subject = fields
        searchable = f"{commit_hash} {authored_at} {subject}"
        matched_terms = tuple(sorted({term for term in query_terms if term in set(tokenize(searchable))}))
        if query_terms and not matched_terms:
            matched_terms = ()
        if not query_terms:
            matched_terms = ("git-history",)
        content = f"commit {commit_hash}\n时间：{authored_at}\n主题：{subject}"
        chunk = ChunkRecord(
            chunk_id=f"git-{commit_hash}",
            source_path=f"git/{commit_hash}",
            file_type="git",
            content=content,
            start_line=1,
            end_line=1,
            metadata={"commit_hash": commit_hash, "subject": subject},
        )
        result = SearchResult(chunk, 1.0, matched_terms)
        if matched_terms:
            commits.append(result)
        else:
            unmatched_commits.append(result)
        if len(commits) >= limit:
            break
    if commits:
        return commits[:limit]
    return [
        SearchResult(result.chunk, result.score, ("git-history",))
        for result in unmatched_commits[:limit]
    ]
