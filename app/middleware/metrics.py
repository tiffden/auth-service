"""Prometheus metrics middleware — instruments every HTTP request.

For each request, this middleware:
  1. Increments the ACTIVE_REQUESTS gauge (decrement on completion)
  2. Times the request duration
  3. On completion: increments REQUEST_COUNT (by method/endpoint/status)
     and observes the duration in REQUEST_DURATION histogram

MIDDLEWARE vs DECORATOR vs MANUAL
-----------------------------------
We COULD instrument each endpoint manually:

  @router.get("/users")
  async def list_users():
      start = time.monotonic()
      try:
          ...
      finally:
          REQUEST_DURATION.observe(time.monotonic() - start)
          REQUEST_COUNT.inc()

But that's repetitive and error-prone (forget one endpoint = blind spot).
A middleware instruments EVERY endpoint automatically — including ones
added by other developers who might not remember to add metrics.

The trade-off: middleware can't easily access route-specific parameters
(like the route name).  We use the URL path as the endpoint label,
which works well enough for dashboards and is universally available.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import ACTIVE_REQUESTS, REQUEST_COUNT, REQUEST_DURATION


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect Prometheus metrics for every HTTP request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip instrumenting the /metrics endpoint itself to avoid
        # Prometheus scrapes inflating the request count.
        if request.url.path == "/metrics":
            return await call_next(request)

        ACTIVE_REQUESTS.inc()
        start = time.monotonic()
        status_code: str | None = None

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            # If the handler raises an unhandled exception, Starlette
            # returns a 500.  We still want to record that.
            status_code = "500"
            raise
        finally:
            duration = time.monotonic() - start
            ACTIVE_REQUESTS.dec()
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=status_code if status_code is not None else "500",
            ).inc()
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path,
            ).observe(duration)

        return response
