# Deployment Strategy

This document covers the two primary deployment strategies for auth-service and the rollback procedure for each.

## Blue/Green Deployment

### How it works

```html
                    ┌──────────────┐
         100%       │  Blue (v1)   │  ← currently serving all traffic
Traffic ──────────► │  3 replicas  │
                    └──────────────┘

                    ┌──────────────┐
         0%         │  Green (v2)  │  ← new version, running but receiving no traffic
                    │  3 replicas  │
                    └──────────────┘
```

1. **Deploy** the new version (Green) alongside the current version (Blue)
2. **Smoke test** Green with internal traffic or synthetic requests
3. **Flip** the load balancer to route 100% of traffic to Green
4. **Monitor** for a bake period (15-30 minutes)
5. If healthy: decommission Blue
6. If unhealthy: flip back to Blue (instant rollback)

### Pros and cons

| Aspect | Blue/Green |
| -------- | ----------- |
| Rollback speed | Instant (flip the LB back) |
| Resource cost | 2x infrastructure during deployment |
| Risk | All-or-nothing — if v2 has a subtle bug, 100% of users see it |
| Complexity | Low (binary switch) |
| Best for | Small services, low-traffic, confidence in staging tests |

## Canary Deployment

### How deployment works

```html
Phase 1:   95% → Blue (v1)     5% → Green (v2)
Phase 2:   75% → Blue (v1)    25% → Green (v2)
Phase 3:   50% → Blue (v1)    50% → Green (v2)
Phase 4:    0% → Blue (v1)   100% → Green (v2)  ✓ done
```

1. **Deploy** v2 to a small subset (5% of traffic)
2. **Monitor** SLOs for 10-15 minutes:
   - Error rate: is v2's error rate higher than v1's?
   - Latency: is v2's p95 higher than v1's?
   - Custom metrics: any anomalies in rate limiting, cache hit ratio?
3. If SLOs hold: **promote** to 25%, then 50%, then 100%
4. If SLOs breach at any stage: **rollback** to 0% (all traffic back to v1)

### SLO-gated promotion

The key advantage of canary is using SLOs as promotion gates:

```html
Deploy 5% → Wait 10min → Check SLOs → If healthy → Promote to 25%
                                      → If breached → Rollback to 0%
```

This is the recommended strategy for auth-service because:

- Auth failures are high-impact: users can't log in
- SLOs are already defined and measured (availability, latency)
- Gradual rollout limits blast radius

### Pros and cons of canary

| Aspect | Canary |
| -------- | -------- |
| Rollback speed | Fast (route back to v1) |
| Resource cost | v1 + small v2 footprint |
| Risk | Limited — only 5% of users see a bad deploy initially |
| Complexity | Higher (traffic splitting, metric comparison) |
| Best for | High-traffic services, critical paths, services with SLOs |

## Rollback Procedure

### When to rollback

Trigger a rollback when ANY of these conditions are met:

1. **Availability SLO breach**: Error rate exceeds 0.5% (check Grafana "Error Rate" panel)
2. **Latency SLO breach**: p95 latency exceeds 500ms (check "Latency Percentiles" panel)
3. **Health check failures**: `/health` returns degraded or `/ready` returns 503
4. **Functional regression**: Core flows (login, token issuance) return unexpected errors

### Rollback steps

#### Blue/Green rollback

```bash
# 1. Flip load balancer back to Blue (v1)
#    In AWS ALB: change target group
#    In Kubernetes: update Service selector
#    In Docker Compose: restart with previous image tag

# 2. Verify traffic is flowing to v1
curl -s http://localhost:8000/health | jq .status
# Expected: "ok"

# 3. Investigate v2 failure (do NOT delete Green yet)
#    Check logs:  docker logs auth-service-api-dev | grep ERROR
#    Check metrics: Grafana → Error Rate panel → look for spike at deploy time

# 4. Once root cause is identified, fix and re-deploy
```

#### Canary rollback

```bash
# 1. Route 100% traffic back to v1 (set canary weight to 0%)
# 2. Verify SLOs recover within 5 minutes
# 3. Investigate the canary failure
# 4. Fix, re-deploy, start canary again from 5%
```

### Post-rollback checklist

- [ ] Verify all SLOs are back to healthy
- [ ] Notify the team (Slack/email) with timeline and impact
- [ ] Create a post-incident ticket with root cause
- [ ] Update deployment notes for the next attempt
