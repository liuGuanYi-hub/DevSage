"""Dependency-free keyword retrieval baseline for the DevMind MVP."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from ..ingestion.models import ChunkRecord
from .models import SearchResult


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


def tokenize(value: str) -> list[str]:
    """Tokenize English identifiers and individual CJK characters."""

    return [token.lower() for token in TOKEN_PATTERN.findall(value)]


def search_keyword(
    chunks: Iterable[ChunkRecord],
    query: str,
    top_k: int = 5,
) -> list[SearchResult]:
    """Return ranked chunks using term frequency and exact phrase bonuses."""

    if top_k <= 0:
        return []

    query_terms = tokenize(query)
    if not query_terms:
        return []

    query_text = query.lower().strip()
    results: list[SearchResult] = []
    for chunk in chunks:
        content_text = chunk.content.lower()
        content_terms = Counter(tokenize(chunk.content))
        matched_terms = tuple(sorted({term for term in query_terms if term in content_terms}))
        if not matched_terms:
            continue

        score = sum(min(content_terms[term], 3) for term in matched_terms)
        if query_text and query_text in content_text:
            score += 2
        path_terms = set(tokenize(chunk.source_path))
        path_matches = set(query_terms).intersection(path_terms)
        if path_matches:
            score += min(len(path_matches) * 2, 4)
        if query_text and query_text in chunk.source_path.lower():
            score += 1
        results.append(SearchResult(chunk, float(score), matched_terms))

    results.sort(
        key=lambda result: (-result.score, result.chunk.source_path, result.chunk.start_line)
    )
    return results[:top_k]
