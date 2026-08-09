"""Read-only search over local or optionally configured external Issues."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from typing import Any, Callable

from ..ingestion.models import ChunkRecord
from ..retrieval.keyword_search import tokenize
from ..retrieval.models import SearchResult


PROJECT_ROOT = Path(
    os.getenv("DEVSAGE_PROJECT_ROOT", str(Path(__file__).resolve().parents[3]))
).resolve()
ISSUE_PATH = PROJECT_ROOT / "sample-data/issues/issues.json"


class IssueToolError(RuntimeError):
    """Raised when Issue data cannot be read safely."""


@dataclass(frozen=True)
class ExternalIssueConfig:
    """Configuration for a GitHub-compatible read-only Issues API."""

    api_url: str
    repository: str
    token_env: str = "GITHUB_TOKEN"
    timeout_seconds: float = 10.0


ExternalOpen = Callable[[Request, float], Any]


def load_external_issue_config() -> ExternalIssueConfig | None:
    """Return validated external configuration, or None for offline mode."""

    api_url = os.getenv("DEVSAGE_EXTERNAL_ISSUE_URL", "").strip()
    repository = os.getenv("DEVSAGE_EXTERNAL_ISSUE_REPOSITORY", "").strip()
    if not api_url and not repository:
        return None
    parsed = urlparse(api_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IssueToolError("external Issue API URL must use http or https")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise IssueToolError("external Issue repository must use owner/name format")
    token_env = os.getenv("DEVSAGE_EXTERNAL_ISSUE_TOKEN_ENV", "GITHUB_TOKEN").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token_env):
        raise IssueToolError("external Issue token environment name is invalid")
    try:
        timeout_seconds = float(os.getenv("DEVSAGE_EXTERNAL_ISSUE_TIMEOUT", "10"))
    except ValueError as exc:
        raise IssueToolError("external Issue timeout is invalid") from exc
    if not 0 < timeout_seconds <= 60:
        raise IssueToolError("external Issue timeout must be between 0 and 60 seconds")
    return ExternalIssueConfig(
        api_url=api_url,
        repository=repository,
        token_env=token_env,
        timeout_seconds=timeout_seconds,
    )


def load_external_issue_write_config() -> ExternalIssueConfig:
    """Load write configuration and fail closed unless explicitly enabled."""

    if os.getenv("DEVSAGE_EXTERNAL_ISSUE_WRITE_ENABLED", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        raise IssueToolError("external Issue write is disabled")
    config = load_external_issue_config()
    if config is None:
        raise IssueToolError("external Issue platform is not configured")
    if not os.getenv(config.token_env, "").strip():
        raise IssueToolError("external Issue write token is not configured")
    return config


def _default_external_open(request: Request, timeout: float):
    return urlopen(request, timeout=timeout)


def search_issues(query: str, limit: int = 5) -> list[SearchResult]:
    """Search external Issues when configured, otherwise use exported records."""

    if limit <= 0:
        return []
    config = load_external_issue_config()
    if config is not None:
        return search_external_issues(query, limit=limit, config=config)
    return _search_exported_issues(query, limit)


def _search_exported_issues(query: str, limit: int) -> list[SearchResult]:
    try:
        issues = json.loads(ISSUE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IssueToolError("Issue dataset could not be loaded") from exc

    query_terms = tokenize(query)
    results: list[SearchResult] = []
    for issue in issues:
        searchable = " ".join(
            [
                issue.get("id", ""),
                issue.get("title", ""),
                issue.get("description", ""),
                issue.get("error", ""),
                issue.get("solution", ""),
                " ".join(issue.get("labels", [])),
            ]
        )
        content_terms = set(tokenize(searchable))
        matched_terms = tuple(sorted({term for term in query_terms if term in content_terms}))
        if not matched_terms:
            continue
        content = (
            f"{issue.get('title', '')}\n"
            f"问题：{issue.get('description', '')}\n"
            f"报错：{issue.get('error', '')}\n"
            f"解决：{issue.get('solution', '')}\n"
            f"状态：{issue.get('status', '')}"
        )
        chunk = ChunkRecord(
            chunk_id=f"issue-{issue.get('id', 'unknown')}",
            source_path=f"issues/{issue.get('id', 'unknown')}",
            file_type="issue",
            content=content,
            start_line=1,
            end_line=1,
            metadata={"issue_id": issue.get("id", "")},
        )
        score = float(len(matched_terms))
        if query.lower().strip() in searchable.lower():
            score += 2.0
        results.append(SearchResult(chunk, score, matched_terms))

    results.sort(key=lambda result: (-result.score, result.chunk.source_path))
    return results[:limit]


def search_external_issues(
    query: str,
    limit: int = 5,
    config: ExternalIssueConfig | None = None,
    opener: ExternalOpen | None = None,
) -> list[SearchResult]:
    """Search a GitHub-compatible Issues endpoint without writing remotely."""

    if limit <= 0 or not query.strip():
        return []
    config = config or load_external_issue_config()
    if config is None:
        raise IssueToolError("external Issue platform is not configured")
    search_url = f"{config.api_url.rstrip('/')}/search/issues"
    params = {
        "q": f"{query} repo:{config.repository} is:issue",
        "per_page": str(min(limit, 20)),
    }
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "DevSage/0.1",
    }
    token = os.getenv(config.token_env, "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        f"{search_url}?{urlencode(params)}",
        headers=headers,
        method="GET",
    )
    open_url = opener or _default_external_open
    try:
        with open_url(request, config.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise IssueToolError("external Issue platform rejected the request") from exc
        raise IssueToolError("external Issue request failed") from exc
    except (OSError, URLError, TimeoutError, ValueError) as exc:
        raise IssueToolError("external Issue request failed or timed out") from exc

    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise IssueToolError("external Issue response has an invalid items field")
    query_terms = tokenize(query)
    results: list[SearchResult] = []
    for index, issue in enumerate(items[:limit]):
        if not isinstance(issue, dict):
            continue
        number = str(issue.get("number", "unknown"))
        title = str(issue.get("title", "")).strip()
        body = str(issue.get("body") or "").strip()
        state = str(issue.get("state", "unknown")).strip()
        labels = issue.get("labels") or []
        label_names = [
            str(label.get("name", ""))
            for label in labels
            if isinstance(label, dict) and label.get("name")
        ]
        searchable = " ".join([number, title, body, state, " ".join(label_names)])
        content_terms = set(tokenize(searchable))
        matched_terms = tuple(sorted({term for term in query_terms if term in content_terms}))
        content = (
            f"{title}\n"
            f"问题：{body[:2000]}\n"
            f"状态：{state}\n"
            f"标签：{', '.join(label_names)}"
        )
        chunk = ChunkRecord(
            chunk_id=f"external-issue-{config.repository}-{number}",
            source_path=f"external-issues/{config.repository}/{number}",
            file_type="issue",
            content=content,
            start_line=1,
            end_line=max(1, len(content.splitlines())),
            metadata={
                "issue_id": number,
                "repository": config.repository,
                "url": str(issue.get("html_url", "")),
            },
        )
        score = float(len(matched_terms)) + max(0.0, 1.0 - index / 100)
        results.append(SearchResult(chunk, score, matched_terms))
    results.sort(key=lambda result: (-result.score, result.chunk.source_path))
    return results[:limit]
