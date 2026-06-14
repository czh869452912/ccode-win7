# Architecture Refactor: Phase 3

**Date:** 2026-05-02
**Scope:** Extract monolithic classes into focused services and strategies

## Changes

> Historical note: this document records the Phase 3 refactor. The
> backward-compatible global aliases described below were later removed by
> Pi-inspired minimal Core Phase M. Current code should use
> `get_mode_registry()`, `get_command_sanitizer()`, and
> `get_inprocess_adapter()` directly.

### InProcessAdapter Extraction (Plan 03-01)

**Before:** `InProcessAdapter` — 2,446 lines in single file
**After:** Facade with 4 extracted services

| Service | Responsibility | File |
|---------|----------------|------|
| SessionLifecycleManager | Session create/restore/teardown/list | `services/session_lifecycle.py` |
| EventEmitter | Event serialization and broadcast | `services/event_emitter.py` |
| WorkspaceFileService | File ops within workspace boundary | `services/workspace_file_service.py` |
| C harness workflow extension | Task graph refresh and state sync | `harness/extension.py` |

The adapter retains core orchestration (turn execution, command dispatch, permission resolution) while delegating discrete responsibilities to services via constructor injection.

### QueryEngine Extraction (Plan 03-02)

**Before:** `QueryEngine` — 1,530 lines in single file
**After:** Orchestrator with 3 extracted strategies

| Strategy | Responsibility | File |
|----------|----------------|------|
| LLMClientRetryWrapper | Retry with backoff, context compaction trigger | `strategies/llm_retry_wrapper.py` |
| ContextCompactionEngine | Token budget enforcement and compaction | `strategies/context_compaction_engine.py` |
| TurnOrchestrator | Single turn: prompt -> LLM -> tools -> observations | `strategies/turn_orchestrator.py` |

QueryEngine instantiates all three strategies and provides backward-compatible `run()` and `stop()` convenience methods.

### Global State Elimination (Plan 03-03)

**Before:** Module-level mutable globals:
- `MODE_REGISTRY` in `modes.py`
- `_DEFAULT_SANITIZER` in `command_sanitizer.py`
- `_inprocess_adapter` in `core/adapter.py`

**After:** Factory functions + DI container:
- `get_mode_registry(fresh=True)` for isolated state
- `get_command_sanitizer(fresh=True)` for isolated instances
- `get_inprocess_adapter(fresh=True)` for isolated adapter references
- `DIContainer` at `di_container.py` for registration and resolution

## Test Coverage

### Characterization Tests (`tests/test_characterization.py`)
- 14 tests capturing current behavior of extracted components
- Service delegation verification (InProcessAdapter -> services)
- Event emission chain behavior
- Workspace boundary enforcement
- LLM retry behavior

### Backward Compatibility Tests (`tests/test_backward_compatibility.py`)
- 25 tests verifying public API stability and removed legacy alias boundaries
- Import verification for all modules
- Instantiation with expected signatures
- Global state isolation via `fresh=True`

## Current Compatibility Boundary

The current public APIs are:
- `InProcessAdapter(client, tools, ...)` — same constructor signature
- `QueryEngine(client, tools, ...)` — same constructor signature, plus new `run()`/`stop()`
- `mode_names()`, `require_mode(mode)`, `initialize_modes()` — same signatures

The old `from embedagent.modes import MODE_REGISTRY` compatibility alias no
longer exists. Use `get_mode_registry()` instead.

## Migration Guide

### For Test Authors

Use `fresh_container` fixture to get isolated state:

```python
def test_something(fresh_container):
    # This test's container is isolated from other tests
    from embedagent.inprocess_adapter import InProcessAdapter
    adapter = InProcessAdapter(client=mock_client, tools=mock_tools)
    ...
```

Use `fresh=True` for explicit isolation:

```python
from embedagent.modes import get_mode_registry
registry = get_mode_registry(fresh=True)
```

### For Component Authors

Register new factories in `di_container.py`:

```python
from embedagent.di_container import get_default_container

def _register_my_factory() -> None:
    get_default_container().register_factory("my_component", lambda: MyComponent())

_register_my_factory()
```
