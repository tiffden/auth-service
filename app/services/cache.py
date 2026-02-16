"""Read-through cache service.

CACHING PATTERNS — A COMPARISON
---------------------------------

1. READ-THROUGH  (what we implement here)
   Flow:  Client → Cache → miss → DB → populate cache → return
          Client → Cache → hit  → return (skip DB entirely)

   The application asks the cache first.  On a miss, it fetches from
   the source of truth, stores the result in cache, and returns it.
   Simple, predictable, easy to debug.

2. CACHE-ASIDE
   Same as read-through, but the caller explicitly manages both the
   cache and the DB as separate calls.  Read-through wraps this into
   a single, cleaner pattern.

3. WRITE-THROUGH
   Every write goes to both the cache and the DB simultaneously.
   Guarantees the cache is always fresh, but doubles write latency.

4. WRITE-BEHIND  (mentioned in syllabus for awareness)
   Writes go to cache immediately, then flush to DB asynchronously.
   Fastest writes, but risks data loss if the cache crashes before
   the flush completes.  Too dangerous for an auth service where
   data integrity matters.

CACHE INVALIDATION — "THE TWO HARD THINGS IN CS"
--------------------------------------------------
  "There are only two hard things in Computer Science:
   cache invalidation and naming things." — Phil Karlton

We use two complementary strategies:

  1. TTL (Time To Live): Every cached entry auto-expires after N seconds.
     This is the SAFETY NET — even if we forget to invalidate somewhere,
     stale data disappears on its own.

  2. Explicit invalidation: When data changes (e.g., a new progress event
     is ingested), we immediately delete the cached entry.  This gives
     near-instant consistency for the common case.

WHY BOTH:
  - TTL alone → users see stale data for up to N seconds after a change
  - Explicit alone → a bug that skips the delete leaves stale data forever
  - Together → they cover each other's weaknesses
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.db.redis import redis_pool


@runtime_checkable
class CacheService(Protocol):
    async def get(self, key: str) -> str | None:
        """Fetch a cached value.  Returns None on cache miss."""
        ...

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store a value with a TTL (time to live)."""
        ...

    async def delete(self, key: str) -> None:
        """Explicitly invalidate a cached entry."""
        ...

    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching a glob pattern (e.g., 'progress:user123:*')."""
        ...


class InMemoryCacheService:
    """In-memory cache for testing — no TTL enforcement.

    Tests run fast enough that TTL expiry isn't relevant.  The autouse
    fixture in conftest.py clears the store between tests.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def delete_pattern(self, pattern: str) -> None:
        prefix = pattern.rstrip("*")
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]


class RedisCacheService:
    """Redis-backed cache — shared across all API instances."""

    # Key prefix prevents collisions with rate limiter, blacklist, etc.
    _PREFIX = "cache:"

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        return await self._redis.get(f"{self._PREFIX}{key}")

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._redis.setex(f"{self._PREFIX}{key}", ttl_seconds, value)

    async def delete(self, key: str) -> None:
        await self._redis.delete(f"{self._PREFIX}{key}")

    async def delete_pattern(self, pattern: str) -> None:
        # WHY SCAN instead of KEYS:
        # The KEYS command blocks Redis while it scans ALL keys in the
        # database.  On a production Redis with millions of keys, this
        # can freeze the server for seconds — essentially a self-inflicted
        # denial of service.
        #
        # SCAN is cursor-based: it returns a batch of matches and a cursor
        # to continue from.  Redis serves other commands between batches,
        # so it never blocks for long.  The trade-off is that SCAN may
        # return duplicates or miss keys that are added/removed during
        # iteration — acceptable for cache invalidation.
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(
                cursor, match=f"{self._PREFIX}{pattern}", count=100
            )
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

if redis_pool is not None:
    cache_service: CacheService = RedisCacheService(redis_pool)
else:
    cache_service = InMemoryCacheService()
