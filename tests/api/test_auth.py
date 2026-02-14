"""Token validation tests — exercise the require_user() dependency.

These test that malformed, expired, and tampered tokens are rejected,
and valid tokens pass through. The token format is the HMAC stub used
across oauth.py and conftest.mint_token().
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.conftest import mint_token

# ---- invalid / missing token cases ----


def test_rejects_garbage_token(client: TestClient) -> None:
    resp = client.get("/users", headers={"Authorization": "Bearer total-garbage"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Malformed token"


def test_rejects_empty_bearer(client: TestClient) -> None:
    resp = client.get("/users", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


def test_rejects_expired_token(client: TestClient) -> None:
    expired = mint_token(ttl_min=-1)
    resp = client.get("/users", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token expired"


def test_rejects_tampered_signature(client: TestClient) -> None:
    exp_ts = int((datetime.now(UTC) + timedelta(minutes=30)).timestamp())
    token_core = f"user:tee|exp:{exp_ts}"
    tampered_token = f"{token_core}|sig:{'a' * 64}"

    resp = client.get(
        "/users",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token signature"


def test_rejects_tampered_username(client: TestClient, token: str) -> None:
    tampered = token.replace("user:test-user|", "user:evil|", 1)
    resp = client.get("/users", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token signature"


# ---- logging assertions ----


def test_expired_token_logs_warning(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    expired = mint_token(ttl_min=-1)
    with caplog.at_level(logging.WARNING, logger="app.api.dependencies"):
        client.get(
            "/users",
            headers={"Authorization": f"Bearer {expired}"},
        )
    assert any("Expired token" in m for m in caplog.messages)


def test_tampered_signature_logs_warning(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    exp_ts = int((datetime.now(UTC) + timedelta(minutes=30)).timestamp())
    token_core = f"user:tee|exp:{exp_ts}"
    tampered_token = f"{token_core}|sig:{'a' * 64}"

    with caplog.at_level(logging.WARNING, logger="app.api.dependencies"):
        client.get(
            "/users",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )
    assert any("Invalid signature" in m for m in caplog.messages)


def test_malformed_token_logs_warning(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.api.dependencies"):
        client.get(
            "/users",
            headers={"Authorization": "Bearer total-garbage"},
        )
    assert any("Malformed token" in m for m in caplog.messages)


def test_valid_token_logs_debug(
    client: TestClient, token: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="app.api.dependencies"):
        client.get(
            "/users",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert any("Token validated" in m for m in caplog.messages)
