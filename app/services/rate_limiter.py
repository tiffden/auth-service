"""Rate limiting using the Token Bucket algorithm.

WHAT IS RATE LIMITING?
-----------------------
Rate limiting controls how many requests a client can make in a given
time window.  Without it, a single misbehaving client (or attacker)
can overwhelm the server, degrading service for everyone else.

CHOOSING AN ALGORITHM
----------------------
There are several rate-limiting algorithms, each with trade-offs:

1. FIXED WINDOW  (e.g., "100 requests per minute")
   Simple: keep a counter, reset it every minute.
   Problem: a user can send 100 requests at 11:59:59 and 100 more
   at 12:00:01 — 200 requests in 2 seconds.  This "boundary burst"
   defeats the purpose.

2. SLIDING WINDOW LOG
   Track every request timestamp.  Count how many fall in the last
   60 seconds.  Accurate, but storing a timestamp per request is
   memory-hungry at scale.

3. LEAKY BUCKET
   Requests enter a queue (bucket) and are processed at a fixed rate,
   like water dripping from a bucket.  Good for smoothing traffic,
   but doesn't allow ANY bursts — even legitimate ones.

4. TOKEN BUCKET  (what we use)
   Imagine a bucket that holds N tokens.  It refills at a steady rate
   (e.g., 1 token/second).  Each request costs 1 token.  If the
   bucket is empty, the request is rejected.

   Why this wins for APIs:
   - Allows short bursts up to bucket capacity.  Real users click in
     bursts (load a page = 5 parallel API calls), not at a uniform rate.
   - Enforces a long-term average rate (the refill rate).
   - Memory-efficient: only stores (token_count, last_refill_time),
     not a list of timestamps.  Two numbers per client.
   - Simple atomic implementation with Redis.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """The outcome of a rate limit check.

    allowed:      True if the request may proceed.
    remaining:    How many tokens are left in the bucket.
    limit:        The bucket's maximum capacity.
    retry_after:  Seconds until the next token is available (0 if allowed).
                  Clients should use this to implement exponential backoff.
    """

    allowed: bool
    remaining: int
    limit: int
    retry_after: float


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """Configurable rate limit parameters.

    Different endpoints have different abuse profiles:
    - Login attempts need strict limits (brute-force protection)
    - Read-only endpoints can be more generous
    - Progress ingestion sits in between

    capacity:    Maximum tokens in the bucket (burst size).
    refill_rate: Tokens added per second (sustained rate).

    Example: capacity=60, refill_rate=1.0 means "60 requests burst,
    then 1 per second sustained" — 60/minute long-term average.
    """

    capacity: int = 60
    refill_rate: float = 1.0


@runtime_checkable
class RateLimiter(Protocol):
    """Protocol for rate limiting backends.

    Same pattern as UserRepo: Protocol interface with InMemory for
    tests and Redis for production.
    """

    async def check(self, key: str, config: RateLimitConfig) -> RateLimitResult: ...
    async def reset(self, key: str) -> None: ...


class InMemoryRateLimiter:
    """In-memory token bucket — works for single-process dev/test.

    LIMITATION FOR PRODUCTION:
    In production with multiple API instances behind a load balancer,
    each process has its own dict.  User A could get 60 requests on
    server 1 AND 60 on server 2 (120 total).  Redis solves this
    because all instances share the same store.
    """

    def __init__(self) -> None:
        # key -> (tokens_remaining, last_refill_timestamp)
        self._buckets: dict[str, tuple[float, float]] = {}

    async def check(self, key: str, config: RateLimitConfig) -> RateLimitResult:
        now = time.monotonic()

        if key not in self._buckets:
            # First request ever from this client: full bucket minus 1
            self._buckets[key] = (config.capacity - 1, now)
            return RateLimitResult(
                allowed=True,
                remaining=config.capacity - 1,
                limit=config.capacity,
                retry_after=0,
            )

        tokens, last_refill = self._buckets[key]

        # Step 1: Refill — how many tokens have accumulated since last check?
        elapsed = now - last_refill
        tokens = min(config.capacity, tokens + elapsed * config.refill_rate)

        # Step 2: Try to consume one token
        if tokens >= 1:
            tokens -= 1
            self._buckets[key] = (tokens, now)
            return RateLimitResult(
                allowed=True,
                remaining=int(tokens),
                limit=config.capacity,
                retry_after=0,
            )

        # Step 3: Bucket empty — calculate when the next token arrives
        retry_after = (1 - tokens) / config.refill_rate
        self._buckets[key] = (tokens, now)
        return RateLimitResult(
            allowed=False,
            remaining=0,
            limit=config.capacity,
            retry_after=retry_after,
        )

    async def reset(self, key: str) -> None:
        """Remove a client's bucket (used in tests)."""
        self._buckets.pop(key, None)


class RedisRateLimiter:
    """Redis-backed token bucket — shared across all API instances.

    WHY A LUA SCRIPT:
    The token bucket algorithm is a read-modify-write operation:
      1. Read current token count
      2. Calculate refill
      3. Decrement (or reject)
      4. Write back

    Without atomicity, two concurrent requests could both read
    "10 tokens", both decrement to 9, and both succeed — consuming
    only 1 token instead of 2.  This is a classic race condition.

    Redis executes Lua scripts atomically: no other command can run
    in between steps.  This guarantees correct counting even under
    high concurrency.
    """

    # The Lua script runs entirely inside Redis, atomically.
    # KEYS[1] = the bucket key
    # ARGV[1] = capacity, ARGV[2] = refill_rate, ARGV[3] = current time
    # Returns: {allowed (0/1), remaining, retry_after_ms}
    _LUA_SCRIPT = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])

    local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
    local tokens = tonumber(bucket[1])
    local last_refill = tonumber(bucket[2])

    if tokens == nil then
        -- First request: start with full bucket minus 1
        tokens = capacity - 1
        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
        -- Auto-expire idle buckets after capacity seconds (cleanup)
        redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 60)
        return {1, tokens, 0}
    end

    -- Refill tokens based on elapsed time
    local elapsed = now - last_refill
    tokens = math.min(capacity, tokens + elapsed * refill_rate)

    if tokens >= 1 then
        tokens = tokens - 1
        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 60)
        return {1, math.floor(tokens), 0}
    end

    -- Rejected: calculate milliseconds until next token
    local retry_after_ms = math.ceil((1 - tokens) / refill_rate * 1000)
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    return {0, 0, retry_after_ms}
    """

    def __init__(self, redis_client) -> None:
        self._redis = redis_client
        self._script = None

    async def _get_script(self):
        if self._script is None:
            self._script = self._redis.register_script(self._LUA_SCRIPT)
        return self._script

    async def check(self, key: str, config: RateLimitConfig) -> RateLimitResult:
        script = await self._get_script()
        result = await script(
            keys=[f"ratelimit:{key}"],
            args=[config.capacity, config.refill_rate, time.time()],
        )
        allowed, remaining, retry_after_ms = result
        return RateLimitResult(
            allowed=bool(allowed),
            remaining=int(remaining),
            limit=config.capacity,
            retry_after=retry_after_ms / 1000,
        )

    async def reset(self, key: str) -> None:
        await self._redis.delete(f"ratelimit:{key}")
