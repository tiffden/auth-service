# NEXT STEPS

Here’s the server-side work that still needs to be finished for the full interview demo to work end-to-end (live, no simulation):

1. POST /auth/refresh (currently marked not implemented)
2. GET /auth/me (currently marked not implemented)
3. Token-expiry semantics on protected routes
    * Return clear 401 for expired token vs invalid token (or a consistent error code/message contract)
4. Admin/authorization endpoints for Scenario 2
    * At least one admin-protected route that returns:
    * 403 for low-privilege user
    * 200 for admin user
5. Role model + claims
    * User roles persisted server-side
    * Role included/derivable during auth checks (JWT claim or DB lookup)
6. Rate limiting for Scenario 3
    * Return 429
    * Include Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining
7. Optional rate-limit identity strategy
    * Per IP / per user / per endpoint rules defined and consistently enforced
8. Observability endpoints/instrumentation for Scenario 5
    * /metrics (Prometheus format)
    * Counters/histograms by endpoint + status
    * Rate-limit and auth-failure metrics
9. Health/readiness depth
    * /health exists, but should include dependency readiness if you want stronger ops demo
10. Error contract consistency
    * Standard JSON shape for all errors (401/403/404/409/422/429/5xx)
    * Stable messages usable by client normalization
11. Test/dev helpers for deterministic demos
    * Seed users: standard + admin
    * Optional forced-expire or short-TTL test mode
12. Deployment/rollback telemetry hooks for Scenario 6
    * Version label in metrics/logs
    * Signals that show error/latency regression by version

    Minimum blockers to unblock all six scenarios live: #1, #2, #4, #5, #6, #8.
