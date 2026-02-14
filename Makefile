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

test-oauth-flow:
	pytest tests/api/test_oauth_pkce_flow.py -v --log-cli-level=INFO 

ci: lint format test
