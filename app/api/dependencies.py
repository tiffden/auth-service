from __future__ import annotations

import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.services import token_service

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/oauth/token")


def require_user(
    raw_token: Annotated[str, Depends(oauth2_scheme)],
) -> str:
    """Extract and validate the JWT bearer token. Returns the sub claim.

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

    username = claims["sub"]
    logger.debug("Token validated for user=%s", username)
    return username


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
