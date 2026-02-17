# Queue Processing SLO Breach (>5% tasks taking >10s)

## What is this alert?

More than 5% of background tasks (credential issuance, grading) are taking longer than 10 seconds to complete.

## Why does it matter?

Users waiting for credentials or grades will experience delays. If the queue grows unbounded, the system may run out of memory.

## How to investigate

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

## How to remediate

| Cause                                   | Fix                                                                  |
| --------------------------------------- | -------------------------------------------------------------------- |
| Workers crashed                         | Restart worker containers. Check logs for root cause                 |
| Queue backlog (exam period)             | Scale workers: add more worker containers                            |
| Slow external API (credential issuance) | Check external service. Consider adding timeouts and retry logic     |
| Redis full                              | Increase Redis `maxmemory`. Check for memory leaks in task payloads  |
| Single slow task type                   | Isolate slow queue to dedicated workers so fast tasks aren't blocked |

## Escalation

If queue depth keeps growing after scaling workers, escalate for capacity planning.
