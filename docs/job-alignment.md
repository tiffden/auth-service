# Job Alignment: auth-service vs Anthropic Senior Education Platform Engineer

Document Last Updated: Feb 14, 2026

This document maps what we've actually built in the auth-service codebase
to the specific requirements in the Anthropic job description. It's a
running document — update it as new features land.

Use this during interview prep (Weeks 23-26) to:

- Answer "tell me about a system you built" with specific, traceable examples
- Point interviewers to concrete code, not abstract claims
- Identify gaps where you have design docs but not running code

---

## JD Requirement: "Authentication/SSO, learner data models, content delivery, credentialing, and progress tracking"

### Authentication — fully implemented

| What | Where | Pattern |
| ---- | ----- | ------- |
| OAuth 2.1 Authorization Code + PKCE | [oauth.py](../app/api/oauth.py) | Full flow: authorize -> code -> token -> resource |
| JWT access tokens (ES256) | [token_service.py](../app/services/token_service.py) | Asymmetric signing, audience separation, algorithm pinning |
| Session cookies (HttpOnly, SameSite) | [login.py](../app/api/login.py) | HTML login form, secure cookie issuance, redirect preservation |
| Password hashing (Argon2) | [auth_service.py](../app/services/auth_service.py) | Memory-hard hashing, automatic rehash on config change |
| PKCE S256 verification | [pkce_service.py](../app/services/pkce_service.py) | Constant-time comparison, timing attack prevention |
| Dependency injection auth guards | [dependencies.py](../app/api/dependencies.py) | require_user, require_role, require_any_role |
| Principal identity object | [principal.py](../app/models/principal.py) | Frozen dataclass, role checking, carries identity through request |

#### Interview talking points

- "I implemented the full OAuth 2.1 + PKCE flow from scratch, including
  hash-based authorization code storage so codes aren't replayable if the
  database is compromised."
- "The token service uses ES256 (ECDSA P-256) — asymmetric signing so the
  private key never leaves the token issuer. I chose ES256 over RS256 for
  smaller tokens and faster verification." (See [JWT-signing-algorithm-selection-2026.md](JWT-signing-algorithm-selection-2026.md))
- "RBAC is implemented as composable FastAPI dependency factories — you
  write `Depends(require_role("admin"))` and the guard chains through
  `require_user` automatically."

### Authentication — designed but not yet coded

- SSO/SAML integration (Week 5/17 in syllabus)
- Learner data models (Week 4 — see [data-model-notes-week4.md](data-model-notes-week4.md))
- Content delivery, credentialing, progress tracking (Week 4 data model
  has the schema; implementation is Week 8+)

---

## JD Requirement: "RBAC" and "Role-based access controls"

### RBAC — what's built

| What | Where | Pattern |
| ---- | ----- | ------- |
| Principal with roles | [principal.py](../app/models/principal.py) | `has_role()`, `has_any_role()`, frozenset roles |
| require_role() factory | [dependencies.py](../app/api/dependencies.py) | Returns FastAPI dependency; 403 on missing role |
| require_any_role() factory | [dependencies.py](../app/api/dependencies.py) | OR-semantics for multiple roles |
| Admin-only endpoints | [admin.py](../app/api/admin.py), [users.py](../app/api/users.py) | GET/POST /users locked to admin |
| Any-authenticated endpoints | [resource.py](../app/api/resource.py) | GET /resource/me uses require_user (any role) |
| Table-driven RBAC tests | [test_rbac.py](../tests/api/test_rbac.py) | 12 parametrized cases: endpoint x role x status |
| 401 vs 403 distinction | [dependencies.py](../app/api/dependencies.py) | 401 = not authenticated, 403 = wrong role |

#### Interview talking points — RBAC

- "I built composable RBAC guards as dependency factories. `require_role`
  wraps `require_user` — the dependency chain handles authentication first,
  then authorization. This means you can't get a 403 without being
  authenticated first."
- "The test matrix is table-driven: every endpoint x role combination is
  a row in a parametrized test. Adding a new endpoint means adding rows,
  not writing new test functions."
- "I separated 401 (not authenticated) from 403 (insufficient permissions)
  because they have different security implications — a 401 should trigger
  a login redirect, a 403 should not."

### RBAC — designed but not yet coded

- Ownership-based access ("users can edit their own profile") — the
  Principal has the data for it, but no endpoints use it yet
- Org-scoped roles (org_role in org_membership) — designed in
  [data-model-notes-week4.md](data-model-notes-week4.md), not implemented
- ABAC / policy engine — discussed conceptually, not planned for this
  codebase (appropriate for a separate service)

---

## JD Requirement: "Full-stack engineering skills with particular strength in backend systems: databases, APIs, authentication, reliability, and infrastructure"

### API design

| What | Where | Pattern |
| ---- | ----- | ------- |
| RESTful endpoints | All routers in [app/api/](../app/api/) | Proper HTTP verbs, status codes (200, 201, 401, 403, 409, 422) |
| Pydantic request/response models | [users.py](../app/api/users.py), [resource.py](../app/api/resource.py) | Type-safe serialization, input validation |
| Error handling with HTTP semantics | [users.py](../app/api/users.py) | Service exceptions -> appropriate HTTP status |
| Health check endpoint | [health.py](../app/api/health.py) | Load balancer / orchestrator readiness |

### Architecture

| What | Where | Pattern |
| ---- | ----- | ------- |
| Service layer | [app/services/](../app/services/) | Business logic isolated from HTTP layer |
| Repository pattern | [app/repos/](../app/repos/) | Protocol-based interfaces, in-memory implementations |
| Dependency injection | [dependencies.py](../app/api/dependencies.py) | FastAPI Depends() for composable guards |
| Immutable domain models | [app/models/](../app/models/) | Frozen dataclasses with slots, factory methods |
| Environment-based config | [config.py](../app/core/config.py) | Typed settings, validation, singleton |

### Infrastructure

| What | Where | Pattern |
| ---- | ----- | ------- |
| Multi-stage Docker build | [Dockerfile](../docker/Dockerfile) | builder -> runtime -> devtest, non-root user |
| Layer caching optimization | [Dockerfile](../docker/Dockerfile) | pyproject.toml before code, bind mount for wheels |
| Docker Compose | [docker-compose.yml](../docker/docker-compose.yml) | Dev (hot-reload) + test services |
| CI/CD pipeline | [ci.yml](../.github/workflows/ci.yml) | Lint + format + test + Docker build + non-root check |
| Pre-commit hooks | [.pre-commit-config.yaml](../.pre-commit-config.yaml) | Ruff linting/formatting on every commit |

#### Interview talking points — backend systems

- "The architecture follows a clean separation: API layer handles HTTP
  semantics, service layer handles business logic, repository layer
  handles persistence. The repo layer uses Python Protocols (structural
  typing) so I can swap in-memory implementations for database-backed
  ones without changing any business logic."
- "The Dockerfile uses a 3-stage build: builder (compiles wheels),
  runtime (minimal production image with non-root user), and devtest
  (extends runtime with pytest/ruff). The runtime image has no compilers
  or build toolchains. I use `RUN --mount=type=bind` for the wheel
  install to avoid persisting a /wheels layer."
- "CI runs lint, format check, tests, Docker build, and verifies the
  container runs as non-root — all on every push and PR."

---

## JD Requirement: "Experience interfacing with security and infrastructure teams"

### What's built — security patterns throughout

| Security concern | Implementation | Where |
| ---------------- | -------------- | ----- |
| Timing attacks | `hmac.compare_digest` for PKCE verification | [pkce_service.py](../app/services/pkce_service.py) |
| Token type confusion | Audience separation (access vs session) | [token_service.py](../app/services/token_service.py) |
| Algorithm confusion | Algorithm pinning (`algorithms=["ES256"]`) | [token_service.py](../app/services/token_service.py) |
| Code replay | Hash-based storage + single-use enforcement | [oauth.py](../app/api/oauth.py), [authorization_code.py](../app/models/authorization_code.py) |
| Open redirect | Exact redirect_uri matching | [oauth.py](../app/api/oauth.py) |
| CSRF | SameSite=Lax cookies | [login.py](../app/api/login.py) |
| XSS | HTML escaping in login template | [login.py](../app/api/login.py) |
| Credential leaks | Passwords/tokens never logged (tested!) | [test_log_secrets.py](../tests/api/test_log_secrets.py) |
| Privilege escalation | Non-root container user | [Dockerfile](../docker/Dockerfile) |
| Password storage | Argon2 (memory-hard, auto-rehash) | [auth_service.py](../app/services/auth_service.py) |

#### Interview talking points — security

- "I have a dedicated test file that asserts passwords, session JWTs,
  and code verifiers never appear in log output. These are negative
  assertions — they prove the absence of sensitive data in logs."
- "Authorization codes are stored as SHA-256 hashes. Even if an attacker
  reads the database, they can't replay codes. The mark_used() method
  is atomic to prevent race conditions."
- "I wrote a threat model document covering the attack surface." (See
  [threat-model.md](threat-model.md) and [threat-model-tests.md](threat-model-tests.md))

---

## JD Requirement: "A working practice of using AI tools in your own engineering workflows"

### What's demonstrated

The entire codebase was built using Claude Code as a pair-programming
tool. Specific examples:

- JWT signing algorithm selection: researched ES256 vs RS256 vs EdDSA
  tradeoffs with AI assistance (see [JWT-signing-algorithm-selection-2026.md](JWT-signing-algorithm-selection-2026.md))
- Threat modeling: systematically identified attack vectors for the OAuth
  flow with AI-assisted analysis
- Test generation: table-driven RBAC tests designed collaboratively
- Docker optimization: multi-stage build with bind-mount wheels (7MB
  savings) discovered through AI-assisted exploration
- Architecture decisions: RBAC vs ABAC vs ReBAC tradeoff analysis for
  the access control model

#### Interview talking points — AI tools

- "I use Claude Code as my primary development tool. Not for generating
  boilerplate — for architectural decision-making. For example, when
  choosing the JWT signing algorithm, I used it to research the security
  tradeoffs of ES256 vs RS256 vs EdDSA, then made the decision based on
  token size, verification speed, and library maturity."
- "My git history shows the AI as co-author on commits. I treat it as a
  senior pair programmer — I make the decisions, it helps me explore the
  solution space faster."

---

## JD Requirement: "Experience building or contributing to learning platforms, credentialing systems, or educational technology"

### What's designed (docs, not yet coded)

| Artifact | Where | What it covers |
| -------- | ----- | -------------- |
| Data model: learner state | [data-model-notes-week4.md](data-model-notes-week4.md) | users, orgs, courses, modules, assessments, progress events, credentials |
| Enterprise tenancy | [data-model-notes-week4.md](data-model-notes-week4.md) | org isolation, org-scoped roles, SSO binding |
| AI interaction logging | [data-model-notes-week4.md](data-model-notes-week4.md) | ai_session, ai_interaction, ai_feedback tables |
| Open Badges v3 mapping | [data-model-notes-week4.md](data-model-notes-week4.md) | credential -> OBv3 Achievement, verification endpoint |
| Data store strategy | [data-model-notes-week4.md](data-model-notes-week4.md) | Postgres + Redis + S3 + vector store, when each is introduced |
| Syllabus alignment | [week-by-week syllabus.txt](week-by-week%20syllabus.txt) | 26-week plan mapping every week to a JD requirement |

#### Interview talking points — education platforms

- "I designed the data model to separate authored content (courses,
  assessments) from user-generated data (attempts, progress events).
  Progress is event-sourced: an append-only log is the source of truth,
  and a projection table makes reads fast. This gives you full audit
  trail and the ability to recompute progress from events."
- "The credential model maps directly to Open Badges v3 (W3C Verifiable
  Credentials). The relational schema is the canonical store; OBv3
  JSON-LD is generated on demand via an export endpoint."
- "I designed tenant isolation from the start: every query scopes to
  org_id. This is the single most common security bug in multi-tenant
  SaaS — getting it wrong means one org can see another's learner data."

---

## JD Requirement: "SSO/identity (SAML, OAuth), badging standards (Open Badges), or LTI integrations"

### SSO and standards — what's built

- **OAuth 2.1 + PKCE**: Full implementation with all security measures
  (see Authentication section above)

### SSO and standards — designed but not yet coded

- **Open Badges v3**: Schema mapping in data model notes, verification
  endpoint planned
- **SAML 2.0**: Org-level SSO binding designed in tenant model
- **LTI 1.3**: Planned for Week 17

---

## JD Requirement: "Comfort with ambiguity and ownership"

### Ownership signals in the project

This is harder to point to code for, but the project structure tells
the story:

- **No spec was provided.** The syllabus is self-directed. Architecture
  decisions (ES256 over RS256, RBAC before ABAC, event-sourced progress,
  Protocol-based repos) were all made independently.
- **Threat model was self-initiated.** Nobody asked for
  [threat-model.md](threat-model.md) — it was created because the OAuth
  flow warranted systematic security analysis.
- **The syllabus was critiqued and restructured.** The original ChatGPT
  syllabus had gaps (no non-engineer tooling, AI too late, generic infra
  weeks). It was rewritten to better align with the JD.

---

## Testing philosophy — a cross-cutting concern

The JD doesn't explicitly mention testing, but the testing approach
demonstrates engineering maturity:

| Pattern | Example | Where |
| ------- | ------- | ----- |
| Integration tests | Full OAuth PKCE flow (login -> token -> resource) | [test_oauth_pkce_flow.py](../tests/api/test_oauth_pkce_flow.py) |
| Table-driven tests | RBAC matrix: 12 endpoint x role x status combos | [test_rbac.py](../tests/api/test_rbac.py) |
| Security tests | Passwords/tokens never in logs | [test_log_secrets.py](../tests/api/test_log_secrets.py) |
| Docker integration | Live container tests via httpx | [test_oauth_pkce_flow_docker.py](../tests/api/test_oauth_pkce_flow_docker.py) |
| Fixture isolation | autouse state reset, per-test token minting | [conftest.py](../tests/conftest.py) |
| Config validation | Monkeypatched env vars, edge cases | [test_config.py](../tests/core/test_config.py) |
| pytest markers | `@pytest.mark.docker` for container-dependent tests | [pyproject.toml](../pyproject.toml) |

**Test count**: 107 tests, all passing. Lint and format clean.

---

## Gap analysis — what's NOT built yet

These are the JD requirements with no running code. Use this to
prioritize remaining weeks.

| JD requirement | Status | Planned week |
| -------------- | ------ | ------------ |
| Learner data models (DB) | Designed (ER + sequences) | Week 4 deliverable |
| Enterprise SSO (SAML) | Designed (org model) | Week 5, 17 |
| Content delivery system | Not started | Week 8 |
| AI-augmented pipelines | Not started | Week 8 |
| Adaptive paths / personalization | Not started | Week 12 |
| AI-evaluated assessments | Not started | Week 10 |
| Competency-based credentialing | Designed (OBv3 mapping) | Week 16 |
| Platform for non-engineers | Not started | Week 13 |
| LTI integration | Not started | Week 17 |
| Observability / SLOs | Logging built; metrics not | Week 7 |
| Production deployment | Docker built; cloud not | Week 7 |
| Vector search / embeddings | Not started | Week 12 |
| Human-in-the-loop review | Not started | Week 11 |
| Cost management / token budgets | Not started | Week 14 |

---

## How to use this document in interviews

1. **"Tell me about a system you built"** — walk through the auth-service
   architecture: config -> logging -> auth -> RBAC -> OAuth PKCE -> testing
   -> Docker -> CI. Every layer has a concrete implementation.

2. **"How do you think about security?"** — point to the security patterns
   table. Each one has a specific threat it mitigates and a test that
   proves it works.

3. **"How would you design X?"** — reference the data model notes and
   syllabus. Show that you've already thought through the full platform
   (tenancy, AI interactions, credentialing) even if not all of it is
   coded yet.

4. **"How do you use AI in your workflow?"** — the git history and docs
   show AI-assisted development throughout. Emphasize decision-making
   assistance, not code generation.

5. **"What would you build next?"** — reference the gap analysis table.
   You have a prioritized roadmap that maps directly to JD requirements.
