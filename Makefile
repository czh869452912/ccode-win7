.PHONY: install test harness lint lint-fix smoke python-distributions-build python-distributions-check python-distributions-smoke offline-bundle-contract ci

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

python-distributions-build:
	uv run python scripts/build-python-distributions.py --dist-dir dist

python-distributions-check: python-distributions-build
	uv run python scripts/check-python-distributions.py --dist-dir dist

python-distributions-smoke: python-distributions-check
	uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe

offline-bundle-contract: python-distributions-smoke
	uv run pytest tests/test_packaging_control_plane.py tests/test_gui_launcher_exe_contract.py -q

ci: lint test smoke offline-bundle-contract
