# Environments & Testing - Local, Test, Production

## Directory layout

tests/
  conftest.py                       # shared fixtures (client, token, state reset)
  api/
    test_auth.py                     # POST /auth/token
    test_health.py                   # GET  /health
    test_login.py                    # GET/POST /login
    test_log_secrets.py              # sensitive data logging checks
    test_oauth_pkce_flow.py          # OAuth PKCE flow (in-process, TestClient)
    test_oauth_pkce_flow_docker.py   # OAuth PKCE flow (live Docker, httpx)
    test_routing.py                  # route registration checks
    test_users.py                    # GET  /users, POST /users
  core/
    test_config.py                   # Settings + env var loading
    test_logging.py                  # log formatter tests
  services/
    test_auth_service.py             # password hashing + authentication
    test_users_service.py            # users_service unit tests

The structure mirrors `app/` so every module has a predictable test
location: `app/api/auth.py` -> `tests/api/test_auth.py`.

## Prerequisites

>bash
(one-time setup:  installs project + dev tooling into your venv)
make setup          # or: pip install -e ".[dev]" && pre-commit install

Installs `pytest`, `pytest-cov`, `ruff`, and `pre-commit` from the
`[project.optional-dependencies] dev` group in `pyproject.toml`.

## Running tests

### 1. Local — unit/integration (no server required)

>bash
(picks up quiet from: -q flag via pyproject.toml addopts)
make test

(equivalent to: python -m pytest -q)

These tests use FastAPI's `TestClient`, which runs the app in-process --
no uvicorn, no Docker, no network. The `docker`-marked tests are excluded
by default via `addopts = "-q -m 'not docker'"` in `pyproject.toml`.

## verbose / single file / single test

python -m pytest -v -m 'not docker'
python -m pytest tests/api/test_auth.py
python -m pytest tests/api/test_auth.py::test_auth_token_accepts_good_creds_and_returns_token_and_expiry

(with coverage)
python -m pytest --cov=app --cov-report=term-missing -m 'not docker'

**Environment used:** whatever is in your `.env` (typically `APP_ENV=dev`).
Pytest does not override `APP_ENV` by default, so `SETTINGS.is_dev` will be
`True` during local runs.  The test suite does not depend on any particular
`APP_ENV` value today, but if you add env-specific tests, set it explicitly:

bash>
APP_ENV=test python -m pytest -q

### 1b. Local — Docker integration (live container required)

Tests in `test_oauth_pkce_flow_docker.py` use `httpx` to send real HTTP
requests to a running Docker container. They are marked `@pytest.mark.docker`
and skipped by default.

>bash
(Terminal 1: start the container)
docker build -f docker/Dockerfile --target runtime -t auth-service:dev .
docker run --rm --name auth-service-dev -p 8000:8000 \
  --env-file .env auth-service:dev

(Terminal 2: run only Docker integration tests)
pytest -m docker -v --log-cli-level=INFO

The `PORT` env var (default `8000`) controls which port both the container
and the test suite use. Set it in `.env` to change the port.

### 2. Docker (containerized)

The Dockerfile has a dedicated **Stage 3 (`devtest`)** that extends the
production `runtime` stage with dev tooling.

>bash
(build the test image: targets the devtest stage)
docker build -f docker/Dockerfile --target devtest -t auth-service:test .

(run tests)
docker run --rm auth-service:test

(... or use compose, which builds + runs in one step, mounts local code)
docker compose -f docker/docker-compose.yml run --rm test

`docker run` (image-only)
Source Code - baked into image at build time
Env vars - `APP_ENV=test` (set in Dockerfile)
Rebuild needed after code change? YES
User - `appuser` (non-root)

`docker compose run --rm test`
Source Code - Mounted from host (`../:/app`) -- picks up local edits
Env vars - `.env` loaded via `env_file`, then overridden to `APP_ENV=test
Rebuild needed after code change? NO (volume mount)
User:`appuser` (non-root)

### 3. CI (GitHub Actions)

Tests run automatically on every push and pull request via
`.github/workflows/ci.yml`.  The CI job:

1. Checks out the repo
2. Installs Python 3.12 + `pip install -e ".[dev]"`
3. Runs `ruff check .` (lint)
4. Runs `ruff format --check .` (format)
5. Runs `pytest -q`
6. Builds the Docker image and verifies it runs as non-root

CI does **not** use Docker for the test step itself -- it runs pytest
directly on the runner.  The Docker build + non-root check is a separate
validation step.

## Environment variables reference

`APP_ENV`
    defaults to: `dev`
    set 3 places: `.env`, Dockerfile `ENV`, compose `environment:`
    Controls `SETTINGS.is_dev/is_test/is_prod`.
    The `devtest` Docker stage and compose `test` service both set this to `test`

`LOG_LEVEL`
    one of:  `debug`, `info`, `warning`, `error`.
    No direct test impact

`PORT`
    defaults to: `8000`
    set in: `.env`, Dockerfile `ENV`
    Controls uvicorn bind port and Docker integration test target URL

`TOKEN_SIGNING_SECRET`
    hard-coded:  `dev-only-secret-change-me`
    set by:  `os.getenv()` in `app/api/auth.py`
    Used by the `token` fixture to issue and validate HMAC tokens.
    The default works for dev/test; production must set a real secret.

### What changes across environments

`/docs` and `/redoc` endpoint
dev:  Enabled
test: Disabled
prod: Disabled

`TOKEN_SIGNING_SECRET`
dev:  Falls back to hardcoded default
test: Falls back to hardcoded default
prod: **Must** be set via env var |

Docker user
dev:  root (compose volume mount)
test: `appuser`
prod: `appuser` |

`--reload` (uvicorn)
(compose `command:`)
dev:  Yes  
test: No
prod: No

## Key files that affect test behavior

pyproject.toml [tool.pytest.ini_options]
  testpaths = ["tests"], addopts = "-q -m 'not docker'"
  markers = ["docker: tests that require a running Docker container"]

tests/conftest.py
  `reset_users_state` (autouse) -- resets the in-memory user list before every test.
  `client` -- FastAPI `TestClient`
  `token` -- valid bearer token for protected endpoints

tests/api/test_oauth_pkce_flow_docker.py
  Docker integration tests using `httpx`. Marked `@pytest.mark.docker`.
  Requires a running container; excluded from default `pytest -q` runs.

.env / .env.example
  Loaded by compose; not loaded automatically by pytest on the host

docker/Dockerfile (stage `devtest`)
  Installs `.[dev]` extras, sets `APP_ENV=test`, runs as `appuser`

docker/docker-compose.yml (service `test`)
  Targets `devtest` stage, mounts local code, forces `APP_ENV=test`

.github/workflows/ci.yml
  Runs lint + format + pytest on `ubuntu-latest` with Python 3.12

## Fixtures (tests/conftest.py)

`reset_users_state` | function | Automatic
Restores `_FAKE_USERS` to the two seed users before every test so tests are isolated

`client` | function
Returns a `fastapi.testclient.TestClient` bound to the app

`token` | function
Authenticates as user `tee` and returns a valid `access_token` string. Inject this into any test that hits a protected endpoint

### Usage

python
def test_example(client: TestClient, token: str) -> None:
    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

## Troubleshooting

`ModuleNotFoundError: No module named 'app'`
  Project not installed in editable mode
  `pip install -e ".[dev]"` or `make setup`

Tests pass locally but fail in Docker
  Stale image; code changed but image was not rebuilt
  Rebuild: `docker compose -f docker/docker-compose.yml build test`

`ValueError: APP_ENV must be dev\|test\|prod`
  Typo or missing env var
  Check `.env` or the `environment:` block in `docker-compose.yml`
  
Fixture `token` fails with 401
  Hardcoded credentials changed in `auth.py`
  Update the `token` fixture in `conftest.py` to match
