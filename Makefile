.PHONY: help setup lint format test test-docker test-docker-happy ci build docker docker-down clean dev migrate migration

help:
	@echo "Available targets:"
	@echo "  make setup             - 1. Install dependencies and pre-commit hooks"
	@echo "  make docker            - 2. Start Docker Compose stack (api + postgres)"
	@echo "  make migrate           - 3. Run alembic upgrade head"
	@echo "  make ci                - 4. Run lint, format, and tests"
	@echo "  "
	@echo "  make dev               - Run uvicorn locally with auto-reload"
	@echo "  make build             - Build production Docker image"
	@echo "  make migration m=msg   - Auto-generate a new alembic migration"
	@echo " "
	@echo "  make lint              - Run ruff linting"
	@echo "  make format            - Check ruff formatting"
	@echo "  make test              - Run tests locally"
	@echo "  make test-docker       - Run Docker integration tests"
	@echo "  make test-docker-happy - Run Docker happy-path tests only"
	@echo " "
	@echo "  make docker-down       - Stop Docker Compose stack"
	@echo "  make clean             - Remove old Docker containers and images"

setup:
	python -m pip install -e ".[dev]"
	pre-commit install

docker:
	docker compose -f docker/docker-compose.yml up --build

migrate:
	alembic upgrade head

ci: lint format test

dev:
	uvicorn app.main:app --reload --port 8000

build:
	docker build -f docker/Dockerfile --target runtime -t auth-service:dev .

migration:
	alembic revision --autogenerate -m "$(m)"

lint:
	python -m ruff check .

format:
	python -m ruff format --check .

test:
	python -m pytest -q

test-docker:
	pytest -m docker -v --log-cli-level=INFO

test-docker-happy:
	pytest -m docker -v --log-cli-level=INFO -k happy

docker-down:
	docker compose -f docker/docker-compose.yml down

clean:
	docker compose -f docker/docker-compose.yml down --rmi local --volumes --remove-orphans
