# auth-service

A minimal FastAPI authentication service with layered structure:
- API routers in `app/api/`
- business logic in `app/services/`
- app wiring in `app/main.py`

## Local Development

### 1) Create and activate virtualenv
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 3) Create local env file
```bash
cp .env.example .env
```

### 4) Run the app
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5) Quick checks
```bash
curl -s http://127.0.0.1:8000/health
```

## CI Command (Local)

Run the same checks used by GitHub Actions:
```bash
make ci
```

Current `make ci` runs:
1. `python -m ruff check .`
2. `python -m ruff format --check .`
3. `python -m pytest -q`

## Docker Build and Run

### Build image
```bash
docker build -f docker/Dockerfile -t auth-service:dev .
```

### Run container
```bash
docker run --rm -p 8000:8000 --env-file .env auth-service:dev
```

### Run with Docker Compose (recommended for local dev)
```bash
docker compose -f docker/docker-compose.yml up --build
```

## GitHub Actions CI

Workflow file: `.github/workflows/ci.yml`

Triggers:
- `push`
- `pull_request`

Job steps:
1. Checkout repository
2. Setup Python 3.12
3. Restore pip cache (based on `pyproject.toml`)
4. Install project + dev dependencies
5. Run lint (`ruff check`)
6. Run format check (`ruff format --check`)
7. Run tests (`pytest -q`)

## Image Size and Measurement

Latest measured runtime image (multi-stage Dockerfile):
- `auth-service:week2-day3` -> `233MB`

How measured:
```bash
docker build -f docker/Dockerfile -t auth-service:week2-day3 .
docker image ls auth-service:week2-day3 --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
```

Useful follow-up inspection commands:
```bash
docker history auth-service:week2-day3 --format "{{.Size}}\t{{.CreatedBy}}"
docker run --rm auth-service:week2-day3 sh -lc 'du -sh /usr/local/lib/python3.12/site-packages/* 2>/dev/null | sort -hr | head -n 20'
```

## Environment Variables

- `APP_ENV`: `dev` | `test` | `prod` (default: `dev`)
- `LOG_LEVEL`: `debug` | `info` | `warning` | `error` (default: `info`)
