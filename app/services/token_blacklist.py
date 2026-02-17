"""Token blacklist for immediate JWT revocation.

THE PROBLEM WITH STATELESS TOKENS
-----------------------------------
JWTs are "stateless" — once issued, they're valid until they expire.
The server doesn't remember which tokens it issued, so it can't
"un-issue" one.  But sometimes you NEED to invalidate a token before
it expires:

  - User logs out (their token should stop working immediately)
  - User changes their password (old tokens should be invalid)
  - Admin revokes a compromised account

THE SOLUTION: A SMALL STATEFUL LAYER
--------------------------------------
We maintain a SET of revoked token IDs (the "jti" claim in the JWT).
On every authenticated request, after verifying the JWT signature,
we check: "is this token's jti in the blacklist?"  If yes, reject it.

This is a conscious trade-off:
  - Pure stateless: no revocation possible, but zero server-side storage
  - Full session store: server tracks ALL active sessions (heavy)
  - Blacklist (our approach): server only tracks REVOKED tokens (lightweight)

WHY REDIS (NOT POSTGRES)
--------------------------
This check runs on EVERY authenticated request.  It must be fast.
  - Redis: ~0.1ms (in-memory, no disk I/O)
  - Postgres: ~1-5ms (connection overhead, query parsing, disk)

With 1000 requests/second, that's the difference between 0.1 seconds
of added latency and 1-5 seconds across all requests.

WHY TTL MATCHING TOKEN EXPIRY
-------------------------------
A token that's already expired doesn't need to stay in the blacklist
(it would be rejected by the signature check anyway).  Setting a Redis
TTL equal to the token's remaining lifetime means entries self-clean.
No cron job, no manual cleanup, no growing memory.

MEMORY MATH
  Each blacklist entry: UUID string (36 bytes) + Redis key overhead (~100 bytes)
  With 15-minute token TTL and 10,000 active users who all log out:
    10,000 * 136 bytes = 1.3 MB — negligible.
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from app.db.redis import redis_pool


@runtime_checkable
class TokenBlacklist(Protocol):
    async def revoke(self, jti: str, expires_at: float) -> None:
        """Add a token's JTI to the blacklist until it would have expired."""
        ...

    async def is_revoked(self, jti: str) -> bool:
        """Check if a token has been revoked."""
        ...


class InMemoryTokenBlacklist:
    """In-memory blacklist for testing and local dev (no Redis needed).

    Limitation: this is per-process.  In production with multiple API
    instances, a logout on server A wouldn't be visible on server B.
    That's why we use Redis in production — shared state.
    """

    def __init__(self) -> None:
        # jti -> expiry timestamp (Unix seconds)
        self._revoked: dict[str, float] = {}

    async def revoke(self, jti: str, expires_at: float) -> None:
        self._revoked[jti] = expires_at

    async def is_revoked(self, jti: str) -> bool:
        from app.core.metrics import TOKEN_BLACKLIST_CHECKS

        exp = self._revoked.get(jti)
        if exp is None:
            TOKEN_BLACKLIST_CHECKS.labels(result="valid").inc()
            return False
        # Mimic Redis TTL behavior: auto-clean expired entries
        if exp < time.time():
            del self._revoked[jti]
            TOKEN_BLACKLIST_CHECKS.labels(result="valid").inc()
            return False
        TOKEN_BLACKLIST_CHECKS.labels(result="revoked").inc()
        return True


class RedisTokenBlacklist:
    """Redis-backed blacklist — shared across all API instances.

    Uses Redis key prefixing to avoid collisions with other features
    (rate limiting, caching) that share the same Redis instance.
    """

    _PREFIX = "blacklist:jti:"

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def revoke(self, jti: str, expires_at: float) -> None:
        ttl_seconds = int(expires_at - time.time())
        if ttl_seconds <= 0:
            return  # Token already expired — no need to blacklist

        # WHY SETEX instead of SET + EXPIRE:
        # SETEX sets the value AND the TTL in one atomic command.
        # With separate SET then EXPIRE, a crash between the two
        # would leave a key that never expires — a slow memory leak.
        await self._redis.setex(f"{self._PREFIX}{jti}", ttl_seconds, "1")

    async def is_revoked(self, jti: str) -> bool:
        # EXISTS is slightly faster than GET when we only need
        # presence, not value.
        return bool(await self._redis.exists(f"{self._PREFIX}{jti}"))


# ---------------------------------------------------------------------------
# Module-level singleton — conditional on Redis availability
# ---------------------------------------------------------------------------

if redis_pool is not None:
    token_blacklist: TokenBlacklist = RedisTokenBlacklist(redis_pool)
else:
    token_blacklist = InMemoryTokenBlacklist()
