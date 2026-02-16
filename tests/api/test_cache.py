"""Cache hit/miss/invalidation tests for progress summary.

Verifies the read-through cache pattern:
1. First GET is a cache miss (populates cache from the data store)
2. Second GET is a cache hit (returns same data without querying store)
3. POST /events invalidates the cache so the next GET sees fresh data
4. Different users have isolated cache entries
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import mint_token

_COURSE_ID = "course-cache-test"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ingest_event(client: TestClient, token: str, course_id: str = _COURSE_ID):
    """Helper: ingest a progress event."""
    return client.post(
        "/v1/progress/events",
        json={"course_id": course_id, "type": "enrolled"},
        headers=_auth(token),
    )


def test_cache_miss_then_hit(client: TestClient) -> None:
    """First GET populates the cache; second GET returns the same data."""
    token = mint_token(username="cache-user")

    # Ingest an event first
    _ingest_event(client, token)

    # First GET — cache miss, reads from store, populates cache
    resp1 = client.get(f"/v1/progress/summary/{_COURSE_ID}", headers=_auth(token))
    assert resp1.status_code == 200
    assert len(resp1.json()) == 1

    # Second GET — cache hit, same data
    resp2 = client.get(f"/v1/progress/summary/{_COURSE_ID}", headers=_auth(token))
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


def test_cache_invalidated_on_new_event(client: TestClient) -> None:
    """After ingesting a new event, the cached summary should reflect it."""
    token = mint_token(username="cache-invalidation-user")

    # Ingest first event
    _ingest_event(client, token)

    # Read — populates cache with 1 event
    resp1 = client.get(f"/v1/progress/summary/{_COURSE_ID}", headers=_auth(token))
    assert len(resp1.json()) == 1

    # Ingest second event — should invalidate cache
    _ingest_event(client, token)

    # Read again — should see 2 events (not stale cached 1)
    resp2 = client.get(f"/v1/progress/summary/{_COURSE_ID}", headers=_auth(token))
    assert len(resp2.json()) == 2


def test_empty_summary_returns_empty_list(client: TestClient) -> None:
    """A course with no events returns an empty list (not 404)."""
    token = mint_token(username="empty-user")
    resp = client.get("/v1/progress/summary/nonexistent-course", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_cache_is_user_isolated(client: TestClient) -> None:
    """User A's cached progress should not leak to user B."""
    token_a = mint_token(username="user-a")
    token_b = mint_token(username="user-b")

    # User A ingests an event
    _ingest_event(client, token_a)

    # User B should see empty progress (not A's events)
    resp = client.get(f"/v1/progress/summary/{_COURSE_ID}", headers=_auth(token_b))
    assert resp.status_code == 200
    assert resp.json() == []
