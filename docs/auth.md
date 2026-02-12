# Auth design notes

## Context and goals

This service requires **first-party authentication** (a UI or trusted client we control) and a path to **service-to-service** auth later.

For week scope, prioritize:
(1) simple request-time validation
(2) clear separation of AuthN vs AuthZ
(3) testable security invariants
(4) upgrade path (revocation, rotation, RBAC/ABAC hardening)

Non-goals (for now): third-party login federation, multi-tenant enterprise SSO, complex consent screens, and full “sessions” product behavior.

---

## OAuth2 flow selection (what we support and why)

### 1) Resource Owner Password Credentials (“password”) — **only for first-party**

- **Use case:** our own UI/client collects username/password and exchanges for tokens.
- **Why (week scope):** simplest to implement; no browser redirects; easy to test locally.
- **Caveat:** generally discouraged for third-party clients; acceptable here because the client is first-party and we control it. Plan to move to Auth Code + PKCE for public clients.

### 2) Authorization Code + PKCE — **target next**

- **Use case:** public clients (mobile/SPA) where secrets can’t be safely stored.
- **Why:** mitigates authorization-code interception; standard modern flow.
- **Status:** not implemented in week scope; design should not block this migration.

### 3) Client Credentials — **service-to-service**

- **Use case:** another internal service calls this API.
- **Why:** avoids end-user context; simpler trust model; good fit for microservices.
- **Status:** not implemented in week scope; reserve claim shapes and auth middleware hooks.

---

## Token strategy

### Access token: **JWT (short TTL)**

Decision: issue **JWT access tokens** with a **short TTL** (e.g., 5–15 minutes).

Rationale:

- **Local validation:** API can validate tokens without calling an auth DB on every request.
- **Performance/availability:** reduced dependency on central storage for each request.
- **Observability:** token claims can support consistent audit logging (subject, scopes, auth_time).

Validation model:

- Verify signature using server-controlled signing key (or JWKS if/when externalized).
- Validate registered claims: `iss`, `aud`, `exp`, `nbf` (optional), `iat` (optional).
- Enforce algorithm and key id (no “alg=none”; pin accepted algorithms).

### Refresh token: **none yet** (TODO)

Decision: do **not** implement refresh in week scope.

Rationale

- Minimizes surface area (rotation, replay detection, breach response).
- Keeps auth lifecycle simple while we stabilize endpoints and middleware.

Upgrade path (TODO)

- Add **opaque refresh tokens** stored server-side (hashed) with:
  - rotation on use
  - reuse detection
  - revocation / logout support
  - device/session binding (optional)

## Where roles/permissions live

### Roles in JWT claims (with upgrade path to server-side re-check)

Decision: include coarse roles/permissions in JWT (e.g., `roles: ["admin"]`, `scope: "users:read users:write"`).

Rationale:

- Keeps authorization checks in-request without DB hits (week scope).
- Clear and testable policy enforcement at route boundaries.

Important constraint:

- Roles in token are trusted **only because the token is server-issued and signed**.
- (TODO) For future hardening: add server-side re-check for high-risk actions (e.g., “admin escalation” or “financial operations”), or use short TTL + centralized revocation list.

## AuthN vs AuthZ: lifecycle separation

### AuthN (Authentication): “Who are you?”

Happens early in the request lifecycle:

1. Extract bearer token from `Authorization: Bearer <token>`.
2. Validate JWT signature + standard claims.
3. Construct a **principal** (a typed user identity object) and attach to request context.

If AuthN fails → return **401 Unauthorized** (never 403).

### AuthZ (Authorization): “Can you do this?”

Happens after AuthN, at the endpoint boundary:

- Evaluate required scopes/roles for the route (or resource-level policy).
- Deny with **403 Forbidden** if authenticated but not permitted.

---

## Claim schema (initial)

Minimal, opinionated starting set:

- `sub`: stable user id (UUID or integer, but consistent)
- `iss`: issuer identifier for this service (or auth subsystem)
- `aud`: audience = this API/service
- `exp`: expiry (short TTL)
- `iat`: issued-at
- `jti`: unique token id (supports future revocation / replay analysis)
- `roles`: list of coarse roles (e.g., `["user"]`, `["admin"]`)
- `scope`: space-delimited OAuth scopes (e.g., `users:read users:write`)

---

## Core security invariants (must always hold)

1. **No endpoint depends on client-supplied role.**  
   Only server-issued, signed tokens can convey roles/scopes.

2. **All privileged actions require a valid server-issued access token.**  
   No “admin” actions via cookies, query params, headers, or request bodies.

3. **Admin-only endpoints are isolated and tested.**  
   Routes requiring `admin` (or equivalent scope) must:
   - live under a clear path segment (e.g., `/admin/*`) or explicit router
   - have dedicated tests for 401 vs 403 behavior

4. **AuthN and AuthZ failures are distinguishable and consistent.**  
   - 401 = missing/invalid/expired token
   - 403 = valid token but insufficient permissions

5. **The service never logs secrets.**  
   No token bodies, passwords, refresh tokens, or signing keys in logs.

6. **Short-lived access tokens are the default containment strategy.**  
   If compromise occurs, blast radius is bounded by TTL (until refresh is added).

---

## Threat model notes (week-level)

- **Token theft:** mitigated by short TTL; later by refresh rotation + revocation.
- **Privilege escalation:** prevented by invariant #1 and explicit route policies.
- **Replay:** partially observable via `jti`; enforce later if needed.
- **Key compromise:** out of scope for week; plan for key rotation and kid-based signing.

---

## Testing requirements (minimum)

- AuthN:
  - missing token → 401
  - malformed token → 401
  - expired token → 401
  - wrong audience/issuer → 401
- AuthZ:
  - valid token w/out scope/role → 403
  - valid admin token → 200 on admin routes
- Regression:
  - ensure protected endpoints cannot be accessed via client-supplied role fields

---

## Open decisions / later upgrades

- Refresh tokens (opaque, stored hashed, rotation + reuse detection)
- Central revocation story (denylist keyed by `jti`, or token version on user record)
- JWKS endpoint + key rotation strategy
- Fine-grained authorization (policy engine / ABAC) for resource ownership checks
