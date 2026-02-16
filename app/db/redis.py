"""Redis connection management.

This module mirrors the pattern in engine.py for PostgreSQL:
when REDIS_URL is configured, we create a real connection pool;
when it's None (local dev, tests), everything falls back to
in-memory implementations and no Redis server is needed.

WHY REDIS?
----------
PostgreSQL is great for durable, relational data (users, orgs,
credentials).  But some data is:
  - Ephemeral (rate-limit counters that reset every minute)
  - Hot-path (checked on every single request, like token blacklists)
  - Shared across processes (all API instances need the same view)

Redis is an in-memory data store that handles these cases:
  - Sub-millisecond reads (vs 1-5ms for Postgres)
  - Built-in TTL (keys auto-expire — no cleanup jobs)
  - Atomic operations (INCR, LPUSH/BRPOP, Lua scripts)
  - Simple key-value model (no schema, no migrations)

The trade-off: Redis data is less durable than Postgres.  A restart
loses everything unless persistence is configured.  That's fine for
caches and counters, but not for user records.

CONNECTION POOLING
------------------
Redis is single-threaded — it processes one command at a time.  But
our FastAPI app handles many requests concurrently via async/await.
A connection pool lets multiple async handlers issue commands without
blocking each other on the Python side.  Each handler borrows a
connection, sends a command, and returns it to the pool.

Think of it like a library with 20 copies of the same book: 20
students can read simultaneously without waiting for each other.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis

from app.core.config import SETTINGS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conditional Redis client (None when REDIS_URL is not set)
# ---------------------------------------------------------------------------
# This follows the same pattern as engine.py: check the config at import
# time, create the client if configured, otherwise set to None.  Every
# consumer of redis_pool checks for None and falls back to in-memory.

if SETTINGS.redis_url:
    redis_pool: aioredis.Redis | None = aioredis.from_url(  # type: ignore[type-arg]
        SETTINGS.redis_url,
        decode_responses=True,  # return str instead of bytes — less casting
        max_connections=20,  # enough for typical API concurrency
    )
else:
    redis_pool = None


@asynccontextmanager
async def lifespan_redis():
    """Startup/shutdown hook for Redis — mirrors lifespan_db().

    WHY a lifespan hook:
    FastAPI's lifespan protocol gives us a clean place to verify
    the connection on startup (fail fast if Redis is unreachable)
    and release resources on shutdown (no leaked connections).
    """
    if redis_pool is None:
        logger.info("No REDIS_URL configured — Redis features use in-memory fallbacks")
        yield
        return

    # Verify connectivity on startup
    try:
        await redis_pool.ping()  # type: ignore[misc]  # redis stubs mistype async ping as bool
        logger.info("Redis connected: %s", SETTINGS.redis_url)
    except Exception:
        logger.exception("Redis connection failed on startup")
        # Yield instead of raising — the app can still start and serve
        # requests using in-memory fallbacks.  This is "graceful
        # degradation": better to run with reduced functionality than
        # to crash entirely.
        yield
        return

    yield

    await redis_pool.aclose()
    logger.info("Redis connection pool closed")
