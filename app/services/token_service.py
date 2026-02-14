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
