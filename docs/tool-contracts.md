# Tool Contracts

## 1. Official Tool Contract

Every official tool should be understood as a contract made of:

- name
- description
- parameter schema
- structured observation shape
- catalog metadata
- permission category

`ToolRuntime` catalog metadata is the source of truth for permission category.
`PermissionPolicy` consumes the active runtime category lookup and must not keep
a parallel built-in tool-name taxonomy. A tool without valid category metadata
is classified as `other`, which asks by default.

Catalog metadata may also declare `read_model_invalidations`, a list of safe
read models that should be refreshed after a tool finishes, such as
`workspace_files`, `tasks`, or `capabilities`. Hosted adapters and GUI/TUI shells
may use those hints to refresh read-only projections, but they must not infer
refresh behavior from hard-coded tool-name lists. These hints do not activate
tools, grant permissions, mutate workflow state, or bypass `PermissionPolicy`.

Catalog metadata may declare safe presentation metadata such as `preview_arg`
and `changed_path_arg`. The runtime projects only the whitelisted presentation
metadata under catalog-entry `metadata`, and GUI timeline previews/changed-file
summaries consume that projection through session capabilities instead of
checking names such as `bash`, `read_file`, `write_file`, or `grep_text`.
Presentation metadata affects display only; it does not activate tools, grant
permissions, execute tools, or change workflow state.

The official runtime facade is:

- `packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py`

Workflow extensions may activate focused subsets of registered tools for a turn. The default C/C++ harness extension owns harness-specific tool activation, recipe readiness/execution, context reducers, and `task_status` behavior, while `ask_user` and `propose_mode_switch` remain core interaction actions executed through the shared action lifecycle.

`CORE_PACK` is the minimal editing/search/shell foundation. Harness-only tools such as `list_recipes`, `run_recipe`, `report_quality_v2`, `record_failing_evidence`, and `task_status` must be registered/activated by workflow packs/extensions rather than being treated as bare Core tools.

Bundled C/C++ workflow pack definitions are owned only by `src/embedagent/workflow_packages/c_cpp/packs.py`. The removed tooling-package pack re-export and package-root aliases must not be treated as official tool contracts.

Built-in mode `allowed_tools` are workflow-neutral permission/write contracts. They must not be used as the complete default C/C++ tool list. The C harness extension reports only its active pack tools; product paths that need the default harness behavior must union the mode contract with active workflow-extension tools and request schemas by explicit active tool names.

`ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single runtime schema projection entry point. Without explicit `tool_names`, it projects only the workflow-neutral mode contract. Harness-aware schema projection belongs to `AgentExtensionHost`, which consults the shared `ExtensionManager`, combines active extension tools with the mode contract, and passes explicit active tool names into runtime schema projection.

`TurnSnapshot` is the provider-request boundary for model-visible tools. After `AgentExtensionHost` projects active tool schemas, `QueryEngine` freezes the messages and schemas into a turn snapshot and calls the provider with `snapshot.messages` and `snapshot.tool_schemas`. Snapshot diagnostics may include safe prompt-unit metadata such as a local skill listing's visible names and counts plus registered/active tool name lists; they must not include skill bodies, prompt bodies, full prompt text, raw file contents, raw tool outputs, or credentials.

`WorkflowPackageManifest` is a read model, not a tool runtime. It describes workflow package identity, declared tools, packs, supported modes/workflow states, resource scopes, and diagnostics. The bundled C/C++ manifest is derived from package-owned constants and exposed through the extension manager. Manifest entries do not make tools active, execute tools, reload resources, load project extensions, or bypass permission policy.

`CapabilityRegistry` is a read model, not a tool runtime. It can describe registered tools, local file resources, slash commands, the active model profile, and workflow packages with provenance metadata. Registration in the registry does not make a tool active, does not execute a tool, does not reload resources, does not load project extensions, and does not bypass permission policy.

Slash command specs for workspace-local skill and prompt resources are
projected by `slash_commands.resource_command_specs(resources)`. Hosted
adapters and capability projections should consume that boundary instead of
owning adapter-local resource command spec builders.

`RuntimeConfigReducer` is a transcript-backed read model, not a tool runtime. It describes replayable runtime configuration such as credential-free model profile metadata, registered tool names, active model-visible tool names, local resource revision metadata, safe prompt-unit metadata, capability counts, and provider snapshot records. Reducer state does not make a tool active, execute a tool, reload resources, load project extensions, or bypass permission policy.

`CompactionStateReducer` is a transcript-backed read model, not a tool runtime. It describes compact boundary diagnostics and compacted-history checkpoint diagnostics such as token/message counts, preserved message anchors, safe file activity paths, evidence refs, replacement-message counts, and duplicate/malformed diagnostics. Reducer state does not make a tool active, execute a tool, reload resources, load project extensions, select context, generate summaries, or bypass permission policy. `compacted_history` checkpoints are context/session-history events, not tool contracts.

`RecoveryStateReducer` is a transcript-backed read model, not a tool runtime. It describes hosted resume diagnostics such as trusted-prefix counts, stop reasons, reducer summaries, and duplicate/malformed diagnostics. Reducer state does not make a tool active, execute a tool, reload resources, load project extensions, change restore validation, select context, or bypass permission policy.

Allowed-tool gating is not a runtime wrapper. Hosted product paths use `AgentExtensionHost.allowed_tool_names(...)` through the shared extension host and request runtime schemas with explicit active tool names.

`author_local_capability` is a workflow-neutral write tool for local self-extension authoring. It creates workspace-bound skills, prompts, workflow-neutral recipe JSON, and disabled-by-default project extension skeletons under `.embedagent`; it does not reload resource caches, stamp generated recipe files with default C/C++ workflow tool names, or load, enable, import, or trust generated Python extension code.

Runtime-invoked external binaries are governed by `scripts/offline-runtime-contract.json`. If a tool implementation, recipe path, or workflow package starts invoking a new bundled binary, the runtime contract and packaging validators must be updated in the same change. The contract currently covers Python, Bash from MinGit, MinGit, ripgrep, Universal Ctags, and LLVM/Clang child executables.

Shell tooling uses `get_command_sanitizer()` directly. Do not depend on or
recreate removed sanitizer proxy/wrapper aliases.

## Extension Tool Hooks

The extension runtime may observe or patch tool calls through typed in-process hooks:

- `tool_call` can block an allowed tool call or return updated arguments before permission/tool execution continues.
- `tool_result` can replace the structured observation or provide a workflow patch after execution.

These hooks do not bypass mode contracts, `PermissionPolicy`, path write checks, or tool metadata categories.

Extensions expose hook participation only through `extension_capabilities()` records. Each record is an `ExtensionCapability` naming the hook, handler, optional event type, reducer/observer kind, fail-closed override, and safe metadata. Method names alone are inert; for example, a project extension that defines `register_tools(...)` or `allowed_tool_names(...)` without returning matching `api.ExtensionCapability(...)` records is loaded but contributes no tools or active-tool policy.

`AgentToolActionService` is the Agent Core boundary that applies those hooks around non-LLM tool action execution. It keeps extension pre/post hooks, permission checks, pending permission/user-input creation, resumed interaction execution, mode-switch proposals, path write guards, extension-owned tool handling, workflow-patch capture, and `ToolRuntime` dispatch in one pipeline. Interactive actions are skipped by parallel pre-execution and re-enter the serial action pipeline, so `QueryEngine` does not own separate `ask_user`, mode-switch, or workflow-patch branches.

## Dynamic Extension Tool Registration

In-process extensions may register tools into the shared `ToolRuntime` through the extension manager. Registered tools must provide:

- `ToolDefinition`
- `permission_category`
- mode and workflow visibility metadata when they need to override defaults
- read-only and concurrency metadata through either the `ToolDefinition` or explicit metadata
- optional read-model invalidation hints such as `read_model_invalidations`
- optional presentation metadata such as `preview_arg` and `changed_path_arg`
- source metadata supplied by the extension runtime

Registration does not make a tool active by itself. A dynamic tool appears in model schemas and frontend catalog views only when its name is active through `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)` as consumed by `AgentExtensionHost`. Project-local Python extensions use the same registration path and source metadata. Extensions cannot replace built-in tools.

Internally the runtime catalog is faceted into execution, presentation, and context-policy metadata while preserving the flat `tool_catalog_entry(...)` payload for protocol/frontend consumption. Extension tool declarations only require a valid `permission_category`; the runtime derives conservative defaults for the remaining facets unless the tool metadata overrides them. Only safe presentation fields are copied into catalog-entry `metadata`.

`ToolRuntime.capability_descriptors()` may project these catalog entries for diagnostics and future reducer work. It must stay read-only and must not become an active-tool policy shortcut.

`runtime_config.active_tool_names` records tools that were model-visible after activation had already happened. It is audit/replay data only. New tool gating must continue to use `ExtensionManager.allowed_tool_names(...)` through `AgentExtensionHost`.

## Enterprise/Intranet Tool Boundary

Intranet Git operations, custom service calls, model/provider gateways, organization-local catalog actions, and telemetry uploaders are not hidden Core tools. They must enter through explicit provider, extension, workflow-package, or passive sink boundaries with source metadata, structured configuration, timeout/fallback behavior, and normal `PermissionPolicy` checks.

Dynamic networked tools must declare a permission category recognized by the runtime catalog and permission model. `network` is the official category for tools that reach intranet/custom services. `telemetry` is the official category for explicit telemetry flush/upload actions. Do not hide network side effects behind generic `read` or unclassified `other` behavior.

Telemetry sinks observe safe structured lifecycle/capability/diagnostic events only. `src/embedagent/telemetry.py` builds local safe envelopes for future sinks by redacting or summarizing sensitive metadata. Sinks must not receive full prompts, skill bodies, source file contents, raw tool outputs, API keys, approval secrets, permission payloads, or permission tokens. Sink failures are diagnostics, not tool failures, unless a future explicit user action is specifically invoking the sink as a tool.

## Local Resource Reload

Workspace-local resources are file-only inputs to the runtime:

- `.embedagent/skills/*.md`, `.embedagent/skills/*.txt`, and directory-local `.embedagent/skills/<name>/SKILL.md`
- `.embedagent/prompts/*.md` and `.embedagent/prompts/*.txt`
- `.embedagent/recipes/*.json`

`ToolRuntime.reload_resources()` refreshes the cached resource snapshot. Hosted product paths expose the same operation through `InProcessAdapter.reload_resources(...)`, `/resources reload`, and `POST /api/sessions/{session_id}/resources/reload`.

Recipe JSON resources are workflow-neutral file resources. The default C/C++ workflow package feeds them into its `list_recipes` and `run_recipe` contract only after applying package-owned recipe normalization. Skills and prompts are discovered and surfaced with diagnostics, but they are not executed as project-local Python code. Skill Markdown may include Agent Skills-style frontmatter (`name`, `description`, `disable-model-invocation`). Skills with valid names, descriptions, and no disable flag are summarized once through the hosted local skill listing prompt unit; disabled skills remain discoverable resources but are omitted from model-invocation listings. Prompt resources are never inlined into default system prompts.

Skill discovery under `.embedagent/skills` honors local `.gitignore`, `.ignore`, and `.fdignore` files with a dependency-free subset: blank lines and `#` comments, exact relative paths, directory rules ending in `/`, `fnmatch`-style globs, and `!` negation. Ignore handling is a file-discovery filter only; it does not execute ignore-file logic, load extensions, grant permissions, or change workspace-bound path checks.

`SkillIndex` is the internal non-executing read model for local skill resources. It unifies prompt listing, `/skill:<name>` lookup, visible skill slash-command projection, and safe skill summaries. It consumes discovered resource metadata only; it does not execute skill files, reload resources, decide permissions, activate tools, or introduce a first-class frontend `skill` capability kind.

`/skill:<name> [args]` is an explicit local skill invocation command. It resolves the named workspace-bound skill resource, strips frontmatter, wraps the Markdown body in a `<skill ...>` context block, appends optional args, and continues as a normal user turn. Visible skill commands are projected into `/help` and command capability descriptors as `skill:<name>`. They do not execute code, load project extensions, grant permissions, or bypass active-tool policy.

`/prompt:<name-or-path> [args]` is an explicit local prompt invocation command. It resolves a workspace-bound prompt resource by unique name or path, wraps the text body in a `<prompt ...>` context block, appends optional args, and continues as a normal user turn. Prompt commands are projected into `/help` and command capability descriptors as `prompt:<name>`. They do not execute code, load project extensions, grant permissions, or bypass active-tool policy.

Reload appends transcript-backed `resource_discovered` and `resource_reloaded` events for session-scoped auditability. Session-scoped reload also refreshes the current session's single `local_skills_prompt` listing message so newly visible skills can be discovered without starting a new session. `resource_reloaded` advances reducer-backed local resource revision metadata; `resource_discovered` remains discovery/replay diagnostics and must not advance runtime resource revision.

## Project-Local Python Extensions

Hosted product paths may load project-local Python extensions from `.embedagent/extensions/<name>/extension.json`. `enabled` defaults to false; enabled manifests must declare permissions and may point only to a workspace-bound `extension.py` entrypoint inside the extension directory.

Loaded project extensions receive a narrow API object exposing extension result dataclasses, `ExtensionCapability`, `ToolDefinition`, `Observation`, and workspace-bound text helpers. The loader does not install dependencies, contact remote registries, execute local resources, or allow built-in tool replacement. Dynamic tools from project extensions remain subject to catalog metadata, active-tool gating, and `PermissionPolicy`.

`WorkflowPatch` is the tool-result hook read-model patch shape. It carries only
`workflow` and safe `metadata`; it does not expose legacy projection fields or
grant tool activation, permission, or history authority.

Generated extension skeletons from `author_local_capability` start disabled. They become executable only through the existing hosted project-extension loading path after a manifest is explicitly enabled and passes validation.

Generated extension validation recipes must remain offline-friendly and workflow-neutral on disk. When the bundled C/C++ workflow package is active, they execute through that package's `run_recipe` projection with managed bundle commands such as `python -m py_compile ...`, not through dependency installers or remote package managers.

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
| `bash` | execute an explicit sanitized shell command with decoded stdout/stderr and structured failure guidance | `command`, optional `cwd`, `timeout_sec` |
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

Command execution is represented by `bash`, not by additional build-shaped wrappers. Recipe calls must report readiness and explicit next steps when a recipe is missing, mismatched, or blocked by prerequisites.

## 3. Observation Shape

Official tools should return structured observations, not raw terminal dumps as the only output.

Common fields include:

- `success`
- `error`
- `tool_name`
- tool-specific structured `data`

Command observations must include decoded output metadata (`stdout_encoding`, `stderr_encoding`, replacement counts, and mojibake hints), tail-preserving truncation flags, and a `full_output_ref` when omitted output was materialized. Failed command-like observations should include `error_kind`, `outcome_class`, `retryable`, and `suggested_next_step` when the tool can infer a useful next action. Ordinary non-zero command exits and command timeouts are diagnostic failures for the agent loop: they should be visible to the next model turn and must not be treated as automatic hard-stop conditions.

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
- `network`
- `telemetry`

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

- `packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py`
- `src/embedagent/workflow_packages/c_cpp/extension.py`
- `src/embedagent/workflow_packages/c_cpp/tool_registry.py`
- `src/embedagent/workflow_packages/c_cpp/tool_metadata.py`

This document must stay aligned with those files.
