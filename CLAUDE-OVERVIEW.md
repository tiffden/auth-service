# CLAUDE-OVERVIEW

Understanding the existing auth implementation:

**Token service** (`app/services/token_service.py`):

    ES256 (ECDSA P-256) with ephemeral key pair generated at import.

    Access tokens include claims: `sub`, `iss` ("auth-service"), `aud` ("auth-service"), `exp` (15min TTL), `iat`, `jti` (uuid4), `scope`, `roles`. Session tokens use audience `auth-service-session` with 30min TTL.

    Refresh tokens use audience `auth-service-refresh` with 7-day TTL. Functions: `create_access_token`, `decode_access_token`, `create_session_token`, `decode_session_token`, `create_refresh_token`, `decode_refresh_token`.

**Login flow** (`app/api/login.py` + `app/api/register.py`):
    Two login flows:

    **Browser**: `POST /login` (form-based) validates credentials via `auth_service.authenticate_user()`, sets an HttpOnly session cookie with a session JWT, and redirects.

    **SPA/API**: `POST /auth/login` (JSON, in `register.py`) returns `AuthResponse { accessToken, refreshToken, user: { id, email, name } }`. Both use `InMemoryUserRepo` singleton from `login.py`.

    A test user (`test@example.com` / `test-password`) is seeded at import.
    Login is rate-limited to 10 attempts/min per IP.

**Auth dependencies** (`app/api/dependencies.py`):

    `require_user()` extracts Bearer token from Authorization header, calls `decode_access_token()` (validates signature, exp, iss, aud), checks blacklist via `token_blacklist.is_revoked(jti)`, returns `Principal(user_id, roles)`. 
    Distinguishes expired tokens ("Token expired") from invalid tokens ("Invalid token") — both 401 with WWW-Authenticate header.

**Config** (`app/core/config.py`):
    No token-specific settings in config. TTLs are hardcoded in `token_service.py` (access=15min, session=30min, refresh=7days).
    Config has: `app_env`, `log_level`, `log_json`, `port`, `database_url`, `redis_url`.
    Algorithm and keys are also hardcoded in `token_service.py`.

**API contract** (`docs/server-api-contract.md`):
    Documents all auth endpoints including `POST /auth/refresh` (token rotation), login, register, logout. AuthResponse includes `accessToken`, `refreshToken`, and `user`.

**Existing routes**:
    Auth routes split across: `register.py` (`POST /auth/login`, `POST /auth/register`), `refresh.py` (`POST /auth/refresh`), `logout.py` (`POST /auth/logout`), `profile.py` (`GET /auth/me`).

**User model** (`app/models/user.py`):
    Frozen dataclass with slots: `id: UUID`, `email: str`, `password_hash: str`, `name: str = ""`, `roles: tuple[str, ...] = ()`, `is_active: bool = True`. Has `User.new()` class method for creation.

**Token blacklist** (`app/services/token_blacklist.py`):
    Protocol with `revoke(jti, expires_at)` and `is_revoked(jti)` methods. Two implementations: `RedisTokenBlacklist` (production, uses SETEX with TTL matching token expiry) and `InMemoryTokenBlacklist` (dev/test, per-process dict). Module-level singleton `token_blacklist` selected based on Redis availability. Used by `require_user()`, `logout`, and refresh token rotation.

**Tests** (`tests/api/test_auth.py`, `tests/api/test_refresh.py`):
    Token validation tests cover garbage/expired/tampered/wrong-audience tokens → 401. Refresh tests cover: login/register return refreshToken, valid refresh returns new pair, rotation (old token rejected), expired/invalid/garbage tokens, access token as refresh rejected, inactive user, logout revokes refresh token. `conftest.py` provides: `client` fixture, `mint_token()` helper, `token`/`admin_token` fixtures, autouse fixtures for resetting blacklist/rate limiter/cache between tests.

**Main app router setup** (`app/main.py`):
    Alphabetically imported and included: admin, courses, credentials, health, login, logout, metrics, oauth, orgs, profile, progress, refresh, register, resource, users.

    Middleware stack:
        RequestContextMiddleware (outermost) → MetricsMiddleware → CORS.
    
    Lifespan manages DB and Redis startup/shutdown.
