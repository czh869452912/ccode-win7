# Remaining Workflow Extension Migration Plan

> **For future agentic workers:** keep using small TDD slices. Do not batch these items into one large rewrite.

**Goal:** Finish slimming Agent Core so the built-in C/C++ harness remains the default hosted workflow while core execution, session state, runtime schema projection, and frontend read models stay workflow-neutral.

## Current Baseline

- `QueryEngine` does not import or construct `CHarnessWorkflowExtension`.
- Hosted product paths install default extensions through `src/embedagent/default_extensions.py`.
- Runtime schema defaults are workflow-neutral; default harness tools are activated through extension-active tool names.
- `Session.workflow_state["workflow"]` is the generic read model for frontend task fields and core strategy task-status compatibility.
- `Session.task_graph` remains as a lazy default-harness compatibility mirror, confined to harness-owned paths.

## Remaining Slices

### 1. Retire `HarnessStateSynchronizer`

- Remove direct focused tests that instantiate `HarnessStateSynchronizer`.
- Replace compatibility import tests with source-boundary tests for the default extension refresh path.
- Delete `src/embedagent/services/harness_state_synchronizer.py` once no supported public import depends on it.
- Update `src/embedagent/services/__init__.py` and docs to remove the lazy facade.

### 2. Shrink `Session.task_graph`

- Move default C harness graph ownership behind `CHarnessWorkflowExtension` or a harness-owned state adapter.
- Keep `Session.workflow_state["workflow"]` as the only cross-boundary task read model.
- Add source-boundary tests proving workflow-neutral modules do not reference `session.task_graph`.
- Remove the `Session.task_graph` dataclass field after harness-owned callers no longer need it.

### 3. Remove Legacy Runtime Schema Aliases

- Rename remaining tests and callers away from `ToolRuntime.schemas_for_mode()`.
- Keep `ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` as the single schema projection entry point.
- Remove or deprecate `ToolRuntime.allowed_tool_names()` if it remains only as a compatibility wrapper.
- Update `docs/tool-contracts.md` and `docs/mode-schema.md` after the alias is gone.

### 4. Clarify Default Extension Configuration

- Keep project-local extension discovery deferred.
- Add a small host configuration point only if the built-in C harness needs to be disabled or replaced in tests.
- Avoid adding a plugin marketplace, remote registry, or multi-agent orchestration layer.

### 5. Archive Completed Slice Documents

- After this branch is merged and global docs are synchronized, move completed workflow-extension slice plans from `docs/superpowers/plans/` into `docs/archive/`.
- Preserve durable conclusions in `README.md`, `AGENTS.md`, `docs/overall-solution-architecture.md`, `docs/agent-harness-v2.md`, and `docs/implementation-roadmap.md`.

### 6. Validate On Product Targets

- Run the fast test suite after every slice.
- Run real C/C++ project smoke tests for build/debug/verify flows.
- Re-run offline bundle and Windows 7 compatibility validation before any release cut.

## Guardrails

- Do not reintroduce default harness construction inside `QueryEngine`.
- Do not make mode schemas own default harness workflow tools again.
- Do not let frontend or workflow-neutral strategy code read `Session.task_graph`.
- Do not add Docker, WSL, VS Code, or online-service runtime dependencies.
- Keep Python syntax compatible with Python 3.8.
