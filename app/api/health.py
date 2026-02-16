"""Health and readiness endpoints.

LIVENESS vs READINESS (Kubernetes concepts)
--------------------------------------------
These are two different questions an orchestrator asks your service:

  /health (liveness):
    "Is this process alive and not deadlocked?"
    If this fails, Kubernetes RESTARTS the container.
    Keep it simple — if the Python process can respond, it's alive.

  /ready (readiness):
    "Can this instance handle traffic right now?"
    If this fails, the load balancer STOPS SENDING traffic (but does NOT
    restart the container).  The service can recover on its own.

    Use this for temporary conditions: database connection lost, Redis
    down, still warming up caches after a restart.

  WHY separate endpoints:
    A service might be alive but temporarily unable to serve requests.
    Restarting it would be destructive (kills in-flight requests, loses
    warm caches).  Removing it from the load balancer is gentle — it
    can recover and rejoin when ready.

    Think of it like a restaurant:
    - Liveness: "Is the restaurant open?" (yes = lights on, staff present)
    - Readiness: "Can I seat a customer right now?" (no = kitchen backed up)
    You don't demolish the building when the kitchen is slow.

HEALTH RESPONSE STRUCTURE
---------------------------
The response includes three sections:
  status:  overall health ("ok" or "degraded")
  checks:  per-dependency status (redis, database)
  slos:    current SLO compliance from Prometheus metrics
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import REGISTRY

from app.core.slo import (
    evaluate_availability,
    evaluate_latency,
    evaluate_queue_processing,
)
from app.db.redis import redis_pool

router = APIRouter(tags=["health"])


def _sum_counter(metric_name: str, label_filter: dict | None = None) -> float:
    """Sum all sample values for a counter across all label combinations.

    Prometheus counters are labeled (e.g., by method, endpoint, status_code).
    To compute "total requests across ALL endpoints", we need to sum across
    all label combinations that match the filter.

    Example: _sum_counter("http_requests_total", {"status_code": "200"})
    sums all 200-status requests regardless of method or endpoint.
    """
    total = 0.0
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name != metric_name:
                continue
            if label_filter and not all(
                sample.labels.get(k) == v for k, v in label_filter.items()
            ):
                continue
            total += sample.value
    return total


@router.get("/health")
async def health() -> dict:
    """Liveness probe + dependency status + SLO compliance.

    Returns 200 even when degraded — the STATUS field indicates the
    actual health.  A 200 with status=degraded means "alive but impaired."
    Returning 503 here would cause Kubernetes to restart the container,
    which is too aggressive for a partial outage.
    """
    checks: dict[str, str] = {}
    overall = "ok"

    # --- Redis check ---
    if redis_pool is not None:
        try:
            await redis_pool.ping()  # type: ignore[misc]
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "degraded"
            overall = "degraded"
    else:
        checks["redis"] = "not_configured"

    # --- SLO status (computed from in-process Prometheus metrics) ---
    #
    # LIMITATION: These SLO values are per-process approximations, NOT
    # production-grade SLO tracking.  In a real system:
    #
    #   1. Prometheus aggregates metrics ACROSS all API instances.
    #      This process only sees its own counters.  With 3 API replicas,
    #      each /health response shows 1/3 of the picture.
    #
    #   2. Prometheus computes true percentiles (p95, p99) from histogram
    #      buckets using histogram_quantile().  We can't do that from
    #      the Python client — we only have sum and count, so we
    #      approximate (see latency section below).
    #
    #   3. SLO evaluation windows (30 days) require persistent time-series
    #      storage.  These counters reset on process restart.
    #
    # For learning purposes, this shows HOW metrics feed SLO evaluation.
    # In production, you'd query Prometheus via its HTTP API or use a
    # dedicated SLO tool (Sloth, Google SLO Generator, Nobl9).

    # Availability: count all requests vs 5xx errors
    total_all = _sum_counter("http_requests_total")
    total_5xx = sum(
        _sum_counter("http_requests_total", {"status_code": str(code)})
        for code in range(500, 512)
    )
    availability_status = evaluate_availability(int(total_all), int(total_5xx))

    # Latency: approximate p95 from histogram sum/count.
    #
    # LIMITATION: avg * 2 is a crude heuristic, not a real percentile.
    # It's directionally useful (if avg is high, p95 is almost certainly
    # high) but can over- or under-estimate depending on the distribution.
    #
    # A more accurate in-process approach would walk the histogram buckets
    # to interpolate p95, but that adds complexity.  In production,
    # Prometheus does this natively with:
    #   histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
    duration_sum = 0.0
    duration_count = 0.0
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name == "http_request_duration_seconds_sum":
                duration_sum += sample.value
            elif sample.name == "http_request_duration_seconds_count":
                duration_count += sample.value

    if duration_count > 0:
        avg_ms = (duration_sum / duration_count) * 1000
        p95_estimate_ms = avg_ms * 2.0
    else:
        p95_estimate_ms = 0.0
    latency_status = evaluate_latency(p95_estimate_ms)

    # Queue processing: the API process doesn't run tasks — the worker
    # does.  We show defaults here.  In production, Prometheus would
    # aggregate worker metrics alongside API metrics.
    queue_status = evaluate_queue_processing(total_tasks=0, slow_tasks=0)

    slos = {}
    for s in [availability_status, latency_status, queue_status]:
        slos[s.slo.name] = {
            "current": s.current,
            "target": s.slo.target,
            "healthy": s.healthy,
        }

    return {
        "status": overall,
        "checks": checks,
        "slos": slos,
    }


@router.get("/ready")
async def ready() -> Response:
    """Readiness probe — can this instance handle traffic?

    Returns 200 if all critical dependencies are reachable.
    Returns 503 if any critical dependency is down.

    The load balancer uses this to decide whether to route traffic here.
    Unlike /health, a 503 here does NOT trigger a restart — it just
    removes this instance from the rotation until it recovers.
    """
    # Redis: optional (in-memory fallback exists), so not critical
    # for readiness.  If we had a database dependency, that would be
    # critical.  For now, readiness always passes — the service can
    # function without Redis via in-memory fallbacks.

    # If Redis is configured but unreachable, we could consider this
    # "not ready" in a strict deployment.  For this educational project,
    # we keep it simple: if the process can respond, it's ready.
    return Response(status_code=200)
