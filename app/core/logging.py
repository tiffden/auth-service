from __future__ import annotations

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


def setup_logging(level_name: str) -> None:
    """Configure root logger for container environments.

    - Sends everything to stdout (Docker captures stdout/stderr)
    - Applies the container formatter
    - Quiets noisy third-party loggers
    """
    level = getattr(logging, level_name.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ContainerFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Keep third-party loggers from flooding at DEBUG
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "httpcore", "httpx"):
        logging.getLogger(name).setLevel(max(level, logging.WARNING))
