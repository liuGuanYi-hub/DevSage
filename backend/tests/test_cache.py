import os
import unittest
from unittest.mock import patch

from backend.app.services.cache import (
    CacheError,
    MemoryCache,
    RedisCache,
    cache_key,
    create_cache_backend,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key: str):
        return self.values.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = ttl

    def scan_iter(self, match: str, count: int):
        prefix = match.removesuffix("*")
        return iter([key for key in self.values if key.startswith(prefix)])

    def delete(self, *keys: str) -> None:
        for key in keys:
            self.values.pop(key, None)


class CacheTests(unittest.TestCase):
    def test_memory_cache_supports_ttl_and_namespace_invalidation(self) -> None:
        cache = MemoryCache()
        cache.set("search:a", "one", ttl_seconds=30)
        cache.set("answer:b", "two", ttl_seconds=30)
        self.assertEqual("one", cache.get("search:a"))
        cache.delete_prefix("search:")
        self.assertIsNone(cache.get("search:a"))
        self.assertEqual("two", cache.get("answer:b"))

    def test_redis_cache_uses_prefixed_keys_and_ttl(self) -> None:
        client = FakeRedis()
        cache = RedisCache(client, key_prefix="test:")
        cache.set("search:a", "one", ttl_seconds=12)
        self.assertEqual("one", cache.get("search:a"))
        self.assertEqual(12, client.ttls["test:search:a"])
        cache.delete_prefix("search:")
        self.assertIsNone(cache.get("search:a"))

    def test_cache_key_does_not_copy_query_text(self) -> None:
        key = cache_key("search", "a private query that must not be a Redis key")
        self.assertTrue(key.startswith("search:"))
        self.assertNotIn("private", key)

    def test_redis_mode_requires_valid_url(self) -> None:
        with patch.dict(os.environ, {"DEVSAGE_CACHE": "redis", "DEVSAGE_REDIS_URL": ""}, clear=False):
            with self.assertRaises(CacheError):
                create_cache_backend()


if __name__ == "__main__":
    unittest.main()
