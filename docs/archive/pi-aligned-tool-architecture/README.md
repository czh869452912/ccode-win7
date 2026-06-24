# Pi-Aligned Tool Architecture Archive

> Status: `archived`
> Type: `completed architecture slice`
> Last synced: `2026-06-25`
> Code scope: Agent Core tools, default C/C++ workflow tools, command execution, recipe readiness, docs, and tests

## Summary

This package archives the completed Pi-aligned tool architecture slice.

The slice moved the model-visible command primitive to `bash`, removed the legacy public `run_build` wrapper and related compiler/build-environment helper surface, kept default C/C++ workflow helpers behind the workflow extension boundary, added recipe readiness/refusal behavior, and improved command-output decoding for byte-oriented subprocess output.

## Completion Review

The implementation goals from the archived plan/design have been met:

- Core exposes a smaller primitive tool surface centered on `read_file`, `list_dir`, `glob_files`, `grep_text`, `write_file`, `edit_file`, `author_local_capability`, `ask_user`, and `bash`.
- Default C/C++ workflow tools remain workflow-package-owned: `list_recipes`, `run_recipe`, `report_quality_v2`, `task_status`, and `record_failing_evidence`.
- `run_build`, `list_compilers`, and `configure_build_env` are no longer model-visible public tools.
- `list_recipes` and `run_recipe` now expose readiness/prerequisite information and refuse missing-prerequisite execution.
- Bash/command output handling uses byte capture with explicit decoding/fallback metadata for non-streaming subprocess execution.
- Active source-of-truth docs and tests were synchronized before this package was archived.

## Archived Materials

- `2026-06-24-pi-aligned-tool-architecture-design.md`
- `2026-06-24-pi-aligned-tool-architecture.md`

## Source Of Truth

These files are historical. Current product truth lives in:

- `AGENTS.md`
- `README.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/tool-contracts.md`
- `docs/mode-schema.md`
- `docs/agent-harness-v2.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
