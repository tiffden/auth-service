from __future__ import annotations

from fastapi.testclient import TestClient

# ---- 404: undefined routes ----


def test_undefined_route_returns_404(client: TestClient) -> None:
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}


def test_undefined_nested_route_returns_404(client: TestClient) -> None:
    resp = client.get("/api/v2/users")
    assert resp.status_code == 404


# ---- 405: wrong HTTP method on existing routes ----


def test_delete_users_returns_405(client: TestClient, token: str) -> None:
    resp = client.delete("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 405


def test_put_health_returns_405(client: TestClient) -> None:
    resp = client.put("/health", json={"status": "bad"})
    assert resp.status_code == 405


def test_get_oauth_token_returns_405(client: TestClient) -> None:
    resp = client.get("/oauth/token")
    assert resp.status_code == 405
