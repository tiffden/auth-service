"""Refresh token endpoint tests.

Covers the refresh token lifecycle:
1. Login/register return a refresh token alongside the access token
2. POST /auth/refresh exchanges refresh token for new token pair
3. Old refresh token is rejected after use (rotation)
4. Expired/invalid refresh tokens are rejected
5. Access token cannot be used as refresh token (audience mismatch)
6. Inactive users cannot refresh
7. Logout with refresh token invalidates it
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from fastapi.testclient import TestClient

from app.api import login as login_module
from app.models.user import User
from app.services import auth_service, token_service

TEST_EMAIL = "refresh@example.com"
TEST_PASSWORD = "securepass123"


def _reset_and_seed(client: TestClient) -> None:
    """Clear user repo and seed a fresh test user."""
    login_module.user_repo._by_email.clear()
    login_module.user_repo._by_id.clear()
    login_module.user_repo.add(
        User.new(
            email=TEST_EMAIL,
            password_hash=auth_service.hash_password(TEST_PASSWORD),
            name="Refresh User",
        )
    )


def _register(client: TestClient, email: str = "new-refresh@example.com") -> dict:
    """Register a user via /auth/register and return the response dict."""
    resp = client.post(
        "/auth/register",
        json={
            "name": "New User",
            "email": email,
            "password": TEST_PASSWORD,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _login(client: TestClient) -> dict:
    """Login via /auth/login and return the response dict."""
    resp = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# Login/register include refresh token
# ---------------------------------------------------------------------------


def test_login_returns_refresh_token(client: TestClient) -> None:
    """POST /auth/login response now includes refreshToken."""
    _reset_and_seed(client)
    data = _login(client)
    assert "refreshToken" in data
    assert data["refreshToken"] != data["accessToken"]


def test_register_returns_refresh_token(client: TestClient) -> None:
    """POST /auth/register response includes refreshToken."""
    data = _register(client)
    assert "refreshToken" in data
    assert data["refreshToken"] != data["accessToken"]


# ---------------------------------------------------------------------------
# POST /auth/refresh — happy path
# ---------------------------------------------------------------------------


def test_refresh_returns_new_tokens(client: TestClient) -> None:
    """Valid refresh token → new access + refresh token pair."""
    _reset_and_seed(client)
    data = _login(client)

    resp = client.post(
        "/auth/refresh",
        json={
            "refreshToken": data["refreshToken"],
        },
    )
    assert resp.status_code == 200
    new_data = resp.json()
    assert "accessToken" in new_data
    assert "refreshToken" in new_data
    assert "user" in new_data
    # New tokens are different from old ones
    assert new_data["accessToken"] != data["accessToken"]
    assert new_data["refreshToken"] != data["refreshToken"]


def test_refresh_returns_user_info(client: TestClient) -> None:
    """Refresh response includes correct user info."""
    _reset_and_seed(client)
    data = _login(client)

    resp = client.post(
        "/auth/refresh",
        json={
            "refreshToken": data["refreshToken"],
        },
    )
    user = resp.json()["user"]
    assert user["email"] == TEST_EMAIL
    assert user["id"] == data["user"]["id"]


def test_new_access_token_works_on_protected_routes(client: TestClient) -> None:
    """The new access token from refresh is usable on protected endpoints."""
    _reset_and_seed(client)
    data = _login(client)

    resp = client.post(
        "/auth/refresh",
        json={
            "refreshToken": data["refreshToken"],
        },
    )
    new_access = resp.json()["accessToken"]

    resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Rotation — old refresh token rejected after use
# ---------------------------------------------------------------------------


def test_old_refresh_token_rejected_after_use(client: TestClient) -> None:
    """Used refresh token is blacklisted (rotation)."""
    _reset_and_seed(client)
    data = _login(client)
    old_refresh = data["refreshToken"]

    # Use it once — should succeed
    resp = client.post("/auth/refresh", json={"refreshToken": old_refresh})
    assert resp.status_code == 200

    # Use it again — should fail (already rotated/blacklisted)
    resp = client.post("/auth/refresh", json={"refreshToken": old_refresh})
    assert resp.status_code == 401
    assert "revoked" in resp.json()["detail"].lower()


def test_chained_refresh_works(client: TestClient) -> None:
    """Can refresh multiple times using each new refresh token."""
    _reset_and_seed(client)
    data = _login(client)

    # Chain: R1 → R2 → R3
    for _ in range(3):
        resp = client.post(
            "/auth/refresh",
            json={
                "refreshToken": data["refreshToken"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_refresh_with_expired_token(client: TestClient) -> None:
    """Expired refresh token → 401."""
    now = datetime.now(UTC)
    payload = {
        "sub": "some-user-id",
        "iss": token_service.ISSUER,
        "aud": token_service.REFRESH_AUDIENCE,
        "exp": now - timedelta(minutes=1),
        "iat": now - timedelta(days=8),
        "jti": str(uuid.uuid4()),
    }
    expired = pyjwt.encode(payload, token_service._private_key, algorithm="ES256")
    resp = client.post("/auth/refresh", json={"refreshToken": expired})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_refresh_with_garbage_token(client: TestClient) -> None:
    """Garbage string → 401."""
    resp = client.post("/auth/refresh", json={"refreshToken": "not.a.jwt"})
    assert resp.status_code == 401


def test_refresh_with_access_token_rejected(client: TestClient) -> None:
    """An access token (wrong audience) must not work as a refresh token."""
    _reset_and_seed(client)
    data = _login(client)
    resp = client.post(
        "/auth/refresh",
        json={
            "refreshToken": data["accessToken"],
        },
    )
    assert resp.status_code == 401


def test_refresh_for_inactive_user(client: TestClient) -> None:
    """Deactivated user cannot refresh."""
    _reset_and_seed(client)
    data = _login(client)

    # Deactivate the user
    from uuid import UUID

    login_module.user_repo.set_active(UUID(data["user"]["id"]), False)

    resp = client.post(
        "/auth/refresh",
        json={
            "refreshToken": data["refreshToken"],
        },
    )
    assert resp.status_code == 401
    assert "inactive" in resp.json()["detail"].lower()


def test_refresh_for_nonexistent_user(client: TestClient) -> None:
    """Refresh token for a deleted user → 401."""
    # Mint a refresh token for a user that doesn't exist in the repo
    fake_id = str(uuid.uuid4())
    refresh = token_service.create_refresh_token(sub=fake_id)

    resp = client.post("/auth/refresh", json={"refreshToken": refresh})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout revokes refresh token
# ---------------------------------------------------------------------------


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    """Logout with refreshToken in body blacklists it."""
    _reset_and_seed(client)
    data = _login(client)

    # Logout, including the refresh token
    resp = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {data['accessToken']}"},
        json={"refreshToken": data["refreshToken"]},
    )
    assert resp.status_code == 204

    # Try to use the refresh token — should be revoked
    resp = client.post(
        "/auth/refresh",
        json={
            "refreshToken": data["refreshToken"],
        },
    )
    assert resp.status_code == 401


def test_logout_without_refresh_token_still_works(client: TestClient) -> None:
    """Backward compat: logout without body still returns 204."""
    _reset_and_seed(client)
    data = _login(client)

    resp = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {data['accessToken']}"},
    )
    assert resp.status_code == 204
