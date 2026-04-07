# Tool Contracts

## 1. Official Tool Contract

Every official tool should be understood as a contract made of:

- name
- description
- parameter schema
- structured observation shape
- catalog metadata
- permission category

The official runtime facade is:

- `src/embedagent/tools/runtime.py`

## 2. Official Workflow Tools

### File / Discovery

| Tool | Purpose | Core Parameters |
|------|---------|-----------------|
| `read_file` | read a single text file | `path` |
| `list_dir` | shallow directory listing | `path`, `limit`, `offset` |
| `glob_files` | file name/path matching | `path`, `pattern`, `limit`, `offset` |
| `grep_text` | text content search | `path`, `query`, `limit`, `offset` |
| `write_file` | write whole-file content | `path`, `content`, `overwrite` |
| `edit_file` | replace a precise text span | `path`, `old_text`, `new_text` |

### Build / Verify

| Tool | Purpose | Core Parameters |
|------|---------|-----------------|
| `list_recipes` | enumerate runnable workspace recipes | none |
| `run_recipe` | execute a workspace recipe | `recipe_id` |
| `report_quality_v2` | summarize minimal quality gate state | `error_count`, `warning_count`, `test_failures` |
| `record_failing_evidence` | capture failing evidence during debug | `summary`, optional evidence fields |

### Workflow / Interaction

| Tool | Purpose | Core Parameters |
|------|---------|-----------------|
| `task_status` | expose current TaskGraph projection | none |
| `ask_user` | request explicit user input or choice | `question`, options |

### Supporting Tools

These are supporting capabilities, not the primary workflow vocabulary:

- `git_status`
- `git_diff`
- `git_log`
- `run_command`

## 3. Observation Shape

Official tools should return structured observations, not raw terminal dumps as the only output.

Common fields include:

- `success`
- `error`
- `tool_name`
- tool-specific structured `data`

For list/search style tools, the preferred output shape is:

- `preview`
- `returned_count`
- `total_count`
- `has_more`
- `next_offset`
- `result_ref`

For task state, the preferred output shape is:

- `summary`
- `current_mode`
- `current_phase`
- `discipline_profile`
- `tasks` or equivalent task list payload

For recipe execution, the preferred output shape includes:

- `recipe_id`
- command/runtime metadata
- diagnostics and/or parsed summaries when available

## 4. Permission Categories

Official categories are:

- `read`
- `workspace_write`
- `shell_exec`
- `toolchain_exec`
- `git_write`

Each catalog entry must identify one permission category.

## 5. Historical Tool Presentation Contract

GUI history serialization depends on a small stable presentation snapshot per tool call:

- `tool_label`
- `permission_category`
- `supports_diff_preview`
- `progress_renderer_key`
- `result_renderer_key`

These fields are part of the durable session-history contract. They must remain reconstructable from transcript-backed session state even when replay logs are trimmed.

Additional contract rules:

- `task_status` uses `progress_renderer_key = "tasks"`, `result_renderer_key = "tasks"`, and `activity_kind = "task"`
- `tool_start` / `tool_finish` / interaction events must preserve engine-issued `turn_id` / `step_id` / `step_index` anchors end-to-end
- adapters and frontends must not mint replacement step identities

## 6. Product Rule

Do not add duplicate first-class tools for the same workflow job.

Examples of duplicates that should not be reintroduced:

- recursive file listing plus shallow/paged directory listing as equal first-class tools
- legacy compile/test wrappers plus recipe execution as equal first-class workflow tools
- prompt-only todo tools plus harness task state as equal first-class workflow systems

## 7. Source Of Truth

The authoritative implementation lives in:

- `src/embedagent/tools/runtime.py`
- `src/embedagent/tools/harness_runtime.py`

This document must stay aligned with those files.
