# Alert Runbooks

Each runbook follows the same structure:

1. **What is this alert?** — plain-language description
2. **Why does it matter?** — user impact
3. **How to investigate** — specific commands and dashboards
4. **How to remediate** — common fixes
5. **Escalation** — when to involve others

## Runbooks

- [Availability SLO Breach](availability-slo-breach.md) — error rate exceeds 0.5%
- [Latency SLO Breach](latency-slo-breach.md) — p95 response time exceeds 500ms
- [Queue Processing SLO Breach](queue-processing-slo-breach.md) — >5% of tasks taking >10s

## General Investigation Tips

1. **Correlate with deployments**: Check `git log --oneline -5` to see if a recent commit correlates with the alert
2. **Check all three pillars**: Logs (what happened), Metrics (how bad), Dashboard (when it started)
3. **Use request IDs**: The `X-Request-ID` header lets you trace a specific failed request through all log lines
4. **Don't panic**: SLO breaches are normal. That's what the error budget is for. Investigate calmly, fix methodically
