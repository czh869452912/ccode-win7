.PHONY: install test harness lint lint-fix smoke ci

install:
	uv sync

test:
	uv run pytest tests/ -m "not slow and not gui" --cov=src/embedagent

harness:
	uv run pytest tests/ -m harness -v

lint:
	uv run ruff check src/ tests/
	uv run black --check src/ tests/

lint-fix:
	uv run ruff check --fix src/ tests/
	uv run black src/ tests/

smoke:
	pip install -e ".[cli]" && python -c "import embedagent; print('import OK')"

ci: lint test smoke
