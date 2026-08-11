"""Select an embedding provider without making implicit network calls."""

from __future__ import annotations

import os

from .embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
    HashEmbeddingProvider,
    LocalSentenceTransformerEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)


def create_embedding_provider() -> EmbeddingProvider:
    """Build the configured provider; default to the offline test baseline."""

    mode = os.getenv("EMBEDDING_PROVIDER", "hash").strip().lower()
    if mode in {"hash", "offline"}:
        return HashEmbeddingProvider()
    if mode in {"openai-compatible", "openai_compatible", "remote"}:
        return OpenAICompatibleEmbeddingProvider.from_env()
    if mode in {"local", "sentence-transformers", "sentence_transformers", "bge", "e5"}:
        return LocalSentenceTransformerEmbeddingProvider.from_env()
    raise EmbeddingProviderError(f"unsupported EMBEDDING_PROVIDER: {mode}")
