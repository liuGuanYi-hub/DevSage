"""Read-only search over exported Issue records."""

from __future__ import annotations

import json
from pathlib import Path

from ..ingestion.models import ChunkRecord
from ..retrieval.keyword_search import tokenize
from ..retrieval.models import SearchResult


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ISSUE_PATH = PROJECT_ROOT / "sample-data/issues/issues.json"


class IssueToolError(RuntimeError):
    """Raised when Issue data cannot be read safely."""


def search_issues(query: str, limit: int = 5) -> list[SearchResult]:
    """Search exported Issues without contacting an external tracker."""

    if limit <= 0:
        return []
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

