"""Ownership and resource-level access checks.

These are plain functions (not FastAPI dependencies) because they need
both the Principal and a resource identifier, which makes them awkward
as pure dependency injection.  Call them at the top of an endpoint body.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.models.principal import Principal


def check_owner_or_admin(
    principal: Principal,
    resource_owner_id: str,
) -> None:
    """Raise 403 unless the principal owns the resource or is a platform admin."""
    if principal.user_id == resource_owner_id:
        return
    if principal.is_platform_admin():
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You can only access your own resource",
    )


def check_owner_or_org_admin(
    principal: Principal,
    resource_owner_id: str,
) -> None:
    # Raise 403 unless the principal owns the resource, is an org admin/owner,
    # or is a platform admin
    if principal.user_id == resource_owner_id:
        return
    if principal.is_platform_admin():
        return
    if principal.org_role in ("admin", "owner"):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions",
    )
