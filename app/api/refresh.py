"""Refresh endpoint — exchange a valid refresh token for a new token pair.

WHY REFRESH TOKENS EXIST
--------------------------
Access tokens are short-lived (15 minutes) to limit the damage window if
one is stolen.  But forcing users to re-enter credentials every 15 minutes
is terrible UX.  Refresh tokens bridge this gap:

  1. Client stores both access token (short TTL) and refresh token (long TTL)
  2. When the access token expires, client sends the refresh token here
  3. Server issues a NEW access token + NEW refresh token
  4. Old refresh token is blacklisted (rotation)

WHY ROTATION
--------------
If we reused the same refresh token, a stolen one would work for 7 days.
With rotation, each refresh token is single-use:

  - Client uses refresh token R1 → gets R2
  - If attacker stole R1 and tries to use it → REJECTED (already used)
  - If attacker uses R1 before the client → client's R2 fails → signals breach

This is called "refresh token rotation" and is recommended by OAuth 2.0
Security Best Current Practice (RFC 9700, Section 2.2.2).
"""

from __future__ import annotations

import logging
from uuid import UUID

import jwt as pyjwt
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.login import user_repo
from app.api.register import AuthResponse, UserOut
from app.services import token_service
from app.services.token_blacklist import token_blacklist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class RefreshIn(BaseModel):
    refreshToken: str


@router.post("/refresh", response_model=AuthResponse)
async def refresh(payload: RefreshIn) -> AuthResponse:
    """Exchange a valid refresh token for a new access + refresh token pair.

    Steps:
      1. Decode and verify the refresh token (signature, expiry, audience)
      2. Check it hasn't been revoked (blacklist lookup)
      3. Look up the user to get current roles (not stale token roles)
      4. Blacklist the old refresh token (rotation — single use)
      5. Issue new access token + new refresh token
    """
    # --- 1. Decode refresh token ---
    try:
        claims = token_service.decode_refresh_token(payload.refreshToken)
    except pyjwt.ExpiredSignatureError:
        logger.warning("Expired refresh token presented")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        ) from None
    except pyjwt.InvalidTokenError as e:
        logger.warning("Invalid refresh token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from None

    # --- 2. Check blacklist (was this refresh token already used?) ---
    jti = claims.get("jti")
    if jti and await token_blacklist.is_revoked(jti):
        # SECURITY: A revoked refresh token being reused may indicate
        # token theft.  In production you'd trigger an alert or revoke
        # ALL of this user's sessions.  For now, just reject.
        logger.warning(
            "Revoked refresh token reuse detected  jti=%s sub=%s",
            jti,
            claims.get("sub"),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    # --- 3. Look up user for current roles ---
    sub = claims["sub"]
    try:
        user = user_repo.get_by_id(UUID(sub))
    except (ValueError, KeyError):
        user = None

    if user is None or not user.is_active:
        logger.warning("Refresh for unknown/inactive user  sub=%s", sub)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # --- 4. Blacklist the old refresh token (rotation) ---
    exp = claims.get("exp")
    if jti and exp:
        await token_blacklist.revoke(jti, float(exp))
        logger.info("Refresh token rotated  old_jti=%s user=%s", jti, sub)

    # --- 5. Issue new token pair ---
    new_access = token_service.create_access_token(
        sub=sub,
        roles=list(user.roles) or ["user"],
    )
    new_refresh = token_service.create_refresh_token(sub=sub)

    return AuthResponse(
        accessToken=new_access,
        refreshToken=new_refresh,
        user=UserOut(id=str(user.id), email=user.email, name=user.name),
    )
