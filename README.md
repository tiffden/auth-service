# auth-service

A minimal FastAPI-based authentication service, evolved incrementally
to demonstrate modern Python backend practices.

## Container size (multi-stage)
Built on: 2026-02-08

Multi-Stage:
	•	Stage 1: build wheels (or install deps in a venv you copy)
	•	Stage 2: runtime only (no compilers, no build deps)

Commands:
```bash
docker build -t auth-services:week2-day3 .
docker image ls auth-services:week2-day3
docker image ls auth-services:week2-day3 --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
REPOSITORY      TAG          SIZE
auth-services   week2-day3   327MB

Measure
	•	docker images | head (size)
	•	Goal: comfortably under 300MB