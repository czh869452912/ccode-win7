# Phase 3 Contract And Runtime Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or superpowers:subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make selected runtime closure, public failure diagnostics, and Host/extension teardown mechanically verifiable without introducing a generic service bag or second lifecycle runtime.

**Architecture:** Extend the product-owned `BundleRuntimePolicy`, Protocol-owned safe `FailureRecord`, and Core-owned `RegistrationScope` at their existing boundaries. Keep composition build-time only, keep Core independent of Protocol, and use owner-scoped data projections/disposers rather than generic runtime lookup.

**Tech Stack:** Python 3.8, stdlib dataclasses/JSON/threading, pytest, Ruff, Black, existing uv workspace and offline bundle scripts.

---

## Task 1: Close The Selected Runtime Projection

**Files:**
- Modify: `src/embedagent/bundle_policy.py`
- Modify: `tests/test_bundle_runtime_policy.py`
- Create: `tests/test_phase3_runtime_contract.py`
- Inspect/modify only if required by failing tests: `scripts/check-python-distributions.py`, `scripts/smoke-python-distributions.py`

- [ ] **Step 1: Write failing policy projection tests**

Add tests that construct temporary plan/manifest JSON and assert that `BundleRuntimePolicy` exposes frozen
`runtime_capability_ids`, `runtime_component_ids`, `asset_ids`, `gate_ids`, `project_distribution_ids`,
and `registration_entries`.

Add negative cases for missing arrays, duplicate ids, unknown/malformed ids, cross-flavor identity, stale
plan hash, and a selected application registration entry not present in the plan.

- [ ] **Step 2: Run the focused tests to verify RED**

Run: `uv run pytest tests/test_bundle_runtime_policy.py tests/test_phase3_runtime_contract.py -q`

Expected: the new projection and negative cases fail because runtime closure fields are not loaded or
validated by the runtime policy.

- [ ] **Step 3: Implement the minimal immutable runtime projection**

Extend `BundleRuntimePolicy` and `load_bundle_policy()` to validate the selected closure fields using one
small local normalizer. Keep validation product-local and stdlib-only. Do not import
`embedagent_composition`, inspect the filesystem to reconstruct the closure, or add fallback ids.

- [ ] **Step 4: Run the focused tests to verify GREEN**

Run: `uv run pytest tests/test_bundle_runtime_policy.py tests/test_phase3_runtime_contract.py -q`

Expected: all focused policy tests pass with no warnings or raw exception payloads.

- [ ] **Step 5: Run distribution contract regression tests**

Run: `uv run pytest tests/test_python_distribution_contract.py tests/test_packaging_control_plane.py -q`

Expected: existing distribution and packaging contracts remain green.

- [ ] **Step 6: Commit the boundary**

```bash
git add src/embedagent/bundle_policy.py tests/test_bundle_runtime_policy.py tests/test_phase3_runtime_contract.py scripts/check-python-distributions.py scripts/smoke-python-distributions.py
git commit -m "fix: validate selected runtime closure at startup"
```

## Task 2: Remove Raw Failure Diagnostics From Public Surfaces

**Files:**
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/session_events.py`
- Modify: `packages/embedagent-host/src/embedagent_host/frontend_errors.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_projector.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/project_extensions.py`
- Modify: `packages/embedagent-core/src/embedagent_core/extensions.py`
- Modify: `tests/test_safe_failure_diagnostics.py`
- Modify: `tests/test_session_event_protocol.py`
- Modify: `tests/test_host_agent_facade.py`
- Modify: `tests/test_project_extensions.py`
- Modify: `tests/test_tui_activity_timeline.py`
- Create: `tests/test_phase3_public_diagnostic_boundaries.py`

- [ ] **Step 1: Write failing public-boundary tests**

Add tests proving sync submit failures, worker failures, interaction resume failures, project extension
load failures, and failed tool frontend events contain `failure` but never raw exception text in event
payloads, snapshots, nested metadata, or extension diagnostics.

Add a regression assertion that snapshots use `last_failure` and do not contain `last_error`.

- [ ] **Step 2: Run the focused tests to verify RED**

Run: `uv run pytest tests/test_safe_failure_diagnostics.py tests/test_session_event_protocol.py tests/test_host_agent_facade.py tests/test_project_extensions.py tests/test_phase3_public_diagnostic_boundaries.py -q`

Expected: tests fail on raw `error`/`last_error` fields and extension diagnostic strings.

- [ ] **Step 3: Normalize the Protocol failure record**

Keep `FailureRecord` JSON-safe and frozen. Make `from_exception()` the only exception classification path;
public serializers use allowlisted fields and safe messages. Preserve exception chaining only for the
current synchronous caller, never in state or payload.

- [ ] **Step 4: Replace Host raw state and event fields**

Rename `ManagedSession.last_error` to `last_failure`, store a detached safe dictionary, remove raw
`error` from `session_error`, and update snapshot/frontend projections. Convert interaction resume and
project extension failures through `failure_for_exception()`.

- [ ] **Step 5: Make Core extension diagnostics Protocol-independent and safe**

Replace Core diagnostic error text with safe code/kind/exception type/message fields. Ensure project
extension metadata contains only workspace-relative identifiers and bounded safe metadata.

- [ ] **Step 6: Sanitize failed frontend tool events**

At `SessionEventEncoder`, retain the structured failure and remove raw error strings from the public
event payload. Keep durable model-visible tool observations owned by the Core session ledger.

- [ ] **Step 7: Run focused tests to verify GREEN**

Run: `uv run pytest tests/test_safe_failure_diagnostics.py tests/test_session_event_protocol.py tests/test_host_agent_facade.py tests/test_project_extensions.py tests/test_tui_activity_timeline.py tests/test_phase3_public_diagnostic_boundaries.py -q`

Expected: all safe-boundary tests pass and no fixture exposes a raw failure field.

- [ ] **Step 8: Commit the boundary**

```bash
git add packages/embedagent-protocol packages/embedagent-host packages/embedagent-core tests/test_safe_failure_diagnostics.py tests/test_session_event_protocol.py tests/test_host_agent_facade.py tests/test_project_extensions.py tests/test_tui_activity_timeline.py tests/test_phase3_public_diagnostic_boundaries.py
git commit -m "fix: make public diagnostics safe by construction"
```

## Task 3: Make Runtime Ownership And Shutdown Quiescent

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/registration_scope.py`
- Modify: `packages/embedagent-core/src/embedagent_core/extensions.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted/runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/services/session_lifecycle.py`
- Modify: `tests/test_registration_scope.py`
- Modify: `tests/test_hosted_runtime.py`
- Modify: `tests/test_project_extensions.py`
- Create: `tests/test_phase3_runtime_lifecycle.py`

- [ ] **Step 1: Write failing scope and concurrent-close tests**

Cover explicit owner identity, admission rejection after quiesce, reverse child/disposer order,
concurrent dispose sharing a completion barrier, and continuation after one disposer failure.

Add adapter tests proving shutdown rejects new session/turn admission, joins active workers, clears
extension/reducer/cache state, and is safe when called twice or concurrently.

- [ ] **Step 2: Run the focused tests to verify RED**

Run: `uv run pytest tests/test_registration_scope.py tests/test_hosted_runtime.py tests/test_phase3_runtime_lifecycle.py -q`

Expected: the new owner/concurrent-close assertions fail before implementation changes.

- [ ] **Step 3: Add owner identity and leak-observation hooks to RegistrationScope**

Keep the existing synchronous API and Python 3.8 compatibility. Expose only immutable owner/state
observations needed by tests and diagnostics; do not add injection or arbitrary service retention.

- [ ] **Step 4: Bind adapter resources to the root scope**

Create a `hosted-runtime` root scope, attach application/project extension registration and runtime-owned
cache/resource disposers, and route public operation admission through the scope. Preserve the existing
focused collaborators and durable store ownership.

- [ ] **Step 5: Refactor shutdown around quiesce and one dispose barrier**

Quiesce before signaling workers, wait for active/resume threads, dispose children in reverse order,
aggregate disposer failures, clear only in-memory state, and make repeated/concurrent close idempotent.

- [ ] **Step 6: Run focused lifecycle tests to verify GREEN**

Run: `uv run pytest tests/test_registration_scope.py tests/test_hosted_runtime.py tests/test_project_extensions.py tests/test_phase3_runtime_lifecycle.py -q`

Expected: no stale registration, worker, or cache remains after a successful close.

- [ ] **Step 7: Commit the boundary**

```bash
git add packages/embedagent-core/src/embedagent_core/registration_scope.py packages/embedagent-core/src/embedagent_core/extensions.py packages/embedagent-host/src/embedagent_host/inprocess_adapter.py packages/embedagent-host/src/embedagent_host/hosted/runtime.py packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py packages/embedagent-host/src/embedagent_host/runtime/services/session_lifecycle.py tests/test_registration_scope.py tests/test_hosted_runtime.py tests/test_project_extensions.py tests/test_phase3_runtime_lifecycle.py
git commit -m "refactor: make hosted runtime shutdown quiescent"
```

## Task 4: Add Architecture Gates And Synchronize Authorities

**Files:**
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify: `tests/test_current_architecture_boundaries.py`
- Modify: `docs/platform/protocol.md`
- Modify: `docs/platform/tools-and-extensions.md`
- Modify: `docs/product/packaging-and-deployment.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/superpowers/README.md`

- [ ] **Step 1: Add source-level architecture guards**

Guard that public payload construction does not serialize raw exception text, runtime policy does not
import composition, bundle closure fields are not reconstructed from global lists, and Host shutdown
has a single owner/dispose path.

- [ ] **Step 2: Run the new guards to verify RED**

Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -q`

Expected: each newly asserted retired path fails before the source is synchronized.

- [ ] **Step 3: Update current authorities in place**

Document one owner for runtime closure, one safe failure DTO path, scope lifecycle states, and the future
Fiber evolution seam. Keep release gates and external evidence explicit; do not append a completion diary.

- [ ] **Step 4: Run the guards to verify GREEN**

Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py tests/test_documentation_navigation.py -q`

Expected: all architecture and navigation tests pass.

- [ ] **Step 5: Commit the synchronized authorities**

```bash
git add tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py docs/platform/protocol.md docs/platform/tools-and-extensions.md docs/product/packaging-and-deployment.md docs/current-status.md docs/implementation-roadmap.md docs/superpowers/README.md
git commit -m "docs: record phase three runtime boundary ownership"
```

## Task 5: Final Verification And Integration

- [ ] **Step 1: Run focused Phase 3 regression tests**

```bash
uv run pytest tests/test_phase3_runtime_contract.py tests/test_phase3_public_diagnostic_boundaries.py tests/test_phase3_runtime_lifecycle.py tests/test_safe_failure_diagnostics.py tests/test_registration_scope.py tests/test_bundle_runtime_policy.py -q
```

- [ ] **Step 2: Run architecture and package contract gates**

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py tests/test_python_distribution_contract.py tests/test_packaging_control_plane.py -q
```

- [ ] **Step 3: Run locked lint and whitespace checks**

```bash
uv run --locked python scripts/lint.py
git diff --check
```

- [ ] **Step 4: Run the full regular partition**

```bash
uv run python scripts/test-suite.py full
```

Expected: zero failures; release-only C++/Win7 evidence remains explicitly out of scope.

- [ ] **Step 5: Review the plan and worktree**

Confirm every checkbox maps to a test or synchronized authority, `git status` contains only intended
Phase 3 files, and no generated GUI assets or user changes are staged.

- [ ] **Step 6: Complete the branch through the finishing workflow**

Use `superpowers:finishing-a-development-branch`: verify the merged result, fast-forward/merge locally
only after tests pass, preserve the user's existing GUI changes, then remove the isolated worktree and
feature branch.
