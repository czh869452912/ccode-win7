.PHONY: install test test-full test-release test-performance test-audit harness lint lint-fix smoke python-distributions-build python-distributions-check python-distributions-smoke offline-bundle-contract ci

install:
	uv sync

test:
	uv run python scripts/test-suite.py pre-push

test-full:
	uv run python scripts/test-suite.py full

test-release:
	uv run python scripts/test-suite.py release

test-performance:
	uv run python scripts/test-suite.py performance

test-audit:
	uv run python scripts/test-suite.py audit

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

# Covers all five project distributions across isolated and composed import scenarios;
# it is not a full GUI, provider, or hosted product runtime smoke.
python-distributions-smoke: python-distributions-check
	uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe

offline-bundle-contract: python-distributions-smoke
	uv run pytest tests/test_packaging_control_plane.py tests/test_gui_launcher_exe_contract.py -q

ci: lint test-audit test-full test-release test-performance smoke offline-bundle-contract
