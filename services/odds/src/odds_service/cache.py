import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol


class Cache(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int) -> None: ...
    async def close(self) -> None: ...


class MemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        entry = self._data.get(key)
        if entry is None or entry[0] < time.monotonic():
            self._data.pop(key, None)
            return None
        return entry[1]

    async def set(self, key: str, value: Any, ttl: int) -> None:
        self._data[key] = (time.monotonic() + ttl, value)

    async def close(self) -> None:
        pass


class RedisCache:
    """Shared across all replicas, so N instances cost one upstream call per key per TTL."""

    def __init__(self, url: str) -> None:
        from redis.asyncio import Redis

        self._redis = Redis.from_url(url)

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        return None if raw is None else json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        await self._redis.set(key, json.dumps(value), ex=ttl)

    async def close(self) -> None:
        await self._redis.aclose()


class CachedLoader:
    """Read-through cache with per-key request coalescing.

    When a hot key expires, concurrent requests in this process wait on one
    upstream call instead of each spending quota on the same data.
    """

    def __init__(self, cache: Cache) -> None:
        self.cache = cache
        self._locks: dict[str, asyncio.Lock] = {}

    async def get(self, key: str, ttl: int, load: Callable[[], Awaitable[Any]]) -> Any:
        if (hit := await self.cache.get(key)) is not None:
            return hit
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            if (hit := await self.cache.get(key)) is not None:
                return hit
            value = await load()
            await self.cache.set(key, value, ttl)
            return value
