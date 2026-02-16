# Alert Runbooks

Each runbook follows the same structure:

1. **What is this alert?** — plain-language description
2. **Why does it matter?** — user impact
3. **How to investigate** — specific commands and dashboards
4. **How to remediate** — common fixes
5. **Escalation** — when to involve others

---

## 4000 Availability SLO Breach (error rate > 0.5%)

### 4000 What is this alert?

More than 0.5% of HTTP requests are returning 5xx (server error) status codes over the rolling 30-day window.

### 4000 Why does it matter?

Users are seeing error pages or failed API calls. If this is the login endpoint, users can't authenticate. If it's progress tracking, learning data might be lost.

### 4000 How to investigate

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

### 4000 How to remediate

| Cause                         | Fix                                                                                         |
| ----------------------------- | ------------------------------------------------------------------------------------------- |
| Redis down                    | Restart Redis. App falls back to in-memory but check for data consistency                   |
| Database connection exhausted | Check connection pool (`max_connections=20`). Increase or fix connection leaks              |
| Recent deployment             | Rollback (see `deployment-strategy.md`)                                                     |
| Memory/CPU exhaustion         | Scale horizontally (add API instances) or vertically (increase resources)                   |
| Dependency timeout            | Check external service status. Consider circuit breaker                                     |

### 4000 Escalation

If the error rate doesn't decrease within 15 minutes of remediation, escalate to the on-call engineer.

---

## 4001 Latency SLO Breach (p95 > 500ms)

### 4001 What is this alert?

The 95th percentile response time exceeds 500ms. This means at least 5% of users are experiencing slow responses.

### 4001 Why does it matter?

Slow auth responses cascade: if login takes 2 seconds, every downstream service that needs auth is also delayed. Users perceive the entire platform as slow.

### 4001 How to investigate

```bash
# 1. Check which endpoints are slow
#    Prometheus query:
#    histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (endpoint, le))

# 2. Check active request count (saturation)
#    Grafana "Active Requests" gauge
#    If near max → the server is overloaded

# 3. Check Redis latency
redis-cli --latency
# Normal: <1ms.  If >5ms, Redis might be overloaded

# 4. Check database query times
#    Look for slow queries in PostgreSQL logs:
#    docker logs auth-service-postgres 2>&1 | grep "duration"

# 5. Check for garbage collection pauses (rare in Python, but possible)
#    Look for log gaps (no logs for >500ms)
```

### 4001 How to remediate

| Cause                   | Fix                                                                                  |
| ----------------------- | ------------------------------------------------------------------------------------ |
| High traffic volume     | Scale API instances horizontally                                                     |
| Slow database queries   | Add indexes, optimize queries, check for N+1 patterns                                |
| Redis latency           | Check Redis memory usage (`redis-cli info memory`). Consider eviction policy         |
| Cache miss storm        | After a cache flush, many requests hit the DB simultaneously. Consider cache warming |
| Large response payloads | Paginate, compress, or cache responses                                               |

### 4001 Escalation

If p95 remains above 500ms after scaling and cache warming, escalate for architectural review.

---

## 4002 Queue Processing SLO Breach (>5% tasks taking >10s)

### 4002 What is this alert?

More than 5% of background tasks (credential issuance, grading) are taking longer than 10 seconds to complete.

### 4002 Why does it matter?

Users waiting for credentials or grades will experience delays. If the queue grows unbounded, the system may run out of memory.

### 4002 How to investigate

```bash
# 1. Check queue depth
#    Grafana "Task Queue Depth" panel
#    Growing depth = workers can't keep up

# 2. Check if workers are running
docker ps | grep worker
# If no worker containers → workers are down

# 3. Check worker logs for errors
docker logs auth-service-worker-dev --since 15m 2>&1 | grep -E "ERROR|EXCEPTION"

# 4. Check Redis memory (task queue stored in Redis)
redis-cli info memory
# used_memory_human should be reasonable (<100MB for most workloads)

# 5. Check task processing rate
#    Compare enqueue rate vs dequeue rate in logs
```

### 4002 How to remediate

| Cause                                    | Fix                                                                            |
| ---------------------------------------- | ------------------------------------------------------------------------------ |
| Workers crashed                          | Restart worker containers. Check logs for root cause                           |
| Queue backlog (exam period)              | Scale workers: add more worker containers                                      |
| Slow external API (credential issuance)  | Check external service. Consider adding timeouts and retry logic               |
| Redis full                               | Increase Redis `maxmemory`. Check for memory leaks in task payloads            |
| Single slow task type                    | Isolate slow queue to dedicated workers so fast tasks aren't blocked           |

### 4002 Escalation

If queue depth keeps growing after scaling workers, escalate for capacity planning.

## 4002 General Investigation Tips

1. **Correlate with deployments**: Check `git log --oneline -5` to see if a recent commit correlates with the alert
2. **Check all three pillars**: Logs (what happened), Metrics (how bad), Dashboard (when it started)
3. **Use request IDs**: The `X-Request-ID` header lets you trace a specific failed request through all log lines
4. **Don't panic**: SLO breaches are normal. That's what the error budget is for. Investigate calmly, fix methodically
