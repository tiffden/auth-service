.PHONY: lint test ci

lint:
	python -m ruff check .

test:
	python -m pytest -q

ci: lint test
