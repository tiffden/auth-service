"""Prometheus metrics endpoint.

This endpoint is called by Prometheus (the monitoring server) every
N seconds to collect the current metric values.  It returns plain
text in Prometheus exposition format — NOT JSON.

Example output:
  # HELP http_requests_total Total HTTP requests
  # TYPE http_requests_total counter
  http_requests_total{method="GET",endpoint="/health",status_code="200"} 1432.0
  http_requests_total{method="POST",endpoint="/login",status_code="401"} 17.0

Prometheus parses this text, stores each line as a time-series data
point, and makes it queryable via PromQL (Prometheus Query Language).

SECURITY NOTE: In production, restrict access to /metrics (e.g., only
allow the Prometheus server's IP, or put it on a separate internal port).
Metric data can reveal internal architecture, request rates, and error
patterns.  For this educational project, we leave it open.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["observability"])


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Expose all Prometheus metrics in text exposition format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
