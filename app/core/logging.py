"""Logging configuration for auth-service.

THE THREE PILLARS OF OBSERVABILITY
------------------------------------
Modern services are monitored through three complementary signals:

  1. LOGS — "what happened, in words"
     A timestamped stream of events: "User X logged in", "Query took 3s".
     Good for debugging individual requests.  Bad for answering "what
     percentage of requests are failing right now?" (you'd have to count
     log lines, which is slow and fragile).

  2. METRICS — "what happened, in numbers"
     Counters, gauges, and histograms: total_requests=50432,
     error_rate=0.3%, p99_latency=420ms.  Good for dashboards, alerts,
     and SLO tracking.  Bad for debugging one specific request.

  3. TRACES — "what happened, across services"
     A trace follows one request through multiple services: API → Redis
     → Postgres → Worker.  Each hop is a "span" with timing.  Good for
     finding "which service is slow?"  Bad for aggregate statistics.

This module handles pillar #1 (logs).  See app/core/metrics.py for #2.

WHY TWO FORMATTERS
--------------------
  _ContainerFormatter — human-readable, single-line, for local dev.
    You read these with your eyes in a terminal.

  _JsonFormatter — machine-parseable, for production.
    In production, logs are piped to a log aggregation system (ELK,
    Datadog, CloudWatch Logs).  These systems parse JSON natively:

      {"timestamp": "2024-...", "level": "ERROR", "user_id": "abc123"}

    With JSON, you can filter and aggregate in the aggregation UI:
      level == "ERROR" AND user_id == "abc123"

    With plain text, you'd need fragile regex patterns to extract fields.

    Set LOG_JSON=true in production to switch to JSON output.
"""

from __future__ import annotations

import json
import logging
import sys


class _ContainerFormatter(logging.Formatter):
    """Single-line formatter tuned for container stdout.

    - Always: ISO-8601 timestamp, level, logger name, message
    - WARNING+: appends [filename:lineno] so you can locate the guard clause
    - ERROR/CRITICAL: stack trace included when exc_info is present
      (caller passes exc_info=True or uses logger.exception())
    """

    _BASE_FMT = "%(asctime)s %(levelname)-8s %(name)s  %(message)s"
    _LOC_SUFFIX = "  [%(filename)s:%(lineno)d]"

    def __init__(self) -> None:
        super().__init__(datefmt="%Y-%m-%dT%H:%M:%S%z")

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        base = super().formatTime(record, datefmt)
        ms = int(record.msecs)
        # Insert .NNN before the timezone offset (last 5 chars: +0000)
        return f"{base[:-5]}.{ms:03d}{base[-5:]}"

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno >= logging.WARNING:
            self._style._fmt = self._BASE_FMT + self._LOC_SUFFIX
        else:
            self._style._fmt = self._BASE_FMT
        return super().format(record)


class _JsonFormatter(logging.Formatter):
    """JSON formatter for machine-parseable log output.

    Each log line is a single JSON object — one per line (JSON Lines format).
    Log aggregation systems ingest this natively, no regex needed.

    Extra context fields (request_id, method, path, user_id, duration_ms)
    are injected by the RequestContextMiddleware and appear as top-level
    keys in the JSON output, making them filterable and searchable.
    """

    # Fields that the RequestContextMiddleware may inject into LogRecords.
    _CONTEXT_FIELDS = (
        "request_id",
        "method",
        "path",
        "user_id",
        "status_code",
        "duration_ms",
    )

    def __init__(self) -> None:
        super().__init__(datefmt="%Y-%m-%dT%H:%M:%S%z")

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject any context fields that the middleware attached
        for key in self._CONTEXT_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        # Include exception info when present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging(level_name: str, *, json_format: bool = False) -> None:
    """Configure root logger for container environments.

    - Sends everything to stdout (Docker captures stdout/stderr)
    - Applies the appropriate formatter based on json_format
    - Quiets noisy third-party loggers

    Args:
        level_name: Log level string (debug/info/warning/error)
        json_format: If True, emit JSON lines. If False, human-readable.
                     Controlled by LOG_JSON env var in Settings.
    """
    level = getattr(logging, level_name.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter() if json_format else _ContainerFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Keep third-party loggers from flooding at DEBUG
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "httpcore", "httpx"):
        logging.getLogger(name).setLevel(max(level, logging.WARNING))
