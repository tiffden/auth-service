"""Table-driven RBAC tests.

Each row describes: endpoint, method, role(s), expected HTTP status.
This ensures the Principal + require_role/require_any_role guards
behave correctly across all protected endpoints.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.login import user_repo
from app.models.user import User
from tests.conftest import mint_token


# Helper: build auth header (or empty dict for unauthenticated)
def _auth(token: str | None) -> dict[str, str]:
    if token is None:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _ensure_user(role: str) -> str:
    """Create a user in the repo and return a token with the given role.

    Endpoints like /auth/me need a real user in the repo, so we seed one.
    """
    user = User.new(email=f"rbac-{role}-{uuid4().hex[:6]}@test.com", password_hash="x")
    user_repo.add(user)
    return mint_token(username=str(user.id), roles=[role])


# ---- Table-driven access-control tests ----

# Endpoints that need a real user seeded in the repo (sub must be a valid UUID
# that exists in user_repo).
_NEEDS_REAL_USER = {"/auth/me", "/v1/orgs"}

_RBAC_CASES = [
    # (endpoint, method, role, expected_status)
    # /resource/me — any authenticated user
    ("/resource/me", "GET", "user", 200),
    ("/resource/me", "GET", "admin", 200),
    ("/resource/me", "GET", None, 401),
    # /admin/users — admin only
    ("/admin/users", "GET", "admin", 200),
    ("/admin/users", "GET", "user", 403),
    ("/admin/users", "GET", None, 401),
    # /users — admin only (GET)
    ("/users", "GET", "admin", 200),
    ("/users", "GET", "user", 403),
    ("/users", "GET", None, 401),
    # /users — admin only (POST)
    ("/users", "POST", "admin", 201),
    ("/users", "POST", "user", 403),
    ("/users", "POST", None, 401),
    # /auth/me — any authenticated user (needs real user in repo)
    ("/auth/me", "GET", "user", 200),
    ("/auth/me", "GET", "admin", 200),
    ("/auth/me", "GET", None, 401),
    # POST /v1/orgs — any authenticated user
    ("/v1/orgs", "POST", "user", 201),
    ("/v1/orgs", "POST", "admin", 201),
    ("/v1/orgs", "POST", None, 401),
]


def _case_id(case: tuple) -> str:
    endpoint, method, role, expected = case
    role_label = role or "anon"
    return f"{method} {endpoint} [{role_label}] -> {expected}"


@pytest.mark.parametrize(
    "endpoint,method,role,expected",
    _RBAC_CASES,
    ids=[_case_id(c) for c in _RBAC_CASES],
)
def test_rbac(
    client: TestClient,
    endpoint: str,
    method: str,
    role: str | None,
    expected: int,
) -> None:
    if role and endpoint in _NEEDS_REAL_USER:
        token = _ensure_user(role)
    else:
        token = mint_token(roles=[role]) if role else None
    headers = _auth(token)

    if method == "GET":
        resp = client.get(endpoint, headers=headers)
    elif method == "POST":
        if "/users" in endpoint:
            body = {"email": "rbac-test@example.com"}
        elif "/v1/orgs" in endpoint:
            body = {"name": "RBAC Org", "slug": f"rbac-{uuid4().hex[:8]}"}
        else:
            body = {}
        resp = client.post(endpoint, json=body, headers=headers)
    else:
        pytest.fail(f"Unsupported method: {method}")

    assert resp.status_code == expected, (
        f"{method} {endpoint} role={role}: expected {expected}, got {resp.status_code}"
    )
