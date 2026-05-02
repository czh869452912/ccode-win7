# Testing Patterns

**Analysis Date:** 2026-05-02

## Test Framework

**Runner:**
- pytest (configured in `pyproject.toml`)
- Config: `[tool.pytest.ini_options]` in `pyproject.toml`
- Default options: `-v` (verbose)
- Test paths: `tests/`

**Assertion Library:**
- Standard `unittest.TestCase` methods (`assertEqual`, `assertTrue`, `assertIn`, etc.)
- pytest serves as runner only; almost no bare pytest functions or fixtures in test files

**Run Commands:**
```bash
# Run all tests (excluding slow and gui)
uv run pytest tests/ -m "not slow and not gui" -v

# Run harness component tests only
uv run pytest tests/ -m harness -v

# Run all tests with coverage
uv run pytest tests/ -m "not slow and not gui" --cov=src/embedagent

# Run full test suite
uv run pytest tests/ -v
```

**Makefile shortcuts:**
```bash
make test    # Fast subset with coverage
make harness # Harness-only tests
make ci      # Full CI pipeline (lint + test + smoke)
```

## Test File Organization

**Location:**
- All tests in `tests/` directory at repository root
- No tests inside `src/` (enforced by project policy)

**Naming:**
- `test_{module_name}.py` for module-level tests
- `test_{feature}_v2.py` for versioned feature tests
- `test_{component}_{subcomponent}.py` for focused component tests

**Structure:**
```
tests/
├── conftest.py                    # Session fixtures
├── test_architecture.py           # Protocol/frontend imports
├── test_config.py                 # Config loading and merging
├── test_context_config.py         # Context manager/reducers
├── test_guard.py                  # Loop guard behavior
├── test_harness_contracts.py      # Harness registry contracts
├── test_harness_runner_*.py       # Harness runner (by mode)
├── test_modes.py                  # Mode registry and prompts
├── test_permissions.py            # Permission policy evaluation
├── test_phase_engine.py           # Phase advancement logic
├── test_query_engine_*.py         # Query engine (by mode)
├── test_session_*.py              # Session store/restore/timeline
├── test_task_graph_v2.py          # Task graph mutations
├── test_tool_*.py                 # Tool runtime and execution
├── test_tools_package.py          # Tool catalog schemas
├── test_verify_quality_v2.py      # Quality report tool
├── fixtures/                      # Test fixtures
│   └── package/
│       ├── mock-check.py
│       └── mock-export.py
└── manual/                        # Manual/integration tests
    └── playwright_example.py
```

## Test Structure

**Suite Organization:**
```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.modes import mode_names, require_mode


class TestModeRegistry(unittest.TestCase):
    def test_all_expected_modes_present(self):
        names = mode_names()
        for m in ("explore", "spec", "build", "debug", "verify"):
            self.assertIn(m, names)

    def test_require_mode_invalid_raises(self):
        with self.assertRaises(ValueError):
            require_mode("nonexistent_mode")


if __name__ == "__main__":
    unittest.main()
```

**Patterns:**
- Every test file adds `src` to `sys.path` at module load time
- Test classes group related assertions by feature area
- Test names describe expected behavior: `test_{behavior}_{condition}`

## Pytest Markers

**Defined markers** (`pyproject.toml`):
- `unit`: Pure unit tests, no I/O
- `harness`: Task graph / phase engine / mode_runner components
- `session`: Session runtime, restore, timeline
- `gui`: GUI and frontend tests (requires display)
- `slow`: Integration tests > 5 seconds

**Usage:**
```python
import pytest

class TestPhaseEngine(unittest.TestCase):
    @pytest.mark.harness
    def test_understand_advances_when_contract_artifact_exists(self):
        ...
```

**Note:** Most test files in the codebase do not explicitly apply markers; the marker system is available for selective execution.

## Mocking

**Framework:** `unittest.mock` (standard library)

**Patterns:**
```python
from unittest import mock
from unittest.mock import patch

# Patch object method
with mock.patch.object(manager, "_measure_messages", return_value=100):
    result = manager.build_messages(session, mode_name="build")

# Patch environment variable
with patch.dict(os.environ, {"EMBEDAGENT_BUNDLE_ROOT": bundle_root}, clear=False):
    runtime = ToolRuntime(self.workspace)

# Patch module attribute
with patch.object(tools_base, "__file__", fake_module_path):
    runtime = ToolRuntime(workspace_root)
```

**What to Mock:**
- External I/O (file system, environment variables)
- LLM client responses (use `DoneClient` pattern)
- Time-dependent or random behavior
- Bundle discovery paths

**What NOT to Mock:**
- Internal dataclass construction
- Pure helper functions under test
- `TaskGraph` mutations (test real objects)

## Fixtures and Factories

**Test Data:**
- Minimal `conftest.py` with session-scoped fixtures:
  ```python
  @pytest.fixture(scope="session")
  def project_root():
      return Path(__file__).parent.parent
  ```

**Workspace Factory Pattern:**
```python
from itertools import count
import shutil

_COUNTER = count(1)

def _make_workspace(name):
    root = os.path.join(
        os.path.dirname(__file__), "..", "build", "test-sandboxes",
        "%s-%s-%s" % (name, os.getpid(), next(_COUNTER)),
    )
    root = os.path.realpath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    return root
```
- Used in `test_tools_package.py`, `test_query_engine_build_lite.py`, `test_verify_quality_v2.py`

**setUp/tearDown Pattern:**
```python
class TestToolRuntimeInit(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("tools-init")
        self.rt = ToolRuntime(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)
```

## Coverage

**Configuration** (`pyproject.toml`):
```toml
[tool.coverage.run]
source = ["src/embedagent"]
omit = ["*/tests/*", "*/fixtures/*", "*/manual/*"]

[tool.coverage.report]
exclude_lines = [
    "if __name__ == .__main__.",
    "raise NotImplementedError",
    "pass",
]
show_missing = true
```

**View Coverage:**
```bash
uv run pytest tests/ -m "not slow and not gui" --cov=src/embedagent --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- Scope: Single module, single function
- No I/O (or mocked I/O)
- Example: `test_phase_engine.py`, `test_guard.py`

**Integration Tests:**
- Scope: Multiple modules working together
- Real file system operations in temp directories
- Example: `test_query_engine_build_lite.py`, `test_session_store.py`

**E2E Tests:**
- Not formally present
- `tests/manual/playwright_example.py` exists for manual browser automation
- GUI tests marked with `gui` marker and excluded from default runs

## Common Patterns

**Async/Threading Testing:**
```python
def test_parallel_executor_returns_cancelled_updates_without_hanging(self):
    started = threading.Event()
    cancel_event = threading.Event()

    def execute_action(action):
        started.set()
        threading.Event().wait(10.0)
        return Observation(...)

    executor = StreamingToolExecutor(
        execute_action, max_parallel=1,
        cancel_event=cancel_event,
        idle_timeout_seconds=0.1,
        poll_interval_seconds=0.02,
    )
    # ... assertions on timing and state
```

**Error Testing:**
```python
def test_require_mode_invalid_raises(self):
    with self.assertRaises(ValueError):
        require_mode("nonexistent_mode")

def test_unknown_tool_returns_error(self):
    obs = self.rt.execute("nonexistent_tool", {})
    self.assertFalse(obs.success)
    self.assertIsNotNone(obs.error)
```

**Import Smoke Tests:**
```python
class TestFrontendTUIImport(unittest.TestCase):
    def test_import_tui_app(self):
        try:
            from embedagent.frontend.tui import TerminalApp
            self.assertIsNotNone(TerminalApp)
        except ImportError:
            self.skipTest("prompt_toolkit not installed")
```

**Structured Assertion Patterns:**
```python
# Assert on Observation structure
self.assertTrue(obs.success)
self.assertEqual(obs.data["recipe_id"], "custom.build")
self.assertIn("build-ok", obs.data["stdout"])

# Assert on lists
self.assertTrue(any("full_spec_tdd" in item for item in units))
self.assertTrue(any("Tasks:" in item for item in units))

# Assert on session messages
system_messages = [m.content for m in result.session.messages if m.role == "system"]
self.assertTrue(any("Mode: build" in c for c in system_messages))
```

## Test Data Location

- `tests/fixtures/package/` — Mock Python scripts for packaging tests
- Temp directories created via `_make_workspace()` and cleaned in `tearDown`
- No large fixture files committed; tests create their own minimal data

---

*Testing analysis: 2026-05-02*
