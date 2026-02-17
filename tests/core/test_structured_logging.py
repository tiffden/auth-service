"""Tests for structured (JSON) logging output.

WHY TEST LOG FORMAT:
If your log pipeline (ELK, Datadog) expects JSON and you accidentally
ship plain text, all log parsing breaks silently — logs arrive but
can't be searched or filtered.  These tests catch that before production.
"""

from __future__ import annotations

import json
import logging

from app.core.logging import _ContainerFormatter, _JsonFormatter


def test_json_formatter_produces_valid_json() -> None:
    """_JsonFormatter output must be parseable as JSON."""
    formatter = _JsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Hello %s",
        args=("world",),
        exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test.logger"
    assert parsed["message"] == "Hello world"
    assert "timestamp" in parsed


def test_json_formatter_includes_extra_fields() -> None:
    """Context fields injected by middleware appear in JSON output."""
    formatter = _JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    # Simulate what the RequestContextMiddleware does
    record.request_id = "abc-123"  # type: ignore[attr-defined]
    record.method = "GET"  # type: ignore[attr-defined]
    record.path = "/health"  # type: ignore[attr-defined]
    record.duration_ms = 12.5  # type: ignore[attr-defined]

    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["request_id"] == "abc-123"
    assert parsed["method"] == "GET"
    assert parsed["path"] == "/health"
    assert parsed["duration_ms"] == 12.5


def test_json_formatter_includes_exception_info() -> None:
    """Exception info appears as an 'exception' key in JSON output."""
    import sys

    formatter = _JsonFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Something failed",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)

    parsed = json.loads(output)
    assert "exception" in parsed
    assert "ValueError: test error" in parsed["exception"]


def test_container_formatter_still_works() -> None:
    """Regression: existing human-readable format is unchanged."""
    formatter = _ContainerFormatter()
    record = logging.LogRecord(
        name="app.main",
        level=logging.INFO,
        pathname="main.py",
        lineno=10,
        msg="server started",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    # Should contain level, logger name, and message as plain text
    assert "INFO" in output
    assert "app.main" in output
    assert "server started" in output
    # Should NOT be JSON
    try:
        json.loads(output)
        raise AssertionError("Container format should not be valid JSON")
    except json.JSONDecodeError:
        pass  # expected
