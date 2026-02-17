"""JWT access token creation and validation (ES256).

Centralizes all token logic so oauth.py (issuance) and
dependencies.py (validation) share the same key and claims schema.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------
# Dev/test: generate an ephemeral EC key pair on import.
# Production: load from env var, file, or KMS (not implemented yet).
_private_key = ec.generate_private_key(ec.SECP256R1())
_public_key = _private_key.public_key()

ALGORITHM = "ES256"
ISSUER = "auth-service"
AUDIENCE = "auth-service"
ACCESS_TOKEN_TTL_MIN = 15  # short TTL per design docs

# Session cookies use the same signing key but a different audience
# so a session JWT can never be confused with an access token.
SESSION_AUDIENCE = "auth-service-session"
SESSION_TTL_MIN = 30  # longer than access token — "logged in to auth server"


def create_access_token(
    *,
    sub: str,
    scope: str = "",
    roles: list[str] | None = None,
) -> str:
    """Build and sign a JWT access token.

    Claims follow the schema in auth-design-notes-week3.md:
    sub, iss, aud, exp, iat, jti, scope, roles.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_TTL_MIN),
        "iat": now,
        "jti": str(uuid.uuid4()),
        "scope": scope,
        "roles": roles or ["user"],
    }
    return jwt.encode(payload, _private_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Verify signature and claims, return the payload.

    Pins algorithm to ES256 to prevent alg:none and alg-switching attacks.
    Validates exp, iss, and aud automatically via PyJWT options.

    Raises jwt.ExpiredSignatureError, jwt.InvalidTokenError on failure.
    """
    return jwt.decode(
        token,
        _public_key,
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={"require": ["sub", "exp", "iat", "jti"]},
    )


# ---------------------------------------------------------------------------
# Session tokens (browser cookies for /oauth/authorize)
# ---------------------------------------------------------------------------
# Same ES256 key pair, different audience. A session JWT proves "this user
# authenticated with the auth server" — it is NOT an API access token.


def create_session_token(*, sub: str) -> str:
    """Build and sign a session JWT for the session cookie."""
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "iss": ISSUER,
        "aud": SESSION_AUDIENCE,
        "exp": now + timedelta(minutes=SESSION_TTL_MIN),
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _private_key, algorithm=ALGORITHM)


def decode_session_token(token: str) -> dict:
    """Verify a session JWT. Pins audience to SESSION_AUDIENCE.

    Raises jwt.ExpiredSignatureError, jwt.InvalidTokenError on failure.
    """
    return jwt.decode(
        token,
        _public_key,
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        audience=SESSION_AUDIENCE,
        options={"require": ["sub", "exp", "iat", "jti"]},
    )


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------
# Refresh tokens use the same ES256 key pair but a DIFFERENT audience claim.
# This prevents a refresh JWT from being accepted as an access token or
# session token, even though all three share the same signing key.
#
# WHY JWT (not opaque)?  This codebase is stateless-first — the blacklist
# handles revocation.  A JWT refresh token avoids a new storage layer
# while still being cryptographically verifiable.
#
# WHY no roles/scope in refresh tokens?  When the client refreshes, the
# endpoint looks up the user's *current* roles from the repo.  This means
# role changes (e.g. admin promotion or revocation) take effect on the
# next refresh (~15 min worst case), not after the 7-day refresh TTL.

REFRESH_AUDIENCE = "auth-service-refresh"
REFRESH_TOKEN_TTL_DAYS = 7


def create_refresh_token(*, sub: str) -> str:
    """Build and sign a refresh token JWT.

    Contains only identity (sub) — no roles or scope.  The refresh
    endpoint will look up current roles from the user repo when issuing
    a new access token.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "iss": ISSUER,
        "aud": REFRESH_AUDIENCE,
        "exp": now + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _private_key, algorithm=ALGORITHM)


def decode_refresh_token(token: str) -> dict:
    """Verify a refresh token JWT. Pins audience to REFRESH_AUDIENCE.

    Raises jwt.ExpiredSignatureError, jwt.InvalidTokenError on failure.
    """
    return jwt.decode(
        token,
        _public_key,
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        audience=REFRESH_AUDIENCE,
        options={"require": ["sub", "exp", "iat", "jti"]},
    )
