# Phase 2A: Reversible Context Reducer Lifecycle

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Execute each task with tests first and keep the scope owner explicit.

**Goal:** Make Host and workflow context reducer registrations reversible, owner-scoped, and safe to reload without duplicate handlers or stale capability state.

**Architecture:** `RegistrationScope` owns admission and teardown. `ReducerRegistry` remains a focused Host collaborator, but every extension registration returns an idempotent disposer. Built-in reducers belong to a baseline scope; application/workspace reducers belong to the extension scope that installed them. A registry snapshot is used during context assembly so disposal cannot mutate an in-flight build.

**Non-goals:** Do not introduce a generic service locator, ambient context lookup, a callback bag, or a second session-history ledger. Do not make reducer registration durable truth; only the session journal is durable truth.

## Task 1: Specify registration identity and ownership

**Files:**
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/context.py`
- Test: `tests/test_context_config.py`

- [ ] Add red tests for disposer idempotence, owner-scoped removal, replacement of the same owner/key, rejection of conflicting registrations, and snapshot stability during disposal.
- [ ] Define a small registration record containing tool name, source id, source type, and reducer/priority payload. Keep the public reducer callable signature unchanged.
- [ ] Make `register_reducer()` and `register_high_priority_tool()` return idempotent disposers. A conflicting source must fail closed instead of silently overwriting another owner.
- [ ] Preserve the built-in reducer set under a baseline owner and explicitly prohibit disposing it through extension handles.

## Task 2: Thread disposers through ExtensionManager

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/extensions.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/context_reducers.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py`
- Test: `tests/test_workflow_extensions.py`
- Test: `tests/test_project_extensions.py`

- [ ] Change `register_context_reducers()` capability dispatch to return one composite disposer for all registrations made by that extension.
- [ ] Attach the composite disposer to the extension child scope created by `ExtensionManager`; repeated registration must dispose or reuse the prior owner binding before installing a new one.
- [ ] Return a disposer from `register_c_workflow_context_reducers()` and keep partial registration transactional: if one reducer fails, previously installed reducers are removed.
- [ ] Verify project/workspace extension reload does not increase reducer or high-priority-tool counts, and disposed extensions no longer participate in context assembly.

## Task 3: Close the Host integration boundary

**Files:**
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/context.py`
- Test: `tests/test_hosted_runtime.py`
- Test: `tests/test_project_extensions.py`

- [ ] Store reducer registration handles on the runtime/session scope that owns them; do not keep hidden module-level handles.
- [ ] Ensure workspace switch, application reload, and `InProcessAdapter.shutdown()` dispose the corresponding scope before clearing projections.
- [ ] Add a regression test that starts two adapters sequentially, submits work through both, closes the first, and proves the second has no stale reducer or handler from the first.
- [ ] Add a race test where context assembly is active while disposal begins; the in-flight snapshot may finish, but no new assembly may admit the disposed owner.

## Task 4: Verification and invariants

- [ ] Run: `uv run pytest tests/test_context_config.py tests/test_workflow_extensions.py tests/test_project_extensions.py tests/test_hosted_runtime.py tests/test_registration_scope.py -q`
- [ ] Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -q`
- [ ] Run: `uv run --locked python scripts/lint.py`
- [ ] Record and test these invariants: every non-baseline registration has one owner; each disposer is idempotent; disposed owners cannot be observed by new context builds; registration order is deterministic; no reducer registration mutates `transcript.jsonl` directly.

## Exit criteria

This slice is complete only when extension reload, workspace switch, and runtime shutdown leave no reducer registrations or high-priority tool names owned by the disposed scope, while the built-in baseline remains available to a fresh context manager.
