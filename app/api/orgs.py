"""Organization management endpoints.

Provides CRUD for organizations and membership management.
Org context is resolved from the URL path and validated against
the user's membership at request time.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import (
    require_any_org_role,
    require_user,
    resolve_org_principal,
)
from app.models.organization import Organization, OrgMembership
from app.models.principal import Principal
from app.repos.org_membership_repo import InMemoryOrgMembershipRepo
from app.repos.org_repo import InMemoryOrgRepo

router = APIRouter(prefix="/v1/orgs", tags=["orgs"])

# --- Module-level repo singletons (in-memory for now) ---
org_repo = InMemoryOrgRepo()
membership_repo = InMemoryOrgMembershipRepo()

# --- Dependency instances wired to these repos ---
_resolve_org = resolve_org_principal(membership_repo)
_require_owner_or_admin = require_any_org_role({"owner", "admin"}, membership_repo)
_require_owner = require_any_org_role({"owner"}, membership_repo)


def _org_id(principal: Principal) -> UUID:
    """Extract org_id from an org-scoped Principal, or 500 if missing.

    The org-scoped dependencies guarantee org_id is set before any
    endpoint body runs. This helper makes that contract explicit
    and satisfies the type checker without `type: ignore`.
    """
    if principal.org_id is None:
        raise HTTPException(status_code=500, detail="org context not resolved")
    return principal.org_id


# --- Pydantic schemas ---


class OrgCreateIn(BaseModel):
    name: str
    slug: str


class OrgOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    status: str


class MemberOut(BaseModel):
    user_id: str
    org_role: str


class AddMemberIn(BaseModel):
    user_id: str
    org_role: str = "learner"


class UpdateRoleIn(BaseModel):
    org_role: str


# --- Endpoints ---


@router.post("", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def create_org(
    body: OrgCreateIn,
    principal: Annotated[Principal, Depends(require_user)],
) -> OrgOut:
    """Create a new organization. The creator becomes the owner."""
    if org_repo.get_by_slug(body.slug) is not None:
        raise HTTPException(status_code=409, detail="slug already taken")

    org = Organization.new(name=body.name, slug=body.slug)
    org_repo.add(org)

    # Creator becomes the owner
    membership_repo.add(
        OrgMembership(
            org_id=org.id,
            user_id=UUID(principal.user_id),
            org_role="owner",
        )
    )

    return OrgOut(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        plan=org.plan,
        status=org.status,
    )


@router.get("/{org_id}", response_model=OrgOut)
def get_org(
    principal: Annotated[Principal, Depends(_resolve_org)],
) -> OrgOut:
    """Get org details. Any member can view."""
    org = org_repo.get_by_id(_org_id(principal))
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    return OrgOut(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        plan=org.plan,
        status=org.status,
    )


@router.get("/{org_id}/members", response_model=list[MemberOut])
def list_members(
    principal: Annotated[Principal, Depends(_resolve_org)],
) -> list[MemberOut]:
    """List org members. Accessible to owner, admin, and instructor."""
    if (
        principal.org_role not in ("owner", "admin", "instructor")
        and not principal.is_platform_admin()
    ):
        raise HTTPException(status_code=403, detail="Insufficient org permissions")

    members = membership_repo.list_by_org(_org_id(principal))
    return [MemberOut(user_id=str(m.user_id), org_role=m.org_role) for m in members]


@router.post(
    "/{org_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    body: AddMemberIn,
    principal: Annotated[Principal, Depends(_require_owner_or_admin)],
) -> MemberOut:
    """Add a member to the org. Requires owner or admin role."""
    if body.org_role not in ("admin", "instructor", "learner"):
        raise HTTPException(status_code=422, detail="invalid org_role")

    oid = _org_id(principal)
    user_id = UUID(body.user_id)
    existing = membership_repo.get(oid, user_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="user is already a member")

    membership = OrgMembership(org_id=oid, user_id=user_id, org_role=body.org_role)
    membership_repo.add(membership)
    return MemberOut(user_id=str(membership.user_id), org_role=membership.org_role)


@router.patch("/{org_id}/members/{user_id}", response_model=MemberOut)
def update_member_role(
    user_id: UUID,
    body: UpdateRoleIn,
    principal: Annotated[Principal, Depends(_require_owner)],
) -> MemberOut:
    """Change a member's role. Only the org owner can do this."""
    if body.org_role not in ("owner", "admin", "instructor", "learner"):
        raise HTTPException(status_code=422, detail="invalid org_role")

    updated = membership_repo.update_role(_org_id(principal), user_id, body.org_role)
    if updated is None:
        raise HTTPException(status_code=404, detail="membership not found")

    return MemberOut(user_id=str(updated.user_id), org_role=updated.org_role)


@router.delete(
    "/{org_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    user_id: UUID,
    principal: Annotated[Principal, Depends(_require_owner_or_admin)],
) -> None:
    """Remove a member from the org. Requires owner or admin role."""
    removed = membership_repo.remove(_org_id(principal), user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="membership not found")
