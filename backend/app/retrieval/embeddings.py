"""Embedding provider contracts and a deterministic offline test provider."""

from __future__ import annotations

import hashlib
import json
import math
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from dataclasses import dataclass
from typing import Any, Protocol

from .keyword_search import tokenize


class EmbeddingProvider(Protocol):
    """Contract for local or remote embedding implementations."""

    dimension: int | None

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector for every input text."""


@dataclass(frozen=True)
class HashEmbeddingProvider:
    """Deterministic hashing baseline for offline tests only.

    This is not a semantic model. It only makes the vector-search boundary
    testable before a real local or hosted embedding provider is selected.
    """

    dimension: int = 64

    def __post_init__(self) -> None:
        if self.dimension < 8:
            raise ValueError("dimension must be at least 8")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in tokenize(text):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] % 2 else -1.0
                vector[index] += sign
            magnitude = math.sqrt(sum(value * value for value in vector))
            if magnitude:
                vector = [value / magnitude for value in vector]
            vectors.append(vector)
        return vectors


class EmbeddingProviderError(RuntimeError):
    """Raised when a configured remote Embedding provider cannot be used."""


@dataclass
class OpenAICompatibleEmbeddingProvider:
    """Embedding client for OpenAI-compatible ``/embeddings`` endpoints.

    The client uses the Python standard library so the offline MVP does not
    require an SDK. It reads the API key only at call time and never includes
    it in errors or logs.
    """

    endpoint: str
    model: str
    api_key_env: str = "EMBEDDING_API_KEY"
    timeout_seconds: float = 30.0
    dimension: int | None = None

    @classmethod
    def from_env(cls) -> "OpenAICompatibleEmbeddingProvider":
        endpoint = os.getenv("EMBEDDING_API_URL", "").strip()
        model = os.getenv("EMBEDDING_MODEL", "").strip()
        if not endpoint or not model:
            raise EmbeddingProviderError(
                "EMBEDDING_API_URL and EMBEDDING_MODEL must be configured"
            )
        return cls(endpoint=endpoint, model=model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        api_key = os.getenv(self.api_key_env, "").strip()
        if not api_key:
            raise EmbeddingProviderError(
                f"{self.api_key_env} must be configured before remote embedding"
            )

        request = Request(
            self._embeddings_url(),
            data=json.dumps({"model": self.model, "input": texts}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise EmbeddingProviderError("remote embedding request failed") from exc

        return self._parse_embeddings(payload, expected_count=len(texts))

    def _embeddings_url(self) -> str:
        endpoint = self.endpoint.rstrip("/")
        return endpoint if endpoint.endswith("/embeddings") else f"{endpoint}/embeddings"

    def _parse_embeddings(self, payload: Any, expected_count: int) -> list[list[float]]:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != expected_count:
            raise EmbeddingProviderError("embedding response has an invalid data count")

        ordered = sorted(data, key=lambda item: item.get("index", 0))
        vectors: list[list[float]] = []
        for item in ordered:
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list) or not vector:
                raise EmbeddingProviderError("embedding response contains an invalid vector")
            try:
                numeric_vector = [float(value) for value in vector]
            except (TypeError, ValueError) as exc:
                raise EmbeddingProviderError("embedding response contains non-numeric values") from exc
            vectors.append(numeric_vector)

        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            raise EmbeddingProviderError("embedding response contains mixed dimensions")
        dimension = dimensions.pop()
        if self.dimension is not None and self.dimension != dimension:
            raise EmbeddingProviderError("embedding dimension does not match configuration")
        self.dimension = dimension
        return vectors
