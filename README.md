# auth-service - a FastAPI authentication service

![CI](https://github.com/tiffden/auth-service/actions/workflows/ci.yml/badge.svg?branch=main)

**auth-service** is a security-first authentication and authorization microservice built with FastAPI, designed around explicit threat modeling and strong security invariants. It implements OAuth 2.1–aligned flows (Authorization Code + PKCE), short-lived JWT access tokens with strict claim validation, and server-managed refresh tokens with rotation and revocation support. Role-based access control is enforced server-side using a “thin router, fat service” architecture to prevent client-supplied privilege escalation. Passwords are hashed using Argon2 with calibrated parameters, tokens are time-bounded and audience-scoped, and all privileged operations require server-issued credentials. The service is containerized via multi-stage Docker builds, integrates CI for linting and test enforcement, and isolates configuration via environment separation to avoid secret leakage. The project emphasizes defensive design, testable security boundaries, and operational clarity consistent with modern backend security practices.

## Security Model

This service is designed under an explicit threat model assuming untrusted clients, token interception attempts, replay attacks, and privilege escalation attempts. Authentication and authorization are strictly separated: identity is established via OAuth 2.1–aligned flows (Authorization Code + PKCE), while authorization decisions are enforced server-side within the service layer—not derived from client input. Access tokens are short-lived, cryptographically signed JWTs with validated issuer, audience, expiration, and scope claims. Refresh tokens are opaque, server-stored, rotated on use, and revocable to limit replay risk. Passwords are hashed using Argon2 with tuned cost parameters to resist GPU-based cracking. No endpoint trusts client-supplied role data, and all privileged actions require a verified server-issued token. Configuration and secrets are environment-scoped to prevent leakage across dev/test/prod boundaries. Security invariants are enforced via automated tests and CI to prevent regression.

## Project Structure

```text
app/
  api/       # FastAPI route handlers
  core/      # config, logging, and security helpers
  db/        # SQLAlchemy engine, session factory, table definitions
  models/    # domain entities (frozen dataclasses)
  repos/     # data access/repository layer (Protocol + implementations)
  services/  # business logic/use cases
  main.py    # app factory/wiring
alembic/
  versions/  # migration scripts
  env.py     # migration environment config
docker/
  Dockerfile
  docker-compose.yml
tests/
  api/
  core/
  services/
```

## Components

FastAPI app  →  Uvicorn (ASGI server)  →  Python process  →  Docker container

**FastAPI** - Python object model to provide async API functionality

**Uvicorn** - ASGI Server
 • Bind to a TCP port
 • Accept HTTP connections
 • Translate HTTP → ASGI calls
 • Run the FastAPI async app instance

**Python process** - auth-server/main.py
 • Creates async app using a FastAPI function: *app=FastAPI()*
 • Adds routers to the asynch app using FastAPI function: *APIRouter(tags=["health"])*
 • Attaches endpoints to routers using FastAPI function in decorators: *@router.get("/health")*
 • Provides the handlers for processing and response creation for the endpoints:  *get, post*

**Docker container** - wraps the above components

1) Docker Build - packages into an **image**:
 • Python
 • Dependencies
 • auth-service code
 • The command to run it (uvicorn)
2) Docker Run - starts a container from the image
 • Executes the CMD in the Dockerfile: *CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", port...]*

**Host 0.0.0.0**
The selection of Host 0.0.0.0 exposes the port outside of Docker.

## 1) Development Environment

### Initial Tools

On a clean macOS, you need four things from Homebrew:

1) **python@3.12** — The project requires >=3.12 and the README uses python3.12 explicitly

2) **git** — macOS includes Apple Git via Xcode CLT, but Homebrew's is newer and avoids needing the full Xcode install

3) **gh** — (optional) GitHub CLI, used in the "Merge Changes into Main" section for gh pr create

4) **Docker** — For building/running container images (use homebrew or install app from docker.com)

```bash
brew install python@3.12 git gh
brew install --cask docker
```

That's it. Everything else (fastapi, uvicorn, ruff, pytest, pre-commit, argon2-cffi) is Python-level and gets installed via pip install -e ".[dev]". No system-level C libraries are needed — argon2-cffi ships pre-built wheels for macOS.

### Create New `.venv`

```bash
# from repo root
python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Set Environment 'dev' and Log Level (found in root/.env)

```bash
cp .env.example .env
```

In **.env**, set: `APP_ENV=dev`

- `APP_ENV`: `dev` | `test` | `prod` (default: `dev`)
- `LOG_LEVEL`: `debug` | `info` | `warning` | `error` (default: `info`)
- `DATABASE_URL`: PostgreSQL connection string (omit to use in-memory repos)

### Start PostgreSQL (via Docker Compose)

The app works without a database (in-memory repos), but to develop
against Postgres:

```bash
docker compose -f docker/docker-compose.yml up -d postgres
```

Then add to your `.env`:

```bash
DATABASE_URL=postgresql+asyncpg://auth:auth@localhost:5432/auth_service
```

Run migrations to create the schema:

```bash
alembic upgrade head
```

To check Postgres is running:

```bash
docker compose -f docker/docker-compose.yml ps
```

To stop Postgres (data persists in the `pgdata` volume):

```bash
docker compose -f docker/docker-compose.yml stop postgres
```

To stop and remove the volume (fresh start):

```bash
docker compose -f docker/docker-compose.yml down -v
```

### Start a Feature Branch

Always work on a branch, not directly on `main`:

1) switch to main branch
2) pull latest code
3) create a new branch

```bash
git checkout main
git pull origin main
git checkout -b feature/short-description
```

### After Pulling Changes (or Adding to the Project)

Pull in any new code, then any changed dependencies:

```bash
git pull origin main
python -m pip install -e ".[dev]"
```

### Terminal 1 - Run ASGI Server

For fast debugging, *don't build and run Docker*, just run the ASGI server directly
and test calls to it from a second terminal.

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2 - Test Code

Health check of server:

```bash
curl -s http://127.0.0.1:8000/health
```

Run auth-service tests:

```bash
python -m pytest -q
make ci
```

`make ci` runs:

1. `python -m ruff check .`
2. `python -m ruff format --check .`
3. `python -m pytest -q`

### Terminal 1 - Run Docker At Least Once Before Committing Code

Stop uvicorn (Ctrl+C)

Start Docker daemon:  Run the MacOS Docker app in: *Applications directory*

```bash
docker build -f docker/Dockerfile --target runtime -t auth-service:dev .
docker run --rm --name auth-service-dev -p 8000:8000 --env-file .env auth-service:dev
```

### Terminal 2 - Run Checks and Docker Tests

Always verify before committing. Run the full CI check and the Docker
integration tests:

```bash
make ci
make test-docker
```

`make ci` runs lint, format check, and the unit/integration test suite.
`make test-docker` runs the Docker-dependent tests against a live
container (`pytest -m docker -v --log-cli-level=INFO`). Both should
pass cleanly before you commit.

### Check Code into Git

Stage specific files (avoid `git add .` which can accidentally include
`.env` or other secrets):

```bash
git status
git add app/services/auth_service.py tests/api/test_auth.py
git commit -m "feat: Imperative-verb task description"
git push -u origin feature/short-description
```

### Merge Changes into Main

Open a pull request on GitHub for review before merging to `main`:

Create the PR through the GitHub web UI. Once CI passes and the PR
is approved:

1. Merge the PR on GitHub (prefer "Squash and merge" for a clean history)
2. Delete the remote feature branch (GitHub offers this after merge)
3. Locally, switch back and clean up:

```bash
git checkout main
git pull origin main
```

If continuing with a new feature, create your new branch

```bash
git checkout -b my-new-branch-name
git push -u origin my-new-branch-name
```

## 2) Staging/Test Environment

Staging mirrors production as closely as possible. Its purpose is to
**validate a release candidate**, not to develop features. Code changes
happen in dev; staging proves they work in a production-like container
before going live.

### Use the Same Clone — Switch to the Release Branch

No separate directory needed. Use your existing clone and check out
the branch or tag you want to validate

```bash
git fetch origin
git checkout main
```

### Set Environment 'test' and Log Level 'info' (found in root/.env)

cp .env.example .env
In **.env**, set: `APP_ENV=test` `LOG_LEVEL=info`

- `APP_ENV`: `dev` | `test` | `prod` (default: `dev`)
- `LOG_LEVEL`: `debug` | `info` | `warning` | `error` (default: `info`)

### Terminal 1 - Build and Run the Runtime Image

Use `docker build` + `docker run` directly — not Compose. The Compose
file mounts local volumes and adds `--reload`, which are dev
conveniences that mask problems the real image would hit. Staging
should run the same sealed image that production will use.

`APP_ENV=test` behaves like `prod` (API docs disabled) but signals
the test environment for config and logging purposes.

```bash
docker build -f docker/Dockerfile --target runtime -t auth-service:test .
docker run --rm --name auth-service-test -p 8000:8000 --env-file .env auth-service:test
```

### Terminal 2 - Run the Test Suite in Docker

The `devtest` Dockerfile stage includes dev dependencies (pytest, ruff)
and sets `APP_ENV=test`. Run it separately to validate tests pass
inside the container:

```bash
docker build -f docker/Dockerfile --target devtest -t auth-service:devtest .
docker run --rm auth-service:devtest
```

## 3) Production Environment

Production uses the same `runtime` Docker image as staging. The
differences are operational, not structural:

- **Test** stages and runs the full test suite inside the container to
  validate the build. API docs (`/docs`, `/redoc`) are disabled.
- **Production** never includes test tooling. API docs are disabled
  (`APP_ENV=prod`). The image is identical to what staging validated —
  only the environment variables and infrastructure (load balancer,
  DNS, secrets) change.

### Set Environment 'prod' and Log Level (found in root/.env)

cp .env.example .env
In **.env**, set: `APP_ENV=prod`, `LOG_LEVEL=info`

- `APP_ENV`: `dev` | `test` | `prod` (default: `dev`)
- `LOG_LEVEL`: `debug` | `info` | `warning` | `error` (default: `info`)

### Build and Run Docker

- Runtime Docker image defaults to `APP_ENV=prod` if not overridden as
  an argument to prevent accidentally running in dev mode
- In prod, API docs endpoints are disabled (`/docs`, `/redoc`)

```bash
docker build -f docker/Dockerfile --target runtime -t auth-service:prod .
docker run --rm --name auth-service-prod -p 8000:8000 --env-file .env auth-service:prod
```

### Verify Production

Production is not tested with pytest — the test suite ran in staging.
Verify production with a health check and smoke test:

```bash
curl -s http://<host>:8000/health
```

Confirm docs are disabled:

```bash
curl -s -o /dev/null -w "%{http_code}" http://<host>:8000/docs
# expect 404
```

## Best Practices

**Environment separation** — Never develop against `APP_ENV=prod`.
Keep `.env` out of version control (`.gitignore`). Each environment
gets its own `.env` with appropriate values; secrets are never shared
across boundaries.

**Branch workflow** — Do all feature work on short-lived branches off
`main`. Merge via pull request with CI passing. Tag releases for
staging/production deploys.

**Run `make ci` before every push** — The pre-commit hook catches lint
issues at commit time, but `make ci` runs the full check (ruff check,
ruff format, pytest) to match what GitHub Actions will enforce.

**Docker image tags** — Use descriptive tags that match the environment:
`auth-service:dev` for the runtime image during development,
`auth-service:test` for the devtest stage, `auth-service:prod` for
production. Never deploy an image tagged `:test` to production.

**Same image, different config** — Staging and production use the same
`runtime` Dockerfile stage. The only difference is environment
variables. This ensures what you tested is what you deploy.

**Non-root containers** — The Dockerfile runs as `appuser`, not root.
Never override this with `--user root` in production.

**Keep dependencies minimal** — The `runtime` stage has no dev tooling.
Test dependencies (pytest, ruff) only exist in the `devtest` stage.
This reduces the attack surface of the production image.

**Structured logging** — Log at appropriate levels (INFO for normal
operations, WARNING for recoverable issues, ERROR for failures). Never
log passwords, tokens, or secrets. Use `LOG_LEVEL` to control
verbosity per environment.

## Docker Cleanup

Stop and remove a running single container:

```bash
docker stop auth-service-dev
docker rm auth-service-dev
```

Remove all stopped containers:

```bash
docker container prune -f
```

Remove auth-service images:

```bash
docker rmi auth-service:dev auth-service:test auth-service:prod
```

Remove unused images (dangling layers from previous builds):

```bash
docker image prune -f
```

Remove unused volumes:

```bash
docker volume prune -f
```

Remove everything — all stopped containers, unused images, networks,
and volumes. ONLY use this when you want a clean slate:

**Warning:** `docker system prune -a --volumes` removes *all* unused
images (not just dangling ones) and all volumes not attached to a
running container. Only run this if you don't need cached layers or
data from other projects.

```bash
docker system prune -a --volumes -f
```
