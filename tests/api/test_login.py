"""Login endpoint tests — session cookie issuance and validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from fastapi.testclient import TestClient

from app.api import login as login_module
from app.main import app
from app.models.user import User
from app.services import auth_service, token_service

TEST_EMAIL = "login-test@example.com"
TEST_PASSWORD = "s3cure-pass"


def _reset_login_state() -> None:
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


# ---- GET /login ----


def test_login_page_renders() -> None:
    """GET /login returns 200 with an HTML form."""
    client = TestClient(app)
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert '<form method="post"' in resp.text
    assert 'name="email"' in resp.text
    assert 'name="password"' in resp.text


def test_login_page_preserves_next() -> None:
    """The ?next param is embedded as a hidden field in the form."""
    client = TestClient(app)
    resp = client.get("/login", params={"next": "/oauth/authorize?client_id=x"})
    assert resp.status_code == 200
    assert "/oauth/authorize" in resp.text


# ---- POST /login ----


def test_login_success_sets_cookie() -> None:
    """Valid credentials → 302 redirect + session cookie set."""
    client = TestClient(app, follow_redirects=False)
    _reset_login_state()
    _seed_user()

    resp = client.post(
        "/login",
        data={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "next": "/oauth/authorize?foo=bar",
        },
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/oauth/authorize?foo=bar"

    # Verify session cookie is present and is a valid JWT
    cookie = resp.cookies.get("session")
    assert cookie is not None, "session cookie not set"
    claims = token_service.decode_session_token(cookie)
    assert "sub" in claims
    assert claims["iss"] == token_service.ISSUER
    assert claims["aud"] == token_service.SESSION_AUDIENCE


def test_login_failure_returns_401() -> None:
    """Bad credentials → 401 with error message in HTML."""
    client = TestClient(app, follow_redirects=False)
    _reset_login_state()
    _seed_user()

    resp = client.post(
        "/login",
        data={
            "email": TEST_EMAIL,
            "password": "wrong-password",
            "next": "/",
        },
    )
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.text


def test_login_failure_no_cookie() -> None:
    """Failed login must not set a session cookie."""
    client = TestClient(app, follow_redirects=False)
    _reset_login_state()
    _seed_user()

    resp = client.post(
        "/login",
        data={
            "email": TEST_EMAIL,
            "password": "wrong",
            "next": "/",
        },
    )
    assert resp.cookies.get("session") is None


def test_login_unknown_user_returns_401() -> None:
    """Non-existent email → 401."""
    client = TestClient(app, follow_redirects=False)
    _reset_login_state()

    resp = client.post(
        "/login",
        data={
            "email": "nobody@example.com",
            "password": "anything",
            "next": "/",
        },
    )
    assert resp.status_code == 401


# ---- inactive account ----


def test_login_inactive_user_returns_401() -> None:
    """Inactive/locked account → 401, even with correct password."""
    client = TestClient(app, follow_redirects=False)
    _reset_login_state()

    from dataclasses import replace

    user = User.new(
        email=TEST_EMAIL,
        password_hash=auth_service.hash_password(TEST_PASSWORD),
    )
    inactive = replace(user, is_active=False)
    login_module.user_repo.add(inactive)

    resp = client.post(
        "/login",
        data={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "next": "/",
        },
    )
    assert resp.status_code == 401


# ---- session cookie edge cases ----


def _authorize_params() -> dict[str, str]:
    """Minimal valid /oauth/authorize query params for session tests."""
    from app.api import oauth
    from app.models.oauth_client import OAuthClient
    from app.services import pkce_service

    cid = "session-test-client"
    ruri = "http://localhost/callback"
    if oauth.client_repo.get(cid) is None:
        oauth.client_repo.register(
            OAuthClient.new(
                client_id=cid,
                redirect_uris=(ruri,),
                is_public=True,
                allowed_scopes=frozenset(["openid"]),
            )
        )
    verifier = pkce_service.generate_code_verifier()
    challenge = pkce_service.compute_code_challenge(verifier)
    return {
        "client_id": cid,
        "redirect_uri": ruri,
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }


def test_expired_session_cookie_redirects_to_login() -> None:
    """An expired session cookie should be treated as unauthenticated."""
    client = TestClient(app, follow_redirects=False)

    # Mint a session JWT that expired 1 minute ago
    now = datetime.now(UTC)
    payload = {
        "sub": "test-user",
        "iss": token_service.ISSUER,
        "aud": token_service.SESSION_AUDIENCE,
        "exp": now - timedelta(minutes=1),
        "iat": now - timedelta(minutes=2),
        "jti": str(uuid.uuid4()),
    }
    expired_jwt = pyjwt.encode(payload, token_service._private_key, algorithm="ES256")
    client.cookies.set("session", expired_jwt)

    resp = client.get("/oauth/authorize", params=_authorize_params())
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("/login?next=")


def test_tampered_session_cookie_redirects_to_login() -> None:
    """A session cookie with a corrupted signature → unauthenticated."""
    client = TestClient(app, follow_redirects=False)

    valid_jwt = token_service.create_session_token(sub="test-user")
    # Corrupt the signature (last segment)
    parts = valid_jwt.split(".")
    parts[2] = parts[2][::-1]
    tampered = ".".join(parts)
    client.cookies.set("session", tampered)

    resp = client.get("/oauth/authorize", params=_authorize_params())
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("/login?next=")


def test_access_token_as_session_cookie_rejected() -> None:
    """An access token (aud=auth-service) must not work as a session cookie.

    The session cookie requires aud=auth-service-session. Using an access
    token should fail audience validation.
    """
    client = TestClient(app, follow_redirects=False)

    # Mint a valid access token (wrong audience for session)
    access_jwt = token_service.create_access_token(sub="test-user")
    client.cookies.set("session", access_jwt)

    resp = client.get("/oauth/authorize", params=_authorize_params())
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("/login?next=")
