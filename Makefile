.PHONY: setup lint format test ci

setup:
	python -m pip install -e ".[dev]"
	pre-commit install

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

ci: lint format test
