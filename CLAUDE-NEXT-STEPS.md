# Week 07 - Observability, SLOs & Cloud Operations

Week 7 introduces observability: making the service measurable, monitorable, and operationally ready. Every new file includes educational comments explaining the "three pillars" (logs, metrics, traces), SLI/SLO/SLA concepts, and deployment strategies.

All new code follows existing codebase conventions: frozen dataclasses, module-level singletons, conditional fallbacks, and Depends() closures.

Phase 1: Structured Logging + Request Context
Everything else benefits from structured logs and request IDs.
Action File What
Modify app/core/config.py Add log_json: bool field (from LOG_JSON env var, default False)
Modify app/core/logging.py Add _JsonFormatter alongside existing_ContainerFormatter; update setup_logging(level, json_format)
Create app/middleware/__init__.py Empty package init
Create app/middleware/request_context.py Middleware: generates/echoes X-Request-ID, uses contextvars for async-safe context, logs request timing on completion
Modify app/main.py Add RequestContextMiddleware, pass json_format=SETTINGS.log_json

* Three pillars of observability: logs (what happened, in words), metrics (in numbers), traces (across services)
* Why structured logging: JSON is machine-parseable for ELK/Datadog/CloudWatch; plain text requires fragile regex
* Why contextvars not thread-locals: async code shares threads, contextvars are per-task
* Why request IDs: correlate interleaved concurrent log lines for one request's lifecycle

Phase 2: Prometheus Metrics
Adds quantitative monitoring — counters, gauges, histograms.
Action File What
Modify pyproject.toml Add prometheus-client>=0.20
Create app/core/metrics.py All metric definitions: REQUEST_COUNT (Counter), REQUEST_DURATION (Histogram), ACTIVE_REQUESTS (Gauge), plus app-specific: RATE_LIMIT_HITS, CACHE_OPERATIONS, TOKEN_BLACKLIST_CHECKS, QUEUE_DEPTH
Create app/middleware/metrics.py Middleware: increments counters, observes duration histogram, tracks active requests gauge
Create app/api/metrics_endpoint.py GET /metrics returning Prometheus exposition format
Modify app/main.py Add MetricsMiddleware, include metrics router
Modify app/api/ratelimit.py +2 lines: increment RATE_LIMIT_HITS on 429
Modify app/services/cache.py +2 lines: increment CACHE_OPERATIONS hit/miss in InMemoryCacheService.get()
Modify app/services/token_blacklist.py +2 lines: increment TOKEN_BLACKLIST_CHECKS in InMemoryTokenBlacklist.is_revoked()
Modify app/worker.py +2 lines: update QUEUE_DEPTH gauge after dequeue

* Counter vs Gauge vs Histogram with concrete analogies
* Why percentiles > averages (one slow request hides in the average)
* How Prometheus scraping works (pull model vs push model)
* Why these histogram buckets (5ms to 5s range for API latencies)

Phase 3: SLO Definitions
Defines what "good" means — pure math, no I/O, fully testable.
Action File What
Create app/core/slo.py SLODefinition and SLOStatus frozen dataclasses; three SLOs: availability (99.5%), latency p95 (<500ms), queue processing (95% <10s); pure evaluation functions

* SLI/SLO/SLA explained with pizza delivery analogy
* Error budget concept (0.5% budget = 50 failures per 10,000 requests)
* Why define SLOs in code: testable, version-controlled, can drive runtime alerts

Phase 4: Enhanced Health & Readiness
Action File What
Modify app/api/health.py Restructure to {"status", "checks": {"redis", "database"}, "slos": {...}}; add GET /ready (200 if critical deps reachable, 503 otherwise)

* Liveness vs readiness: liveness = "restart me"; readiness = "stop sending traffic"
* Why separate: alive but temporarily unable to serve → don't restart, just remove from LB

Phase 5: Observability Stack (Docker Compose)
Action File What
Create docker/prometheus.yml Scrape config: api:8000/metrics every 15s
Create docker/grafana/provisioning/datasources/prometheus.yml Auto-provision Prometheus datasource
Create docker/grafana/provisioning/dashboards/dashboard.yml Dashboard provisioning config
Create docker/grafana/dashboards/auth-service-slo.json Pre-built dashboard: request rate, error rate + SLO line, p50/p95/p99 latency, cache hit ratio, queue depth
Modify docker/docker-compose.yml Add prometheus and grafana services

Phase 6: Deployment Strategy & Runbook Documentation
Action File What
Create docs/deployment-strategy.md Blue/green vs canary with diagrams, rollback procedure, SLO-gated promotion
Create docs/alert-runbooks.md Per-SLO runbooks: what fired, why it matters, how to investigate, how to fix, when to escalate
Create docs/slo-dashboard-guide.md Panel-by-panel guide to reading the Grafana dashboard

Phase 7: Tests
Action File What
Create tests/middleware/__init__.py Package init
Create tests/core/test_structured_logging.py JSON formatter: valid JSON, extra fields, exceptions, existing formatter unchanged
Create tests/middleware/test_request_context.py Request ID generated/echoed, response header set, timing logged
Create tests/middleware/test_metrics.py Counter increments (delta assertions), histogram observes, /metrics returns Prometheus format
Create tests/core/test_slo.py Availability healthy/breached/zero-requests; latency; queue processing
Modify tests/api/test_health.py Updated for nested structure + SLO fields + /ready
Modify tests/core/test_config.py Add log_json=False to_make_settings()
Modify tests/conftest.py Document delta-assertion pattern for Prometheus metrics
Note on Prometheus in tests
prometheus-client uses a global registry. Counters can't be reset. Tests assert on deltas: read value before action, act, read value after, assert difference.

Implementation Order

1. Phase 1 — Structured logging + request context (foundation)
2. Phase 2 — Prometheus metrics (quantitative monitoring)
3. Phase 3 — SLO definitions (pure math, no deps)
4. Phase 4 — Enhanced health/readiness (consumes SLO evaluations)
5. Phase 7 — Tests (alongside each phase, consolidated run)
6. Phase 5 — Docker Compose stack (Prometheus + Grafana)
7. Phase 6 — Documentation (deployment strategy, runbooks)

New Files (18)
File Purpose
app/middleware/__init__.py Package init
app/middleware/request_context.py Request ID + timing middleware
app/middleware/metrics.py Prometheus instrumentation middleware
app/core/metrics.py Metric definitions (Counter, Gauge, Histogram)
app/core/slo.py SLO definitions + evaluation functions
app/api/metrics_endpoint.py GET /metrics for Prometheus
docker/prometheus.yml Prometheus scrape config
docker/grafana/provisioning/datasources/prometheus.yml Grafana datasource
docker/grafana/provisioning/dashboards/dashboard.yml Dashboard provisioning
docker/grafana/dashboards/auth-service-slo.json Pre-built SLO dashboard
docs/deployment-strategy.md Blue/green, canary, rollback
docs/alert-runbooks.md Per-SLO investigation runbooks
docs/slo-dashboard-guide.md Dashboard reading guide
tests/middleware/__init__.py Package init
tests/core/test_structured_logging.py JSON formatter tests
tests/middleware/test_request_context.py Request context tests
tests/middleware/test_metrics.py Metrics middleware tests
tests/core/test_slo.py SLO evaluation tests

Modified Files (12)
File Change
app/core/config.py Add log_json: bool field
app/core/logging.py Add_JsonFormatter, update setup_logging()
app/main.py Add 2 middlewares, metrics router, json_format param
app/api/health.py Nested response, SLO status, /ready endpoint
app/api/ratelimit.py Increment rate limit counter
app/services/cache.py Increment cache hit/miss counter
app/services/token_blacklist.py Increment blacklist check counter
app/worker.py Update queue depth gauge
docker/docker-compose.yml Add prometheus + grafana services
pyproject.toml Add prometheus-client dependency
tests/api/test_health.py Updated assertions for new structure
tests/core/test_config.py Add log_json to _make_settings()

Verification

1. python -m pytest tests/ -v — all existing + new tests pass
2. docker compose up — API, Prometheus, Grafana all start
3. <http://localhost:9090/targets> — Prometheus shows API as "UP"
4. <http://localhost:3000> — Grafana dashboard shows live metrics
5. curl localhost:8000/metrics — returns Prometheus text format
6. curl localhost:8000/health — returns nested structure with SLO status
7. curl localhost:8000/ready — returns 200
