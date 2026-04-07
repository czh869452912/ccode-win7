# AGENTS.md

## Purpose

This file is the project constitution for future agent and contributor work.

It exists to keep implementation and documentation aligned with the current product baseline:

- Windows 7 compatibility is mandatory.
- Offline deployment is mandatory.
- Agent Core is the product core; UI shells are replaceable.
- The first-class target workflow is C/C++ application development with a Clang-centered toolchain.

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

Official execution semantics are:

- `mode`
- `discipline_profile`
- `execution_phase`
- `TaskGraph`

### Task System

Official task truth is:

- `TaskGraph`
- `task_status`
- session task snapshots

`manage_todos` is not part of the official workflow architecture.

### Tooling

Official workflow tools center on:

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

Historical notes belong in `docs/archive/` or changelog material, not in current architecture docs.

## Non-Goals

The repository is not currently trying to become:

- a browser automation agent
- a web search system
- a heavyweight RAG platform
- a plugin marketplace
- a general multi-agent orchestration framework

The product is a focused native Agent IDE core for offline C engineering work.
