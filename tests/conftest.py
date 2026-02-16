from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.orgs import membership_repo, org_repo
from app.main import app
from app.models.organization import Organization, OrgMembership
from app.services import token_service, users_service
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
