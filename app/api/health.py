"""Health check endpoint.

A load balancer (or Kubernetes readiness probe) calls /health to decide
whether to route traffic to this instance.  Reporting the status of each
backing service lets operators spot partial outages — the API might still
serve cached responses even if Redis is down (graceful degradation).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.db.redis import redis_pool

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    result: dict[str, str] = {"status": "ok"}

    if redis_pool is not None:
        try:
            await redis_pool.ping()  # type: ignore[misc]
            result["redis"] = "ok"
        except Exception:
            result["redis"] = "degraded"
    else:
        result["redis"] = "not_configured"

    return result
