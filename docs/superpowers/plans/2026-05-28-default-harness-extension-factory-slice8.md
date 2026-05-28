# Default Harness Extension Factory Slice 8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move default C harness extension registration out of `QueryEngine` so Agent Core consumes an `ExtensionManager` without importing or constructing `CHarnessWorkflowExtension`.

**Architecture:** `QueryEngine` defaults to an empty `ExtensionManager` when no host supplies one. The hosted product path uses a small factory owned outside core execution to create the default C harness extension set, and `InProcessAdapter` passes that shared manager to session engines and frontend tool catalog visibility.

**Tech Stack:** Python 3.8, pytest, existing `ExtensionManager`, `CHarnessWorkflowExtension`, `QueryEngine`, and `InProcessAdapter`.

---

### Task 1: Lock The Core Boundary

**Files:**
- Modify: `tests/test_workflow_extensions.py`
- Modify: `tests/test_query_engine_build_lite.py`
- Modify: `tests/test_query_engine_debug_lite.py`
- Modify: `tests/test_query_engine_verify_slice.py`

- [ ] **Step 1: Add failing boundary tests**

Add a source-inspection regression asserting `src/embedagent/query_engine.py` does not import `CHarnessWorkflowExtension` and does not construct it. Update direct `QueryEngine(...)` harness tests to pass a default harness extension manager explicitly.

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_query_engine_no_longer_imports_default_harness_extension_directly -v
```

Expected: FAIL because `query_engine.py` still imports and constructs `CHarnessWorkflowExtension`.

### Task 2: Add A Default Extension Factory

**Files:**
- Create: `src/embedagent/default_extensions.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/query_engine.py`

- [ ] **Step 1: Implement the factory**

Create `build_default_extension_manager(tools)` that constructs `CHarnessWorkflowExtension(tools=tools)` and returns `(manager, harness_workflow)` or another small carrier that preserves adapter compatibility with `adapter.harness_workflow`.

- [ ] **Step 2: Make QueryEngine core-only**

Remove the harness import from `query_engine.py` and change the fallback to `ExtensionManager()` when `extension_manager` is not supplied.

- [ ] **Step 3: Move adapter registration to the factory**

Use the factory in `InProcessAdapter.__init__()` to keep default product behavior unchanged while avoiding a direct `CHarnessWorkflowExtension` import in the adapter.

### Task 3: Synchronize Architecture Docs

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Document the new ownership**

State that QueryEngine has no built-in default harness construction; hosted products install default extensions through the host/factory boundary.

- [ ] **Step 2: Mark this as Slice 8**

Add a DC entry and tracker row for the default harness extension factory slice.

### Task 4: Verify Slice

**Files:**
- Test: boundary, QueryEngine harness behavior, adapter extension sharing

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py -v
```

Expected: PASS. Direct QueryEngine tests that need default harness behavior pass by supplying the default extension manager; adapter product path still passes because it uses the factory.

- [ ] **Step 2: Run static checks**

Run:

```bash
uv run ruff check src/embedagent/default_extensions.py src/embedagent/query_engine.py src/embedagent/inprocess_adapter.py tests/test_workflow_extensions.py tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py
uv run ruff format --check src/embedagent/default_extensions.py src/embedagent/query_engine.py src/embedagent/inprocess_adapter.py tests/test_workflow_extensions.py tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py
git diff --check
```

Expected: PASS.
