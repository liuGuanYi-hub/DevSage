"""Read-only Git history tool for local repositories."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from ..ingestion.models import ChunkRecord
from ..retrieval.keyword_search import tokenize
from ..retrieval.models import SearchResult


PROJECT_ROOT = Path(
    os.getenv(
        "DEVSAGE_GIT_ROOT",
        os.getenv("DEVSAGE_PROJECT_ROOT", str(Path(__file__).resolve().parents[3])),
    )
).resolve()


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
    timeout_seconds: float = 5.0,
) -> list[SearchResult]:
    """Return recent matching commits from a local repository."""

    if limit <= 0:
        return []
    _validate_timeout(timeout_seconds)
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
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitToolError("git history query timed out") from exc
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


def get_commit_diff(
    commit_hash: str,
    repository_path: str | Path | None = None,
    path: str | Path | None = None,
    max_lines: int = 1200,
    timeout_seconds: float = 10.0,
) -> SearchResult:
    """Return a bounded, read-only diff for one validated commit."""

    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", commit_hash):
        raise GitToolError("commit_hash must be a hexadecimal Git object id")
    if max_lines <= 0:
        raise GitToolError("max_lines must be positive")
    _validate_timeout(timeout_seconds)
    repository = _resolve_repository(repository_path)
    path_argument = _resolve_diff_path(repository, path)
    command = [
        "git",
        "-C",
        str(repository),
        "show",
        "--no-ext-diff",
        "--format=fuller",
        "--no-renames",
        "--unified=3",
        commit_hash,
    ]
    if path_argument is not None:
        command.extend(["--", path_argument])
    else:
        command.append("--")
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitToolError("git commit diff query timed out") from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GitToolError("git commit diff query failed") from exc

    lines = completed.stdout.splitlines()
    truncated = len(lines) > max_lines
    selected_lines = lines[:max_lines]
    if truncated:
        selected_lines.append(f"[diff truncated at {max_lines} lines]")
    content = "\n".join(selected_lines)
    chunk = ChunkRecord(
        chunk_id=f"git-diff-{commit_hash}",
        source_path=f"git/{commit_hash}/diff",
        file_type="git_diff",
        content=content,
        start_line=1,
        end_line=max(1, len(selected_lines)),
        metadata={
            "commit_hash": commit_hash,
            "path": path_argument or "",
            "truncated": str(truncated).lower(),
        },
    )
    return SearchResult(chunk=chunk, score=1.0, matched_terms=("git-diff",))


def _validate_timeout(timeout_seconds: float) -> None:
    if timeout_seconds <= 0 or timeout_seconds > 60:
        raise GitToolError("timeout_seconds must be between 0 and 60")


def _resolve_diff_path(repository: Path, path: str | Path | None) -> str | None:
    if path is None:
        return None
    requested = Path(path)
    if requested.is_absolute():
        raise GitToolError("diff path must be relative to the repository")
    resolved = (repository / requested).resolve()
    try:
        relative = resolved.relative_to(repository)
    except ValueError as exc:
        raise GitToolError("diff path escaped the repository") from exc
    return relative.as_posix()
