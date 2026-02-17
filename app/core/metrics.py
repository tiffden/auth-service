"""Application metrics using the Prometheus client library.

This module defines all metrics in one place — a single inventory of
everything the service measures.  Other modules import specific metrics
and increment/observe them at the point of action.

THE THREE METRIC TYPES
------------------------

1. COUNTER — a number that only goes UP (never decreases).
   Example: total HTTP requests served.  If you've served 1,000,000
   requests, that number never drops.

   Useful for RATES: "requests per second" = delta(counter) / delta(time).
   Prometheus computes this with the rate() function:
     rate(http_requests_total[5m]) → average requests/sec over 5 minutes.

2. GAUGE — a number that goes UP and DOWN.
   Example: in-flight HTTP requests right now.  One moment it's 47,
   the next it's 12.  A gauge is a snapshot of current state.

   Useful for SATURATION: "how full is this resource?"
   If active_requests is near your thread/connection limit, you're overloaded.

3. HISTOGRAM — groups observations into "buckets" by value.
   Example: request durations with buckets [10ms, 50ms, 100ms, 500ms, 1s].
   Each request's duration falls into a bucket.  From the bucket counts,
   Prometheus can calculate percentiles (p50, p95, p99).

   WHY PERCENTILES > AVERAGES:
   Average latency hides problems.  If 99 requests take 10ms and 1 request
   takes 10 SECONDS, the average is 109ms — looks fine.  But the p99 is
   10s — that's 1% of users having a terrible experience.

   histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
   → "99% of requests completed in under X seconds"

HOW PROMETHEUS SCRAPING WORKS
-------------------------------
Unlike push-based systems (StatsD, CloudWatch agent), Prometheus PULLS
metrics from your app.  Every 15 seconds (configurable), Prometheus
sends a GET to /metrics.  Your app responds with a text dump of all
current metric values.

This "pull" model has advantages:
  - Prometheus controls the load (your app doesn't flood the monitor)
  - If your app is down, Prometheus notices immediately (scrape fails)
  - Adding a new service to monitor = one line in Prometheus config
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# HTTP metrics (populated by the MetricsMiddleware)
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests by method, endpoint, and status code",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    # Buckets chosen for typical API latencies:
    #   5ms   — cache hits, health checks
    #   10ms  — simple DB queries
    #   25ms  — complex queries
    #   50ms  — multiple queries or Redis round-trips
    #   100ms — typical API response
    #   250ms — slow but acceptable
    #   500ms — our p95 SLO target
    #   1s+   — something is wrong
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

ACTIVE_REQUESTS = Gauge(
    "http_active_requests",
    "Number of HTTP requests currently being processed",
)

# ---------------------------------------------------------------------------
# Application-specific metrics
# ---------------------------------------------------------------------------
# These are incremented in the specific modules that own the behavior.
# Defining them here keeps the metric inventory in one place.

RATE_LIMIT_HITS = Counter(
    "rate_limit_hits_total",
    "Requests rejected by rate limiting (429s)",
    ["key_type"],  # "user" or "ip" — shows if limits are hitting authed or anon users
)

CACHE_OPERATIONS = Counter(
    "cache_operations_total",
    "Cache get operations by result",
    ["operation"],  # "hit" or "miss"
)

TOKEN_BLACKLIST_CHECKS = Counter(
    "token_blacklist_checks_total",
    "Token blacklist lookups by result",
    ["result"],  # "revoked" or "valid"
)

QUEUE_DEPTH = Gauge(
    "task_queue_depth",
    "Number of tasks waiting in a queue",
    ["queue_name"],  # "credential_issuance", "grading"
)
