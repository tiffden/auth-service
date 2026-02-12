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
  models/    # domain entities
  repos/     # data access/repository layer
  services/  # business logic/use cases
  main.py    # app factory/wiring
docker/
  Dockerfile
  docker-compose.yml
tests/
  api/
  core/
  services/
```

## 1) New `.venv` Build and Run

```bash
# from repo root
python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

cp .env.example .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl -s http://127.0.0.1:8000/health
```

Run tests:

```bash
python -m pytest -q
# or
make test
```

## 2) Run After Adding to the Project

Use this flow after pulling changes or adding code in an existing clone:

```bash
# from repo root
source .venv/bin/activate
python -m pip install -e ".[dev]"

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests and checks:

```bash
python -m pytest -q
make ci
```

`make ci` runs:

1. `python -m ruff check .`
2. `python -m ruff format --check .`
3. `python -m pytest -q`

## 3) Docker Build and Run

Build runtime image:

```bash
docker build -f docker/Dockerfile --target runtime -t auth-service:dev .
```

Run runtime image:

```bash
docker run --rm -p 8000:8000 --env-file .env auth-service:dev
```

Build and run with Compose (dev API service):

```bash
docker compose -f docker/docker-compose.yml up --build api
```

Run tests in Docker:

```bash
docker build -f docker/Dockerfile --target devtest -t auth-service:test .
docker run --rm auth-service:test

# or compose test service
docker compose -f docker/docker-compose.yml run --rm test
```

## 4) Test and Prod Modes

Test mode:

- Local tests: `APP_ENV=test python -m pytest -q`
- Docker test image (`devtest` stage) sets `APP_ENV=test`
- Compose `test` service forces `APP_ENV=test`

Prod mode:

- Set `APP_ENV=prod` in runtime environment
- Runtime Docker image defaults to `APP_ENV=prod`
- In prod, API docs endpoints are disabled (`/docs`, `/redoc`)

## Environment Variables

- `APP_ENV`: `dev` | `test` | `prod` (default: `dev`)
- `LOG_LEVEL`: `debug` | `info` | `warning` | `error` (default: `info`)
