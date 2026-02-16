"""Token blacklist tests.

Verifies JWT revocation via the blacklist:
1. A valid token works normally before revocation
2. After POST /auth/logout, the same token is rejected (401)
3. A different user's token is unaffected by another's logout
4. Logout is idempotent (calling it twice doesn't error)
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import mint_token


def test_token_works_before_logout(client: TestClient) -> None:
    """Baseline: a valid token reaches the protected endpoint."""
    token = mint_token(username="blacklist-user")
    resp = client.get("/resource/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_token_rejected_after_logout(client: TestClient) -> None:
    """After logout, the same token should be rejected with 401."""
    token = mint_token(username="blacklist-user")

    # Verify it works first
    resp = client.get("/resource/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # Logout — revokes the token
    resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204

    # Same token is now rejected
    resp = client.get("/resource/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "revoked" in resp.json()["detail"].lower()


def test_other_tokens_unaffected_by_logout(client: TestClient) -> None:
    """Revoking user A's token should not affect user B's token."""
    token_a = mint_token(username="user-a")
    token_b = mint_token(username="user-b")

    # Revoke A
    resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 204

    # B still works
    resp = client.get("/resource/me", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200


def test_logout_is_idempotent(client: TestClient) -> None:
    """Calling logout twice with the same token should not error."""
    token = mint_token(username="idempotent-user")

    resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204

    # Second call — token is already revoked/invalid, but should still 204
    resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204
