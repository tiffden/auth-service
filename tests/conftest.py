from __future__ import annotations

import hashlib
import hmac
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import TOKEN_SIGNING_SECRET
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


def mint_token(username: str = "test-user", ttl_min: int = 30) -> str:
    """Create a valid HMAC-signed token for testing.

    Mirrors the token format produced by oauth.py's exchange_token.
    """
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_min)
    exp_ts = int(expires_at.timestamp())
    token_core = f"user:{username}|exp:{exp_ts}"
    sig = hmac.new(
        TOKEN_SIGNING_SECRET.encode(),
        token_core.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{token_core}|sig:{sig}"


@pytest.fixture
def token() -> str:
    return mint_token()
