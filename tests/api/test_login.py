"""Login endpoint tests — session cookie issuance and validation."""

from __future__ import annotations

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
