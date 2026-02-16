"""Background task queue tests.

Verifies:
1. POST /v1/credentials/issue returns 202 with a task_id
2. The task appears in the in-memory queue after enqueue
3. Unauthenticated requests are rejected (401)
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.services.task_queue import task_queue
from tests.conftest import mint_token


def test_credential_issuance_returns_202(client: TestClient) -> None:
    """POST /v1/credentials/issue enqueues a task and returns 202 Accepted."""
    token = mint_token(username="queue-user")
    resp = client.post(
        "/v1/credentials/issue",
        json={"credential_id": "cred-001", "course_id": "course-001"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "task_id" in data
    assert data["status"] == "queued"


def test_credential_issuance_requires_auth(client: TestClient) -> None:
    """Unauthenticated requests to issue credentials should be rejected."""
    resp = client.post(
        "/v1/credentials/issue",
        json={"credential_id": "cred-001", "course_id": "course-001"},
    )
    assert resp.status_code == 401


def test_task_appears_in_queue_after_enqueue(client: TestClient) -> None:
    """After enqueue via the API, the task should be dequeue-able."""
    token = mint_token(username="queue-user")
    client.post(
        "/v1/credentials/issue",
        json={"credential_id": "cred-002", "course_id": "course-002"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Dequeue directly from the in-memory queue
    task = asyncio.run(_dequeue("credential_issuance"))
    assert task is not None
    assert task.payload["credential_id"] == "cred-002"
    assert task.payload["user_id"] == "queue-user"


def test_queue_length_reflects_enqueued_tasks(client: TestClient) -> None:
    """Queue length should increase with each enqueued task."""
    token = mint_token(username="queue-length-user")

    for i in range(3):
        client.post(
            "/v1/credentials/issue",
            json={"credential_id": f"cred-{i}", "course_id": "course-x"},
            headers={"Authorization": f"Bearer {token}"},
        )

    length = asyncio.run(_queue_length("credential_issuance"))
    assert length == 3


async def _dequeue(queue: str):
    return await task_queue.dequeue(queue)


async def _queue_length(queue: str):
    return await task_queue.queue_length(queue)
