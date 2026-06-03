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
- Frontend task snapshot fallback now goes through `ExtensionManager.load_session_tasks(...)`; `InProcessAdapter` no longer imports the default harness task snapshot store directly.
- `docs/guides/configuration-guide.md` has been rewritten for the current `explore/spec/build/debug/verify` vocabulary and no longer documents `manage_todos` usage as a current workflow.

## Remaining Slices

### 1. Validate On Product Targets

Repo-side validation completed on 2026-05-29:

- Fast suite: `uv run pytest tests/ -m "not slow and not gui" -v` passed with 685 passed / 11 deselected.
- Harness suite: `uv run pytest tests/ -m harness -v` now selects real component tests and passed with 23 passed / 673 deselected after marker coverage was restored.
- Focused C/C++ workflow regressions: build/debug/verify query-engine slices plus frontend CMake recipe detection passed with 15 passed.
- Current-branch release bundle validation: rebuilt `build/offline-dist/embedagent-win7-x64` locally from offline cache, vendored site-packages, and LLVM root; `scripts/validate-offline-bundle.ps1 -RequireComplete` passed with 59 pass / 0 warn / 0 fail; `scripts/check-bundle-dependencies.py` passed; `scripts/package.ps1 verify -Profile release -Json` returned `final_status == READY`.
- Local cleanup follow-up completed on 2026-06-03: adapter task fallback boundary tests passed after routing inactive-session task reads through `ExtensionManager.load_session_tasks(...)`; configuration guide active vocabulary was updated.

Release validation remains open:

- Clean Windows 7 unpack-and-run smoke was not run in this workspace.

Remaining release-blocking work:

- Transfer the validated bundle candidate to a clean Windows 7 target.
- Run bundle unpack-and-run smoke, including CLI/TUI launcher checks, `validate-gui-smoke.cmd`, and `validate-gui-smoke.cmd --windowed --auto-close-seconds 8`.
- Record renderer/runtime/toolchain results before any release cut.

## Guardrails

- Do not reintroduce default harness construction inside `QueryEngine`.
- Do not make mode schemas own default harness workflow tools again.
- Do not let frontend or workflow-neutral strategy code read harness task graph internals.
- Do not add Docker, WSL, VS Code, or online-service runtime dependencies.
- Keep Python syntax compatible with Python 3.8.
