"""Table-driven RBAC tests.

Each row describes: endpoint, method, role(s), expected HTTP status.
This ensures the Principal + require_role/require_any_role guards
behave correctly across all protected endpoints.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import mint_token


# Helper: build auth header (or empty dict for unauthenticated)
def _auth(token: str | None) -> dict[str, str]:
    if token is None:
        return {}
    return {"Authorization": f"Bearer {token}"}


# Tokens for each role, created once per module
@pytest.fixture
def user_token() -> str:
    return mint_token(username="role-user", roles=["user"])


@pytest.fixture
def admin_token_local() -> str:
    return mint_token(username="role-admin", roles=["admin"])


# ---- Table-driven access-control tests ----

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
    token = mint_token(roles=[role]) if role else None
    headers = _auth(token)

    if method == "GET":
        resp = client.get(endpoint, headers=headers)
    elif method == "POST":
        body = {"email": "rbac-test@example.com"} if "/users" in endpoint else {}
        resp = client.post(endpoint, json=body, headers=headers)
    else:
        pytest.fail(f"Unsupported method: {method}")

    assert resp.status_code == expected, (
        f"{method} {endpoint} role={role}: expected {expected}, got {resp.status_code}"
    )
