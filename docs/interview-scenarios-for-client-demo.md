# Interview Scenarios for `auth-client-demo`

Purpose: structured, repeatable demo flows that show backend/platform depth through a client UI.

Use this doc in the client repo as `docs/interview-scenarios.md`.

## Positioning

- `auth-service` = reference backend (security, reliability, observability patterns)
- `auth-client-demo` = interviewer-facing experience proving you can expose and operate those patterns

## Demo Format

Each scenario should include:

- `Goal`: what competency this proves
- `Setup`: data or account preconditions
- `UI path`: exact clicks/steps in client
- `Expected API behavior`: key request/response/status
- `Talking points`: what to say in interview
- `Failure drill`: one intentional failure and recovery

## Scenario 1: Secure Auth Happy Path

- Goal: prove strong auth fundamentals and clean UX handling
- Setup: no existing user
- UI path:
  1. Register a new account
  2. Login
  3. Open protected resource view
- Expected API behavior:
  - `POST /auth/register` returns `201`
  - `POST /auth/login` returns `200` with token payload
  - `GET /resource/me` returns `200` with identity
- Talking points:
  - distinguish authentication vs authorization
  - show token handling strategy in client (memory/session, not localStorage if avoidable)
  - explain 401 handling and redirect flow
- Failure drill:
  - submit wrong password, show stable error UX (`401`) without leaking account existence

## Scenario 2: Role- and Access-Aware UI

- Goal: prove backend-enforced authorization with client-side affordances
- Setup: one user with low privilege, one admin
- UI path:
  1. Login as standard user
  2. Navigate to admin screen
  3. See blocked state
  4. Login as admin and retry
- Expected API behavior:
  - standard user gets `403` on admin endpoint
  - admin gets `200`
- Talking points:
  - backend is source of truth for authorization
  - client hides/disables actions for UX but never trusts itself for security
  - 401 vs 403 UX difference
- Failure drill:
  - call admin action from devtools as low-privilege user and show server still blocks

## Scenario 3: Rate Limit and Backoff UX

- Goal: prove resilience and production-grade API consumption
- Setup: a screen/action that can be spammed (login or protected action)
- UI path:
  1. Trigger rapid repeated requests
  2. Observe rate-limit banner/toast
  3. Show retry countdown and disabled action until retry window
- Expected API behavior:
  - `429` with `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`
- Talking points:
  - proactive client throttling
  - graceful degradation under protection mechanisms
  - bots/abuse protection without poor user experience
- Failure drill:
  - intentionally trigger `429`, then show automatic recovery after wait

## Scenario 4: Token Expiry and Session Recovery

- Goal: prove lifecycle handling for auth state transitions
- Setup: short-lived token in dev/test config
- UI path:
  1. Login and load protected data
  2. Wait for expiry (or use forced-expire endpoint/script)
  3. Retry protected call
  4. Show session-expired UX and re-authenticate
- Expected API behavior:
  - expired token path returns `401` with token-expired semantics
- Talking points:
  - consistent auth error normalization in client
  - preserving user intent on re-login (return to original page)
- Failure drill:
  - expired token during in-progress workflow; demonstrate safe recovery

## Scenario 5: Observability Walkthrough (Week 7 Core)

- Goal: prove you can operate what you build
- Setup: Grafana/Prometheus running with server
- UI path:
  1. Use client to generate normal traffic
  2. Trigger a known error case and a rate-limit case
  3. Open dashboard and correlate changes
- Expected API behavior:
  - request counters increase by endpoint/status
  - error-rate and latency panels reflect traffic shape
  - rate-limit metrics change during `429` burst
- Talking points:
  - SLI vs SLO vs error budget
  - how alerts map to runbooks
  - what rollback trigger looks like
- Failure drill:
  - simulate degraded dependency and explain incident response sequence

## Scenario 6: Deployment/Rollback Narrative

- Goal: prove release safety mindset
- Setup: two app versions (or mocked feature flag)
- UI path:
  1. demonstrate baseline flow
  2. introduce bad release behavior (simulated)
  3. show canary rollback decision using SLO signal
- Expected API behavior:
  - elevated error/latency signal after bad version
  - recovery after rollback
- Talking points:
  - canary gates tied to SLO thresholds
  - blast-radius control and time-to-detect/time-to-recover
- Failure drill:
  - “what if rollback fails?” explain fallback and escalation

## Minimal UI Surfaces to Build

- Auth panel: register/login/logout, token state, current user
- Protected resource panel: fetch and render `/resource/me`
- Error console: normalized error object and last response metadata
- Rate-limit inspector: show `Retry-After` and remaining quota
- Ops panel: links to `/health`, `/metrics`, Grafana dashboard, runbook docs
- Scenario runner: buttons that trigger scripted calls per scenario

## Scripts to Include in Client Repo

- `npm run demo:happy` -> register/login/me flow
- `npm run demo:ratelimit` -> burst requests and collect headers
- `npm run demo:expiry` -> run request, wait/force expiry, retry
- `npm run demo:observability` -> generate mixed traffic for dashboard

## Interview Narrative Structure (Use Every Time)

1. What user/business risk this scenario addresses
2. What API and security invariant enforce it
3. How the client exposes state clearly to user
4. Which metric proves behavior in production
5. How you detect and recover from failure

## Mapping to JD Themes

- Authentication/SSO: Scenarios 1 and 4
- RBAC and access control: Scenario 2
- Reliability at scale: Scenarios 3, 5, and 6
- Infrastructure + operations: Scenarios 5 and 6
- Product/education platform judgment: scenario framing and tradeoff discussion
