.PHONY: install test harness lint lint-fix smoke ci

install:
	uv sync

test:
	uv run pytest tests/ -m "not slow and not gui" --cov=src/embedagent

harness:
	uv run pytest tests/ -m harness -v

lint:
	uv run --locked python scripts/lint.py

lint-fix:
	uv run --locked python scripts/lint.py --fix

smoke:
	uv pip install -e ".[cli]" && uv run python -c "import embedagent; print('import OK')"

ci: lint test smoke
