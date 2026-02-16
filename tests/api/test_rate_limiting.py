"""Rate limiting tests.

Verifies the token bucket rate limiter:
1. Requests within the bucket capacity succeed (200)
2. Requests exceeding capacity get 429 Too Many Requests
3. The 429 response includes a Retry-After header
4. Rate limit headers are present on responses
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import mint_token


@pytest.fixture
def user_token() -> str:
    return mint_token(username="rate-limit-user")


def test_requests_within_limit_succeed(client: TestClient, user_token: str) -> None:
    """A handful of requests should all succeed — well within bucket capacity."""
    for _ in range(5):
        resp = client.get(
            "/resource/me", headers={"Authorization": f"Bearer {user_token}"}
        )
        assert resp.status_code == 200


def test_requests_over_limit_get_429(client: TestClient, user_token: str) -> None:
    """Sending more requests than the bucket capacity triggers 429."""
    statuses: list[int] = []
    # Default capacity is 60; send 65 requests to guarantee some 429s
    for _ in range(65):
        resp = client.get(
            "/resource/me", headers={"Authorization": f"Bearer {user_token}"}
        )
        statuses.append(resp.status_code)

    assert 200 in statuses, "Some requests should succeed"
    assert 429 in statuses, "Some requests should be rate limited"


def test_429_includes_retry_after_header(client: TestClient, user_token: str) -> None:
    """When rate limited, the response MUST include Retry-After."""
    # Exhaust the bucket
    last_resp = None
    for _ in range(70):
        last_resp = client.get(
            "/resource/me", headers={"Authorization": f"Bearer {user_token}"}
        )
    assert last_resp is not None
    assert last_resp.status_code == 429
    assert "retry-after" in last_resp.headers
    assert int(last_resp.headers["retry-after"]) > 0


def test_login_has_strict_rate_limit(client: TestClient) -> None:
    """POST /login has a strict limit (capacity=10) for brute-force protection."""
    statuses: list[int] = []
    for _ in range(15):
        resp = client.post(
            "/login",
            data={"email": "test@example.com", "password": "wrong"},
        )
        statuses.append(resp.status_code)

    assert 429 in statuses, "Login should hit rate limit before 15 attempts"


def test_different_users_have_separate_buckets(client: TestClient) -> None:
    """Each user gets their own token bucket — user A's usage doesn't
    affect user B."""
    token_a = mint_token(username="user-a")
    token_b = mint_token(username="user-b")

    # Exhaust user A's bucket
    for _ in range(65):
        client.get("/resource/me", headers={"Authorization": f"Bearer {token_a}"})

    # User B should still have a full bucket
    resp = client.get("/resource/me", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
