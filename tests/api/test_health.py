from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    # In tests, Redis is not configured — should report as such
    assert data["checks"]["redis"] == "not_configured"


def test_health_includes_slo_status(client: TestClient) -> None:
    resp = client.get("/health")
    data = resp.json()
    assert "slos" in data
    # All three SLOs should be present
    assert "availability" in data["slos"]
    assert "latency_p95" in data["slos"]
    assert "queue_processing" in data["slos"]
    # Each SLO has current, target, healthy fields
    for slo_name in ("availability", "latency_p95", "queue_processing"):
        slo = data["slos"][slo_name]
        assert "current" in slo
        assert "target" in slo
        assert "healthy" in slo


def test_ready_returns_200(client: TestClient) -> None:
    resp = client.get("/ready")
    assert resp.status_code == 200
