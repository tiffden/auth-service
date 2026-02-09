from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

router = APIRouter(tags=["auth"])

# Endpoint Logic - defines POST /auth/token and require_user token dependency

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
TOKEN_TTL_MIN = 30
TOKEN_SIGNING_SECRET = os.getenv("TOKEN_SIGNING_SECRET", "dev-only-secret-change-me")


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


@router.post("/auth/token", response_model=Token)
def issue_token(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    if not (
        secrets.compare_digest(form.username, "tee")
        and secrets.compare_digest(form.password, "password")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_at = datetime.now(UTC) + timedelta(minutes=TOKEN_TTL_MIN)
    exp_ts = int(expires_at.timestamp())
    token_core = f"user:{form.username}|exp:{exp_ts}"
    sig = hmac.new(
        TOKEN_SIGNING_SECRET.encode("utf-8"),
        token_core.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    token = f"{token_core}|sig:{sig}"

    return Token(access_token=token, expires_at=expires_at)


def require_user(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    try:
        parts = token.split("|")
        user_part = parts[0]
        exp_part = parts[1]
        username = user_part.split(":", 1)[1]
        exp_ts = int(exp_part.split(":", 1)[1])
        sig_part = parts[2] if len(parts) > 2 else None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    if datetime.now(UTC).timestamp() > exp_ts:
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return username
