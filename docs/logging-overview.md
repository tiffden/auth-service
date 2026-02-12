# Core — Configuration & Logging

This directory contains the application's cross-cutting infrastructure:
config loading, environment validation, and structured logging.

## Files

    app/core/
      __init__.py
      config.py       # Settings dataclass, load_settings(), APP_ENV / LOG_LEVEL validation
      logging.py       # Container-friendly formatter, setup_logging()

## How logging is wired up

`app/main.py` calls `setup_logging(SETTINGS.log_level)` at import time,
before any router is registered.  Every module that needs to log creates
its own logger:

    logger = logging.getLogger(__name__)

This produces a logger hierarchy that mirrors the package tree:

    app.main
    app.api.auth
    app.api.users
    app.services.users_service

## Output destination

All log output goes to **stdout** (via `logging.StreamHandler(sys.stdout)`).
Nothing is written to files.  This is deliberate for containers —
Docker and orchestrators capture stdout/stderr automatically.

`PYTHONUNBUFFERED=1` is set in the Dockerfile so log lines appear
immediately without Python buffering them.

### Viewing logs

Local (no Docker):

    # uvicorn prints to the terminal you started it from
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    # or
    LOG_LEVEL=debug uvicorn app.main:app --host 0.0.0.0 --port 8000

Docker Compose (dev):

    # follow live logs for the api service
    docker compose -f docker/docker-compose.yml logs -f api

    # follow live logs for the test service
    docker compose -f docker/docker-compose.yml logs -f test

Docker standalone:

    # foreground (logs print directly)
    docker run --rm -p 8000:8000 auth-service:dev

    # detached — read logs afterward
    docker run -d --name auth auth-service:dev
    docker logs auth
    docker logs -f auth          # follow
    docker logs --tail 50 auth   # last 50 lines

CI (GitHub Actions):

    Logs appear in the step output for "Test (pytest)".
    pytest captures log output by default; add -s to see it live.

## Log format

    <timestamp> <LEVEL>    <logger>  <message>  [<file>:<line>]
                                                  ↑ WARNING+ only

Examples:

    2026-02-10T09:00:00-0600 INFO     app.main  auth-service started  env=dev log_level=info docs=on
    2026-02-10T09:00:01-0600 INFO     app.api.auth  Token issued for user=tee
    2026-02-10T09:00:02-0600 WARNING  app.api.auth  Login failed for user=hacker  [auth.py:38]
    2026-02-10T09:00:03-0600 WARNING  app.api.auth  Expired token rejected for user=tee  [auth.py:76]
    2026-02-10T09:00:04-0600 INFO     app.services.users_service  Created user id=3 email=new@example.com

Key points:
    Timestamps are ISO-8601 with timezone offset
    `[filename:lineno]` is appended only at WARNING and above
    Stack traces are included when the caller uses `logger.exception()`
        or `logger.error(..., exc_info=True)` (ERROR and CRITICAL)

## Log levels — what goes where

    DEBUG       Token validation steps, internal decisions
                → only visible when LOG_LEVEL=debug
                → no file:line, no stack trace

    INFO        Normal operations worth recording
                → token issued, user created, app started
                → no file:line, no stack trace

    WARNING     Expected client errors / suspicious activity
                → bad credentials, expired token, tampered signature
                → duplicate email, blank email
                → includes [file:line], no stack trace

    ERROR       Unexpected failures (should trigger alerts)
                → unhandled exceptions in request handlers
                → includes [file:line] and stack trace

    CRITICAL    App cannot start or continue
                → missing required config, can't bind port
                → includes [file:line] and stack trace

## Current log statements

    app.main
      INFO   "auth-service started  env=... log_level=... docs=..."

    app.api.auth
      WARNING "Login failed for user=..."
      INFO    "Token issued for user=..."
      WARNING "Malformed token rejected"
      WARNING "Expired token rejected for user=..."
      WARNING "Invalid signature rejected for user=..."
      DEBUG   "Token validated for user=..."

    app.api.users
      WARNING "Duplicate user rejected email=..."
      WARNING "Invalid user payload: ..."

    app.services.users_service
      WARNING "Rejected blank email"
      WARNING "Rejected duplicate email=..."
      INFO    "Created user id=... email=..."

## Environment differences

### LOG_LEVEL control

The `LOG_LEVEL` env var drives everything.  It is read by
`config.py` and passed to `setup_logging()`.

    .env.example default:   info
    Dockerfile runtime:     not set (inherits .env or defaults to info)
    Dockerfile devtest:     not set (inherits .env or defaults to info)
    Compose api service:    whatever is in .env
    Compose test service:   whatever is in .env

To change the level, set `LOG_LEVEL` in `.env` or override it:

    # local
    LOG_LEVEL=debug make test

    # compose
    LOG_LEVEL=debug docker compose -f docker/docker-compose.yml up api

    # standalone container
    docker run --rm -e LOG_LEVEL=debug -p 8000:8000 auth-service:dev

### What differs by APP_ENV

Default LOG_LEVEL: info

3rd party loggers (uvicorn, httpx) - Quieted to WARNING (or current level if higher)

/docs and /redoc endpoints
    Production: Disabled

PYTHONUNBUFFERED (Docker only) 1

Log destination
    Local: stdout
    Test:  stdout (captured by pytest/caplog
    Production: stdout (captured by Docker/orchestrator)

Logging itself does not change behavior based on APP_ENV — only
LOG_LEVEL matters.  

APP_ENV distinction affects other app behavior (docs endpoints,
future secret-validation strictness) but the logging pipeline is identical
across all three environments.

### Third-party logger suppression

`setup_logging()` sets these loggers to `max(level, WARNING)`:

    uvicorn
    uvicorn.access
    uvicorn.error
    httpcore
    httpx

This prevents uvicorn's per-request access log lines from drowning out
application logs at DEBUG.  At WARNING or above they behave normally.

## Testing logging

Tests use pytest's `caplog` fixture to assert that log events fire at
the expected level with the expected content.  See:

    tests/api/test_auth.py        — auth logging assertions
    tests/api/test_users.py       — user logging assertions
    tests/core/test_logging.py    — formatter and setup_logging() unit tests

Example pattern:

    def test_failed_login_logs_warning(client, caplog):
        with caplog.at_level(logging.WARNING, logger="app.api.auth"):
            client.post("/auth/token", data={...})
        assert any("Login failed" in m for m in caplog.messages)
