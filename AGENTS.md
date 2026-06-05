# AGENTS.md

## Purpose

This file is the project constitution for future agent and contributor work.

It exists to keep implementation and documentation aligned with the current product baseline:

- Windows 7 compatibility is mandatory.
- Offline deployment is mandatory.
- Agent Core is the product core; UI shells and workflow extensions are replaceable.
- The first-class target workflow is C/C++ application development with a Clang-centered toolchain.

## Quick Commands

These are the exact commands to use — copy-paste directly.

```bash
# Install dev environment
uv sync

# Run tests (fast subset — excludes GUI and slow integration tests)
uv run pytest tests/ -m "not slow and not gui" -v

# Run harness component tests only (task_graph, phase_engine, mode_runner)
uv run pytest tests/ -m harness -v

# Run all tests
uv run pytest tests/ -v

# Check lint (read-only)
uv run ruff check src/ tests/
uv run black --check src/ tests/

# Auto-fix lint
uv run ruff check --fix src/ tests/ && uv run black src/ tests/

# Full local CI equivalent
make ci
```

**Constraints (always enforce)**:
- Python **3.8.x strictly** — never use 3.9+ syntax (no walrus operator `:=`, no `match`, no `dict | dict`)
- Never import modules absent from `pyproject.toml` dependencies
- Never modify `uv.lock` manually
- Never commit `config/config.json` (contains `api_key`)
- Test files belong in `tests/` — never in `src/`

## Read First

Before non-trivial work, read in this order:

1. `README.md`
2. `docs/overall-solution-architecture.md`
3. `docs/implementation-roadmap.md`

Use `docs/archive/` and `analysis/` as historical/reference material only.

## Hard Constraints

- Do not introduce runtime dependencies on Docker, WSL, VS Code, or external online services.
- Keep runtime compatibility at Python `>=3.8,<3.9`.
- Do not use Python 3.9+/3.10+ syntax features.
- Prefer standard library plus a very small dependency surface.
- The offline bundle must include every runtime tool it invokes.

Required bundled runtime assets include:

- Python 3.8 embeddable distribution
- vendored Python third-party packages
- MinGit portable
- ripgrep
- Universal Ctags
- Clang toolchain binaries needed by runtime flows
- any other binary invoked by the product at runtime

If a clean Windows 7 machine cannot unpack and run the bundle without preinstalled tools, it is a defect.

## Official Product Vocabulary

The repository now has one official architecture vocabulary.

### Modes

Official first-class modes are:

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

`code` is no longer a first-class mode.

### Harness

Official C/C++ execution semantics are provided by the default built-in harness workflow extension:

- `mode`
- `discipline_profile`
- `execution_phase`
- `TaskGraph`

Agent Core must route harness-specific prompt injection, task initialization, and workflow tool handling through the extension boundary instead of importing harness classes directly.

`InProcessAdapter` owns the hosted runtime's shared `ExtensionManager` and passes it to session-scoped `QueryEngine` instances. Frontend tool catalog visibility must use that same manager instead of a separate adapter-only harness extension chain.

`ExtensionManager` is also the shared in-process capability boundary for prompt/context hooks, tool-call and tool-result hooks, resource discovery contracts, dynamic in-process tool registration, and extension diagnostics. Workspace-local file resources under `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` are discoverable and reloadable, but this does not enable project-local Python extension loading; that remains a separate, explicitly guarded follow-up.

Default extension assembly lives in `src/embedagent/default_extensions.py`. `QueryEngine` must not import or construct `CHarnessWorkflowExtension`; direct `QueryEngine` tests or hosts that need default C/C++ behavior must pass an explicit `ExtensionManager`.

`HarnessStateSynchronizer` has been removed. Product adapter paths must refresh harness state through `CHarnessWorkflowExtension.refresh_managed_session()` behind the default harness workflow extension.

### Task System

Official task truth for the default C/C++ harness workflow is:

- `TaskGraph`
- `task_status`
- session task snapshots

`Session.workflow_state` is the generic workflow-state carrier. Frontend-facing task fields are projected from `Session.workflow_state["workflow"]`.

Default C/C++ workflow projection assembly lives in `src/embedagent/harness/workflow_projection.py`. Harness internals may use `TaskGraph`, but the core/frontend boundary must consume the generic workflow payload produced there.

`Session.task_graph` has been removed. Default C/C++ graph ownership lives behind `CHarnessWorkflowExtension` and its harness-owned session graph state. Workflow-neutral strategies, projectors, and frontend task APIs must consume only `Session.workflow_state["workflow"]`.

Importing or instantiating `embedagent.session.Session` must not load `embedagent.harness.task_graph`; C harness graph internals stay behind the default harness workflow extension.

`manage_todos` is not part of the official workflow architecture.

### Tooling

Official default workflow tools center on:

- `read_file`
- `list_dir`
- `glob_files`
- `grep_text`
- `write_file`
- `edit_file`
- `list_recipes`
- `run_recipe`
- `report_quality_v2`
- `task_status`
- `record_failing_evidence`
- `ask_user`

Built-in mode `allowed_tools` are workflow-neutral permission/write contracts. Default C/C++ harness tools such as `list_recipes`, `run_recipe`, `report_quality_v2`, `record_failing_evidence`, and `task_status` are activated by the default harness workflow extension, not owned by the core mode schema.

`ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single runtime schema projection entry point. Without explicit `tool_names`, it projects only the workflow-neutral mode contract. Do not use runtime mode contracts as a shortcut for default harness pack activation; use the shared `ExtensionManager` and pass explicit active tool names into runtime schema projection.

Dynamic in-process extension tools are registered into the shared `ToolRuntime` with source metadata and explicit permission categories. A registered extension tool is model-visible only when active through the shared `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)` path and remains subject to `PermissionPolicy`.

Local resource reload is a file discovery operation. `ToolRuntime.reload_resources()`, `InProcessAdapter.reload_resources(...)`, `/resources reload`, and `POST /api/sessions/{session_id}/resources/reload` refresh workspace-bound skills, prompts, and recipe JSON resources. Skills/prompts are surfaced as resources; `.embedagent/recipes/*.json` feeds the existing recipe contract. Reload does not execute local Python code.

### Session History

Official session-history truth is:

- `transcript.jsonl` as the only durable session-history ledger
- `Session` / `session.turns` as the only live structured session state
- `SessionHistoryAssembler` as the only GUI history serializer
- `GET /api/sessions/{id}/bootstrap` as the only GUI activation bootstrap contract

`timeline.jsonl` is transport/replay infrastructure only. It is not a historical database.

## Mode Policy

- Modes are product contracts, not UI decorations.
- `explore` is the default entry mode.
- `verify` is read-only and owns quality-gate style execution.
- The LLM does not autonomously switch modes.
- User-driven switching happens through `/mode <name>` or confirmed `ask_user` choices.

Mode definitions live in `src/embedagent/modes.py`.

## Permission Policy

One official permission engine only:

- `src/embedagent/permissions.py`

Permission rules are structured data, not free-form prompt behavior.
When changing permission behavior, keep rule matching, decision categories, and explanation text aligned.

## Frontend / Protocol Policy

One official frontend vocabulary only:

- `tasks`, not `todos`
- `build`, not `code`
- `current_phase`, `discipline_profile`, `current_activity`, `task_summary`, `task_items`

Frontend-facing contract changes must be reflected together in:

- `src/embedagent/protocol/`
- `src/embedagent/core/`
- `src/embedagent/frontend/`

Frontend session activation must not reintroduce split snapshot/timeline bootstrap. Use the single bootstrap payload and transcript-backed structured history only.

## Documentation Maintenance

When changing architecture or workflow assumptions, update the matching source-of-truth documents in the same change:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/mode-schema.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`

- `docs/superpowers/` design and plan documents are slice-local working materials, not permanent architecture truth.
- When a slice is completed, its durable conclusions must be synchronized back into global source-of-truth docs and module docs.
- Governance rules, workflow rules, terminology, and templates live under `docs/` active documentation, not inside archived or slice-local files.
- Completed slice documents should be moved to `docs/archive/` after global docs are synchronized.

Historical notes belong in `docs/archive/` or changelog material, not in current architecture docs.

## Non-Goals

The repository is not currently trying to become:

- a browser automation agent
- a web search system
- a heavyweight RAG platform
- a plugin marketplace
- a general multi-agent orchestration framework

The product is a focused native Agent IDE core for offline C engineering work.
