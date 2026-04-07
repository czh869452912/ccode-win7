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

| Mode | Responsibility | Official Tool Focus | Write Policy |
|------|----------------|---------------------|--------------|
| `explore` | code reading, explanation, impact analysis, discussion | `read_file`, `list_dir`, `glob_files`, `grep_text`, `git_status`, `git_log`, `task_status`, `ask_user` | read-only |
| `spec` | requirements, constraints, acceptance criteria, docs | `read_file`, `list_dir`, `glob_files`, `grep_text`, `write_file`, `task_status`, `ask_user` | docs/text-oriented writes |
| `build` | implementation loop | `read_file`, `list_dir`, `glob_files`, `grep_text`, `write_file`, `edit_file`, `list_recipes`, `run_recipe`, `task_status`, `ask_user` | implementation writes |
| `debug` | reproduction, isolation, minimal repair | `read_file`, `list_dir`, `glob_files`, `grep_text`, `write_file`, `edit_file`, `list_recipes`, `run_recipe`, `record_failing_evidence`, `task_status`, `ask_user` | implementation writes |
| `verify` | build/test/static analysis summary without source edits | `list_recipes`, `run_recipe`, `report_quality_v2`, `task_status`, `ask_user` | read-only |

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
