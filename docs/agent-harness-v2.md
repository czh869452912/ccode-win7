# Agent Harness V2

## 1. Status

This document is now the official architecture baseline, not a future design draft.

Agent Harness is the promoted default C/C++ workflow model for EmbedAgent.

The harness is now being extracted behind the in-process workflow extension boundary. It remains bundled and enabled by default, but Agent Core should interact with it through `ExtensionManager` rather than importing harness task classes directly.

The hosted runtime has one adapter-owned `ExtensionManager` shared by `InProcessAdapter`, each session-scoped `QueryEngine`, and frontend tool catalog visibility. `QueryEngine` consumes that manager through `AgentExtensionHost`, which centralizes prompt/context hooks, active tool names, dynamic tool registration, explicit schema projection, tool-call hooks, tool-result hooks, and extension-owned tool handling. `src/embedagent/default_extensions.py` installs the bundled C harness into that manager for hosted product paths. A bare `QueryEngine` does not import or construct the default harness extension. Hosted product paths may load manifest-gated project-local Python extensions into the same manager. Local file resources, including Agent Skills-style Markdown skills, text prompt files, `/skill:<name>` expansion, and `/prompt:<name-or-path>` expansion, remain file-only Agent Core resources rather than harness package execution; remote registries, plugin marketplaces, dependency installation, built-in tool replacement, and multi-agent orchestration remain outside the harness baseline.

The C harness contributes workflow prompt units through the generic workflow prompt boundary. New prompt descriptors use `WorkflowPrompt`, and newly appended prompt messages use `kind="workflow_prompt"`; `HarnessPrompt` and `kind="harness_prompt"` are compatibility names only for older source/session history.

## 2. Core Ideas

Harness exists to balance:

- task focus for weaker/offline models
- enough flexibility for real project work
- explicit workflow discipline
- deterministic tool access

It does that by separating three concerns:

- user-visible `mode`
- internal `discipline_profile`
- internal `execution_phase`

Execution ownership is concentrated in one session-scoped `QueryEngine` facade. `AgentKernel` owns turn frames and pending interaction lifecycle boundaries, `AgentLifecycleJournal` owns durable lifecycle operation writes and save points, `AgentLoop` owns turn-loop orchestration, `AgentToolActionService` owns non-LLM tool action execution, and `AgentExtensionHost` owns extension dispatch. Harness updates workflow truth inside that engine-owned session through the default workflow extension; it is not a second runtime.

Provider requests consume an explicit `TurnSnapshot` built by `QueryEngine` after context assembly and active schema projection. The snapshot records the harness-influenced workflow state and active schemas as frozen inputs, but it does not decide harness phase, active packs, permissions, or tool execution.

Structured compaction state is reducer-backed diagnostics, not harness workflow truth. `compaction_state` may explain compact boundaries and safe file/evidence metadata after restore, but harness phase, task graph state, active packs, permissions, and tool execution remain owned by their existing harness/core boundaries.

Recovery state is reducer-backed diagnostics, not harness workflow truth. `recovery_state` may explain hosted resume attempts and trusted transcript prefixes after restore, but harness phase, task graph state, active packs, permissions, and tool execution remain owned by their existing harness/core boundaries.

## 3. Official Modes

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

## 4. Discipline Profiles

Current harness supports:

- `lite_spec_tdd`
- `full_spec_tdd`

`build` and `debug` may operate in either profile depending on workflow state and harness context.

## 5. Phase Model

Representative phase tracks:

### Build

- `understand`
- `contract`
- `implement`
- `check`
- `handoff`

Full profile may insert:

- `test_design`
- `repair`

### Debug

- `reproduce`
- `isolate`
- `patch`
- `regression_check`
- `handoff`

### Verify

- `select_recipe`
- `execute`
- `summarize`

## 6. Task Truth

The official task system is:

- `TaskGraph`
- projected into `task_status`
- persisted as session task snapshots

`Session.workflow_state` is the generic carrier for workflow-neutral Agent Core. `Session.task_graph` has been removed; the default C/C++ harness keeps `TaskGraph` state behind `CHarnessWorkflowExtension` and its harness-owned session graph state. Frontend projection reads `Session.workflow_state["workflow"]`. Importing or instantiating `embedagent.session.Session` must not import harness task graph internals.

`describe_mode(...)` is read-only prompt/context description.
`update_task_graph(...)` is the harness path that returns updated harness-owned graph state; the extension then projects it into `Session.workflow_state["workflow"]`.

The built-in C harness workflow extension owns synchronization from harness internals into `Session.workflow_state["workflow"]`, including:

- `summary`
- `items`
- `activity`
- `metadata.current_phase`
- `metadata.discipline_profile`

The generic workflow payload is assembled by `src/embedagent/harness/workflow_projection.py`. This keeps the C harness `TaskGraph` shape separate from the core/frontend workflow read model.

Workflow-neutral strategies and projectors read this generic workflow payload. They must not inspect harness task graph internals directly.

The old `HarnessStateSynchronizer` service facade has been removed. Refresh and task-snapshot persistence behavior now lives behind `CHarnessWorkflowExtension.refresh_managed_session()`, and `InProcessAdapter` reaches it through the default C harness workflow extension.

Frontends consume:

- `task_summary`
- `task_items`

The old prompt-only todo flow is no longer the architecture baseline.

## 7. Tool Packs

Harness exposes focused packs instead of an undifferentiated tool wall.

Main pack families:

- discovery/file tools
- recipe/build/verify tools
- task/interaction tools

This keeps model tool selection tight without hard mode walls becoming unusable.

The workflow-neutral `CORE_PACK` does not contain harness workflow tools. Built-in mode `allowed_tools` are also workflow-neutral permission/write contracts; they do not own `list_recipes`, `run_recipe`, `report_quality_v2`, `record_failing_evidence`, or `task_status`.

The built-in C harness extension registers and activates compiler/build helpers, recipe execution, quality reporting, failing-evidence capture, and task-status tools through the shared extension capability boundary. Tool definitions are assembled in `src/embedagent/harness/tool_registry.py`, their metadata lives in `src/embedagent/harness/tool_metadata.py`, and pack ownership lives in `src/embedagent/harness/packs.py`. Its active-tool hook returns pack tools only; `AgentExtensionHost` unions those with the mode contract when the engine needs the full default C/C++ tool set. `AgentExtensionHost` requests schemas by explicit active tool names through `ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)`. Runtime schema filtering no longer activates the default harness pack by itself, and bare `ToolRuntime` construction does not register default C/C++ workflow tools.

The built-in C harness extension also registers C workflow context reducers from `src/embedagent/harness/context_reducers.py`. Core `ReducerRegistry` stays workflow-neutral; build diagnostics, recipe summaries, quality reports, and task-status reduction belong to the workflow package.

The old `embedagent.tooling.packs` compatibility export has been removed. Current code must import bundled C/C++ workflow pack definitions from `embedagent.harness.packs`.

Harness code should also consume current core accessors directly. The old
`MODE_REGISTRY` and sanitizer compatibility aliases are not harness contracts;
mode registry and shell command sanitizer access now go through
`get_mode_registry()` and `get_command_sanitizer()`.

The built-in C harness extension also exposes a read-only workflow package manifest. The manifest describes package identity, supported modes/workflow states, declared workflow tools, packs, and recipe resource scope from harness-owned constants. It is control-plane metadata only and is not the harness pack activation mechanism.

`CapabilityRegistry` can project harness-registered tools through the shared runtime catalog and the C workflow package manifest through `workflow_package` descriptors for diagnostics and future reducer work. That projection is not the harness pack activation mechanism; active C/C++ workflow tools still come from the default harness extension and `ExtensionManager.allowed_tool_names(...)`.

`RuntimeConfigReducer` can project registered tool names, harness-influenced active model-visible tool names, and local resource revision metadata after those decisions have been emitted to the transcript. That projection is not the harness pack activation mechanism; the default C/C++ extension still owns pack selection and `AgentExtensionHost` still owns schema projection.

Harness recipes and quality flows must invoke only bundled external tools described by `scripts/offline-runtime-contract.json`. The packaging gate validates Python, MinGit, ripgrep, Universal Ctags, and LLVM/Clang child executables from that shared contract, so adding a harness runtime binary requires updating the contract and tests in the same change.

## 8. Prompting Model

Prompt construction is layered through harness prompt units, not only through monolithic mode prompts.

The important result is:

- modes stay understandable
- tool focus stays narrow
- task state is surfaced explicitly

## 9. Permission / Context Relationship

Harness does not replace permission or context systems.

- Harness decides workflow focus
- Permission decides whether an action is allowed/ask/deny
- Context decides what prior information is preserved and surfaced

These are cooperating subsystems, not one overloaded prompt.

## 10. Frontend Projection

The official frontend vocabulary for harness state is:

- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`

GUI and TUI should treat these as the stable shell-facing summary of harness state.

GUI session activation must layer that harness summary through one bootstrap payload sourced from transcript-backed session state. Replay logs remain live transport metadata only.

`SessionSnapshotProjector` is the official snapshot read model for that shell-facing summary. It reads `Session.workflow_state["workflow"]`, not `TaskGraph`.

## 11. Design Rule

Do not reintroduce long-lived parallel V1/V2 paths.

When harness changes:

- promote the new path into the official runtime/frontends
- then delete the old path or archive its documentation
