"""Cross-tenant isolation tests.

Validates that a member of org A cannot access org B's resources,
and that org-scoped operations never leak across tenant boundaries.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import add_test_member, create_test_org, mint_token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_org_a_member_cannot_see_org_b(client: TestClient) -> None:
    """A member of org A should get 403 when accessing org B."""
    org_a = create_test_org("tenant-a")
    org_b = create_test_org("tenant-b")
    user_id = uuid4()

    add_test_member(org_a.id, user_id, "admin")
    # user is NOT a member of org_b

    token = mint_token(username=str(user_id), roles=["user"])

    resp = client.get(f"/v1/orgs/{org_b.id}", headers=_auth(token))
    assert resp.status_code == 403


def test_org_a_admin_cannot_add_member_to_org_b(client: TestClient) -> None:
    """Org A admin should get 403 when trying to add a member to org B."""
    org_a = create_test_org("iso-a")
    org_b = create_test_org("iso-b")
    admin_id = uuid4()

    add_test_member(org_a.id, admin_id, "admin")

    token = mint_token(username=str(admin_id), roles=["user"])

    resp = client.post(
        f"/v1/orgs/{org_b.id}/members",
        json={"user_id": str(uuid4()), "org_role": "learner"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_org_a_member_cannot_list_org_b_members(client: TestClient) -> None:
    """Org A instructor should get 403 when listing org B members."""
    org_a = create_test_org("list-a")
    org_b = create_test_org("list-b")
    user_id = uuid4()

    add_test_member(org_a.id, user_id, "instructor")

    token = mint_token(username=str(user_id), roles=["user"])

    resp = client.get(f"/v1/orgs/{org_b.id}/members", headers=_auth(token))
    assert resp.status_code == 403


def test_platform_admin_can_access_any_org(client: TestClient) -> None:
    """Platform admin bypasses membership check."""
    org = create_test_org("admin-access")
    # No membership added for the admin

    admin_token = mint_token(username=str(uuid4()), roles=["admin"])

    resp = client.get(f"/v1/orgs/{org.id}", headers=_auth(admin_token))
    assert resp.status_code == 200

    resp = client.get(f"/v1/orgs/{org.id}/members", headers=_auth(admin_token))
    assert resp.status_code == 200


def test_creating_org_isolates_membership(client: TestClient) -> None:
    """Creating org A should not grant access to org B."""
    user_id = uuid4()
    token = mint_token(username=str(user_id), roles=["user"])

    # Create org A — user becomes owner
    resp = client.post(
        "/v1/orgs",
        json={"name": "Org A", "slug": "create-iso-a"},
        headers=_auth(token),
    )
    assert resp.status_code == 201

    # Create org B with a different user
    other_id = uuid4()
    other_token = mint_token(username=str(other_id), roles=["user"])
    resp = client.post(
        "/v1/orgs",
        json={"name": "Org B", "slug": "create-iso-b"},
        headers=_auth(other_token),
    )
    assert resp.status_code == 201
    org_b_id = resp.json()["id"]

    # First user cannot access org B
    resp = client.get(f"/v1/orgs/{org_b_id}", headers=_auth(token))
    assert resp.status_code == 403
