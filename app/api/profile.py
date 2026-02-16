"""Profile endpoints with ownership-based access control.

GET  /auth/me           — load own profile (any authenticated user)
PATCH /users/{user_id}  — edit profile (self or platform admin)
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.access import check_owner_or_admin
from app.api.dependencies import require_user
from app.api.login import user_repo
from app.models.principal import Principal

router = APIRouter(tags=["profile"])


class ProfileOut(BaseModel):
    id: str
    email: str
    name: str
    roles: list[str]
    is_active: bool


class UpdateProfileIn(BaseModel):
    name: str


@router.get("/auth/me", response_model=ProfileOut)
def get_my_profile(
    principal: Annotated[Principal, Depends(require_user)],
) -> ProfileOut:
    """Load the authenticated user's own profile."""
    user = user_repo.get_by_id(UUID(principal.user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    return ProfileOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        roles=list(user.roles),
        is_active=user.is_active,
    )


@router.patch("/users/{user_id}", response_model=ProfileOut)
def update_profile(
    user_id: UUID,
    body: UpdateProfileIn,
    principal: Annotated[Principal, Depends(require_user)],
) -> ProfileOut:
    """Edit a user's profile. Self or platform admin only."""
    check_owner_or_admin(principal, str(user_id))

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name must not be empty")

    updated = user_repo.update_name(user_id, name)
    if updated is None:
        raise HTTPException(status_code=404, detail="user not found")

    return ProfileOut(
        id=str(updated.id),
        email=updated.email,
        name=updated.name,
        roles=list(updated.roles),
        is_active=updated.is_active,
    )
