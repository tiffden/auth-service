# Security Invariants → Corresponding Tests

Maps each threat-model invariant to the test(s) that enforce it.
`-` marks invariants with no test coverage yet.

## 1. Authentication & Credential Security

### 1.1 User Passwords — Argon2 hashing with unique salt

- Argon2 hasher is used — `hash_password()` delegates to `PasswordHasher().hash()` (`app/services/auth_service.py:25`)
- Empty password rejected — `hash_password` raises `ValueError` (`app/services/auth_service.py:23`)
- Verify returns False on mismatch — `verify_password` catches `VerifyMismatchError` (`app/services/auth_service.py:33`)
- Verify returns False on empty input — `verify_password` short-circuits (`app/services/auth_service.py:30-31`)
- Rehash check on login — `test_authenticate_user_rehashes_when_needed` (`tests/services/test_auth_service.py:10`)

### 1.2 Login Endpoint — Session cookie issuance

- Login page renders HTML form — `test_login_page_renders` (`tests/api/test_login.py:35`)
- Login preserves ?next for redirect — `test_login_page_preserves_next` (`tests/api/test_login.py:46`)
- Valid credentials → session cookie set — `test_login_success_sets_cookie` (`tests/api/test_login.py:57`)
- Bad credentials → 401 — `test_login_failure_returns_401` (`tests/api/test_login.py:83`)
- Failed login does not set cookie — `test_login_failure_no_cookie` (`tests/api/test_login.py:101`)
- Unknown user → 401 (uniform message) — `test_login_unknown_user_returns_401` (`tests/api/test_login.py:118`)

**Cookie attributes:** HttpOnly, SameSite=Lax, signed JWT (ES256 with `aud=auth-service-session`). Secure=False for dev (must be True in prod).

**Gap:** No rate-limiting or progressive-backoff tests.

### 1.3 Session Cookies — Signed JWT (ES256)

- Session cookie is a valid JWT with correct iss/aud — `test_login_success_sets_cookie` (`tests/api/test_login.py:77-80`)
- Session audience is distinct from access token audience — `SESSION_AUDIENCE = "auth-service-session"` (`app/services/token_service.py:28`)
- Missing/invalid session → redirect to /login — `test_authorize_redirects_to_login_without_session` (`tests/api/test_oauth_pkce_flow.py:188`)
- Expired session cookie → redirect to /login — `test_expired_session_cookie_redirects_to_login` (`tests/api/test_login.py:193`)
- Tampered session cookie → redirect to /login — `test_tampered_session_cookie_redirects_to_login` (`tests/api/test_login.py:217`)
- Access token cannot be used as session cookie (audience mismatch) — `test_access_token_as_session_cookie_rejected` (`tests/api/test_login.py:233`)

### 1.4 Account State — Active / Locked bypass

- Inactive user rejected in `authenticate_user` — `if not user.is_active: return None` (`app/services/auth_service.py:43`)
- Inactive user rejected through /login endpoint — `test_login_inactive_user_returns_401` (`tests/api/test_login.py:137`)

## 2. OAuth & Token Security

### 2.1 Authorization Code Flow (OAuth 2.1)

- Full PKCE handshake: login → authorize → token → access resource — `test_pkce_flow_happy_path` (`tests/api/test_oauth_pkce_flow.py:87`)
- Unauthenticated user redirected to /login — `test_authorize_redirects_to_login_without_session` (`tests/api/test_oauth_pkce_flow.py:188`)
- Authorization code single-use enforced — `test_replay_rejected` (`tests/api/test_oauth_pkce_flow.py:214`)
- State parameter round-tripped — asserted in `test_pkce_flow_happy_path` (`tests/api/test_oauth_pkce_flow.py:135`)
- Authorization code stored as hash — `hashlib.sha256(raw_code)` in `/authorize`, lookup by hash in `/token` (`app/api/oauth.py:121,189`)
- Redirect URI exact-match validated — `if redirect_uri not in client.redirect_uris` (`app/api/oauth.py:93`)
- Server logs all 9 authorize steps + 9 token steps — asserted in `test_pkce_flow_happy_path` (`tests/api/test_oauth_pkce_flow.py:140-145,172-173`)
- Unknown client_id → 400 — `test_unknown_client_id_rejected` (`tests/api/test_oauth_pkce_flow.py:307`)
- Wrong redirect_uri → 400 — `test_wrong_redirect_uri_rejected` (`tests/api/test_oauth_pkce_flow.py:330`)
- Wrong response_type → 400 — `test_wrong_response_type_rejected` (`tests/api/test_oauth_pkce_flow.py:354`)
- Fabricated authorization code → 400 — `test_invalid_authorization_code_rejected` (`tests/api/test_oauth_pkce_flow.py:425`)
- Wrong grant_type → 400 — `test_wrong_grant_type_rejected` (`tests/api/test_oauth_pkce_flow.py:445`)
- client_id mismatch on /token → 400 — `test_client_id_mismatch_rejected` (`tests/api/test_oauth_pkce_flow.py:464`)
- redirect_uri mismatch on /token → 400 — `test_redirect_uri_mismatch_on_token_rejected` (`tests/api/test_oauth_pkce_flow.py:500`)

**Gap:** No test for expired authorization code (requires time mocking).

### 2.2 PKCE (S256 only)

- Wrong code_verifier rejected — `test_wrong_verifier_rejected` (`tests/api/test_oauth_pkce_flow.py:265`)
- `code_challenge_method` must be S256 — `if code_challenge_method != "S256"` (`app/api/oauth.py:100`)
- Constant-time comparison in verify — `hmac.compare_digest` (`app/services/pkce_service.py`)
- `plain` PKCE method rejected → 400 — `test_plain_pkce_method_rejected` (`tests/api/test_oauth_pkce_flow.py:378`)
- Malformed (short) code_challenge rejected → 400 — `test_short_code_challenge_rejected` (`tests/api/test_oauth_pkce_flow.py:401`)

### 2.3 Access Tokens (JWT / ES256)

- Algorithm pinned to ES256 — `algorithms=[ALGORITHM]` prevents alg:none and alg-switching (`app/services/token_service.py:65`)
- Required claims enforced — `options={"require": ["sub", "exp", "iat", "jti"]}` (`app/services/token_service.py:68`)
- Garbage token → 401 — `test_rejects_garbage_token` (`tests/api/test_auth.py:22`)
- Empty bearer → 401 — `test_rejects_empty_bearer` (`tests/api/test_auth.py:28`)
- Expired token → 401 "Token expired" — `test_rejects_expired_token` (`tests/api/test_auth.py:33`)
- Tampered payload → 401 — `test_rejects_tampered_payload` (`tests/api/test_auth.py:52`)
- Wrong issuer → 401 — `test_rejects_wrong_issuer` (`tests/api/test_auth.py:67`)
- Wrong audience → 401 — `test_rejects_wrong_audience` (`tests/api/test_auth.py:86`)
- Expired token logged at WARNING — `test_expired_token_logs_warning` (`tests/api/test_auth.py:108`)
- Invalid token logged at WARNING — `test_invalid_token_logs_warning` (`tests/api/test_auth.py:131`)
- Valid token logged at DEBUG — `test_valid_token_logs_debug` (`tests/api/test_auth.py:142`)

### 2.4 Refresh Tokens

**Gap:** Not yet implemented. No rotation, revocation, or hashed-storage tests.

### 2.5 Signing Keys

- Ephemeral EC key pair generated at startup for dev/test — `ec.generate_private_key(ec.SECP256R1())` (`app/services/token_service.py:20`)

**Gap:** No key rotation, `kid` support, or JWKS endpoint tests.

## 3. Authorization & Access Control

### 3.1 Role-Based Access Control — Privilege escalation

- Protected endpoint requires bearer token — `test_users_rejects_missing_token` (`tests/api/test_users.py:9`)
- POST also requires bearer token — `test_users_create_rejects_missing_token` (`tests/api/test_users.py:69`)

**Gap:** No role/permission enforcement tests (roles are in the JWT but not checked).

### 3.2 IDOR / Resource Authorization

- Undefined route → 404 — `test_undefined_route_returns_404` (`tests/api/test_routing.py:8`)
- Wrong HTTP method → 405 — `test_delete_users_returns_405` (`tests/api/test_routing.py:22`)
- GET /oauth/token → 405 — `test_get_oauth_token_returns_405` (`tests/api/test_routing.py:32`)

**Gap:** No per-resource ownership checks (user A can't access user B's data).

### 3.3 Admin/Privileged Endpoints

**Gap:** No admin endpoints or step-up auth tests.

## 4. API & Data Layer Security

### 4.1 Injection Attacks

- In-memory repos use dict lookups (no SQL) — implicitly safe (`app/repos/user_repo.py`, `app/repos/auth_code_repo.py`)

**Gap:** No injection-specific tests (will matter when a real DB is added).

### 4.2 Account Enumeration — Uniform error messages

- Unknown user → same 401 as bad password — `test_login_unknown_user_returns_401` and `test_login_failure_returns_401` both return 401 with same message (`tests/api/test_login.py:118,83`)

**Gap:** No timing-consistency test (constant-time comparison on both paths).

### 4.3 Logging & Telemetry — No secret leakage

- Login attempts logged (no password in message) — `logger.info("Login attempt email=%s", email)` (`app/api/login.py:128`)
- Login success logged — `logger.info("Login succeeded user_id=%s email=%s", ...)` (`app/api/login.py:179`)
- PKCE flow logged at each step (no code_verifier in logs) — `# NOTE: Never log code_verifier` (`app/api/oauth.py:176`)
- User creation logged — `test_user_creation_logs_info` (`tests/api/test_users.py:182`)
- Duplicate email logged — `test_duplicate_email_logs_warning` (`tests/api/test_users.py:196`)
- Blank email logged — `test_blank_email_logs_warning` (`tests/api/test_users.py:207`)
- Log formatter excludes location at INFO — `test_formatter_excludes_location_for_info` (`tests/core/test_logging.py:31`)
- Log formatter includes location at WARNING+ — `test_formatter_includes_location_for_warning` (`tests/core/test_logging.py:47`)
- Password never in login logs (failed) — `test_failed_login_does_not_log_password` (`tests/api/test_log_secrets.py:43`)
- Password never in login logs (success) — `test_successful_login_does_not_log_password` (`tests/api/test_log_secrets.py:62`)
- Session JWT never in login logs — `test_successful_login_does_not_log_session_jwt` (`tests/api/test_log_secrets.py:81`)
- code_verifier never in token exchange logs — `test_token_exchange_does_not_log_code_verifier` (`tests/api/test_log_secrets.py:103`)

## 5. Transport & Browser Security

### 5.1 Transport Layer

**Gap:** TLS/HSTS enforced at proxy layer — no application-level tests.

### 5.2 CORS

**Gap:** No CORS configuration or tests.

### 5.3 CSRF

- Session cookie uses SameSite=Lax — `samesite="lax"` (`app/api/login.py:174`)
- OAuth state parameter round-tripped — `test_pkce_flow_happy_path` asserts `state` match (`tests/api/test_oauth_pkce_flow.py:135`)

**Gap:** No explicit CSRF token on login form (SameSite=Lax mitigates most vectors).

## 6. Operational & Supply Chain Security

### 6.1 Dependencies

- Pinned in `pyproject.toml` — CI runs `ruff check` + `pytest` (`.github/workflows/ci.yml`)

### 6.2 CI/CD Pipeline

- Lint + format + test on every push/PR — `make ci` runs ruff check, ruff format --check, pytest (`Makefile`, `.github/workflows/ci.yml`)

### 6.3 Container Runtime — Non-root user

- Non-root runtime user — `USER appuser` (`docker/Dockerfile:113`)
- Minimal base image — `python:3.12-slim` (`docker/Dockerfile:64`)
- `APP_ENV=prod` default in runtime — `ENV APP_ENV=prod` (`docker/Dockerfile:78`)

## Summary of Coverage Gaps

**Closed since last review:**
- ~~OAuth 2.1 / PKCE flow~~ → implemented + tested (4 happy-path tests)
- ~~JWT claim validation (`iss`, `aud`)~~ → implemented + tested (ES256, 10 tests)
- ~~Login endpoint~~ → implemented with session cookies (6 tests)
- ~~CSRF (cookie-based auth)~~ → mitigated via SameSite=Lax + state parameter
- ~~Expired/tampered session cookie~~ → 3 tests (expired, tampered, wrong audience)
- ~~Inactive account login rejection~~ → `test_login_inactive_user_returns_401`
- ~~OAuth FAIL POINT coverage~~ → 7 tests (unknown client, wrong redirect_uri, wrong response_type, fabricated code, wrong grant_type, client_id mismatch, redirect_uri mismatch)
- ~~PKCE plain method / malformed challenge~~ → 2 tests
- ~~Log output contains no secrets~~ → 4 tests (password, session JWT, code_verifier)

**Still open:**
- Rate limiting / brute-force protection — not implemented
- Refresh token rotation/revocation — not implemented
- Key rotation / `kid` / JWKS endpoint — not implemented
- Role-based access control enforcement — not implemented
- Per-resource ownership (IDOR) — not implemented
- Account enumeration timing consistency — missing
- CORS configuration — not implemented
- Expired authorization code test — missing (requires time mocking)
