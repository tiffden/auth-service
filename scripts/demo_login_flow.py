"""Demo: walk the login → OAuth PKCE flow using FastAPI TestClient.

Run with:
    python scripts/demo_login_flow.py
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.api import login as login_module
from app.api import oauth
from app.main import app
from app.models.oauth_client import OAuthClient
from app.models.user import User
from app.services import auth_service, pkce_service

CLIENT_ID = "demo-client"
REDIRECT_URI = "http://localhost/callback"
TEST_EMAIL = "demo@example.com"
TEST_PASSWORD = "demo-pass"


def main() -> None:
    client = TestClient(app, follow_redirects=False)

    # ── Seed data ───────────────────────────────────────────────────
    oauth.client_repo.register(
        OAuthClient.new(
            client_id=CLIENT_ID,
            redirect_uris=(REDIRECT_URI,),
            is_public=True,
            allowed_scopes=frozenset(["openid"]),
        )
    )
    if login_module.user_repo.get_by_email(TEST_EMAIL) is None:
        login_module.user_repo.add(
            User.new(
                email=TEST_EMAIL,
                password_hash=auth_service.hash_password(TEST_PASSWORD),
            )
        )

    # ── Step 1: GET /login ──────────────────────────────────────────
    r = client.get("/login")
    print(f"1. GET  /login             → {r.status_code}  (form HTML)")

    # ── Step 2: POST /login (bad creds) ─────────────────────────────
    r = client.post(
        "/login",
        data={
            "email": TEST_EMAIL,
            "password": "wrong",
            "next": "/",
        },
    )
    print(f"2. POST /login (bad creds) → {r.status_code}  (rejected)")

    # ── Step 3: POST /login (good creds) ────────────────────────────
    r = client.post(
        "/login",
        data={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "next": "/",
        },
    )
    print(f"3. POST /login (good)      → {r.status_code}  (session cookie set)")
    assert r.cookies.get("session"), "no session cookie!"

    # ── Step 4: GET /oauth/authorize without session ────────────────
    fresh = TestClient(app, follow_redirects=False)  # no cookie
    verifier = pkce_service.generate_code_verifier()
    challenge = pkce_service.compute_code_challenge(verifier)
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": "openid",
        "state": "demo-state",
    }
    r = fresh.get("/oauth/authorize", params=params)
    print(
        f"4. GET  /oauth/authorize (no session) → {r.status_code}  "
        f"Location: {r.headers.get('location', '')[:60]}..."
    )

    # ── Step 5: GET /oauth/authorize with session ───────────────────
    r = client.get("/oauth/authorize", params=params)
    location = r.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    code = query["code"][0]
    state = query.get("state", [""])[0]
    print(
        f"5. GET  /oauth/authorize (with session) → {r.status_code}  "
        f"code={code[:12]}…  state={state}"
    )

    # ── Step 6: POST /oauth/token ───────────────────────────────────
    r = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": verifier,
        },
    )
    token_data = r.json()
    access_token = token_data["access_token"]
    print(
        f"6. POST /oauth/token       → {r.status_code}  "
        f"token={access_token[:20]}…  "
        f"expires_in={token_data['expires_in']}s"
    )

    # ── Step 7: GET /users (protected) ──────────────────────────────
    r = client.get("/users", headers={"Authorization": f"Bearer {access_token}"})
    print(f"7. GET  /users (bearer)    → {r.status_code}  {r.json()}")

    # ── Step 8: replay the code ─────────────────────────────────────
    r = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": verifier,
        },
    )
    print(f"8. POST /oauth/token (replay) → {r.status_code}  {r.json()['detail']}")

    print("\nAll steps completed.")


if __name__ == "__main__":
    main()
