from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.models.authorization_code import AuthorizationCode
from app.repos.auth_code_repo import InMemoryAuthCodeRepo
from app.repos.oauth_client_repo import InMemoryOAuthClientRepo
from app.services import pkce_service

# ---------------------------------------------------------------------------
# Authorization Server — OAuth 2.1 Authorization Code + PKCE
#
# Endpoints:
#   GET  /oauth/authorize  — issue authorization code, redirect back to client
#   POST /oauth/token       — exchange code + code_verifier for access token
#
# Future:
#   /.well-known/openid-configuration  (OIDC discovery)
#   /jwks.json                          (asymmetric key publication)
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

router = APIRouter(tags=["oauth"])

# Module-level singletons (will move to DI / app state later)
auth_code_repo = InMemoryAuthCodeRepo()
client_repo = InMemoryOAuthClientRepo()

TOKEN_TTL_MIN = 30
TOKEN_SIGNING_SECRET = os.getenv("TOKEN_SIGNING_SECRET", "dev-only-secret-change-me")
AUTH_CODE_TTL_SEC = 600  # 10 minutes — intentionally generous for stub

# TRADE-OFF: Authorization codes should be short-lived (30-120s in production).
# We use 600s here so manual debugging is comfortable. Tighten before shipping.


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ========================== GET /oauth/authorize ==========================
# The client redirects the user's browser here. We validate everything, then
# redirect back to the client's redirect_uri with an authorization code.


@router.get("/oauth/authorize")
def authorize(
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query(...),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query(...),
    scope: str = Query("openid"),
    state: str | None = Query(None),
) -> RedirectResponse:
    logger.info(
        "PKCE FLOW [authorize] step 1: received authorization request  "
        "client_id=%s redirect_uri=%s scope=%s",
        client_id,
        redirect_uri,
        scope,
    )

    # --- Validate response_type ------------------------------------------------
    # FAIL POINT: response_type must be "code" (OAuth 2.1 drops implicit grant)
    if response_type != "code":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "response_type must be 'code'")
    logger.info("PKCE FLOW [authorize] step 2: response_type=code  ✓")

    # --- Validate client -------------------------------------------------------
    # FAIL POINT: unknown client_id → 400 (never redirect to an unvalidated URI)
    client = client_repo.get(client_id)
    if client is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown client_id")
    logger.info("PKCE FLOW [authorize] step 3: client_id recognized  ✓")

    # --- Validate redirect_uri -------------------------------------------------
    # FAIL POINT: redirect_uri must exactly match one of the client's registered URIs.
    # TRADE-OFF: exact-match is stricter than substring/prefix matching, but it's
    # what OAuth 2.1 requires. Wildcard or localhost exceptions are common pitfalls
    # that open redirect vulnerabilities.
    if redirect_uri not in client.redirect_uris:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "redirect_uri not registered")
    logger.info("PKCE FLOW [authorize] step 4: redirect_uri matches registration  ✓")

    # --- Validate PKCE parameters ----------------------------------------------
    # FAIL POINT: code_challenge must be present and method must be S256.
    # OAuth 2.1 requires PKCE for all public clients; "plain" method is banned.
    if code_challenge_method != "S256":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "code_challenge_method must be S256"
        )
    if not code_challenge or len(code_challenge) < 43:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid code_challenge")
    logger.info("PKCE FLOW [authorize] step 5: PKCE params valid (S256)  ✓")

    # --- Authenticate the user -------------------------------------------------
    # FAIL POINT: user not authenticated → show login page (not implemented yet).
    # STUB: hardcoded user_id for skeleton. In production this would come from
    # a session cookie or an upstream identity provider.
    user_id = "test-user"
    logger.info(
        "PKCE FLOW [authorize] step 6: user authenticated  user_id=%s  (stub)", user_id
    )

    # --- Generate authorization code -------------------------------------------
    # Use high-entropy random bytes. We store only the hash — if the code leaks in
    # logs or a database dump, the raw code is still unknown.
    # TRADE-OFF: hashing the code adds a sha256 call per /token request. This is
    # negligible (~1µs) compared to the network round-trip.
    raw_code = secrets.token_urlsafe(32)
    code_hash = hashlib.sha256(raw_code.encode()).hexdigest()
    logger.info(
        "PKCE FLOW [authorize] step 7: authorization code generated  (hash=%s…)",
        code_hash[:12],
    )

    # --- Store code metadata ---------------------------------------------------
    expires_at = int(
        (datetime.now(UTC) + timedelta(seconds=AUTH_CODE_TTL_SEC)).timestamp()
    )
    record = AuthorizationCode.new(
        code_hash=code_hash,
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        user_id=user_id,
        expires_at=expires_at,
    )
    auth_code_repo.create(record)
    logger.info(
        "PKCE FLOW [authorize] step 8: code metadata stored  expires_at=%s", expires_at
    )

    # --- Redirect back to client -----------------------------------------------
    params = {"code": raw_code}
    if state is not None:
        params["state"] = state
    redirect_url = f"{redirect_uri}?{urlencode(params)}"
    logger.info(
        "PKCE FLOW [authorize] step 9: redirecting to client  uri=%s", redirect_uri
    )
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


# ========================== POST /oauth/token =============================
# The client sends the authorization code + code_verifier here. We verify
# everything and return an access token.


@router.post("/oauth/token", response_model=Token)
def exchange_token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    code_verifier: str = Form(...),
) -> Token:
    logger.info(
        "PKCE FLOW [token] step 1: received token exchange request  "
        "client_id=%s grant_type=%s",
        client_id,
        grant_type,
    )
    # NOTE: Never log code_verifier — it is a secret the client proves possession of.

    # --- Validate grant_type ---------------------------------------------------
    # FAIL POINT: only "authorization_code" is accepted on this endpoint.
    if grant_type != "authorization_code":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "grant_type must be authorization_code"
        )
    logger.info("PKCE FLOW [token] step 2: grant_type valid  ✓")

    # --- Lookup authorization code by hash -------------------------------------
    # TRADE-OFF: We hash the code before lookup so we never store raw codes.
    # If the DB is compromised, attackers can't replay captured codes.
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    record = auth_code_repo.get_by_code_hash(code_hash)
    # FAIL POINT: code not found → either invalid, already consumed, or fabricated.
    if record is None:
        logger.warning("PKCE FLOW [token] FAIL: authorization code not found")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid authorization code")
    logger.info("PKCE FLOW [token] step 3: authorization code found  ✓")

    # --- Check code not expired ------------------------------------------------
    # FAIL POINT: expired codes must be rejected even if otherwise valid.
    # TRADE-OFF: clock skew between servers could cause false rejections in
    # distributed setups. A small grace window (e.g., 5s) may be needed later.
    now_ts = int(datetime.now(UTC).timestamp())
    if now_ts > record.expires_at:
        logger.warning("PKCE FLOW [token] FAIL: authorization code expired")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "authorization code expired")
    logger.info("PKCE FLOW [token] step 4: code not expired  ✓")

    # --- Consume code (atomic single-use) --------------------------------------
    # FAIL POINT: code already used → must reject. OAuth 2.1 §4.1.2 requires
    # single-use codes. If a code is replayed, the spec recommends revoking any
    # tokens issued from that code (defense-in-depth, not implemented in stub).
    consumed = auth_code_repo.mark_used(code_hash)
    if consumed is None:
        logger.warning(
            "PKCE FLOW [token] FAIL: authorization code already used (replay attempt)"
        )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "authorization code already used"
        )
    logger.info("PKCE FLOW [token] step 5: code consumed (single-use enforced)  ✓")

    # --- Verify client_id matches stored ---------------------------------------
    # FAIL POINT: code was issued to a different client → code theft / confusion.
    if record.client_id != client_id:
        logger.warning("PKCE FLOW [token] FAIL: client_id mismatch")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "client_id mismatch")
    logger.info("PKCE FLOW [token] step 6: client_id matches  ✓")

    # --- Verify redirect_uri matches stored ------------------------------------
    # FAIL POINT: redirect_uri must exactly match what was sent in /authorize.
    if record.redirect_uri != redirect_uri:
        logger.warning("PKCE FLOW [token] FAIL: redirect_uri mismatch")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "redirect_uri mismatch")
    logger.info("PKCE FLOW [token] step 7: redirect_uri matches  ✓")

    # --- PKCE verification -----------------------------------------------------
    # The core of PKCE: recompute challenge from the verifier the client sends
    # now, and compare it to the challenge the client committed to in /authorize.
    # FAIL POINT: mismatch means either the wrong verifier, or an attacker
    # intercepted the code but doesn't have the original verifier.
    # TRADE-OFF: verify_code_challenge uses constant-time comparison. This
    # prevents timing side-channels but is ~negligible overhead.
    if not pkce_service.verify_code_challenge(code_verifier, record.code_challenge):
        logger.warning("PKCE FLOW [token] FAIL: PKCE verification failed")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PKCE verification failed")
    logger.info(
        "PKCE FLOW [token] step 8: PKCE verified "
        "- client proved possession of verifier  ✓"
    )

    # --- Issue access token ----------------------------------------------------
    # STUB: reusing the existing HMAC token format. Replace with real JWT (RFC 7519)
    # using asymmetric signing (EdDSA/ES256) in the next iteration.
    expires_at = datetime.now(UTC) + timedelta(minutes=TOKEN_TTL_MIN)
    exp_ts = int(expires_at.timestamp())
    token_core = f"user:{record.user_id}|exp:{exp_ts}"
    sig = hmac.new(
        TOKEN_SIGNING_SECRET.encode(),
        token_core.encode(),
        hashlib.sha256,
    ).hexdigest()
    access_token = f"{token_core}|sig:{sig}"

    logger.info(
        "PKCE FLOW [token] step 9: access token issued  user=%s expires_in=%d min  ✓",
        record.user_id,
        TOKEN_TTL_MIN,
    )
    return Token(
        access_token=access_token, token_type="bearer", expires_in=TOKEN_TTL_MIN * 60
    )
