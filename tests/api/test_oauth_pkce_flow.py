"""OAuth 2.1 Authorization Code + PKCE — full flow test.

This test acts as the OAuth **client**, driving every step of the handshake
against the authorization server (app/api/oauth.py) and finally using the
issued token to access a protected resource.

Flow:
  1. Setup     — register a public client, generate PKCE verifier + challenge
  2. Authorize — GET /oauth/authorize → 302 redirect with code
  3. Token     — POST /oauth/token (code + verifier) → access_token
  4. Resource  — GET /users with Bearer token → 200
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.api import oauth
from app.main import app
from app.models.oauth_client import OAuthClient
from app.services import pkce_service

logger = logging.getLogger(__name__)

CLIENT_ID = "test-client-id"
REDIRECT_URI = "http://localhost/callback"
SCOPE = "openid"


def _register_test_client() -> None:
    """Seed the in-memory client repo with a public test client."""
    oauth.client_repo.register(
        OAuthClient.new(
            client_id=CLIENT_ID,
            redirect_uris=(REDIRECT_URI,),
            is_public=True,
            allowed_scopes=frozenset(["openid"]),
        )
    )


def _reset_oauth_state() -> None:
    """Clear module-level repos between tests so runs are isolated."""
    oauth.auth_code_repo._by_code_hash.clear()
    oauth.client_repo._by_client_id.clear()


def test_pkce_flow_happy_path(caplog: pytest.LogCaptureFixture) -> None:
    """Complete PKCE handshake: authorize → token → access resource."""
    client = TestClient(app, follow_redirects=False)
    _reset_oauth_state()

    # ── Phase 1: Setup ─────────────────────────────────────────────
    # The client registers itself and generates PKCE material.
    # In production the client would be pre-registered; the verifier
    # is generated fresh per authorization request.
    _register_test_client()
    code_verifier = pkce_service.generate_code_verifier()
    code_challenge = pkce_service.compute_code_challenge(code_verifier)
    logger.info("CLIENT: generated PKCE verifier + challenge (S256)")

    # ── Phase 2: Authorization Request ─────────────────────────────
    # The client redirects the user's browser to GET /oauth/authorize
    # with the code_challenge. The server validates everything, then
    # redirects back with an authorization code.
    with caplog.at_level(logging.INFO, logger="app.api.oauth"):
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
        f"Expected redirect, got {auth_resp.status_code}"
    )

    # Extract the authorization code from the redirect Location header
    location = auth_resp.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert "code" in query, f"No code in redirect: {location}"
    assert query.get("state") == ["xyz-anti-csrf"], "state mismatch"
    auth_code = query["code"][0]
    logger.info("CLIENT: received authorization code from redirect")

    # Verify the server logged all 9 authorize steps
    authorize_logs = [
        r.message for r in caplog.records if "PKCE FLOW [authorize]" in r.message
    ]
    assert len(authorize_logs) == 9, (
        f"Expected 9 authorize log steps, got {len(authorize_logs)}"
    )

    # ── Phase 3: Token Exchange ────────────────────────────────────
    # The client sends the authorization code + code_verifier to
    # POST /oauth/token. The server verifies PKCE and issues a token.
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.api.oauth"):
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

    assert token_resp.status_code == 200, f"Token exchange failed: {token_resp.text}"
    token_data = token_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["expires_in"] > 0
    access_token = token_data["access_token"]
    logger.info("CLIENT: received access token")

    # Verify the server logged all 9 token steps
    token_logs = [r.message for r in caplog.records if "PKCE FLOW [token]" in r.message]
    assert len(token_logs) == 9, f"Expected 9 token log steps, got {len(token_logs)}"

    # ── Phase 4: Access Protected Resource ─────────────────────────
    # The client uses the access token to call a protected endpoint.
    # This proves the full circle: authorize → token → use.
    resource_resp = client.get(
        "/users",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resource_resp.status_code == 200, (
        f"Protected resource failed: {resource_resp.text}"
    )
    logger.info("CLIENT: accessed protected resource with OAuth token  ✓")


def test_replay_rejected() -> None:
    """Using the same authorization code twice must fail."""
    client = TestClient(app, follow_redirects=False)
    _reset_oauth_state()
    _register_test_client()

    verifier = pkce_service.generate_code_verifier()
    challenge = pkce_service.compute_code_challenge(verifier)

    # Get a code
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
    client = TestClient(app, follow_redirects=False)
    _reset_oauth_state()
    _register_test_client()

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

    # Use a different verifier — simulates attacker who stole the code
    # but doesn't have the original verifier
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
