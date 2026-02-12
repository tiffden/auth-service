# Security Invariants → Corresponding Tests

Maps each threat-model invariant to the test(s) that enforce it.
`-` marks invariants with no test coverage yet.

## 1. Authentication & Credential Security

### 1.1 User Passwords — Argon2 hashing with unique salt

- Argon2 hasher is used — `hash_password()` delegates to `PasswordHasher().hash()` (`app/services/auth_service.py:18`)
- Empty password rejected — `hash_password` raises `ValueError` (`app/services/auth_service.py:16`)
- Verify returns False on mismatch — `verify_password` catches `VerifyMismatchError` (`app/services/auth_service.py:22-28`)
- Verify returns False on empty input — `verify_password` short-circuits (`app/services/auth_service.py:23-24`)
- Rehash check on login — `authenticate_user` calls `check_needs_rehash` (`app/services/auth_service.py:43`)

**Gap:** No dedicated unit tests for `hash_password`, `verify_password`, or `authenticate_user` in `tests/`.

### 1.2 Login Endpoint — Brute-force / credential stuffing

- Bad credentials → 401 — `test_auth_token_rejects_bad_creds` (`tests/api/test_auth.py:14`)
- Wrong username → 401, uniform message — `test_auth_token_rejects_wrong_username` (`tests/api/test_auth.py:92`)
- Missing body → 422 — `test_auth_token_rejects_missing_body` (`tests/api/test_auth.py:105`)
- Missing password → 422 — `test_auth_token_rejects_missing_password` (`tests/api/test_auth.py:110`)
- Missing username → 422 — `test_auth_token_rejects_missing_username` (`tests/api/test_auth.py:119`)
- Failed login logged — `test_failed_login_logs_warning` (`tests/api/test_auth.py:131`)

**Gap:** No rate-limiting or progressive-backoff tests.

### 1.3 Account State — Active / Locked bypass

- Inactive user rejected in `authenticate_user` — `if not user.is_active: return None` (`app/services/auth_service.py:35-36`)

**Gap:** No test exercising an inactive/locked account through the login endpoint.

## 2. OAuth & Token Security

### 2.1 Authorization Code Flow

**Gap:** Not yet implemented. No PKCE, redirect URI, or `state` parameter tests.

### 2.2 PKCE

**Gap:** Not yet implemented.

### 2.3 Access Tokens (JWT) — Theft and replay

- Token includes expiry and bearer type — `test_auth_token_accepts_good_creds_and_returns_token_and_expiry` (`tests/api/test_auth.py:23`)
- Expired token → 401 — `test_protected_endpoint_rejects_expired_token` (`tests/api/test_auth.py:54`)
- Tampered signature → 401 — `test_protected_endpoint_rejects_tampered_signature` (`tests/api/test_auth.py:69`)
- Tampered username → 401 — `test_protected_endpoint_rejects_tampered_username` (`tests/api/test_auth.py:79`)
- Garbage token → 401 — `test_protected_endpoint_rejects_garbage_token` (`tests/api/test_auth.py:43`)
- Empty bearer → 401 — `test_protected_endpoint_rejects_empty_bearer` (`tests/api/test_auth.py:49`)
- Expired token logged — `test_expired_token_logs_warning` (`tests/api/test_auth.py:155`)
- Tampered sig logged — `test_tampered_signature_logs_warning` (`tests/api/test_auth.py:172`)
- Malformed token logged — `test_malformed_token_logs_warning` (`tests/api/test_auth.py:184`)
- Valid token logged at debug — `test_valid_token_logs_debug` (`tests/api/test_auth.py:192`)

**Gap:** No `iss`/`aud`/`nbf` claim validation (tokens are HMAC-signed strings, not full JWTs yet).

### 2.4 Refresh Tokens

**Gap:** Not yet implemented. No rotation, revocation, or hashed-storage tests.

### 2.5 Signing Keys

**Gap:** No key rotation or `kid` support tests. Signing secret is a module-level constant.

## 3. Authorization & Access Control

### 3.1 Role-Based Access Control — Privilege escalation

- Protected endpoint requires token — `test_users_rejects_missing_token` (`tests/api/test_users.py:9`)
- POST also requires token — `test_users_create_rejects_missing_token` (`tests/api/test_users.py:69`)

**Gap:** No role/permission enforcement tests (no roles in token yet).

### 3.2 IDOR / Resource Authorization

- Undefined route → 404 — `test_undefined_route_returns_404` (`tests/api/test_routing.py:8`)
- Wrong HTTP method → 405 — `test_delete_users_returns_405` (`tests/api/test_routing.py:22`)

**Gap:** No per-resource ownership checks (user A can't access user B's data).

### 3.3 Admin/Privileged Endpoints

**Gap:** No admin endpoints or step-up auth tests.

## 4. API & Data Layer Security

### 4.1 Injection Attacks

- In-memory repo uses list lookups (no SQL) — implicitly safe (`app/repos/user_repo.py`)

**Gap:** No injection-specific tests (will matter when a real DB is added).

### 4.2 Account Enumeration — Uniform error messages

- Wrong username → same 401 message as wrong password — `test_auth_token_rejects_wrong_username` returns `"Invalid credentials"` (`tests/api/test_auth.py:99`)
- Bad password → same 401 message — `test_auth_token_rejects_bad_creds` returns 401 (`tests/api/test_auth.py:14`)

**Gap:** No timing-consistency test (constant-time comparison on both paths).

### 4.3 Logging & Telemetry — No secret leakage

- Failed login logged (no password in message) — `test_failed_login_logs_warning` (`tests/api/test_auth.py:131`)
- Successful login logged — `test_successful_login_logs_info` (`tests/api/test_auth.py:143`)
- User creation logged — `test_user_creation_logs_info` (`tests/api/test_users.py:182`)
- Duplicate email logged — `test_duplicate_email_logs_warning` (`tests/api/test_users.py:196`)
- Blank email logged — `test_blank_email_logs_warning` (`tests/api/test_users.py:207`)
- Log formatter excludes location at INFO — `test_formatter_excludes_location_for_info` (`tests/core/test_logging.py:31`)
- Log formatter includes location at WARNING+ — `test_formatter_includes_location_for_warning` (`tests/core/test_logging.py:47`)

**Gap:** No explicit assertion that passwords/tokens are never present in log output.

## 5. Transport & Browser Security

### 5.1 Transport Layer

**Gap:** TLS/HSTS enforced at proxy layer — no application-level tests.

### 5.2 CORS

**Gap:** No CORS configuration or tests.

### 5.3 CSRF

**Gap:** Not applicable yet (no cookie-based auth).

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

- Password hashing (unit tests for `auth_service`) — missing
- Inactive/locked account login rejection — missing
- Rate limiting / brute-force protection — missing
- OAuth 2.1 / PKCE flow — not implemented
- JWT claim validation (`iss`, `aud`, `nbf`) — not implemented
- Refresh token rotation/revocation — not implemented
- Key rotation / `kid` — not implemented
- Role-based access control — not implemented
- Per-resource ownership (IDOR) — not implemented
- Account enumeration timing consistency — missing
- Log output contains no secrets (explicit assert) — missing
- CORS configuration — not implemented
