from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.orgs import membership_repo, org_repo
from app.api.progress import _PROGRESS_EVENTS
from app.api.ratelimit import _rate_limiter
from app.main import app
from app.models.organization import Organization, OrgMembership
from app.services import token_service, users_service
from app.services.cache import cache_service
from app.services.task_queue import task_queue
from app.services.token_blacklist import token_blacklist
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


@pytest.fixture(autouse=True)
def reset_org_state() -> None:
    """Clear org and membership repos between tests."""
    org_repo._by_id.clear()
    org_repo._by_slug.clear()
    membership_repo._store.clear()


@pytest.fixture(autouse=True)
def reset_progress_state() -> None:
    """Clear progress events between tests."""
    _PROGRESS_EVENTS.clear()


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """Clear rate limit buckets between tests so limits don't bleed."""
    if hasattr(_rate_limiter, "_buckets"):
        _rate_limiter._buckets.clear()  # type: ignore[union-attr]


@pytest.fixture(autouse=True)
def reset_token_blacklist() -> None:
    """Clear token blacklist between tests."""
    if hasattr(token_blacklist, "_revoked"):
        token_blacklist._revoked.clear()  # type: ignore[union-attr]


@pytest.fixture(autouse=True)
def reset_cache() -> None:
    """Clear cache between tests."""
    if hasattr(cache_service, "_store"):
        cache_service._store.clear()  # type: ignore[union-attr]


@pytest.fixture(autouse=True)
def reset_task_queue() -> None:
    """Clear task queues between tests."""
    if hasattr(task_queue, "_queues"):
        task_queue._queues.clear()  # type: ignore[union-attr]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def mint_token(
    username: str = "test-user",
    roles: list[str] | None = None,
) -> str:
    """Create a valid ES256 JWT for testing."""
    return token_service.create_access_token(sub=username, roles=roles)


@pytest.fixture
def token() -> str:
    """Token with default role (user)."""
    return mint_token()


@pytest.fixture
def admin_token() -> str:
    """Token with admin role."""
    return mint_token(username="test-admin", roles=["admin"])


# ---------------------------------------------------------------------------
# Org test helpers
# ---------------------------------------------------------------------------


def create_test_org(slug: str = "test-org") -> Organization:
    """Create and persist an org in the in-memory repo."""
    org = Organization.new(name=slug.replace("-", " ").title(), slug=slug)
    org_repo.add(org)
    return org


def add_test_member(org_id, user_id, org_role: str = "learner") -> OrgMembership:
    """Add a membership to the in-memory repo."""
    m = OrgMembership(org_id=org_id, user_id=user_id, org_role=org_role)
    membership_repo.add(m)
    return m
