# Pi Core + Cordis-lite Composition Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small, Python 3.8-compatible registration scope that makes extension ownership, rollback, quiescence, and idempotent disposal executable without moving Cordis runtime semantics into Agent Core.

**Architecture:** Keep Agent Core's explicit Agent/Session/Loop contracts unchanged. Add `RegistrationScope` as a dependency-free lifecycle primitive, use it first in application registration, and make event registration return disposer handles so later Host/session integration can be incremental. Durable session truth and permission boundaries remain outside this lifecycle primitive.

**Tech Stack:** Python 3.8 standard library (`threading`, `contextlib`), pytest, existing `embedagent_core` contracts, Markdown ADRs.

---

### Task 1: Define the lifecycle contract

**Files:**
- Create: `packages/embedagent-core/src/embedagent_core/registration_scope.py`
- Modify: `packages/embedagent-core/src/embedagent_core/__init__.py`
- Test: `tests/test_registration_scope.py`

- [x] **Step 1: Write contract tests**

  Cover reverse disposer order, idempotent disposal, child-before-parent disposal, rejection after quiescence, operation admission draining, and transaction rollback.

- [x] **Step 2: Run the focused tests and verify failure**

  Run: `uv run pytest tests/test_registration_scope.py -q`

  Expected: collection failure because `embedagent_core.registration_scope` does not exist.

- [x] **Step 3: Implement the minimal scope state machine**

  Implement `RegistrationScope`, `ScopeStateError`, `ScopeDisposeError`, `register()`, `create_child()`, `operation()`, `transaction()`, `quiesce()`, `wait_for_quiescence()`, and idempotent `dispose()`. Use a lock and a context manager; do not add async dependencies or ambient lookup.

- [x] **Step 4: Export the public primitive and rerun tests**

  Run: `uv run pytest tests/test_registration_scope.py -q`

  Expected: all focused lifecycle tests pass.

### Task 2: Make event registrations reversible

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/agent_event_bus.py`
- Test: `tests/test_registration_scope.py`
- Test: `tests/test_capability_extensions.py`

- [x] **Step 1: Add a failing disposer assertion**

  Register one reducer, call the returned disposer, dispatch the event, and assert the reducer is not called; call the disposer twice and assert no error.

- [x] **Step 2: Implement disposer-returning registration**

  Make `register_reducer()` and `register_observer()` return idempotent callables. Remove registrations by object identity under the existing bus lock/snapshot boundary. Preserve current ordering and fail-closed behavior.

- [x] **Step 3: Run event and extension tests**

  Run: `uv run pytest tests/test_capability_extensions.py tests/test_registration_scope.py -q`

  Expected: all existing dispatch behavior plus new unregister behavior pass.

### Task 3: Reuse the primitive in application registration

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/application.py`
- Test: `tests/test_application_plugin_contract.py`

- [x] **Step 1: Keep existing application contract tests as the regression suite**

  Verify `ApplicationRegistrar.dispose()` remains idempotent and still removes runtime, extension, and shell contributions.

- [x] **Step 2: Replace the private disposer list with `RegistrationScope`**

  Preserve source tracking and reverse order, but delegate registration and disposal to the scope. Do not change `ApplicationRuntimeContribution` serialization or add compatibility aliases.

- [x] **Step 3: Run application registration tests**

  Run: `uv run pytest tests/test_application_plugin_contract.py tests/test_cpp_application_registration.py -q`

  Expected: all registration/disposal tests pass.

### Task 4: Document the current platform contract

**Files:**
- Modify: `docs/platform/tools-and-extensions.md`
- Modify: `docs/adrs/README.md`

- [x] **Step 1: Document registration ownership and lifecycle states**

  State that registrations return disposers, scope admission closes before disposal, and event registration is not durable session truth.

- [x] **Step 2: Index ADR-0009**

  Add the accepted decision to the ADR table without copying the full rationale into the navigation document.

### Task 5: Verify the slice and record remaining integration work

**Files:**
- Modify: `docs/superpowers/plans/2026-08-18-pi-cordis-composition-runtime.md`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted/runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Test: `tests/test_hosted_runtime.py`

- [x] **Step 1: Run focused and architecture tests**

  Run: `uv run pytest tests/test_registration_scope.py tests/test_capability_extensions.py tests/test_application_plugin_contract.py tests/test_cpp_application_registration.py tests/test_hosted_runtime.py tests/test_host_frontend_ports.py tests/test_project_extensions.py tests/test_workflow_extensions.py tests/test_dynamic_tool_registration.py -q`

  Then run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -q`

- [x] **Step 2: Run lint for touched Python files**

  Run: `uv run --locked python scripts/lint.py`

- [x] **Step 3: Update this plan with completed steps and explicit follow-ups**

  Host runtime quiescent close is included in this slice through `HostedRuntime.close()` and `InProcessAdapter.shutdown()`. C++ TaskGraph single truth, safe diagnostics, and manifest closure validation remain subsequent slices; do not claim them complete here.
