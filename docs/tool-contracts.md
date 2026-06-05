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

Workflow extensions may activate focused subsets of registered tools for a turn. The default C/C++ harness extension owns harness-specific tool activation and `task_status` behavior, while `ask_user` remains core interaction infrastructure.

`CORE_PACK` is workflow-neutral. Harness tools such as `list_recipes`, `run_recipe`, `report_quality_v2`, `record_failing_evidence`, and `task_status` must be activated by workflow packs/extensions rather than being treated as core tools.

Built-in mode `allowed_tools` are workflow-neutral permission/write contracts. They must not be used as the complete default C/C++ tool list. The C harness extension reports only its active pack tools; product paths that need the default harness behavior must union the mode contract with active workflow-extension tools and request schemas by explicit active tool names.

`ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single runtime schema projection entry point. Without explicit `tool_names`, it projects only the workflow-neutral mode contract. Harness-aware schema projection belongs to callers that have consulted the shared `ExtensionManager` and pass extension-active tool names explicitly.

Allowed-tool gating is not a runtime wrapper. Core orchestration receives an explicit allowed-tool policy from its host; hosted product paths use `QueryEngine._allowed_tools_for_mode(...)`, which combines the mode contract with extension-active tool names from the shared `ExtensionManager`.

## Extension Tool Hooks

The extension runtime may observe or patch tool calls through typed in-process hooks:

- `tool_call` can block an allowed tool call or return updated arguments before permission/tool execution continues.
- `tool_result` can replace the structured observation or provide a workflow patch after execution.

These hooks do not bypass mode contracts, `PermissionPolicy`, path write checks, or tool metadata categories.

## Dynamic Extension Tool Registration

In-process extensions may register tools into the shared `ToolRuntime` through the extension manager. Registered tools must provide:

- `ToolDefinition`
- `permission_category`
- mode and workflow visibility metadata
- read-only and concurrency metadata
- source metadata supplied by the extension runtime

Registration does not make a tool active by itself. A dynamic tool appears in model schemas and frontend catalog views only when its name is active through `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)`. Extensions cannot replace built-in tools in this slice.

## Local Resource Reload

Workspace-local resources are file-only inputs to the runtime:

- `.embedagent/skills/*.md` and `.embedagent/skills/*.txt`
- `.embedagent/prompts/*.md` and `.embedagent/prompts/*.txt`
- `.embedagent/recipes/*.json`

`ToolRuntime.reload_resources()` refreshes the cached resource snapshot. Hosted product paths expose the same operation through `InProcessAdapter.reload_resources(...)`, `/resources reload`, and `POST /api/sessions/{session_id}/resources/reload`.

Recipe JSON resources feed the existing `list_recipes` and `run_recipe` contract. Skills and prompts are discovered and surfaced with diagnostics, but they are not executed as project-local Python code. Reload appends transcript-backed `resource_discovered` and `resource_reloaded` events for session-scoped auditability.

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
| `task_status` | expose current default harness workflow projection | none |
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
- `source_type`
- `source_id`

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
- `src/embedagent/harness/extension.py`

This document must stay aligned with those files.
