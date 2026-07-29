"""Embedding provider contracts and a deterministic offline test provider."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Protocol

from .keyword_search import tokenize


class EmbeddingProvider(Protocol):
    """Contract for local or remote embedding implementations."""

    dimension: int

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

