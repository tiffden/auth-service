# Latency SLO Breach (p95 > 500ms)

## What is this alert?

The 95th percentile response time exceeds 500ms. This means at least 5% of users are experiencing slow responses.

## Why does it matter?

Slow auth responses cascade: if login takes 2 seconds, every downstream service that needs auth is also delayed. Users perceive the entire platform as slow.

## How to investigate

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

## How to remediate

| Cause                   | Fix                                                                                  |
| ----------------------- | ------------------------------------------------------------------------------------ |
| High traffic volume     | Scale API instances horizontally                                                     |
| Slow database queries   | Add indexes, optimize queries, check for N+1 patterns                                |
| Redis latency           | Check Redis memory usage (`redis-cli info memory`). Consider eviction policy         |
| Cache miss storm        | After a cache flush, many requests hit the DB simultaneously. Consider cache warming |
| Large response payloads | Paginate, compress, or cache responses                                               |

## Escalation

If p95 remains above 500ms after scaling and cache warming, escalate for architectural review.
