"""Logout endpoint — revokes the current access token.

WHY a dedicated endpoint (not just "delete the cookie"):
  Access tokens may be stored by API clients (mobile apps, SPAs, CLI
  tools) that don't use cookies.  Blacklisting the JTI (JWT ID) ensures
  the token is invalid regardless of where the client stored it.

  We also clear the session cookie for browser-based sessions, covering
  both API and browser clients in one endpoint.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.services import token_service
from app.services.token_blacklist import token_blacklist

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/oauth/token")


class LogoutBody(BaseModel):
    """Optional body — clients may include their refresh token for revocation."""

    refreshToken: str | None = None


@router.post("/auth/logout", status_code=204)
async def logout(
    raw_token: Annotated[str, Depends(oauth2_scheme)],
    body: LogoutBody | None = None,
) -> Response:
    """Revoke the current token (and optional refresh token) and clear the
    session cookie.

    The token's JTI is added to the blacklist with a TTL matching
    the token's remaining lifetime.  After this, any request using
    this token will be rejected by require_user().
    """
    try:
        claims = token_service.decode_access_token(raw_token)
    except Exception:
        # Even if the token is invalid/expired, return 204.
        # Logout should be idempotent — "make this token not work"
        # is already true if it's invalid.
        claims = None

    if claims:
        jti = claims.get("jti")
        exp = claims.get("exp")
        if jti and exp:
            await token_blacklist.revoke(jti, float(exp))
            logger.info("Token revoked jti=%s", jti)

    # Also revoke the refresh token if the client included it.
    if body and body.refreshToken:
        try:
            refresh_claims = token_service.decode_refresh_token(body.refreshToken)
            r_jti = refresh_claims.get("jti")
            r_exp = refresh_claims.get("exp")
            if r_jti and r_exp:
                await token_blacklist.revoke(r_jti, float(r_exp))
                logger.info("Refresh token revoked on logout  jti=%s", r_jti)
        except Exception:
            pass  # Best effort — logout is idempotent

    response = Response(status_code=204)
    response.delete_cookie("session")
    return response
