from __future__ import annotations

from datetime import datetime, timezone

# FastAPI → Starlette → httpx
# pip install "fastapi[standard]"
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _get_token() -> str:
    resp = client.post(
        "/auth/token",
        data={"username": "tee", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "access_token" in payload
    return payload["access_token"]

def test_health_returns_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_auth_token_rejects_bad_creds() -> None:
    resp = client.post(
        "/auth/token",
        data={"username": "tee", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


def test_auth_token_accepts_good_creds_and_returns_token_and_expiry() -> None:
    resp = client.post(
        "/auth/token",
        data={"username": "tee", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["token_type"] == "bearer"  # bearer, common name for authorization
    assert payload["access_token"].startswith("user:tee|exp:")
    assert "expires_at" in payload
    expires_at = datetime.fromisoformat(payload["expires_at"])
    assert expires_at.tzinfo in (timezone.utc, None)


def test_users_rejects_missing_token() -> None:
    resp = client.get("/users")
    assert resp.status_code == 401


def test_users_accepts_valid_token_and_returns_list() -> None:
    token = _get_token()
    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload, list)
    assert payload == [
        {"id": 1, "email": "tee@example.com"},
        {"id": 2, "email": "d-man@example.com"},
    ]
