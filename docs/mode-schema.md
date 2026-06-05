# Mode Schema

## 1. Official Modes

EmbedAgent now has one official first-class mode set:

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

`code` is not a valid first-class mode.

## 2. Mode Responsibilities

| Mode | Responsibility | Mode-Contract Tool Focus | Write Policy |
|------|----------------|--------------------------|--------------|
| `explore` | code reading, explanation, impact analysis, discussion | `read_file`, `list_dir`, `glob_files`, `grep_text`, `git_status`, `git_log`, `ask_user` | read-only |
| `spec` | requirements, constraints, acceptance criteria, docs | `read_file`, `list_dir`, `glob_files`, `grep_text`, `write_file`, `ask_user` | docs/text-oriented writes |
| `build` | implementation loop | `read_file`, `list_dir`, `glob_files`, `grep_text`, `write_file`, `edit_file`, `ask_user` | implementation writes |
| `debug` | reproduction, isolation, minimal repair | `read_file`, `list_dir`, `glob_files`, `grep_text`, `write_file`, `edit_file`, `ask_user` | implementation writes |
| `verify` | build/test/static analysis summary without source edits | `read_file`, `list_dir`, `glob_files`, `grep_text`, `ask_user` | read-only |

Mode-contract tool lists are workflow-neutral. Default C/C++ harness tools such as `list_recipes`, `run_recipe`, `report_quality_v2`, `record_failing_evidence`, and `task_status` are registered runtime tools, but they are activated by the default C harness workflow extension and selected tool packs, not by the built-in mode schema itself.

Local resource reload does not alter mode contracts. Reloaded recipe JSON resources still execute only through the existing `run_recipe` tool path and its current mode/permission checks.

## 3. Switching Rules

- Mode switching is user-driven.
- The model does not autonomously switch modes.
- The agent may ask for a mode switch through `ask_user`, but the user confirms it.
- Unknown mode names are invalid input and must fail fast instead of silently falling back to another mode.

## 4. Harness Relationship

Modes are user-visible contracts only.

Actual workflow progression is handled by:

- `discipline_profile`
- `execution_phase`
- `TaskGraph`

That means a mode does not directly encode the whole workflow state.

The C/C++ harness provides this progression through the default built-in workflow extension. Agent Core may keep `current_mode` for compatibility, but harness prompt injection, task initialization, and harness tool activation should flow through the extension boundary.

`ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single runtime schema projection entry point. Without explicit `tool_names`, it projects only the workflow-neutral mode contract. Default harness-aware paths such as `QueryEngine` extension activation must combine the mode contract with extension-active tools and request schemas by explicit tool names.

Turn orchestration receives allowed-tool policy by injection rather than by calling runtime aliases. Hosted paths use the shared `ExtensionManager` to combine mode-contract tools with default C harness active tools.

## 5. Writable Scope

Mode-specific writable path policy is still enforced by mode configuration plus permission policy.

High-level rule:

- `explore` and `verify` are read-only
- `spec` writes documentation/text artifacts
- `build` and `debug` may write implementation files within allowed globs

## 6. Source Of Truth

Mode definitions live in:

- `src/embedagent/modes.py`

If this document disagrees with that file, update one of them immediately so they match.
