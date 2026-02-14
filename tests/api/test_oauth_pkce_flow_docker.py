"""OAuth 2.1 Authorization Code + PKCE — live Docker integration test.

This is the HTTP-over-the-wire counterpart of test_oauth_pkce_flow.py.
Instead of FastAPI's in-process TestClient, it uses httpx to drive the
full PKCE handshake against a **running Docker container** on port 8000.

Prerequisites:
  1. Build and start the container:
       docker build -f docker/Dockerfile --target runtime -t auth-service:dev .
       docker run --rm --name auth-service-dev -p 8000:8000 \
         --env-file .env auth-service:dev

  2. Run only these tests:
       pytest -m docker -v --log-cli-level=INFO

Flow:
  0. Register client — POST /oauth/clients (dev-only endpoint)
  1. Login           — POST /login to get a session cookie
  2. Authorize       — GET /oauth/authorize → 302 redirect with code
  3. Token           — POST /oauth/token (code + verifier) → access_token
  4. Resource        — GET /users with Bearer token → 200
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.services import pkce_service

logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

CLIENT_ID = "docker-test-client"
REDIRECT_URI = "http://localhost/callback"
SCOPE = "openid"

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test-password"

pytestmark = pytest.mark.docker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_client(client: httpx.Client) -> None:
    """Register a test OAuth client via the dev-only endpoint."""
    resp = client.post(
        "/oauth/clients",
        json={
            "client_id": CLIENT_ID,
            "redirect_uris": [REDIRECT_URI],
            "is_public": True,
            "allowed_scopes": ["openid"],
        },
    )
    assert resp.status_code == 201, f"Client registration failed: {resp.text}"
    logger.info("CLIENT: registered OAuth client via POST /oauth/clients")


def _login(client: httpx.Client) -> None:
    """Authenticate via POST /login so the session cookie is set."""
    resp = client.post(
        "/login",
        data={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "next": "/",
        },
    )
    assert resp.status_code in (200, 302), f"Login failed: {resp.status_code}"
    logger.info("CLIENT: session cookie obtained via /login")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pkce_flow_happy_path() -> None:
    """Complete PKCE handshake: register → login → authorize → token → resource."""
    with httpx.Client(base_url=BASE_URL, follow_redirects=False) as client:
        # ── Phase 0: Register OAuth client ──────────────────────────
        _register_client(client)

        # ── Phase 1: Login ──────────────────────────────────────────
        _login(client)

        # ── Phase 2: Generate PKCE material ─────────────────────────
        code_verifier = pkce_service.generate_code_verifier()
        code_challenge = pkce_service.compute_code_challenge(code_verifier)
        logger.info("CLIENT: generated PKCE verifier + challenge (S256)")

        # ── Phase 3: Authorization Request ──────────────────────────
        auth_resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "scope": SCOPE,
                "state": "xyz-anti-csrf",
            },
        )
        assert auth_resp.status_code == 302, (
            f"Expected redirect, got {auth_resp.status_code}: {auth_resp.text}"
        )

        location = auth_resp.headers["location"]
        parsed = urlparse(location)
        assert parsed.netloc == "localhost", f"Unexpected redirect target: {location}"
        query = parse_qs(parsed.query)
        assert "code" in query, f"No code in redirect: {location}"
        assert query.get("state") == ["xyz-anti-csrf"], "state mismatch"
        auth_code = query["code"][0]
        logger.info("CLIENT: received authorization code from redirect")

        # ── Phase 4: Token Exchange ─────────────────────────────────
        token_resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": code_verifier,
            },
        )
        assert token_resp.status_code == 200, (
            f"Token exchange failed: {token_resp.text}"
        )
        token_data = token_resp.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["expires_in"] > 0
        access_token = token_data["access_token"]
        logger.info("CLIENT: received access token")

        # ── Phase 5: Access Protected Resource ──────────────────────
        resource_resp = client.get(
            "/users",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resource_resp.status_code == 200, (
            f"Protected resource failed: {resource_resp.text}"
        )
        logger.info("CLIENT: accessed protected resource with OAuth token  ✓")


def test_authorize_redirects_to_login_without_session() -> None:
    """GET /oauth/authorize without a session cookie → redirect to /login."""
    with httpx.Client(base_url=BASE_URL, follow_redirects=False) as client:
        _register_client(client)

        verifier = pkce_service.generate_code_verifier()
        challenge = pkce_service.compute_code_challenge(verifier)

        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert location.startswith("/login?next="), (
            f"Expected redirect to /login, got: {location}"
        )


def test_replay_rejected() -> None:
    """Using the same authorization code twice must fail."""
    with httpx.Client(base_url=BASE_URL, follow_redirects=False) as client:
        _register_client(client)
        _login(client)

        verifier = pkce_service.generate_code_verifier()
        challenge = pkce_service.compute_code_challenge(verifier)

        auth_resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        code = parse_qs(urlparse(auth_resp.headers["location"]).query)["code"][0]

        # First exchange — should succeed
        first = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": verifier,
            },
        )
        assert first.status_code == 200

        # Replay — must fail
        replay = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": verifier,
            },
        )
        assert replay.status_code == 400
        assert "already used" in replay.json()["detail"]


def test_wrong_verifier_rejected() -> None:
    """A code_verifier that doesn't match the challenge must fail."""
    with httpx.Client(base_url=BASE_URL, follow_redirects=False) as client:
        _register_client(client)
        _login(client)

        verifier = pkce_service.generate_code_verifier()
        challenge = pkce_service.compute_code_challenge(verifier)

        auth_resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        code = parse_qs(urlparse(auth_resp.headers["location"]).query)["code"][0]

        wrong_verifier = pkce_service.generate_code_verifier()
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": wrong_verifier,
            },
        )
        assert resp.status_code == 400
        assert "PKCE verification failed" in resp.json()["detail"]
