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

Repo-side validation completed on 2026-05-29:

- Fast suite: `uv run pytest tests/ -m "not slow and not gui" -v` passed with 684 passed / 11 deselected.
- Harness suite: `uv run pytest tests/ -m harness -v` now selects real component tests and passed with 23 passed / 672 deselected after marker coverage was restored.
- Focused C/C++ workflow regressions: build/debug/verify query-engine slices plus frontend CMake recipe detection passed with 15 passed.

Release validation remains open:

- `scripts/package.ps1 verify -Profile release -Json` returned `bundle_root_missing` for `build/offline-dist/embedagent-win7-x64`.
- `scripts/validate-offline-bundle.ps1 -RequireComplete` against that release path returned 37 fail / 2 warn because there is no release artifact to inspect.
- Clean Windows 7 unpack-and-run smoke was not run because a release bundle is not present.

Remaining release-blocking work:

- Generate `build/offline-dist/embedagent-win7-x64` with Python 3.8 embeddable runtime, vendored packages, MinGit, ripgrep, Universal Ctags, Clang runtime tools, GUI static assets, and WebView2 fixed runtime.
- Ensure `toolchains/llvm/current` or an equivalent configured LLVM/Clang root is available before package assembly.
- Re-run `scripts/validate-offline-bundle.ps1 -RequireComplete` and clean Windows 7 target-machine smoke before any release cut.

## Guardrails

- Do not reintroduce default harness construction inside `QueryEngine`.
- Do not make mode schemas own default harness workflow tools again.
- Do not let frontend or workflow-neutral strategy code read harness task graph internals.
- Do not add Docker, WSL, VS Code, or online-service runtime dependencies.
- Keep Python syntax compatible with Python 3.8.
