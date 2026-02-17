"""Request context middleware — assigns a unique ID to every request.

WHY REQUEST IDs
-----------------
When multiple requests run concurrently, log lines interleave:

  INFO  Processing order for user=alice
  INFO  Processing order for user=bob
  ERROR Database timeout
  INFO  Order complete

Which order failed?  Without a request ID, you can't tell.  With one:

  INFO  [req-abc] Processing order for user=alice
  INFO  [req-xyz] Processing order for user=bob
  ERROR [req-abc] Database timeout        ← now it's obvious
  INFO  [req-xyz] Order complete

WHY CONTEXT VARIABLES (NOT THREAD-LOCALS)
-------------------------------------------
FastAPI uses async/await, where multiple requests run concurrently on
the SAME thread.  Thread-local storage (threading.local()) would leak
data between requests because they share a thread.

Python's `contextvars` module was designed for exactly this: per-task
state in async code.  Each async task (request) gets its own copy of
the context variable, even when running on the same thread.

Think of it like a name tag at a conference: even though everyone is
in the same room (thread), each person (request) has their own tag.

REQUEST TIMING
---------------
We also measure how long each request takes.  This is the raw data
that feeds the REQUEST_DURATION histogram in metrics.py and the
"duration_ms" field in structured log output.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Context variable: holds the current request's ID
# ---------------------------------------------------------------------------
# Any code in the async call chain can read this to get the request ID
# without passing it explicitly through every function call.

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestContextFilter(logging.Filter):
    """Logging filter that injects request context into every LogRecord.

    WHY A FILTER (NOT A FORMATTER):
    Formatters can only read fields that already exist on the LogRecord.
    Filters can ADD fields to the record before formatting.  This filter
    reads from the ContextVar and attaches the request_id to every log
    line emitted during this request, regardless of which module logs it.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")  # type: ignore[attr-defined]
        return True


# Install the filter on the root logger so ALL loggers inherit it.
# Guard against duplicate installation across module reloads.
root_logger = logging.getLogger()
if not any(isinstance(f, _RequestContextFilter) for f in root_logger.filters):
    root_logger.addFilter(_RequestContextFilter())


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a request ID, times requests, and logs completion.

    For every incoming request:
    1. Reads X-Request-ID header (if client provided one) or generates a UUID
    2. Stores it in a ContextVar (accessible anywhere in the async chain)
    3. Times the request
    4. Logs a summary line on completion (method, path, status, duration)
    5. Sets X-Request-ID on the response (for client correlation)
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Step 1: Get or generate request ID
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request_id_var.set(req_id)

        # Step 2: Time the request
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        # Step 3: Log a summary line with structured fields
        # These extra fields are picked up by _JsonFormatter when LOG_JSON=true,
        # and are visible in the text formatter as part of the message.
        logger.info(
            "%s %s → %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        # Step 4: Set response header so clients can correlate
        response.headers["X-Request-ID"] = req_id

        return response
