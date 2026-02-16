"""Table-driven org-scoped RBAC tests.

Each row describes: endpoint pattern, method, org_role, expected HTTP status.
Tests ensure that org-scoped guards (resolve_org_principal, require_org_role,
require_any_org_role) behave correctly across all org management endpoints.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import add_test_member, create_test_org, mint_token


def _auth(token: str | None) -> dict[str, str]:
    if token is None:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _setup_org_with_roles() -> tuple[str, dict[str, str]]:
    """Create an org and users with every org role. Return (org_id, role->token map)."""
    org = create_test_org("rbac-org")
    org_id = str(org.id)

    tokens: dict[str, str] = {}
    for role in ("owner", "admin", "instructor", "learner"):
        user_id = uuid4()
        add_test_member(org.id, user_id, role)
        tokens[role] = mint_token(username=str(user_id), roles=["user"])

    # non-member: valid user but no membership in this org
    tokens["non_member"] = mint_token(username=str(uuid4()), roles=["user"])

    # platform admin: not a member but has admin platform role
    tokens["platform_admin"] = mint_token(username=str(uuid4()), roles=["admin"])

    return org_id, tokens


# (endpoint_template, method, role_key, expected_status, body_factory)
_ORG_RBAC_CASES: list[tuple[str, str, str | None, int, dict | None]] = [
    # GET /v1/orgs/{org_id} — any member
    ("/v1/orgs/{org_id}", "GET", "owner", 200, None),
    ("/v1/orgs/{org_id}", "GET", "admin", 200, None),
    ("/v1/orgs/{org_id}", "GET", "instructor", 200, None),
    ("/v1/orgs/{org_id}", "GET", "learner", 200, None),
    ("/v1/orgs/{org_id}", "GET", "platform_admin", 200, None),
    ("/v1/orgs/{org_id}", "GET", "non_member", 403, None),
    ("/v1/orgs/{org_id}", "GET", None, 401, None),
    # GET /v1/orgs/{org_id}/members — owner/admin/instructor
    ("/v1/orgs/{org_id}/members", "GET", "owner", 200, None),
    ("/v1/orgs/{org_id}/members", "GET", "admin", 200, None),
    ("/v1/orgs/{org_id}/members", "GET", "instructor", 200, None),
    ("/v1/orgs/{org_id}/members", "GET", "learner", 403, None),
    ("/v1/orgs/{org_id}/members", "GET", "platform_admin", 200, None),
    ("/v1/orgs/{org_id}/members", "GET", "non_member", 403, None),
    ("/v1/orgs/{org_id}/members", "GET", None, 401, None),
    # POST /v1/orgs/{org_id}/members — owner/admin only
    ("/v1/orgs/{org_id}/members", "POST", "owner", 201, None),
    ("/v1/orgs/{org_id}/members", "POST", "admin", 201, None),
    ("/v1/orgs/{org_id}/members", "POST", "instructor", 403, None),
    ("/v1/orgs/{org_id}/members", "POST", "learner", 403, None),
    ("/v1/orgs/{org_id}/members", "POST", "platform_admin", 201, None),
    ("/v1/orgs/{org_id}/members", "POST", "non_member", 403, None),
    ("/v1/orgs/{org_id}/members", "POST", None, 401, None),
]


def _case_id(case: tuple) -> str:
    endpoint, method, role, expected, _ = case
    role_label = role or "anon"
    return f"{method} {endpoint} [{role_label}] -> {expected}"


@pytest.mark.parametrize(
    "endpoint_tpl,method,role_key,expected,body",
    _ORG_RBAC_CASES,
    ids=[_case_id(c) for c in _ORG_RBAC_CASES],
)
def test_org_rbac(
    client: TestClient,
    endpoint_tpl: str,
    method: str,
    role_key: str | None,
    expected: int,
    body: dict | None,
) -> None:
    org_id, tokens = _setup_org_with_roles()
    endpoint = endpoint_tpl.format(org_id=org_id)
    token = tokens.get(role_key) if role_key else None
    headers = _auth(token)

    if method == "GET":
        resp = client.get(endpoint, headers=headers)
    elif method == "POST":
        # Generate unique user_id for each add-member call to avoid 409
        post_body = body or {"user_id": str(uuid4()), "org_role": "learner"}
        resp = client.post(endpoint, json=post_body, headers=headers)
    else:
        pytest.fail(f"Unsupported method: {method}")

    assert resp.status_code == expected, (
        f"{method} {endpoint} role={role_key}: "
        f"expected {expected}, got {resp.status_code}"
        f"\n  body: {resp.json()}"
    )


# --- Role change tests (PATCH) — owner only ---


def test_only_owner_can_change_role(client: TestClient) -> None:
    org = create_test_org("role-change-org")
    owner_id = uuid4()
    target_id = uuid4()
    admin_id = uuid4()

    add_test_member(org.id, owner_id, "owner")
    add_test_member(org.id, target_id, "learner")
    add_test_member(org.id, admin_id, "admin")

    owner_token = mint_token(username=str(owner_id), roles=["user"])
    admin_token = mint_token(username=str(admin_id), roles=["user"])

    url = f"/v1/orgs/{org.id}/members/{target_id}"
    body = {"org_role": "instructor"}

    # Admin cannot change roles
    resp = client.patch(url, json=body, headers=_auth(admin_token))
    assert resp.status_code == 403

    # Owner can change roles
    resp = client.patch(url, json=body, headers=_auth(owner_token))
    assert resp.status_code == 200
    assert resp.json()["org_role"] == "instructor"


# --- Remove member tests ---


def test_owner_can_remove_member(client: TestClient) -> None:
    org = create_test_org("remove-org")
    owner_id = uuid4()
    target_id = uuid4()

    add_test_member(org.id, owner_id, "owner")
    add_test_member(org.id, target_id, "learner")

    owner_token = mint_token(username=str(owner_id), roles=["user"])
    url = f"/v1/orgs/{org.id}/members/{target_id}"

    resp = client.delete(url, headers=_auth(owner_token))
    assert resp.status_code == 204


def test_learner_cannot_remove_member(client: TestClient) -> None:
    org = create_test_org("remove-org-2")
    learner_id = uuid4()
    target_id = uuid4()

    add_test_member(org.id, learner_id, "learner")
    add_test_member(org.id, target_id, "learner")

    learner_token = mint_token(username=str(learner_id), roles=["user"])
    url = f"/v1/orgs/{org.id}/members/{target_id}"

    resp = client.delete(url, headers=_auth(learner_token))
    assert resp.status_code == 403
