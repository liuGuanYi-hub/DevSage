"""Reciprocal Rank Fusion for combining independent retrieval lists."""

from __future__ import annotations

from collections.abc import Iterable

from .models import SearchResult


def reciprocal_rank_fusion(
    ranked_lists: Iterable[Iterable[SearchResult]],
    top_k: int = 5,
    smoothing: int = 60,
) -> list[SearchResult]:
    """Fuse ranked lists by Chunk ID while preserving source metadata."""

    if top_k <= 0:
        return []
    if smoothing <= 0:
        raise ValueError("smoothing must be positive")

    scores: dict[str, float] = {}
    representatives: dict[str, SearchResult] = {}
    matched_terms: dict[str, set[str]] = {}
    for ranked_list in ranked_lists:
        for rank, result in enumerate(ranked_list, start=1):
            chunk_id = result.chunk.chunk_id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (smoothing + rank)
            representatives.setdefault(chunk_id, result)
            matched_terms.setdefault(chunk_id, set()).update(result.matched_terms)

    fused: list[SearchResult] = []
    for chunk_id, score in scores.items():
        representative = representatives[chunk_id]
        fused.append(
            SearchResult(
                chunk=representative.chunk,
                score=score,
                matched_terms=tuple(sorted(matched_terms[chunk_id])),
            )
        )

    fused.sort(
        key=lambda result: (-result.score, result.chunk.source_path, result.chunk.start_line)
    )
    return fused[:top_k]

