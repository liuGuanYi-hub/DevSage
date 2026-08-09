"""Small cache boundary with an offline implementation and optional Redis."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from threading import RLock
import time
from typing import Any, Protocol
from urllib.parse import urlparse


class CacheError(RuntimeError):
    """Raised when the configured cache cannot be used safely."""


class CacheBackend(Protocol):
    name: str

    def get(self, key: str) -> str | None:
        """Return a cached string or ``None``."""

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store a value for a bounded amount of time."""

    def delete_prefix(self, prefix: str) -> None:
        """Invalidate keys in one logical namespace."""


class NullCache:
    name = "disabled"

    def get(self, _key: str) -> None:
        return None

    def set(self, _key: str, _value: str, _ttl_seconds: int) -> None:
        return None

    def delete_prefix(self, _prefix: str) -> None:
        return None


@dataclass
class MemoryCache:
    """Bounded in-process cache used by offline mode and unit tests."""

    max_items: int = 256

    def __post_init__(self) -> None:
        self.name = "memory"
        self._items: dict[str, tuple[float, str]] = {}
        self._lock = RLock()

    def get(self, key: str) -> str | None:
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._items.pop(key, None)
                return None
            return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        with self._lock:
            if len(self._items) >= self.max_items and key not in self._items:
                oldest = min(self._items, key=lambda item_key: self._items[item_key][0])
                self._items.pop(oldest, None)
            self._items[key] = (time.monotonic() + ttl_seconds, value)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for key in tuple(self._items):
                if key.startswith(prefix):
                    self._items.pop(key, None)


class RedisCache:
    """Redis-backed cache. The Redis SDK is imported only when selected."""

    name = "redis"

    def __init__(self, client: Any, key_prefix: str = "devsage:") -> None:
        self.client = client
        self.key_prefix = key_prefix

    @classmethod
    def from_environment(cls) -> "RedisCache":
        url = os.getenv("DEVSAGE_REDIS_URL", "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"redis", "rediss"} or not parsed.netloc:
            raise CacheError("DEVSAGE_REDIS_URL must use redis or rediss")
        try:
            import redis  # type: ignore
        except ImportError as exc:
            raise CacheError("Redis cache requires the redis Python package") from exc
        try:
            timeout = float(os.getenv("DEVSAGE_REDIS_TIMEOUT", "2"))
        except ValueError as exc:
            raise CacheError("DEVSAGE_REDIS_TIMEOUT is invalid") from exc
        if not 0 < timeout <= 30:
            raise CacheError("DEVSAGE_REDIS_TIMEOUT must be between 0 and 30 seconds")
        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
        )
        return cls(client)

    def _key(self, key: str) -> str:
        return f"{self.key_prefix}{key}"

    def get(self, key: str) -> str | None:
        return self.client.get(self._key(key))

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if ttl_seconds > 0:
            self.client.setex(self._key(key), ttl_seconds, value)

    def delete_prefix(self, prefix: str) -> None:
        pattern = self._key(prefix) + "*"
        keys = list(self.client.scan_iter(match=pattern, count=100))
        if keys:
            self.client.delete(*keys)


def create_cache_backend() -> CacheBackend:
    mode = os.getenv("DEVSAGE_CACHE", "memory").strip().lower() or "memory"
    if mode in {"none", "disabled", "off"}:
        return NullCache()
    if mode == "redis":
        return RedisCache.from_environment()
    if mode in {"memory", "in-memory"}:
        return MemoryCache()
    raise CacheError(f"unsupported DEVSAGE_CACHE mode: {mode}")


def cache_key(namespace: str, *parts: object) -> str:
    """Hash query material so sensitive text is not copied into Redis keys."""

    digest = hashlib.sha256(
        json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"{namespace}:{digest}"
