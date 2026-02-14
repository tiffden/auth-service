from __future__ import annotations

import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.models.principal import Principal
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
