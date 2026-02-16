from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.api.dependencies import resolve_org_principal
from app.models.organization import OrgMembership
from app.models.principal import Principal
from app.repos.org_membership_repo import InMemoryOrgMembershipRepo


def test_resolve_org_principal_rejects_non_uuid_subject() -> None:
    repo = InMemoryOrgMembershipRepo()
    resolve = resolve_org_principal(repo)

    with pytest.raises(HTTPException) as exc:
        resolve(
            org_id=uuid4(),
            principal=Principal(user_id="test-user", roles=frozenset({"user"})),
        )

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc.value.detail == "Invalid token subject"


def test_resolve_org_principal_returns_org_context_for_member() -> None:
    repo = InMemoryOrgMembershipRepo()
    resolve = resolve_org_principal(repo)
    org_id = uuid4()
    user_id = uuid4()
    repo.add(OrgMembership(org_id=org_id, user_id=user_id, org_role="learner"))

    principal = resolve(
        org_id=org_id,
        principal=Principal(user_id=str(user_id), roles=frozenset({"user"})),
    )

    assert principal.org_id == org_id
    assert principal.org_role == "learner"


def test_resolve_org_principal_allows_platform_admin_without_membership() -> None:
    repo = InMemoryOrgMembershipRepo()
    resolve = resolve_org_principal(repo)
    org_id = uuid4()

    principal = resolve(
        org_id=org_id,
        principal=Principal(user_id="not-a-uuid", roles=frozenset({"admin"})),
    )

    assert principal.org_id == org_id
    assert principal.org_role == "admin"
