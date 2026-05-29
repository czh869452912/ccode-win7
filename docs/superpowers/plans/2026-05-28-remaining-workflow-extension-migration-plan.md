# Remaining Workflow Extension Migration Plan

> **For future agentic workers:** keep using small TDD slices. Do not batch these items into one large rewrite.

**Goal:** Finish slimming Agent Core so the built-in C/C++ harness remains the default hosted workflow while core execution, session state, runtime schema projection, and frontend read models stay workflow-neutral.

**Execution handoff:** completed implementation detail is archived at `docs/archive/workflow-extension-boundary/2026-05-28-workflow-extension-migration-handoff.md`; use this active file only for remaining release validation.

## Current Baseline

- `QueryEngine` does not import or construct `CHarnessWorkflowExtension`.
- Hosted product paths install default extensions through `src/embedagent/default_extensions.py`.
- Runtime schema defaults are workflow-neutral; default harness tools are activated through extension-active tool names.
- `Session.workflow_state["workflow"]` is the generic read model for frontend task fields and core strategy task-status compatibility.
- `HarnessStateSynchronizer` has been removed; harness refresh and task snapshot persistence now go through `CHarnessWorkflowExtension.refresh_managed_session()`.
- `Session.task_graph` has been removed; default C harness `TaskGraph` state is held behind `CHarnessWorkflowExtension` and projected into `Session.workflow_state["workflow"]`.

## Remaining Slices

### 1. Validate On Product Targets

- Run the fast test suite after every slice.
- Run real C/C++ project smoke tests for build/debug/verify flows.
- Re-run offline bundle and Windows 7 compatibility validation before any release cut.

## Guardrails

- Do not reintroduce default harness construction inside `QueryEngine`.
- Do not make mode schemas own default harness workflow tools again.
- Do not let frontend or workflow-neutral strategy code read harness task graph internals.
- Do not add Docker, WSL, VS Code, or online-service runtime dependencies.
- Keep Python syntax compatible with Python 3.8.
