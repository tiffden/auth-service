from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

# ---- 401: missing token ----


def test_users_rejects_missing_token(client: TestClient) -> None:
    resp = client.get("/users")
    assert resp.status_code == 401


def test_users_create_rejects_missing_token(client: TestClient) -> None:
    resp = client.post("/users", json={"email": "no-auth@example.com"})
    assert resp.status_code == 401


# ---- 403: authenticated but not admin ----


def test_users_list_forbidden_for_non_admin(client: TestClient, token: str) -> None:
    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_users_create_forbidden_for_non_admin(client: TestClient, token: str) -> None:
    resp = client.post(
        "/users",
        json={"email": "new@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ---- 200/201: admin success paths ----


def test_users_accepts_admin_token_and_returns_list(
    client: TestClient,
    admin_token: str,
) -> None:
    resp = client.get("/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json() == [
        {"id": 1, "email": "tee@example.com"},
        {"id": 2, "email": "d-man@example.com"},
    ]


def test_users_create_accepts_admin_token_and_returns_created_user(
    client: TestClient,
    admin_token: str,
) -> None:
    resp = client.post(
        "/users",
        json={"email": "new-user@example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json() == {"id": 3, "email": "new-user@example.com"}


# ---- 409: duplicate email (admin token) ----


def test_users_create_rejects_duplicate_email(
    client: TestClient, admin_token: str
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    first = client.post(
        "/users", json={"email": "duplicate@example.com"}, headers=headers
    )
    assert first.status_code == 201

    second = client.post(
        "/users", json={"email": "duplicate@example.com"}, headers=headers
    )
    assert second.status_code == 409
    assert second.json() == {"detail": "email already exists"}


def test_users_create_rejects_empty_email(client: TestClient, admin_token: str) -> None:
    resp = client.post(
        "/users",
        json={"email": "   "},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    assert resp.json() == {"detail": "email must be non-empty"}


# ---- 422: malformed POST /users requests (admin token) ----


def test_users_create_rejects_missing_body(
    client: TestClient, admin_token: str
) -> None:
    resp = client.post(
        "/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


def test_users_create_rejects_missing_email_field(
    client: TestClient, admin_token: str
) -> None:
    resp = client.post(
        "/users",
        json={"name": "not-the-right-field"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


def test_users_create_rejects_wrong_content_type(
    client: TestClient, admin_token: str
) -> None:
    resp = client.post(
        "/users",
        data={"email": "form-data@example.com"},
        headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    assert resp.status_code == 422


# ---- service edge cases surfaced through the API ----


def test_users_create_normalizes_email_in_response(
    client: TestClient, admin_token: str
) -> None:
    resp = client.post(
        "/users",
        json={"email": "  UPPER@EXAMPLE.COM  "},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "upper@example.com"


def test_users_create_rejects_case_variant_duplicate(
    client: TestClient, admin_token: str
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    first = client.post("/users", json={"email": "case@example.com"}, headers=headers)
    assert first.status_code == 201

    second = client.post("/users", json={"email": "CASE@EXAMPLE.COM"}, headers=headers)
    assert second.status_code == 409
    assert second.json() == {"detail": "email already exists"}


def test_users_create_rejects_duplicate_of_seed_user(
    client: TestClient, admin_token: str
) -> None:
    resp = client.post(
        "/users",
        json={"email": "tee@example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409


def test_users_create_ids_increment_across_multiple_creates(
    client: TestClient, admin_token: str
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    r3 = client.post("/users", json={"email": "a@example.com"}, headers=headers)
    r4 = client.post("/users", json={"email": "b@example.com"}, headers=headers)
    r5 = client.post("/users", json={"email": "c@example.com"}, headers=headers)
    assert (r3.json()["id"], r4.json()["id"], r5.json()["id"]) == (3, 4, 5)


def test_users_list_reflects_newly_created_user(
    client: TestClient, admin_token: str
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    client.post("/users", json={"email": "new@example.com"}, headers=headers)
    resp = client.get("/users", headers=headers)
    emails = [u["email"] for u in resp.json()]
    assert "new@example.com" in emails
    assert len(resp.json()) == 3


def test_users_list_returns_json_content_type(
    client: TestClient, admin_token: str
) -> None:
    resp = client.get("/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.headers["content-type"] == "application/json"


# ---- logging assertions ----


def test_user_creation_logs_info(
    client: TestClient, admin_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.services.users_service"):
        client.post(
            "/users",
            json={"email": "logged@example.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert any(
        "Created user" in m and "logged@example.com" in m for m in caplog.messages
    )


def test_duplicate_email_logs_warning(
    client: TestClient, admin_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    client.post("/users", json={"email": "first@example.com"}, headers=headers)

    with caplog.at_level(logging.WARNING, logger="app.services.users_service"):
        client.post("/users", json={"email": "first@example.com"}, headers=headers)
    assert any("duplicate" in m.lower() for m in caplog.messages)


def test_blank_email_logs_warning(
    client: TestClient, admin_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.services.users_service"):
        client.post(
            "/users",
            json={"email": "  "},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert any("blank" in m.lower() for m in caplog.messages)
