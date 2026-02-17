# Availability SLO Breach (error rate > 0.5%)

## What is this alert?

More than 0.5% of HTTP requests are returning 5xx (server error) status codes over the rolling 30-day window.

## Why does it matter?

Users are seeing error pages or failed API calls. If this is the login endpoint, users can't authenticate. If it's progress tracking, learning data might be lost.

## How to investigate

```bash
# 1. Check the health endpoint
curl -s http://localhost:8000/health | jq .

# 2. Look for recent errors in logs
docker logs auth-service-api-dev --since 15m 2>&1 | grep ERROR

# 3. Check Grafana "Error Rate" panel
#    → Look for a spike. When did it start?
#    → Does it correlate with a deployment?

# 4. Check which endpoints are failing
#    Prometheus query:
#    topk(5, sum(rate(http_requests_total{status_code=~"5.."}[5m])) by (endpoint))

# 5. Check backing services
curl -s http://localhost:8000/health | jq .checks
# If redis: "degraded" → Redis may be down
# Check Redis directly: redis-cli ping
# Check PostgreSQL: pg_isready -U auth -d auth_service
```

## How to remediate

| Cause                         | Fix                                                                                         |
| ----------------------------- | ------------------------------------------------------------------------------------------- |
| Redis down                    | Restart Redis. App falls back to in-memory but check for data consistency                   |
| Database connection exhausted | Check connection pool (`max_connections=20`). Increase or fix connection leaks              |
| Recent deployment             | Rollback (see `deployment-strategy.md`)                                                     |
| Memory/CPU exhaustion         | Scale horizontally (add API instances) or vertically (increase resources)                   |
| Dependency timeout            | Check external service status. Consider circuit breaker                                     |

## Escalation

If the error rate doesn't decrease within 15 minutes of remediation, escalate to the on-call engineer.
