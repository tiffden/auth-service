# Threat Model

## 1. Authentication & Credential Security

### 1.1 User Passwords

- Asset: Stored user credentials
- Threat: Offline cracking after database compromise
- Mitigation:
- Argon2 (memory-hard) with calibrated parameters
- Unique salt per password
- Optional server-side pepper stored in environment/secret manager
- Enforced password policy
- Residual Risk:
- Weak parameter tuning reduces resistance
- Pepper compromise weakens defense

### 1.2 Login Endpoint

- Asset: Authentication entrypoint
- Threat: Credential stuffing / brute-force attacks
- Mitigation:
- Rate limiting (per IP and per account)
- Progressive backoff
- Suspicious-pattern lockouts
- Structured audit logging
- Residual Risk:
- Botnet-distributed attacks
- False positives impacting legitimate users

### 1.3 Account State (Active / Locked)

- Asset: Account status controls
- Threat: Bypass of lock/disable checks
- Mitigation:
- Centralized checks in `auth_service.authenticate_user`
- Enforced on token issuance and refresh
- Explicit tests for inactive/locked accounts
- Residual Risk:
- New endpoints bypassing service-layer enforcement

## 2. OAuth & Token Security

### 2.1 Authorization Code Flow

- Asset: Authorization codes
- Threat: Code interception via malicious redirect
- Mitigation:
- Authorization Code + PKCE (OAuth 2.1-aligned)
- Strict redirect URI allowlist
- `state` parameter validation
- HTTPS-only enforcement
- Residual Risk:
- Compromised client device can still leak tokens

### 2.2 PKCE

- Asset: Code verifier/challenge
- Threat: Downgrade or weak verifier
- Mitigation:
- Require S256 only
- Reject plain
- Enforce minimum entropy for verifier
- Residual Risk:
- Poor client implementation quality

### 2.3 Access Tokens (JWT)

- Asset: Short-lived access tokens
- Threat: Token theft and replay
- Mitigation:
- Short TTL
- Signature verification
- Strict validation of `iss`, `aud`, `exp`, `nbf`
- Optional `jti` for sensitive endpoints
- TLS required
- Residual Risk:
- If stolen within TTL, attacker can act until expiration

### 2.4 Refresh Tokens

- Asset: Long-lived session continuity
- Threat: Replay or theft
- Mitigation:
- Opaque server-stored tokens
- Rotate on use
- Revoke prior token on rotation
- Store hashed at rest
- Residual Risk:
- "Race condition" where attacker refreshes first

### 2.5 Signing Keys

- Asset: JWT signing keys
- Threat: Key exfiltration -> forged tokens
- Mitigation:
- Store in secret manager
- Key rotation with `kid` support
- Restricted access controls
- Audit logging
- Residual Risk:
- Insider threat
- Delayed rotation response

## 3. Authorization & Access Control

### 3.1 Role-Based Access Control

- Asset: Role / permission system
- Threat: Privilege escalation via forged claims
- Mitigation:
- Never trust client-supplied roles
- Validate token signature
- Enforce authorization server-side
- Optional server-side role re-check
- Residual Risk:
- Signing key compromise invalidates role guarantees

### 3.2 IDOR / Resource Authorization

- Asset: Protected resources
- Threat: Access to unauthorized records
- Mitigation:
- Explicit per-endpoint permission checks
- Deny-by-default policy
- Tests for privileged endpoints
- Residual Risk:
- Policy drift as API surface grows

### 3.3 Admin/Privileged Endpoints

- Asset: Administrative actions
- Threat: Abuse of elevated privileges
- Mitigation:
- Separate policy enforcement
- Optional step-up authentication
- Audit trail for privileged actions
- Residual Risk:
- Admin credential compromise remains high impact

## 4. API & Data Layer Security

### 4.1 Injection Attacks

- Asset: Database integrity
- Threat: SQL/NoSQL injection
- Mitigation:
- Parameterized queries / ORM usage
- Strict input validation
- Least-privilege database roles
- Residual Risk:
- Future unsafe query construction

### 4.2 Account Enumeration

- Asset: User identity privacy
- Threat: Differentiating "user not found" vs bad password
- Mitigation:
- Uniform error messages
- Consistent timing responses
- Rate limiting
- Residual Risk:
- Timing side-channels remain possible

### 4.3 Logging & Telemetry

- Asset: Logs and monitoring systems
- Threat: Credential/token leakage
- Mitigation:
- No logging of secrets or tokens
- Structured logging with redaction
- Safe error messages
- Residual Risk:
- Third-party log processor exposure

## 5. Transport & Browser Security

### 5.1 Transport Layer

- Asset: In-transit data
- Threat: MITM / downgrade attack
- Mitigation:
- TLS-only
- HSTS at proxy layer
- Reject HTTP in production
- Residual Risk:
- Reverse proxy misconfiguration

### 5.2 CORS

- Asset: Browser API surface
- Threat: Token leakage via misconfiguration
- Mitigation:
- Narrow allowlist
- Avoid wildcard with credentials
- Prefer Authorization header
- Residual Risk:
- Frontend storage vulnerabilities

### 5.3 CSRF (if cookies used)

- Asset: Session integrity
- Threat: Cross-site request forgery
- Mitigation:
- SameSite cookies
- CSRF tokens or origin checks
- Residual Risk:
- Complex cross-site requirements increase attack surface

## 6. Operational & Supply Chain Security

### 6.1 Dependencies

- Asset: Dependency chain
- Threat: Supply-chain compromise
- Mitigation:
- Pinned dependencies
- Automated vulnerability scanning
- Minimal runtime image
- Residual Risk:
- Zero-day vulnerabilities

### 6.2 CI/CD Pipeline

- Asset: Build and deployment pipeline
- Threat: Secret exfiltration / malicious PRs
- Mitigation:
- Protected branches
- Required reviews
- No secrets in PR builds
- Minimal token scopes
- Residual Risk:
- Maintainer account compromise

### 6.3 Container Runtime

- Asset: Running service instance
- Threat: Container escape / privilege abuse
- Mitigation:
- Non-root user
- Minimal base image
- Drop unnecessary capabilities
- Limit network egress
- Residual Risk:
- Kernel-level exploits remain high impact
