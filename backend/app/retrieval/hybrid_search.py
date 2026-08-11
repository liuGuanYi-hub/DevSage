"""Hybrid retrieval combining keyword and vector candidate lists."""

from __future__ import annotations

from collections.abc import Iterable

from ..ingestion.models import ChunkRecord
from .embeddings import EmbeddingProvider
from .keyword_search import search_keyword
from .models import SearchResult
from .rrf import reciprocal_rank_fusion, select_source_diverse
from .vector_search import search_vector


def search_hybrid(
    chunks: Iterable[ChunkRecord],
    query: str,
    top_k: int = 5,
    provider: EmbeddingProvider | None = None,
) -> list[SearchResult]:
    """Fuse keyword and local-vector candidates with keyword-first RRF."""

    chunk_list = list(chunks)
    candidate_k = max(top_k * 4, 10)
    keyword_results = search_keyword(chunk_list, query, top_k=candidate_k)
    vector_results = search_vector(
        chunk_list,
        query,
        top_k=candidate_k,
        provider=provider,
    )
    fused = reciprocal_rank_fusion(
        [keyword_results, vector_results],
        top_k=candidate_k,
        weights=(1.25, 0.75),
    )
    return select_source_diverse(fused, top_k=top_k, max_per_source=1)
