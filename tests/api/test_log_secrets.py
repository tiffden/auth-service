"""Assert that passwords, tokens, and secrets never appear in log output.

These tests exercise endpoints that handle sensitive data and verify
the log records contain no leaked secrets.
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app.api import login as login_module
from app.main import app
from app.models.user import User
from app.services import auth_service

TEST_EMAIL = "secrets-test@example.com"
TEST_PASSWORD = "super-s3cret-p@ssw0rd!"


def _reset() -> None:
    login_module.user_repo._by_email.clear()
    login_module.user_repo._by_id.clear()


def _seed_user() -> None:
    if login_module.user_repo.get_by_email(TEST_EMAIL) is not None:
        return
    login_module.user_repo.add(
        User.new(
            email=TEST_EMAIL,
            password_hash=auth_service.hash_password(TEST_PASSWORD),
        )
    )


def test_failed_login_does_not_log_password(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """POST /login with wrong password — password must not appear in logs."""
    client = TestClient(app, follow_redirects=False)
    _reset()
    _seed_user()

    with caplog.at_level(logging.DEBUG):
        client.post(
            "/login",
            data={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "next": "/",
            },
        )

    all_log_text = " ".join(caplog.messages)
    assert TEST_PASSWORD not in all_log_text, "Password found in log output!"


def test_successful_login_does_not_log_password(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """POST /login success — password must not appear in logs."""
    client = TestClient(app, follow_redirects=False)
    _reset()
    _seed_user()

    with caplog.at_level(logging.DEBUG):
        client.post(
            "/login",
            data={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "next": "/",
            },
        )

    all_log_text = " ".join(caplog.messages)
    assert TEST_PASSWORD not in all_log_text, "Password found in log output!"


def test_successful_login_does_not_log_session_jwt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """POST /login success — session JWT must not appear in logs."""
    client = TestClient(app, follow_redirects=False)
    _reset()
    _seed_user()

    with caplog.at_level(logging.DEBUG):
        resp = client.post(
            "/login",
            data={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "next": "/",
            },
        )

    session_jwt = resp.cookies.get("session")
    assert session_jwt is not None

    all_log_text = " ".join(caplog.messages)
    assert session_jwt not in all_log_text, "Session JWT found in log output!"


def test_token_exchange_does_not_log_code_verifier(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """POST /oauth/token — code_verifier must not appear in logs."""
    from urllib.parse import parse_qs, urlparse

    from app.api import oauth
    from app.models.oauth_client import OAuthClient
    from app.services import pkce_service

    client = TestClient(app, follow_redirects=False)
    _reset()
    _seed_user()
    oauth.auth_code_repo._by_code_hash.clear()
    oauth.client_repo._by_client_id.clear()

    cid = "secrets-test-client"
    ruri = "http://localhost/callback"
    oauth.client_repo.register(
        OAuthClient.new(
            client_id=cid,
            redirect_uris=(ruri,),
            is_public=True,
            allowed_scopes=frozenset(["openid"]),
        )
    )

    # Login
    client.post(
        "/login",
        data={"email": TEST_EMAIL, "password": TEST_PASSWORD, "next": "/"},
    )

    verifier = pkce_service.generate_code_verifier()
    challenge = pkce_service.compute_code_challenge(verifier)

    # Authorize
    auth_resp = client.get(
        "/oauth/authorize",
        params={
            "client_id": cid,
            "redirect_uri": ruri,
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
    )
    code = parse_qs(urlparse(auth_resp.headers["location"]).query)["code"][0]

    # Token exchange — capture logs
    with caplog.at_level(logging.DEBUG):
        client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": ruri,
                "client_id": cid,
                "code_verifier": verifier,
            },
        )

    all_log_text = " ".join(caplog.messages)
    assert verifier not in all_log_text, "code_verifier found in log output!"
