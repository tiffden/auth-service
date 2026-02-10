from __future__ import annotations

import logging

from app.core.logging import _ContainerFormatter, setup_logging


def test_setup_logging_sets_root_level() -> None:
    setup_logging("debug")
    assert logging.getLogger().level == logging.DEBUG

    setup_logging("warning")
    assert logging.getLogger().level == logging.WARNING


def test_setup_logging_defaults_to_info_for_unknown_level() -> None:
    setup_logging("nonexistent")
    assert logging.getLogger().level == logging.INFO


def test_setup_logging_quiets_uvicorn_at_debug() -> None:
    setup_logging("debug")
    assert logging.getLogger("uvicorn").level == logging.WARNING


def test_setup_logging_allows_uvicorn_at_error() -> None:
    setup_logging("error")
    assert logging.getLogger("uvicorn").level == logging.ERROR


def test_formatter_excludes_location_for_info() -> None:
    fmt = _ContainerFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    output = fmt.format(record)
    assert "hello" in output
    assert "[test.py:" not in output


def test_formatter_includes_location_for_warning() -> None:
    fmt = _ContainerFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="test.py",
        lineno=42,
        msg="bad thing",
        args=(),
        exc_info=None,
    )
    output = fmt.format(record)
    assert "bad thing" in output
    assert "[test.py:42]" in output


def test_formatter_includes_location_for_error() -> None:
    fmt = _ContainerFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="svc.py",
        lineno=99,
        msg="broke",
        args=(),
        exc_info=None,
    )
    output = fmt.format(record)
    assert "[svc.py:99]" in output
