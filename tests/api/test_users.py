from __future__ import annotations

from fastapi.testclient import TestClient


def test_users_rejects_missing_token(client: TestClient) -> None:
    resp = client.get("/users")
    assert resp.status_code == 401


def test_users_accepts_valid_token_and_returns_list(
    client: TestClient,
    token: str,
) -> None:
    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == [
        {"id": 1, "email": "tee@example.com"},
        {"id": 2, "email": "d-man@example.com"},
    ]


def test_users_create_accepts_valid_token_and_returns_created_user(
    client: TestClient,
    token: str,
) -> None:
    resp = client.post(
        "/users",
        json={"email": "new-user@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json() == {"id": 3, "email": "new-user@example.com"}


def test_users_create_rejects_duplicate_email(client: TestClient, token: str) -> None:
    first = client.post(
        "/users",
        json={"email": "duplicate@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 201

    second = client.post(
        "/users",
        json={"email": "duplicate@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second.status_code == 409
    assert second.json() == {"detail": "email already exists"}


def test_users_create_rejects_empty_email(client: TestClient, token: str) -> None:
    resp = client.post(
        "/users",
        json={"email": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json() == {"detail": "email must be non-empty"}
