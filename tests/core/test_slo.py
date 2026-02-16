"""Tests for SLO evaluation logic.

These tests verify the MATH, not the monitoring system.  The SLO module
is pure functions: give it numbers, get back a status.  No I/O, no
mocking, no network — just arithmetic.
"""

from __future__ import annotations

from app.core.slo import (
    evaluate_availability,
    evaluate_latency,
    evaluate_queue_processing,
)

# ---- Availability SLO (target: 99.5%) ----


def test_availability_healthy() -> None:
    status = evaluate_availability(total_requests=10000, error_requests=10)
    assert status.healthy is True
    assert status.current == 99.9
    assert status.budget_remaining > 0


def test_availability_exactly_at_target() -> None:
    status = evaluate_availability(total_requests=10000, error_requests=50)
    assert status.healthy is True
    assert status.current == 99.5


def test_availability_breached() -> None:
    status = evaluate_availability(total_requests=10000, error_requests=100)
    assert status.healthy is False
    assert status.current == 99.0
    assert status.budget_remaining < 0


def test_availability_zero_requests() -> None:
    """No requests = no errors = healthy (you can't fail what you haven't served)."""
    status = evaluate_availability(total_requests=0, error_requests=0)
    assert status.healthy is True
    assert status.current == 100.0


# ---- Latency SLO (target: p95 < 500ms) ----


def test_latency_healthy() -> None:
    status = evaluate_latency(p95_ms=200.0)
    assert status.healthy is True
    assert status.current >= 95.0


def test_latency_at_threshold() -> None:
    status = evaluate_latency(p95_ms=500.0)
    assert status.healthy is True
    assert status.current >= 95.0


def test_latency_breached() -> None:
    status = evaluate_latency(p95_ms=800.0)
    assert status.healthy is False
    assert status.current < 95.0


def test_latency_zero() -> None:
    """Zero latency = best possible performance."""
    status = evaluate_latency(p95_ms=0.0)
    assert status.healthy is True
    assert status.current == 100.0


# ---- Queue Processing SLO (target: 95% within 10s) ----


def test_queue_processing_healthy() -> None:
    status = evaluate_queue_processing(total_tasks=1000, slow_tasks=10)
    assert status.healthy is True
    assert status.current == 99.0


def test_queue_processing_breached() -> None:
    status = evaluate_queue_processing(total_tasks=100, slow_tasks=10)
    assert status.healthy is False
    assert status.current == 90.0


def test_queue_processing_zero_tasks() -> None:
    status = evaluate_queue_processing(total_tasks=0, slow_tasks=0)
    assert status.healthy is True
    assert status.current == 100.0
