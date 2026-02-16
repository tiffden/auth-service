"""Tests for credential verification endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import credentials as credentials_api


@pytest.fixture(autouse=True)
def reset_credentials_state() -> None:
    credentials_api._CREDENTIALS.clear()
    credentials_api._USER_CREDENTIALS.clear()


def test_verify_credential_is_public(client: TestClient) -> None:
    credentials_api._CREDENTIALS["cred-1"] = {
        "id": "cred-1",
        "name": "Claude Fundamentals",
        "issuer": "Anthropic Academy",
    }
    credentials_api._USER_CREDENTIALS["uc-1"] = {
        "id": "uc-1",
        "credential_id": "cred-1",
        "user_id": "user-123",
        "issued_at": 1739600000,
        "status": "issued",
    }

    resp = client.get("/v1/credentials/uc-1/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "uc-1"
    assert body["credential_name"] == "Claude Fundamentals"
    assert body["issuer"] == "Anthropic Academy"
    assert body["valid"] is True
