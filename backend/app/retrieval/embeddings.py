"""Embedding provider contracts and a deterministic offline test provider."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections import OrderedDict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .keyword_search import tokenize


class EmbeddingProvider(Protocol):
    """Contract for local or remote embedding implementations."""

    dimension: int | None

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector for every input text."""

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        """Embed query texts using the provider's query formatting."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document texts using the provider's document formatting."""


def embed_query(provider: EmbeddingProvider, texts: list[str]) -> list[list[float]]:
    """Use query-aware formatting when a provider exposes it."""

    method = getattr(provider, "embed_query", None)
    return method(texts) if callable(method) else provider.embed(texts)


def embed_documents(
    provider: EmbeddingProvider, texts: list[str]
) -> list[list[float]]:
    """Use document-aware formatting when a provider exposes it."""

    method = getattr(provider, "embed_documents", None)
    return method(texts) if callable(method) else provider.embed(texts)


@dataclass(frozen=True)
class HashEmbeddingProvider:
    """Deterministic hashing baseline for offline tests only.

    This is not a semantic model. It only makes the vector-search boundary
    testable before a real local or hosted embedding provider is selected.
    """

    # Keep the offline baseline compatible with the pgvector migration and
    # the common BGE-M3 embedding dimension used by the project.
    dimension: int = 1024

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

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        return self.embed(texts)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed(texts)


class EmbeddingProviderError(RuntimeError):
    """Raised when a configured remote Embedding provider cannot be used."""


@dataclass
class LocalSentenceTransformerEmbeddingProvider:
    """Lazy local BGE/E5-style embedding provider.

    The optional ``sentence-transformers`` dependency is imported only when
    the first embedding request is made. This keeps the default Hash provider
    lightweight and preserves the offline MVP test path. Model files are
    stored in the caller-provided cache folder rather than an implicit user
    cache location.
    """

    model_name: str = "BAAI/bge-small-zh-v1.5"
    cache_folder: str | None = "data/models"
    device: str = "cpu"
    batch_size: int = 16
    normalize_embeddings: bool = True
    backend: str = "torch"
    file_name: str | None = None
    query_prefix: str = ""
    document_prefix: str = ""
    dimension: int | None = None
    _model: Any = field(init=False, default=None, repr=False)
    _cache: OrderedDict[tuple[str, ...], list[list[float]]] = field(
        init=False, default_factory=OrderedDict, repr=False
    )

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if not 1 <= self.batch_size <= 256:
            raise ValueError("batch_size must be between 1 and 256")
        if self.backend not in {"torch", "onnx", "openvino"}:
            raise ValueError("backend must be torch, onnx, or openvino")
        if (
            self.file_name is None
            and self.backend == "onnx"
            and "e5" in self.model_name.lower()
        ):
            self.file_name = "model_qint8_avx512_vnni.onnx"
        if "e5" in self.model_name.lower():
            self.query_prefix = self.query_prefix or "query: "
            self.document_prefix = self.document_prefix or "passage: "

    @classmethod
    def from_env(cls) -> "LocalSentenceTransformerEmbeddingProvider":
        """Build a local provider from non-secret environment variables."""

        model_name = os.getenv(
            "LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"
        ).strip()
        cache_folder = os.getenv(
            "LOCAL_EMBEDDING_CACHE", "data/models"
        ).strip() or None
        device = os.getenv("LOCAL_EMBEDDING_DEVICE", "cpu").strip() or "cpu"
        backend = os.getenv("LOCAL_EMBEDDING_BACKEND", "torch").strip().lower() or "torch"
        file_name = os.getenv("LOCAL_EMBEDDING_FILE_NAME", "").strip() or None
        try:
            batch_size = int(os.getenv("LOCAL_EMBEDDING_BATCH_SIZE", "16"))
        except ValueError as exc:
            raise EmbeddingProviderError(
                "LOCAL_EMBEDDING_BATCH_SIZE must be an integer"
            ) from exc
        normalize_value = os.getenv("LOCAL_EMBEDDING_NORMALIZE", "true")
        normalize_embeddings = normalize_value.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        is_e5_model = "e5" in model_name.lower()
        query_prefix = os.getenv(
            "LOCAL_EMBEDDING_QUERY_PREFIX",
            "query: " if is_e5_model else "",
        )
        document_prefix = os.getenv(
            "LOCAL_EMBEDDING_DOCUMENT_PREFIX",
            "passage: " if is_e5_model else "",
        )
        try:
            return cls(
                model_name=model_name,
                cache_folder=cache_folder,
                device=device,
                batch_size=batch_size,
                normalize_embeddings=normalize_embeddings,
                backend=backend,
                file_name=file_name,
                query_prefix=query_prefix,
                document_prefix=document_prefix,
            )
        except ValueError as exc:
            raise EmbeddingProviderError(
                "local embedding configuration is invalid"
            ) from exc

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingProviderError(
                "local embedding requires sentence-transformers; "
                "install backend/requirements-local-embedding.txt"
            ) from exc

        cache_path = str(Path(self.cache_folder).expanduser()) if self.cache_folder else None
        try:
            model_kwargs = {}
            if self.file_name:
                model_kwargs["file_name"] = (
                    self.file_name
                    if "/" in self.file_name or "\\" in self.file_name
                    else f"onnx/{self.file_name}"
                )
            self._model = SentenceTransformer(
                self.model_name,
                cache_folder=cache_path,
                device=self.device,
                trust_remote_code=False,
                backend=self.backend,
                model_kwargs=model_kwargs,
            )
            dimension_getter = getattr(self._model, "get_embedding_dimension", None)
            if not callable(dimension_getter):
                dimension_getter = self._model.get_sentence_embedding_dimension
            self.dimension = int(dimension_getter())
        except Exception as exc:
            raise EmbeddingProviderError(
                "local embedding model could not be loaded"
            ) from exc
        if self.dimension < 1:
            raise EmbeddingProviderError("local embedding model returned an invalid dimension")
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._embed_with_prefix(texts, "")

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        return self._embed_with_prefix(texts, self.query_prefix)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_with_prefix(texts, self.document_prefix)

    def _embed_with_prefix(self, texts: list[str], prefix: str) -> list[list[float]]:
        if not texts:
            return []
        cache_key = (prefix, *texts)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return [vector[:] for vector in cached]

        model = self._load_model()
        try:
            encoded = model.encode(
                [f"{prefix}{text}" for text in texts],
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=self.normalize_embeddings,
            )
        except Exception as exc:
            raise EmbeddingProviderError("local embedding inference failed") from exc

        vectors: list[list[float]] = []
        try:
            for vector in encoded:
                numeric_vector = [float(value) for value in vector]
                if not numeric_vector or not all(
                    math.isfinite(value) for value in numeric_vector
                ):
                    raise EmbeddingProviderError(
                        "local embedding returned an invalid vector"
                    )
                if self.dimension != len(numeric_vector):
                    raise EmbeddingProviderError(
                        "local embedding returned mixed dimensions"
                    )
                vectors.append(numeric_vector)
        except TypeError as exc:
            raise EmbeddingProviderError(
                "local embedding returned an invalid batch"
            ) from exc
        if len(vectors) != len(texts):
            raise EmbeddingProviderError(
                "local embedding returned an invalid vector count"
            )

        self._cache[cache_key] = vectors
        self._cache.move_to_end(cache_key)
        while len(self._cache) > 512:
            self._cache.popitem(last=False)
        return [vector[:] for vector in vectors]


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
    batch_size: int = 64
    opener: Callable[[Request, float], Any] | None = None

    @classmethod
    def from_env(cls) -> "OpenAICompatibleEmbeddingProvider":
        endpoint = os.getenv("EMBEDDING_API_URL", "").strip()
        model = os.getenv("EMBEDDING_MODEL", "").strip()
        if not endpoint or not model:
            raise EmbeddingProviderError(
                "EMBEDDING_API_URL and EMBEDDING_MODEL must be configured"
            )
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise EmbeddingProviderError("EMBEDDING_API_URL must use http or https")
        api_key_env = os.getenv("EMBEDDING_API_KEY_ENV", "EMBEDDING_API_KEY").strip()
        if not api_key_env or not api_key_env.replace("_", "a").isalnum() or api_key_env[0].isdigit():
            raise EmbeddingProviderError("EMBEDDING_API_KEY_ENV is invalid")
        try:
            timeout_seconds = float(os.getenv("EMBEDDING_TIMEOUT", "30"))
            batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
            dimension_value = os.getenv("EMBEDDING_DIMENSION", "").strip()
            dimension = int(dimension_value) if dimension_value else None
        except ValueError as exc:
            raise EmbeddingProviderError("remote embedding numeric configuration is invalid") from exc
        if not 0 < timeout_seconds <= 120:
            raise EmbeddingProviderError("EMBEDDING_TIMEOUT must be between 0 and 120 seconds")
        if not 1 <= batch_size <= 256:
            raise EmbeddingProviderError("EMBEDDING_BATCH_SIZE must be between 1 and 256")
        if dimension is not None and dimension < 8:
            raise EmbeddingProviderError("EMBEDDING_DIMENSION must be at least 8")
        return cls(
            endpoint=endpoint,
            model=model,
            api_key_env=api_key_env,
            timeout_seconds=timeout_seconds,
            dimension=dimension,
            batch_size=batch_size,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        api_key = os.getenv(self.api_key_env, "").strip()
        if not api_key:
            raise EmbeddingProviderError(
                f"{self.api_key_env} must be configured before remote embedding"
            )

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed_batch(texts[start : start + self.batch_size], api_key))
        return vectors

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        return self.embed(texts)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed(texts)

    def _embed_batch(self, texts: list[str], api_key: str) -> list[list[float]]:
        request = Request(
            self._embeddings_url(),
            data=json.dumps(
                {"model": self.model, "input": texts, "encoding_format": "float"}
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "DevSage/0.1",
            },
            method="POST",
        )
        open_url = self.opener or urlopen
        try:
            with open_url(request, self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise EmbeddingProviderError("remote embedding request failed") from exc
        return self._parse_embeddings(payload, expected_count=len(texts))

    def _embeddings_url(self) -> str:
        endpoint = self.endpoint.rstrip("/")
        return endpoint if endpoint.endswith("/embeddings") else f"{endpoint}/embeddings"

    def _parse_embeddings(self, payload: Any, expected_count: int) -> list[list[float]]:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != expected_count:
            raise EmbeddingProviderError("embedding response has an invalid data count")

        if any(not isinstance(item, dict) or not isinstance(item.get("index"), int) for item in data):
            raise EmbeddingProviderError("embedding response contains invalid indexes")
        indexes = [item["index"] for item in data]
        if sorted(indexes) != list(range(expected_count)):
            raise EmbeddingProviderError("embedding response indexes are incomplete or duplicated")
        ordered = sorted(data, key=lambda item: item["index"])
        vectors: list[list[float]] = []
        for item in ordered:
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list) or not vector:
                raise EmbeddingProviderError("embedding response contains an invalid vector")
            try:
                numeric_vector = [float(value) for value in vector]
            except (TypeError, ValueError) as exc:
                raise EmbeddingProviderError("embedding response contains non-numeric values") from exc
            if not all(math.isfinite(value) for value in numeric_vector):
                raise EmbeddingProviderError("embedding response contains non-finite values")
            vectors.append(numeric_vector)

        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            raise EmbeddingProviderError("embedding response contains mixed dimensions")
        dimension = dimensions.pop()
        if self.dimension is not None and self.dimension != dimension:
            raise EmbeddingProviderError("embedding dimension does not match configuration")
        self.dimension = dimension
        return vectors
