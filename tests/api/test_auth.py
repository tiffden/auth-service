"""Token validation tests — exercise the require_user() dependency.

These test that garbage, expired, and tampered JWT tokens are rejected,
and valid ES256 tokens pass through.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.services import token_service

# ---- invalid / missing token cases ----


def test_rejects_garbage_token(client: TestClient) -> None:
    resp = client.get("/users", headers={"Authorization": "Bearer total-garbage"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


def test_rejects_empty_bearer(client: TestClient) -> None:
    resp = client.get("/users", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


def test_rejects_expired_token(client: TestClient) -> None:
    """Mint a JWT that expired 1 minute ago."""
    now = datetime.now(UTC)
    payload = {
        "sub": "test-user",
        "iss": token_service.ISSUER,
        "aud": token_service.AUDIENCE,
        "exp": now - timedelta(minutes=1),
        "iat": now - timedelta(minutes=2),
        "jti": str(uuid.uuid4()),
        "scope": "",
        "roles": ["user"],
    }
    expired = pyjwt.encode(payload, token_service._private_key, algorithm="ES256")
    resp = client.get("/users", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token expired"


def test_rejects_tampered_payload(client: TestClient, token: str) -> None:
    """Modify the payload segment of a valid JWT — signature won't match."""
    # A JWT has 3 base64 segments: header.payload.signature
    # Swapping a character in the payload corrupts it.
    parts = token.split(".")
    parts[1] = parts[1][::-1]  # reverse the payload
    tampered = ".".join(parts)
    resp = client.get(
        "/users",
        headers={"Authorization": f"Bearer {tampered}"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


def test_rejects_wrong_issuer(client: TestClient) -> None:
    """JWT signed with our key but wrong issuer claim."""
    now = datetime.now(UTC)
    payload = {
        "sub": "test-user",
        "iss": "evil-service",
        "aud": token_service.AUDIENCE,
        "exp": now + timedelta(minutes=15),
        "iat": now,
        "jti": str(uuid.uuid4()),
        "scope": "",
        "roles": ["user"],
    }
    bad_iss = pyjwt.encode(payload, token_service._private_key, algorithm="ES256")
    resp = client.get("/users", headers={"Authorization": f"Bearer {bad_iss}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


def test_rejects_wrong_audience(client: TestClient) -> None:
    """JWT signed with our key but wrong audience claim."""
    now = datetime.now(UTC)
    payload = {
        "sub": "test-user",
        "iss": token_service.ISSUER,
        "aud": "wrong-service",
        "exp": now + timedelta(minutes=15),
        "iat": now,
        "jti": str(uuid.uuid4()),
        "scope": "",
        "roles": ["user"],
    }
    bad_aud = pyjwt.encode(payload, token_service._private_key, algorithm="ES256")
    resp = client.get("/users", headers={"Authorization": f"Bearer {bad_aud}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


# ---- logging assertions ----


def test_expired_token_logs_warning(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "test-user",
        "iss": token_service.ISSUER,
        "aud": token_service.AUDIENCE,
        "exp": now - timedelta(minutes=1),
        "iat": now - timedelta(minutes=2),
        "jti": str(uuid.uuid4()),
        "scope": "",
        "roles": ["user"],
    }
    expired = pyjwt.encode(payload, token_service._private_key, algorithm="ES256")
    with caplog.at_level(logging.WARNING, logger="app.api.dependencies"):
        client.get(
            "/users",
            headers={"Authorization": f"Bearer {expired}"},
        )
    assert any("Expired token" in m for m in caplog.messages)


def test_invalid_token_logs_warning(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.api.dependencies"):
        client.get(
            "/users",
            headers={"Authorization": "Bearer total-garbage"},
        )
    assert any("Invalid token" in m for m in caplog.messages)


def test_valid_token_logs_debug(
    client: TestClient, token: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="app.api.dependencies"):
        client.get(
            "/users",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert any("Token validated" in m for m in caplog.messages)
