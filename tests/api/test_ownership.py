"""Ownership-based access control tests.

Validates that:
- Users can view/edit their own profile
- Platform admins can view/edit any profile
- Regular users cannot view/edit other users' profiles
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.login import user_repo
from app.models.user import User
from tests.conftest import mint_token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user(name: str = "Test User") -> User:
    """Create a user in the repo and return it."""
    user = User.new(email=f"{uuid4()}@example.com", password_hash="hash", name=name)
    user_repo.add(user)
    return user


# --- GET /auth/me ---


def test_get_own_profile(client: TestClient) -> None:
    user = _create_user("Alice")
    token = mint_token(username=str(user.id), roles=["user"])

    resp = client.get("/auth/me", headers=_auth(token))
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == str(user.id)
    assert data["email"] == user.email
    assert data["name"] == "Alice"


def test_get_profile_unauthenticated(client: TestClient) -> None:
    resp = client.get("/auth/me")
    assert resp.status_code == 401


# --- PATCH /users/{user_id} ---


_OWNERSHIP_CASES = [
    # (acting_as, target, expected_status)
    ("self", "self", 200),
    ("admin", "other", 200),
    ("user", "other", 403),
]


@pytest.mark.parametrize(
    "acting_as,target,expected",
    _OWNERSHIP_CASES,
    ids=[f"{a} editing {t} -> {e}" for a, t, e in _OWNERSHIP_CASES],
)
def test_patch_profile_ownership(
    client: TestClient,
    acting_as: str,
    target: str,
    expected: int,
) -> None:
    owner = _create_user("Owner")
    other = _create_user("Other")

    if acting_as == "self":
        token = mint_token(username=str(owner.id), roles=["user"])
        target_id = owner.id
    elif acting_as == "admin":
        token = mint_token(username=str(uuid4()), roles=["admin"])
        target_id = other.id
    else:  # "user"
        token = mint_token(username=str(owner.id), roles=["user"])
        target_id = other.id

    resp = client.patch(
        f"/users/{target_id}",
        json={"name": "Updated"},
        headers=_auth(token),
    )
    assert resp.status_code == expected, (
        f"acting_as={acting_as} target={target}: expected {expected}, "
        f"got {resp.status_code}"
    )

    if expected == 200:
        assert resp.json()["name"] == "Updated"


def test_patch_profile_empty_name_rejected(client: TestClient) -> None:
    user = _create_user("Valid")
    token = mint_token(username=str(user.id), roles=["user"])

    resp = client.patch(
        f"/users/{user.id}",
        json={"name": "   "},
        headers=_auth(token),
    )
    assert resp.status_code == 422


def test_patch_nonexistent_user_returns_404(client: TestClient) -> None:
    fake_id = uuid4()
    token = mint_token(username=str(fake_id), roles=["user"])

    resp = client.patch(
        f"/users/{fake_id}",
        json={"name": "Ghost"},
        headers=_auth(token),
    )
    assert resp.status_code == 404
