from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.auth import TOKEN_SIGNING_SECRET


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


# ---- invalid / missing token cases ----


def test_protected_endpoint_rejects_garbage_token(client: TestClient) -> None:
    resp = client.get("/users", headers={"Authorization": "Bearer total-garbage"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Malformed token"


def test_protected_endpoint_rejects_empty_bearer(client: TestClient) -> None:
    resp = client.get("/users", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


def test_protected_endpoint_rejects_expired_token(client: TestClient) -> None:
    exp_ts = int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())
    token_core = f"user:tee|exp:{exp_ts}"
    sig = hmac.new(
        TOKEN_SIGNING_SECRET.encode(),
        token_core.encode(),
        hashlib.sha256,
    ).hexdigest()
    expired_token = f"{token_core}|sig:{sig}"

    resp = client.get("/users", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token expired"


def test_protected_endpoint_rejects_tampered_signature(client: TestClient) -> None:
    exp_ts = int((datetime.now(UTC) + timedelta(minutes=30)).timestamp())
    token_core = f"user:tee|exp:{exp_ts}"
    tampered_token = f"{token_core}|sig:{'a' * 64}"

    resp = client.get("/users", headers={"Authorization": f"Bearer {tampered_token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token signature"


def test_protected_endpoint_rejects_tampered_username(
    client: TestClient, token: str
) -> None:
    # Swap "tee" for "evil" while keeping the original signature.
    tampered = token.replace("user:tee|", "user:evil|", 1)
    resp = client.get("/users", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token signature"


# ---- 401: credential variants ----


def test_auth_token_rejects_wrong_username(client: TestClient) -> None:
    resp = client.post(
        "/auth/token",
        data={"username": "nobody", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


# ---- 422: malformed login requests ----


def test_auth_token_rejects_missing_body(client: TestClient) -> None:
    resp = client.post("/auth/token")
    assert resp.status_code == 422


def test_auth_token_rejects_missing_password(client: TestClient) -> None:
    resp = client.post(
        "/auth/token",
        data={"username": "tee"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 422


def test_auth_token_rejects_missing_username(client: TestClient) -> None:
    resp = client.post(
        "/auth/token",
        data={"password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 422


# ---- logging assertions ----


def test_failed_login_logs_warning(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.api.auth"):
        client.post(
            "/auth/token",
            data={"username": "hacker", "password": "wrong"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert any("Login failed" in m and "hacker" in m for m in caplog.messages)


def test_successful_login_logs_info(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.api.auth"):
        client.post(
            "/auth/token",
            data={"username": "tee", "password": "password"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert any("Token issued" in m and "tee" in m for m in caplog.messages)


def test_expired_token_logs_warning(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    exp_ts = int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())
    token_core = f"user:tee|exp:{exp_ts}"
    sig = hmac.new(
        TOKEN_SIGNING_SECRET.encode(),
        token_core.encode(),
        hashlib.sha256,
    ).hexdigest()
    expired_token = f"{token_core}|sig:{sig}"

    with caplog.at_level(logging.WARNING, logger="app.api.auth"):
        client.get("/users", headers={"Authorization": f"Bearer {expired_token}"})
    assert any("Expired token" in m for m in caplog.messages)


def test_tampered_signature_logs_warning(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    exp_ts = int((datetime.now(UTC) + timedelta(minutes=30)).timestamp())
    token_core = f"user:tee|exp:{exp_ts}"
    tampered_token = f"{token_core}|sig:{'a' * 64}"

    with caplog.at_level(logging.WARNING, logger="app.api.auth"):
        client.get("/users", headers={"Authorization": f"Bearer {tampered_token}"})
    assert any("Invalid signature" in m for m in caplog.messages)


def test_malformed_token_logs_warning(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.api.auth"):
        client.get("/users", headers={"Authorization": "Bearer total-garbage"})
    assert any("Malformed token" in m for m in caplog.messages)


def test_valid_token_logs_debug(
    client: TestClient, token: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="app.api.auth"):
        client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert any("Token validated" in m for m in caplog.messages)
