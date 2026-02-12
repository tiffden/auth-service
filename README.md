# auth-service

![CI](https://github.com/tiffden/auth-service/actions/workflows/ci.yml/badge.svg?branch=main)

FastAPI authentication service with layered structure:
app routers in `app/api/`,
business logic in `app/services/`,
app wiring in `app/main.py`,
logging in `app/core/`.

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
