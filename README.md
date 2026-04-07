# EmbedAgent

EmbedAgent is a native, offline-first Agent IDE core for the full C development lifecycle.

The current product baseline is:

- Windows 7 compatible
- Offline deployable
- Python 3.8 runtime target
- Agent Core first, UI replaceable
- Clang-centered C/C++ workflow

## Current Official Architecture

The repository now treats Agent Harness as the only official execution model.

- User-visible modes: `explore`, `spec`, `build`, `debug`, `verify`
- Internal execution model: `mode + discipline_profile + execution_phase`
- Official task system: `TaskGraph` projected through `task_status` and session task snapshots
- Official build/verify execution: `list_recipes` + `run_recipe` + `report_quality_v2`
- Official file discovery: `list_dir`, `glob_files`, `grep_text`
- Official permission engine: `PermissionPolicy` with structured rule matching and stable explanation text
- Official frontend vocabulary: `build`, `tasks`, `current_phase`, `discipline_profile`
- Official session-history model: `transcript.jsonl -> Session -> SessionHistoryAssembler -> /api/sessions/{id}/bootstrap`

The product no longer treats the old `code` mode or `manage_todos`-style workflow as the architecture baseline.

## Main Components

- `src/embedagent/query_engine.py`
  The main turn loop, tool orchestration, permission interaction, context assembly, and transcript integration.
- `src/embedagent/harness/`
  Mode registry, discipline/phase modeling, prompt stack, task graph, and session task snapshot persistence.
- `src/embedagent/tools/`
  Official tool runtime, catalog metadata, managed environment discovery, and tool execution.
- `src/embedagent/context.py`
  Context policy, reducer registry, replacement logic, and compaction pipeline.
- `src/embedagent/permissions.py`
  Structured permission categories, rule loading, rule matching, and explanation rendering.
- `src/embedagent/inprocess_adapter.py`
  Product-facing adapter used by CLI/TUI/GUI, including session snapshots and slash command handling.
- `src/embedagent/session_history.py`
  Canonical GUI history assembler built from transcript-backed `Session` state.
- `src/embedagent/core/` and `src/embedagent/protocol/`
  Stable frontend/core contract layer.
- `src/embedagent/frontend/`
  TUI and GUI shells built on the same core contract.

## Official Tools

The official user/model-facing tool vocabulary is centered on:

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

Git/status helpers and `run_command` remain available as supporting capabilities where appropriate, but the architecture no longer treats the old duplicate file/build/todo tools as first-class workflow primitives.

## Development Constraints

- Do not require Docker, WSL, VS Code, Node.js-at-runtime, or online services.
- Keep runtime compatible with Python `>=3.8,<3.9`.
- The offline bundle must contain every runtime dependency it uses.
- A clean Windows 7 machine must be able to unpack and run the bundle without preinstalled tools.

## Read In This Order

For implementation work, start with:

1. `README.md`
2. `AGENTS.md`
3. `docs/overall-solution-architecture.md`
4. `docs/implementation-roadmap.md`

## Status

Current architecture cutover status:

- Runtime promotion: completed
- Mode vocabulary cutover: completed
- Context/intelligence cutover: completed
- Permission/task truth cutover: completed
- Frontend/protocol officialization: completed
- Session-history single-source cutover: completed
- Remaining work: finish legacy helper deletion and keep validating on real C projects and Win7 bundle targets

## Verification

Recent focused verification includes:

- Python unit tests for harness, query engine, adapter, GUI backend, and tool runtime
- Webapp helper/runtime tests
- GUI static asset rebuild from current webapp source

## Repository Scope

This repository is not trying to be:

- a browser automation platform
- an online search agent
- a plugin marketplace
- a general-purpose cloud coding service

It is a focused native Agent IDE core for offline C engineering workflows.
