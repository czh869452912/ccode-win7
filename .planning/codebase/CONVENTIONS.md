# Coding Conventions

**Analysis Date:** 2026-05-02

## Naming Patterns

**Files:**
- Modules use `snake_case.py` (e.g., `task_graph.py`, `phase_engine.py`)
- Test files use `test_{module_name}.py` (e.g., `test_modes.py`, `test_permissions.py`)
- Private/internal modules prefixed with underscore: `tools/_base.py`
- Package `__init__.py` files are minimal barrel files exposing public API

**Functions:**
- Use `snake_case` for all functions and methods
- Private helpers prefixed with underscore: `_merge()`, `_load_json_file()`, `_make_policy()`
- Factory functions use `make_` or `build_` prefix: `make_context_config()`, `build_system_prompt()`

**Variables:**
- Module-level constants use `UPPER_SNAKE_CASE`: `DEFAULT_MODE`, `READ_TOOLS`, `MAX_READ_CHARS`
- Private module constants prefixed with underscore: `_USER_CONFIG_DIR`, `_MODE_RE`, `_DEFAULT_PROMPT_FRAME`
- Instance variables use `snake_case`
- Type variables use PascalCase in comments for compatibility

**Types:**
- Use `from __future__ import annotations` at the top of most modules
- Use `typing` imports (`Dict`, `List`, `Optional`, `Tuple`, `Any`) rather than built-in generics (Python 3.8 compatibility)
- Dataclass names use `PascalCase`: `AppConfig`, `TaskGraph`, `PermissionRule`
- Explicit `object` inheritance common: `class TaskNode(object):`

**Classes:**
- Use `PascalCase` for class names
- Explicit `(object)` inheritance in many classes for Python 2 style parity
- Dataclasses heavily preferred over plain classes for data containers

## Code Style

**Formatting:**
- **Tool:** Black
- **Line length:** 100 characters (`pyproject.toml`: `line-length = 100`)
- **Target:** Python 3.8 (`target-version = ["py38"]`)

**Linting:**
- **Tool:** Ruff
- **Rules enabled:** `E`, `W`, `F`, `I` (errors, warnings, Pyflakes, isort)
- **Ignored:** `E501` (line too long — handled by Black instead)
- **Excluded:** `tests/manual/`

**String Formatting:**
- Mixed usage of `%` formatting and `.format()`; `%` is common in existing code:
  ```python
  "task-%s" % (index + 1)
  ```
- `.format()` used for more complex templates:
  ```python
  frame.format(mode_name=mode_name, ...)
  ```
- Prefer `%` for simple concatenation to match existing style

**Comments:**
- Chinese comments common in module docstrings and inline notes
- Docstrings use triple double-quotes with Chinese language for business logic descriptions
- Use `#` for inline comments, especially section separators:
  ```python
  # ---------------------------------------------------------------------------
  # Public API
  # ---------------------------------------------------------------------------
  ```

## Import Organization

**Order:**
1. `from __future__ import annotations`
2. Standard library imports
3. Third-party imports (minimal — mostly stdlib)
4. Local application imports (`from embedagent...`)

**Path Aliases:**
- No import aliases used in production code
- Tests occasionally alias for brevity: `from embedagent.tools import ToolRuntime as RT`

**Example import block:**
```python
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from embedagent.harness.task_graph import TaskGraph
```

## Error Handling

**Patterns:**
- Silent fallback to empty defaults on config/file errors:
  ```python
  def _load_json_file(path: str) -> dict:
      try:
          with open(path, "r", encoding="utf-8") as fh:
              data = json.load(fh)
          return data if isinstance(data, dict) else {}
      except (IOError, OSError, ValueError):
          return {}
  ```
- Tool errors return `Observation` with `success=False` rather than raising exceptions
- Permission system returns `PermissionDecision` objects with `outcome` field
- Guard system uses `LoopGuard.should_block()` to prevent retry loops

**Anti-pattern to avoid:**
- Do not use bare `except:` — always catch specific exceptions
- Do not let file I/O errors bubble up to callers without graceful degradation

## Logging

**Framework:** Standard library `logging`

**Patterns:**
- Module-level logger: `_LOG = logging.getLogger(__name__)`
- Use `%s` style in log messages (lazy evaluation):
  ```python
  _LOG.warning("Failed to load modes config %s: %s", path, exc)
  ```

## Function Design

**Size:** Functions are generally small (under 50 lines). Large modules split into focused helper functions.

**Parameters:**
- Use type hints on all public function signatures
- Default to `None` for optional parameters, then normalize inside function
- Use `**kwargs` sparingly; prefer explicit parameters

**Return Values:**
- Return dataclass instances or simple structures
- For uncertain operations, return empty collections rather than `None`

## Module Design

**Exports:**
- `__init__.py` files expose only public API via `__all__`:
  ```python
  from embedagent.tools._base import ToolDefinition
  from embedagent.tools.runtime import ToolRuntime
  __all__ = ["ToolRuntime", "ToolDefinition"]
  ```

**Barrel Files:**
- Used at package level to provide clean import paths
- Internal modules (`_base.py`) are not re-exported directly

## Python Version Constraints

**Critical:**
- Python 3.8.x strictly — never use 3.9+ syntax
- Forbidden features: walrus operator `:=`, `match`/`case`, `dict | dict` union types, built-in generic types (`list[str]`)
- Always use `from __future__ import annotations` to enable forward references

---

*Convention analysis: 2026-05-02*
