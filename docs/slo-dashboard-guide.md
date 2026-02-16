# SLO Dashboard Guide

This guide explains each panel on the Grafana dashboard (`Auth Service — SLO Dashboard`) and how to read the data.

**Access**: http://localhost:3000 (after `docker compose up`)

## Dashboard Layout

```
┌─────────────────────────┬──────────────────────────┐
│  Request Rate (req/s)   │  Error Rate (%) + SLO    │
│  by status code         │  line at 0.5%            │
├─────────────────────────┼────────────┬─────────────┤
│  Latency Percentiles    │  Active    │ Rate Limit  │
│  p50 / p95 / p99        │  Requests  │ Rejections  │
├────────────┬────────────┼────────────┼─────────────┤
│ Cache Hit  │ Task Queue │  Token Blacklist Checks   │
│   Ratio    │   Depth    │  valid vs revoked         │
└────────────┴────────────┴───────────────────────────┘
```

## Panel-by-Panel Guide

### Request Rate (req/s)
**What it shows**: HTTP requests per second, split by status code (200, 401, 404, 429, 500, etc.)

**How to read it**:
- Green (200) should dominate — these are successful requests
- Yellow/orange (4xx) are client errors — expected for auth failures, rate limits
- Red (5xx) are server errors — these eat your error budget

**What to look for**:
- Sudden drop in request rate → possible outage or load balancer issue
- Spike in 5xx → check logs for the root cause
- Growing 429 rate → clients are being rate-limited (check if legitimate)

### Error Rate (%) — SLO: 99.5% availability
**What it shows**: Percentage of responses that are 5xx, with a red threshold line at 0.5%

**How to read it**:
- Line below 0.5% = SLO healthy, error budget being preserved
- Line above 0.5% = SLO breached, investigate immediately
- The gap between the line and 0.5% = your remaining error budget

**PromQL behind this panel**:
```
sum(rate(http_requests_total{status_code=~"5.."}[5m]))
  / sum(rate(http_requests_total[5m])) * 100
```

### Latency Percentiles — SLO: p95 < 500ms
**What it shows**: Three lines — p50 (median), p95, p99 response times

**How to read it**:
- p50 (median): half of requests are faster than this. Your "typical" user experience
- p95: 95% of requests are faster than this. This is the SLO target — should be <500ms
- p99: 99% of requests are faster. The "worst case" for almost all users

**Why three lines**:
- p50 dropping while p99 spikes → a few requests are very slow (check specific endpoints)
- All three rising together → systemic slowdown (check CPU, memory, DB)

### Active Requests (Gauge)
**What it shows**: How many HTTP requests are currently being processed

**How to read it**:
- Low number (0-10) = healthy, plenty of capacity
- Sustained high number = approaching saturation
- If this equals your worker/thread count, you're at capacity

### Rate Limit Rejections (/s)
**What it shows**: Requests rejected with 429 (Too Many Requests), split by key type (user vs IP)

**How to read it**:
- Occasional spikes are normal (a user refreshing rapidly)
- Sustained high rate from "ip" key type → possible bot/attack
- Sustained from "user" key type → a specific user is hitting limits (check if the limit is too strict)

### Cache Hit Ratio (Gauge)
**What it shows**: Percentage of cache lookups that returned cached data

**How to read it**:
- >80% (green) = cache is effective, most reads skip the database
- 50-80% (yellow) = moderate — consider increasing TTL or warming cache
- <50% (red) = cache is mostly missing — check if TTL is too short or if cache was recently flushed

**After a deployment**: Expect the hit ratio to drop temporarily (caches are cold). It should recover within a few minutes.

### Task Queue Depth
**What it shows**: Number of tasks waiting in each queue (credential_issuance, grading)

**How to read it**:
- 0 = workers are keeping up (ideal)
- Small number (1-10) = normal backlog, being processed
- Growing steadily = workers can't keep up → scale workers
- Sudden spike = burst of submissions (exam?) or workers crashed

### Token Blacklist Checks (/s)
**What it shows**: Rate of blacklist lookups, split by result (valid vs revoked)

**How to read it**:
- "valid" should be much higher than "revoked" (most tokens are active)
- Spike in "revoked" = many users logging out or tokens being revoked (password reset?)
- This metric running at 0 = blacklist check might be broken (verify `require_user` includes the check)

## Using the Dashboard for Incident Response

1. **When an alert fires**: Open the dashboard and look at the time range around the alert
2. **Correlate panels**: Did the error rate spike when latency increased? Did queue depth grow when rate limits spiked?
3. **Zoom in**: Click and drag on any panel to zoom into a specific time range
4. **Compare with deployment**: Check git log for recent deployments that correlate with changes
