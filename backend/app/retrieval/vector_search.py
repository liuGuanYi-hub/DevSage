"""Vector retrieval boundary with an injectable embedding provider."""

from __future__ import annotations

import math
from collections.abc import Iterable

from ..ingestion.models import ChunkRecord
from .embeddings import (
    EmbeddingProvider,
    HashEmbeddingProvider,
    embed_documents,
    embed_query,
)
from .models import SearchResult


def cosine_similarity(first: list[float], second: list[float]) -> float:
    """Calculate cosine similarity for equal-length vectors."""

    if len(first) != len(second):
        raise ValueError("vectors must have equal dimensions")
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    if not first_norm or not second_norm:
        return 0.0
    return sum(a * b for a, b in zip(first, second)) / (first_norm * second_norm)


def embedding_text(chunk: ChunkRecord) -> str:
    """Embed content together with stable source and responsibility metadata."""

    metadata = " ".join(
        f"{key}: {value}" for key, value in sorted(chunk.metadata.items())
    )
    return f"source: {chunk.source_path} {metadata}\n{chunk.content}".strip()


def search_vector(
    chunks: Iterable[ChunkRecord],
    query: str,
    top_k: int = 5,
    provider: EmbeddingProvider | None = None,
) -> list[SearchResult]:
    """Search chunks using an injectable provider and cosine similarity."""

    if top_k <= 0:
        return []
    embedding_provider = provider or HashEmbeddingProvider()
    chunk_list = list(chunks)
    if not chunk_list:
        return []

    query_vector = embed_query(embedding_provider, [query])[0]
    chunk_vectors = embed_documents(
        embedding_provider,
        [embedding_text(chunk) for chunk in chunk_list],
    )
    results = [
        SearchResult(
            chunk=chunk,
            score=cosine_similarity(query_vector, vector),
            matched_terms=(),
        )
        for chunk, vector in zip(chunk_list, chunk_vectors)
    ]
    results.sort(
        key=lambda result: (-result.score, result.chunk.source_path, result.chunk.start_line)
    )
    return results[:top_k]
