# auth-service

A minimal FastAPI-based authentication service, evolved incrementally
to demonstrate modern Python backend practices.

## Container size (multi-stage)
Built on: 2026-02-08

Multi-Stage:
	•	Stage 1: build wheels (or install deps in a venv you copy)
	•	Stage 2: runtime only (no compilers, no build deps)
    Goal:  Image size < 300MB

Commands:
```bash
docker build -t auth-services:week2-day3 .
docker image ls auth-services:week2-day3

docker image ls auth-services:week2-day3 --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
    REPOSITORY      TAG          SIZE
    auth-services   week2-day3   327MB
	
    Image Bigger than expected?
        •	python -m pip index versions fastapi 2>/dev/null | head -n 5 for 7s
        •	docker image ls --format "table {{.Repository}}\\t{{.Tag}}\\t{{.Size}}"
        •	docker image ls --format "table {{.Repository}}\\t{{.Tag}}\\t{{.Size}}"
        •	docker history --no-trunc auth-services:week2-day3
        •	docker history auth-services:week2-day3 --format "{{.Size}}\\t{{.CreatedBy}}"
    Layer history confirms most of the size is base Python + installed dependencies, not the app code.
        •	docker run --rm auth-services:week2-day3 sh -lc 'du -sh /usr/local/lib/python3.12/site-packages/* 2>/dev/null | sort -hr | head -n 20' for 6s
        •	docker run --rm auth-services:week2-day3 sh -lc "python -m pip show fastapi fastapi-cli uvicorn | sed -n '1,200p'"
        •	docker run --rm auth-services:week2-day3 sh -lc "python - <<'PY' from importlib.metadata import metadata m=metadata('fastapi')

    Changed pyproject.toml dependencies from FastApi[standard] to fastapi, uvicorn, httpx - REDUCED from 327MB to 233MB:
        REPOSITORY      TAG          SIZE
        auth-services   week2-day3   233MB
        
    Why fastapi[standard] is heavy - fastapi[standard] is a convenience meta-extra. It pulls in a broad set of production and developer-adjacent dependencies, including:
        •	uvicorn[standard]
        •	uvloop (C extension)
        •	httptools (C extension)
        •	watchfiles
        •	python-multipart
        •	email-validator
        •	orjson (C extension)
        •	websockets
        •	python-dotenv
        •	other transitive dependencies
