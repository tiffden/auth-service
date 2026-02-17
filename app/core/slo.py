"""SLO (Service Level Objective) definitions for auth-service.

WHAT ARE SLIs, SLOs, AND SLAs?
---------------------------------
Imagine a pizza delivery service:

  SLI (Service Level Indicator):
    "How long does delivery actually take?"
    A measurable property — you can compute it from data.

  SLO (Service Level Objective):
    "95% of deliveries arrive within 30 minutes."
    An internal quality target your team agrees on.

  SLA (Service Level Agreement):
    "If delivery takes > 60 minutes, the pizza is free."
    A contractual promise with financial consequences.

For our auth-service:

  SLI: Percentage of requests returning non-5xx status codes
  SLO: 99.5% of requests succeed (availability)

  SLI: 95th percentile response time
  SLO: p95 latency < 500ms

  SLI: Percentage of background tasks completing within 10 seconds
  SLO: 95% of tasks complete within 10s

ERROR BUDGET
--------------
If your SLO is 99.5% availability, your ERROR BUDGET is 0.5%.
Out of 10,000 requests, 50 can fail before you breach the SLO.

This budget is powerful for engineering decisions:
  - "Can we deploy on Friday?" → Check the error budget.
    If 0.4% is already spent this month, probably not.
  - "Should we add a risky feature?" → How much budget is left?
  - "Do we need to invest in reliability?" → Is the budget
    consistently exhausted before the end of each month?

The error budget turns reliability from a vague goal ("make it more
reliable") into a quantifiable resource you can spend and track.

WHY DEFINE SLOs IN CODE (NOT JUST A WIKI PAGE)?
  Because code-defined SLOs can be:
  - Evaluated at runtime (the health endpoint reports SLO status)
  - Tested (unit tests verify the computation logic)
  - Version-controlled (SLO changes show up in git history)
  - Used to drive alerts (breach → PagerDuty notification)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SLODefinition:
    """A single SLO target.

    name:        Human-readable identifier (e.g., "availability")
    description: What this SLO measures and why it matters
    target:      The target percentage (e.g., 99.5 means 99.5%)
    window:      Rolling evaluation window (e.g., "30d" = 30 days)
    """

    name: str
    description: str
    target: float
    window: str


@dataclass(frozen=True, slots=True)
class SLOStatus:
    """Current status of an SLO evaluation.

    slo:              The SLO definition being evaluated
    current:          The actual measured value (e.g., 99.8%)
    budget_remaining: Error budget left (positive = healthy, negative = breached)
    healthy:          True if current >= target
    """

    slo: SLODefinition
    current: float
    budget_remaining: float
    healthy: bool


# ---------------------------------------------------------------------------
# SLO definitions for auth-service
# ---------------------------------------------------------------------------

AVAILABILITY_SLO = SLODefinition(
    name="availability",
    description="Percentage of non-5xx responses (successful requests)",
    target=99.5,
    window="30d",
)

LATENCY_SLO = SLODefinition(
    name="latency_p95",
    description="95th percentile response time under 500ms",
    target=95.0,
    window="30d",
)

QUEUE_PROCESSING_SLO = SLODefinition(
    name="queue_processing",
    description="95% of background tasks complete within 10 seconds",
    target=95.0,
    window="7d",
)

ALL_SLOS = [AVAILABILITY_SLO, LATENCY_SLO, QUEUE_PROCESSING_SLO]


# ---------------------------------------------------------------------------
# Pure evaluation functions — no I/O, just math
# ---------------------------------------------------------------------------
# These functions take metric values as arguments (not read from Prometheus).
# This separation makes them trivially testable: pass in numbers, get a status.


def evaluate_availability(total_requests: int, error_requests: int) -> SLOStatus:
    """Compute current availability SLO status.

    availability = (total - errors) / total × 100

    Example:
      10,000 total, 10 errors → 99.9% → healthy (target 99.5%)
      10,000 total, 100 errors → 99.0% → breached
    """
    if total_requests == 0:
        # No data yet — assume healthy (can't have errors with no requests)
        current = 100.0
    else:
        current = ((total_requests - error_requests) / total_requests) * 100

    budget_remaining = current - AVAILABILITY_SLO.target
    return SLOStatus(
        slo=AVAILABILITY_SLO,
        current=round(current, 3),
        budget_remaining=round(budget_remaining, 3),
        healthy=current >= AVAILABILITY_SLO.target,
    )


def evaluate_latency(p95_ms: float) -> SLOStatus:
    """Compute current latency SLO status.

    We measure: "what percentage of requests complete in under 500ms?"
    The p95_ms argument is the 95th percentile latency in milliseconds.

    If p95 < 500ms, then ≥95% of requests are fast enough → healthy.
    If p95 ≥ 500ms, then <95% of requests meet the bar → breached.

    For the SLO status, we express this as "the percentage of requests
    that are within the 500ms threshold" — approximated from the p95 value.
    """
    threshold_ms = 500.0
    if p95_ms <= threshold_ms:
        # p95 is under threshold, so ≥95% of requests are fast enough
        current = 95.0 + (threshold_ms - p95_ms) / threshold_ms * 5.0
        current = min(current, 100.0)
    else:
        # p95 exceeds threshold — fewer than 95% of requests are fast enough
        current = max(0.0, 95.0 - (p95_ms - threshold_ms) / threshold_ms * 95.0)

    budget_remaining = current - LATENCY_SLO.target
    return SLOStatus(
        slo=LATENCY_SLO,
        current=round(current, 3),
        budget_remaining=round(budget_remaining, 3),
        healthy=current >= LATENCY_SLO.target,
    )


def evaluate_queue_processing(total_tasks: int, slow_tasks: int) -> SLOStatus:
    """Compute current queue processing SLO status.

    A task is "slow" if it takes more than 10 seconds to complete.
    The SLO target is 95% of tasks completing within 10s.
    """
    if total_tasks == 0:
        current = 100.0
    else:
        current = ((total_tasks - slow_tasks) / total_tasks) * 100

    budget_remaining = current - QUEUE_PROCESSING_SLO.target
    return SLOStatus(
        slo=QUEUE_PROCESSING_SLO,
        current=round(current, 3),
        budget_remaining=round(budget_remaining, 3),
        healthy=current >= QUEUE_PROCESSING_SLO.target,
    )
