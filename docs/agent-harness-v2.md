# Agent Harness V2

## 1. Status

This document is now the official architecture baseline, not a future design draft.

Agent Harness is the promoted default C/C++ workflow model for EmbedAgent.

The harness is now being extracted behind the in-process workflow extension boundary. It remains bundled and enabled by default, but Agent Core should interact with it through `ExtensionManager` rather than importing harness task classes directly.

The hosted runtime has one adapter-owned `ExtensionManager` shared by `InProcessAdapter`, each session-scoped `QueryEngine`, and frontend tool catalog visibility. This is internal wiring for the built-in harness boundary, not project-local extension discovery or a plugin marketplace.

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

Execution ownership is concentrated in one session-scoped `QueryEngine`.
Harness updates workflow truth inside that engine-owned session through the default workflow extension; it is not a second runtime.

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

`Session.workflow_state` is the generic carrier introduced for workflow-neutral Agent Core. `Session.task_graph` remains the compatibility mirror for this default harness, but frontend projection now reads `Session.workflow_state["workflow"]`.

`describe_mode(...)` is read-only prompt/context description.
`update_task_graph(...)` is the harness path that mutates workflow truth inside `Session`.

The built-in C harness workflow extension owns synchronization from harness internals into `Session.workflow_state["workflow"]`, including:

- `summary`
- `items`
- `activity`
- `metadata.current_phase`
- `metadata.discipline_profile`

`HarnessStateSynchronizer` remains as a lazy compatibility facade for older service imports, but the refresh and task-snapshot persistence behavior now lives behind the C harness workflow extension. `InProcessAdapter` does not construct the synchronizer in the product path.

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

The built-in C harness extension activates recipe, quality, evidence, and task-status tools through its selected workflow pack. Its active-tool hook returns pack tools only; callers union those with the mode contract when they need the full default C/C++ tool set. `QueryEngine` requests schemas by explicit active tool names. `ToolRuntime.schemas_for(mode)` remains the pure mode-contract projection, while `ToolRuntime.schemas_for_mode(mode)` is the default-harness compatibility projection.

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
