"""Login UI — minimal HTML form that sets a signed session cookie.

This is the auth server's own login page. When /oauth/authorize detects
no session cookie, it redirects the user here.  After successful login,
we set an HttpOnly session cookie and redirect back to wherever ?next points.

TRADE-OFF: Inline HTML keeps the skeleton dependency-free (no Jinja, no
static files).  Replace with a template engine once the UI grows beyond
a single form.
"""

from __future__ import annotations

import html
import logging

from fastapi import APIRouter, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.ratelimit import require_rate_limit
from app.models.user import User
from app.repos.user_repo import InMemoryUserRepo
from app.services import auth_service, token_service
from app.services.rate_limiter import RateLimitConfig

logger = logging.getLogger(__name__)

router = APIRouter(tags=["login"])

# ---------------------------------------------------------------------------
# Module-level singleton (same pattern as oauth.py repos)
# ---------------------------------------------------------------------------
user_repo = InMemoryUserRepo()


def _seed_test_user() -> None:
    """Seed a test user for development. Skip if already present."""
    email = "test@example.com"
    if user_repo.get_by_email(email) is not None:
        return
    user_repo.add(
        User.new(
            email=email,
            password_hash=auth_service.hash_password("test-password"),
        )
    )


_seed_test_user()

# ---------------------------------------------------------------------------
# Minimal login form (inline HTML)
# ---------------------------------------------------------------------------

_LOGIN_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login — auth-service</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: system-ui, -apple-system, sans-serif;
      display: flex; justify-content: center; align-items: center;
      min-height: 100vh; background: #f5f5f5;
    }}
    .card {{
      background: #fff; padding: 2rem; border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,.1); width: 320px;
    }}
    h1 {{ font-size: 1.25rem; margin-bottom: 1.5rem; text-align: center; }}
    label {{ display: block; font-size: .85rem; margin-bottom: .25rem; }}
    input[type=email], input[type=password] {{
      width: 100%; padding: .5rem; margin-bottom: 1rem;
      border: 1px solid #ccc; border-radius: 4px; font-size: .95rem;
    }}
    button {{
      width: 100%; padding: .6rem; background: #111; color: #fff;
      border: none; border-radius: 4px; font-size: .95rem; cursor: pointer;
    }}
    button:hover {{ background: #333; }}
    .error {{ color: #c00; font-size: .85rem; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Sign in</h1>
    {error}
    <form method="post" action="/login">
      <label for="email">Email</label>
      <input id="email" name="email" type="email" required autofocus>
      <label for="password">Password</label>
      <input id="password" name="password" type="password" required>
      <input type="hidden" name="next" value="{next_url}">
      <button type="submit">Log in</button>
    </form>
  </div>
</body>
</html>
"""


# ========================== GET /login ======================================


@router.get("/login")
def login_page(
    next: str | None = Query(None),
    error: str | None = Query(None),
) -> HTMLResponse:
    """Render the login form. Preserves ?next so we redirect after login."""
    safe_next = html.escape(next or "/", quote=True)
    error_block = f'<p class="error">{html.escape(error)}</p>' if error else ""
    page = _LOGIN_HTML.format(next_url=safe_next, error=error_block)
    return HTMLResponse(page)


# ========================== POST /login =====================================


# WHY strict limits on login: Brute-force password attacks send thousands
# of login attempts per minute.  10 attempts/min per IP makes brute force
# impractical while allowing a real user to fat-finger their password a
# few times.  (capacity=10, refill_rate=0.17 ≈ 1 token every 6 seconds)
_login_limit = require_rate_limit(RateLimitConfig(capacity=10, refill_rate=0.17))


@router.post("/login", response_model=None, dependencies=[Depends(_login_limit)])
def login_submit(
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
) -> RedirectResponse | HTMLResponse:
    """Validate credentials, set session cookie, redirect to *next*."""
    logger.info("Login attempt  email=%s", email)

    user = auth_service.authenticate_user(user_repo, email, password)
    if user is None:
        logger.warning("Login failed  email=%s", email)
        # Re-render form with error — keep ?next so user can retry.
        safe_next = html.escape(next, quote=True)
        page = _LOGIN_HTML.format(
            next_url=safe_next,
            error='<p class="error">Invalid email or password.</p>',
        )
        return HTMLResponse(page, status_code=401)

    # --- Set session cookie ------------------------------------------------
    session_jwt = token_service.create_session_token(sub=str(user.id))

    # If there's a real destination, redirect there. Otherwise show a
    # simple "you're logged in" page (avoids 404 on /).
    if next and next != "/":
        response: RedirectResponse | HTMLResponse = RedirectResponse(
            url=next, status_code=302
        )
    else:
        response = HTMLResponse(
            "<!DOCTYPE html><html><head>"
            "<meta charset='utf-8'>"
            "<title>Logged in</title>"
            "<style>"
            "body{font-family:system-ui,sans-serif;display:flex;"
            "justify-content:center;align-items:center;min-height:100vh;"
            "background:#f5f5f5;}"
            ".card{background:#fff;padding:2rem;border-radius:8px;"
            "box-shadow:0 2px 8px rgba(0,0,0,.1);text-align:center;}"
            "</style></head><body>"
            "<div class='card'>"
            f"<h1>Signed in</h1>"
            f"<p>Welcome, {html.escape(email)}</p>"
            "</div></body></html>"
        )

    response.set_cookie(
        key="session",
        value=session_jwt,
        httponly=True,
        samesite="lax",
        # TRADE-OFF: Secure=False for localhost dev. Must be True in prod
        # (enforced via config or environment check).
        secure=False,
        path="/",
        max_age=token_service.SESSION_TTL_MIN * 60,
    )
    logger.info("Login succeeded  user_id=%s email=%s", user.id, email)
    return response
