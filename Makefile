.PHONY: lint test ci

lint:
	python -m ruff check .

format:
	python -m ruff format --check .

test:
	python -m pytest -q

ci: lint format test
