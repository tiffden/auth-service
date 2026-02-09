from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import users_service
from app.services.users_service import User

# Ensure repo root is on sys.path so `import app` works under pytest.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_INITIAL_USERS = [
    User(id=1, email="tee@example.com"),
    User(id=2, email="d-man@example.com"),
]


@pytest.fixture(autouse=True)
def reset_users_state() -> None:
    users_service._FAKE_USERS[:] = list(_INITIAL_USERS)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def token(client: TestClient) -> str:
    resp = client.post(
        "/auth/token",
        data={"username": "tee", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "access_token" in payload
    return payload["access_token"]
