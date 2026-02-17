"""Tests for Prometheus metrics middleware.

NOTE ON TESTING PROMETHEUS METRICS:
The prometheus-client library uses a global default registry.  Counters
can only go up — they cannot be reset between tests.  To avoid test
pollution, we assert on DELTAS: read the value before the action, perform
the action, read the value after, and assert the difference.

This is the standard pattern for testing Prometheus metrics in Python.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY


def _get_sample(name: str, labels: dict | None = None) -> float:
    """Read a metric sample's current value from the global registry."""
    value = REGISTRY.get_sample_value(name, labels=labels or {})
    return value if value is not None else 0.0


def test_request_counter_increments(client: TestClient) -> None:
    """Each HTTP request should increment the request counter."""
    before = _get_sample(
        "http_requests_total",
        {"method": "GET", "endpoint": "/health", "status_code": "200"},
    )
    client.get("/health")
    after = _get_sample(
        "http_requests_total",
        {"method": "GET", "endpoint": "/health", "status_code": "200"},
    )
    assert after - before >= 1


def test_request_duration_histogram_observes(client: TestClient) -> None:
    """Each request should add an observation to the duration histogram."""
    before = _get_sample(
        "http_request_duration_seconds_count",
        {"method": "GET", "endpoint": "/health"},
    )
    client.get("/health")
    after = _get_sample(
        "http_request_duration_seconds_count",
        {"method": "GET", "endpoint": "/health"},
    )
    assert after - before >= 1


def test_metrics_endpoint_returns_prometheus_format(client: TestClient) -> None:
    """GET /metrics should return Prometheus text exposition format."""
    # Make a request first so there's data to report
    client.get("/health")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    # Prometheus text format contains HELP and TYPE lines
    assert "http_requests_total" in resp.text
    assert "http_request_duration_seconds" in resp.text


def test_metrics_endpoint_not_self_instrumented(client: TestClient) -> None:
    """Requests to /metrics itself should not be counted in metrics."""
    before = _get_sample(
        "http_requests_total",
        {"method": "GET", "endpoint": "/metrics", "status_code": "200"},
    )
    client.get("/metrics")
    client.get("/metrics")
    after = _get_sample(
        "http_requests_total",
        {"method": "GET", "endpoint": "/metrics", "status_code": "200"},
    )
    # Should not have incremented (we skip /metrics in the middleware)
    assert after == before
