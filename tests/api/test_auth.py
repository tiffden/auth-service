from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient


def test_auth_token_rejects_bad_creds(client: TestClient) -> None:
    resp = client.post(
        "/auth/token",
        data={"username": "tee", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


def test_auth_token_accepts_good_creds_and_returns_token_and_expiry(
    client: TestClient,
) -> None:
    resp = client.post(
        "/auth/token",
        data={"username": "tee", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"].startswith("user:tee|exp:")
    assert "expires_at" in payload
    expires_at = datetime.fromisoformat(payload["expires_at"])
    assert expires_at.tzinfo in (UTC, None)
