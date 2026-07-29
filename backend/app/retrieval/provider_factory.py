"""Select an embedding provider without making implicit network calls."""

from __future__ import annotations

import os

from .embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
    HashEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)


def create_embedding_provider() -> EmbeddingProvider:
    """Build the configured provider; default to the offline test baseline."""

    mode = os.getenv("EMBEDDING_PROVIDER", "hash").strip().lower()
    if mode in {"hash", "offline"}:
        return HashEmbeddingProvider()
    if mode in {"openai-compatible", "openai_compatible", "remote"}:
        return OpenAICompatibleEmbeddingProvider.from_env()
    raise EmbeddingProviderError(f"unsupported EMBEDDING_PROVIDER: {mode}")

