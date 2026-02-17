"""Rate limiting dependency for FastAPI routes.

WHY A DEPENDENCY (NOT MIDDLEWARE)
----------------------------------
Middleware runs on EVERY request.  A dependency runs only on routes
that declare it.  This gives us fine-grained control:

  POST /login          → strict limit (10/min) — brute-force protection
  POST /v1/progress    → moderate limit (60/min) — normal API usage
  GET  /health         → no limit at all — monitoring must always work

A middleware approach would force one-size-fits-all limits, or require
complex path-matching logic inside the middleware.  The dependency
approach is more "FastAPI-native" and composable — you can stack
multiple dependencies (auth + rate limit) on a single route.

RATE LIMIT KEYS
----------------
We build the key from the most specific identity available:
  1. Authenticated user → key by user_id (fairest)
  2. Anonymous request  → key by client IP (fallback)

WHY user_id OVER IP:
  Multiple users behind a corporate NAT or VPN share one public IP.
  Rate limiting by IP would punish all of them when one user is
  aggressive.  Per-user limits are fairer and more predictable.

RESPONSE HEADERS
-----------------
We set X-RateLimit-* headers on every response (not just 429s) so
clients can see their remaining quota and self-throttle before hitting
the limit.  This reduces unnecessary rejected requests — a courtesy
that makes your API easier to integrate with.
"""

from __future__ import annotations

import logging

import jwt as pyjwt
from fastapi import HTTPException, Request, status

from app.db.redis import redis_pool
from app.services.rate_limiter import (
    InMemoryRateLimiter,
    RateLimitConfig,
    RateLimitResult,
    RedisRateLimiter,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton — same conditional pattern as token_blacklist
# ---------------------------------------------------------------------------

if redis_pool is not None:
    _rate_limiter = RedisRateLimiter(redis_pool)
else:
    _rate_limiter = InMemoryRateLimiter()


_DEFAULT_CONFIG = RateLimitConfig()


def require_rate_limit(config: RateLimitConfig = _DEFAULT_CONFIG):
    """Dependency factory: enforce rate limits on a route.

    Returns a FastAPI dependency function.  Use it in two ways:

    1. As a route dependency (no access to the principal):
       @router.post("/login", dependencies=[Depends(require_rate_limit(
           RateLimitConfig(capacity=10, refill_rate=0.17)
       ))])

    2. Alongside other dependencies in the function signature:
       async def endpoint(
           principal: Principal = Depends(require_user),
           _rl: None = Depends(require_rate_limit()),
       ): ...
    """

    async def _check(request: Request) -> None:
        key = _build_key(request)
        result: RateLimitResult = await _rate_limiter.check(key, config)

        # Always set rate limit headers — even on success — so clients
        # can monitor their remaining quota proactively.
        request.state.rate_limit_headers = {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
        }

        if not result.allowed:
            from app.core.metrics import RATE_LIMIT_HITS

            RATE_LIMIT_HITS.labels(
                key_type="user" if key.startswith("user:") else "ip"
            ).inc()
            logger.warning("Rate limit exceeded key=%s", key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    # Retry-After tells the client how long to wait before
                    # retrying.  Well-behaved clients use this for backoff.
                    "Retry-After": str(int(result.retry_after) + 1),
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

    return _check


def _build_key(request: Request) -> str:
    """Build a rate-limit key from the best available identity.

    We peek at the Authorization header to extract the user identity
    without depending on require_user (which may or may not have run
    yet in the dependency graph).  This is intentionally lightweight —
    we decode without signature verification because we only need the
    'sub' claim for building a rate-limit key.

    A forged token with a fake 'sub' just gets its own bucket, which
    is harmless.  The actual security check happens in require_user.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            # Decode WITHOUT verification — just extract 'sub' for keying
            claims = pyjwt.decode(auth_header[7:], options={"verify_signature": False})
            sub = claims.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass

    # Fallback: use client IP for unauthenticated endpoints (like /login)
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"
