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

`ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single runtime schema projection entry point. Without explicit `tool_names`, it projects only the workflow-neutral mode contract. Harness-aware schema projection belongs to `AgentExtensionHost`, which consults the shared `ExtensionManager`, combines active extension tools with the mode contract, and passes explicit active tool names into runtime schema projection.

`TurnSnapshot` is the provider-request boundary for model-visible tools. After `AgentExtensionHost` projects active tool schemas, `QueryEngine` freezes the messages and schemas into a turn snapshot and calls the provider with `snapshot.messages` and `snapshot.tool_schemas`.

`CapabilityRegistry` is a read model, not a tool runtime. It can describe registered tools, local file resources, slash commands, and the active model profile with provenance metadata. Registration in the registry does not make a tool active, does not execute a tool, does not reload resources, does not load project extensions, and does not bypass permission policy.

Allowed-tool gating is not a runtime wrapper. Core orchestration receives an explicit allowed-tool policy from its host; hosted product paths use `QueryEngine._allowed_tools_for_mode(...)` as a compatibility facade over `AgentExtensionHost.allowed_tool_names(...)`.

`author_local_capability` is a workflow-neutral write tool for local self-extension authoring. It creates workspace-bound skills, prompts, recipes, and disabled-by-default project extension skeletons under `.embedagent`; it does not reload resource caches and does not load, enable, import, or trust generated Python extension code.

Runtime-invoked external binaries are governed by `scripts/offline-runtime-contract.json`. If a tool implementation, recipe path, or workflow package starts invoking a new bundled binary, the runtime contract and packaging validators must be updated in the same change. The contract currently covers Python, MinGit, ripgrep, Universal Ctags, and LLVM/Clang child executables.

## Extension Tool Hooks

The extension runtime may observe or patch tool calls through typed in-process hooks:

- `tool_call` can block an allowed tool call or return updated arguments before permission/tool execution continues.
- `tool_result` can replace the structured observation or provide a workflow patch after execution.

These hooks do not bypass mode contracts, `PermissionPolicy`, path write checks, or tool metadata categories.

`AgentToolActionService` is the Agent Core boundary that applies those hooks around non-LLM tool action execution. It keeps extension pre/post hooks, permission checks, path write guards, extension-owned tool handling, and `ToolRuntime` dispatch in one pipeline.

## Dynamic Extension Tool Registration

In-process extensions may register tools into the shared `ToolRuntime` through the extension manager. Registered tools must provide:

- `ToolDefinition`
- `permission_category`
- mode and workflow visibility metadata
- read-only and concurrency metadata
- source metadata supplied by the extension runtime

Registration does not make a tool active by itself. A dynamic tool appears in model schemas and frontend catalog views only when its name is active through `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)` as consumed by `AgentExtensionHost`. Project-local Python extensions use the same registration path and source metadata. Extensions cannot replace built-in tools.

`ToolRuntime.capability_descriptors()` may project these catalog entries for diagnostics and future reducer work. It must stay read-only and must not become an active-tool policy shortcut.

## Local Resource Reload

Workspace-local resources are file-only inputs to the runtime:

- `.embedagent/skills/*.md` and `.embedagent/skills/*.txt`
- `.embedagent/prompts/*.md` and `.embedagent/prompts/*.txt`
- `.embedagent/recipes/*.json`

`ToolRuntime.reload_resources()` refreshes the cached resource snapshot. Hosted product paths expose the same operation through `InProcessAdapter.reload_resources(...)`, `/resources reload`, and `POST /api/sessions/{session_id}/resources/reload`.

Recipe JSON resources feed the existing `list_recipes` and `run_recipe` contract. Skills and prompts are discovered and surfaced with diagnostics, but they are not executed as project-local Python code. Reload appends transcript-backed `resource_discovered` and `resource_reloaded` events for session-scoped auditability.

## Project-Local Python Extensions

Hosted product paths may load project-local Python extensions from `.embedagent/extensions/<name>/extension.json`. `enabled` defaults to false; enabled manifests must declare permissions and may point only to a workspace-bound `extension.py` entrypoint inside the extension directory.

Loaded project extensions receive a narrow API object exposing extension result dataclasses, `ToolDefinition`, `Observation`, and workspace-bound text helpers. The loader does not install dependencies, contact remote registries, execute local resources, or allow built-in tool replacement. Dynamic tools from project extensions remain subject to catalog metadata, active-tool gating, and `PermissionPolicy`.

Generated extension skeletons from `author_local_capability` start disabled. They become executable only through the existing hosted project-extension loading path after a manifest is explicitly enabled and passes validation.

Generated extension validation recipes must remain offline-friendly. They should execute through `run_recipe` and managed bundle commands such as `python -m py_compile ...`, not through dependency installers or remote package managers.

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
| `author_local_capability` | create local self-extension artifacts | `kind`, `name`, optional `summary`, `body`, `command`, `recipe_action`, `permissions`, `overwrite` |

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
- `src/embedagent/harness/extension.py`
- `src/embedagent/harness/tool_registry.py`
- `src/embedagent/harness/tool_metadata.py`

This document must stay aligned with those files.
