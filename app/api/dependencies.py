from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/oauth/token")
TOKEN_SIGNING_SECRET = os.getenv("TOKEN_SIGNING_SECRET", "dev-only-secret-change-me")


def require_user(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    """Extract and validate the bearer token. Returns the username (sub).

    Used as a FastAPI dependency on any protected endpoint.
    """
    try:
        parts = token.split("|")
        user_part = parts[0]
        exp_part = parts[1]
        username = user_part.split(":", 1)[1]
        exp_ts = int(exp_part.split(":", 1)[1])
        sig_part = parts[2] if len(parts) > 2 else None
    except Exception as e:
        logger.warning("Malformed token rejected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    if datetime.now(UTC).timestamp() > exp_ts:
        logger.warning("Expired token rejected for user=%s", username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if sig_part is not None:
        sig = sig_part.split(":", 1)[1]
        token_core = f"user:{username}|exp:{exp_ts}"
        expected = hmac.new(
            TOKEN_SIGNING_SECRET.encode("utf-8"),
            token_core.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not secrets.compare_digest(sig, expected):
            logger.warning("Invalid signature rejected for user=%s", username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature",
                headers={"WWW-Authenticate": "Bearer"},
            )

    logger.debug("Token validated for user=%s", username)
    return username
