"""Tests for progress event ingestion endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

# ---- 401: unauthenticated ----


def test_progress_event_rejects_missing_token(client: TestClient) -> None:
    payload = {"course_id": "x", "type": "enrolled"}
    resp = client.post("/v1/progress/events", json=payload)
    assert resp.status_code == 401


# ---- 202: accepted ----


def test_progress_event_accepted(client: TestClient, token: str) -> None:
    resp = client.post(
        "/v1/progress/events",
        json={"course_id": "intro-to-claude", "type": "item_completed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["type"] == "item_completed"
    assert body["course_id"] == "intro-to-claude"
    assert "id" in body
    assert "occurred_at" in body


# ---- idempotency ----


def test_progress_event_idempotency(client: TestClient, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "course_id": "intro-to-claude",
        "type": "item_completed",
        "idempotency_key": "unique-key-123",
    }
    first = client.post("/v1/progress/events", json=payload, headers=headers)
    second = client.post("/v1/progress/events", json=payload, headers=headers)
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
