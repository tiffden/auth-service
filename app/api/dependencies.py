from __future__ import annotations

import logging
from dataclasses import replace
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.models.principal import Principal
from app.repos.org_membership_repo import OrgMembershipRepo
from app.services import token_service

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/oauth/token")


def require_user(
    raw_token: Annotated[str, Depends(oauth2_scheme)],
) -> Principal:
    """Extract and validate the JWT bearer token. Returns a Principal.

    Used as a FastAPI dependency on any protected endpoint.
    """
    try:
        claims = token_service.decode_access_token(raw_token)
    except jwt.ExpiredSignatureError:
        logger.warning("Expired token rejected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid token rejected: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    principal = Principal(
        user_id=claims["sub"],
        roles=frozenset(claims.get("roles", [])),
    )
    logger.debug(
        "Token validated for user=%s roles=%s",
        principal.user_id,
        principal.roles,
    )
    return principal


def require_role(role: str):
    """Dependency factory: demand a specific role.

    Usage: Depends(require_role("admin"))
    Returns the Principal if the role is present, else 403.
    """

    def _guard(
        principal: Annotated[Principal, Depends(require_user)],
    ) -> Principal:
        if not principal.has_role(role):
            logger.warning(
                "Access denied: user=%s missing role=%s",
                principal.user_id,
                role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return principal

    return _guard


def require_any_role(roles: set[str]):
    """Dependency factory: demand at least one of the given roles.

    Usage: Depends(require_any_role({"admin", "instructor"}))
    """

    def _guard(
        principal: Annotated[Principal, Depends(require_user)],
    ) -> Principal:
        if not principal.has_any_role(roles):
            logger.warning(
                "Access denied: user=%s has none of roles=%s",
                principal.user_id,
                roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return principal

    return _guard


def get_interactive_user(request: Request) -> str | None:
    """Return user_id from the session cookie, or None if not authenticated.

    Used by /oauth/authorize (browser-facing). The caller decides what to do
    when None is returned (e.g. redirect to /login).
    """
    cookie = request.cookies.get("session")
    if not cookie:
        return None
    try:
        claims = token_service.decode_session_token(cookie)
        return claims["sub"]
    except jwt.ExpiredSignatureError:
        logger.debug("Session cookie expired")
        return None
    except jwt.InvalidTokenError:
        logger.debug("Invalid session cookie")
        return None


# ---------------------------------------------------------------------------
# Org-scoped access guards
# ---------------------------------------------------------------------------


def resolve_org_principal(membership_repo: OrgMembershipRepo):
    """Dependency factory: resolve org context from URL path param.

    Reads org_id from the path, looks up the user's membership,
    and returns a new Principal enriched with org_id and org_role.
    Raises 403 if the user is not a member of the org.
    Platform admins bypass the membership check.

    Usage::

        _resolve = resolve_org_principal(membership_repo)

        @router.get("/v1/orgs/{org_id}")
        def get_org(principal: Annotated[Principal, Depends(_resolve)]):
            ...
    """

    def _resolve(
        org_id: UUID,
        principal: Annotated[Principal, Depends(require_user)],
    ) -> Principal:
        if principal.is_platform_admin():
            return replace(principal, org_id=org_id, org_role="admin")

        membership = membership_repo.get(org_id, UUID(principal.user_id))
        if membership is None:
            logger.warning(
                "Access denied: user=%s not a member of org=%s",
                principal.user_id,
                org_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization",
            )

        return replace(principal, org_id=org_id, org_role=membership.org_role)

    return _resolve


def require_org_role(role: str, membership_repo: OrgMembershipRepo):
    """Dependency factory: demand a specific org role.

    Usage::

        _require_admin = require_org_role("admin", membership_repo)

        @router.post("/v1/orgs/{org_id}/members")
        def add_member(principal: Annotated[Principal, Depends(_require_admin)]):
            ...
    """
    _resolve = resolve_org_principal(membership_repo)

    def _guard(
        principal: Annotated[Principal, Depends(_resolve)],
    ) -> Principal:
        if principal.is_platform_admin():
            return principal
        if not principal.has_org_role(role):
            logger.warning(
                "Access denied: user=%s org_role=%s required=%s org=%s",
                principal.user_id,
                principal.org_role,
                role,
                principal.org_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient org permissions",
            )
        return principal

    return _guard


def require_any_org_role(roles: set[str], membership_repo: OrgMembershipRepo):
    """Dependency factory: demand at least one of the given org roles.

    Usage::

        _require = require_any_org_role({"owner", "admin"}, membership_repo)
    """
    _resolve = resolve_org_principal(membership_repo)

    def _guard(
        principal: Annotated[Principal, Depends(_resolve)],
    ) -> Principal:
        if principal.is_platform_admin():
            return principal
        if not principal.has_any_org_role(roles):
            logger.warning(
                "Access denied: user=%s org_role=%s required_any=%s org=%s",
                principal.user_id,
                principal.org_role,
                roles,
                principal.org_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient org permissions",
            )
        return principal

    return _guard
