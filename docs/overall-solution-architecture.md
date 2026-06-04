# Overall Solution Architecture

## 1. Scope

EmbedAgent is a native, offline-first Agent IDE core for C/C++ engineering.

The stable architecture assumptions are:

- Windows 7 compatibility
- Python 3.8 runtime target
- Offline bundle delivery
- Agent Core first, UI shells replaceable
- Clang-centered toolchain

## 2. Top-Level Structure

The product is organized around one main execution spine:

`Frontend -> Core Adapter -> InProcessAdapter -> Session Runtime -> QueryEngine -> ExtensionManager -> Harness/ToolRuntime -> Permission/Context/Stores`

### Frontend Layer

- `src/embedagent/frontend/tui/`
- `src/embedagent/frontend/gui/`

These are shells only. They do not own workflow semantics.

### Protocol / Core Layer

- `src/embedagent/protocol/`
- `src/embedagent/core/`

This is the stable contract boundary between UI and Agent Core.

### Agent Core Layer

- `src/embedagent/inprocess_adapter.py`
- `src/embedagent/query_engine.py`
- `src/embedagent/session_runtime.py`
- `src/embedagent/session_projector.py`
- `src/embedagent/session_history.py`
- `src/embedagent/extensions.py`
- `src/embedagent/default_extensions.py`
- `src/embedagent/harness/workflow_projection.py`
- `src/embedagent/tools/`
- `src/embedagent/context.py`
- `src/embedagent/permissions.py`

This is the product core.

The default C/C++ harness is now entered through the in-process workflow extension boundary. Harness internals remain bundled and enabled by default, but `QueryEngine` must not import concrete harness task classes directly.

`InProcessAdapter` owns the hosted runtime's `ExtensionManager` and passes that same manager to each session-scoped `QueryEngine`. Frontend tool catalog visibility is computed from the same manager, so model-facing tools and shell metadata share one extension chain.

`ExtensionManager` is now the shared in-process capability boundary. The current default C/C++ harness remains the bundled workflow extension, while the same boundary also carries generic prompt/context hooks, tool-call and tool-result interception, resource discovery contracts, and extension diagnostics. Project-local Python extension loading is not enabled in this slice; only the contract and built-in/injected extension path are official.

Default bundled extension assembly is outside `QueryEngine` in `src/embedagent/default_extensions.py`. A bare `QueryEngine` receives an empty `ExtensionManager`; hosted product paths install the default C/C++ harness explicitly before constructing session engines. This is the closed default-extension configuration decision for the current product baseline: there is no project-local extension discovery, remote registry, plugin marketplace, or multi-agent orchestration layer in scope.

Harness state refresh in the product adapter path goes through `CHarnessWorkflowExtension.refresh_managed_session()` behind the default C harness workflow extension. The old `HarnessStateSynchronizer` service facade has been removed rather than kept as a parallel compatibility path.

### Session Runtime Ownership

- `ManagedSession` hosts thread/lock/status and durable `Session` references
- one session-scoped `QueryEngine` is the only owner of turn/step/interactions and transcript mutation
- `InProcessAdapter` is a host/bridge layer and must not mint duplicate workflow identities
- `SessionSnapshotProjector` and `SessionHistoryAssembler` are projections, not workflow truth
- `SessionSnapshotProjector` reads the generic workflow projection, not default harness internals

## 3. Official Execution Model

The repository now uses one default C/C++ workflow model:

- user-visible `mode`
- internal `discipline_profile`
- internal `execution_phase`
- `TaskGraph` as default harness workflow truth
- `Session.workflow_state` as the generic workflow-state carrier

### Official Modes

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

`build` is the only implementation mode.

### Official Task Model

The default task system is no longer prompt-only.

Official task truth flows through:

- `TaskGraph`
- `task_status`
- session task snapshots

`Session.task_graph` has been removed. The default C/C++ harness keeps `TaskGraph` ownership behind `CHarnessWorkflowExtension` and a harness-owned session graph state adapter, while the core/frontend boundary carries only `Session.workflow_state["workflow"]`. Importing or instantiating `embedagent.session.Session` must not load harness task graph internals.

Frontend-facing task projection now comes from `Session.workflow_state["workflow"]`. The default C/C++ harness extension is responsible for keeping that projection synchronized with its internal task graph and persisted session task snapshots. The payload assembly itself is centralized in `src/embedagent/harness/workflow_projection.py`, which is the adapter from C harness internals to generic workflow state.

Workflow-neutral strategies, projectors, and frontend task APIs read task state from that generic workflow projection rather than from harness task graph internals.

Session snapshots carry:

- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`
- `extensions`
- `extension_diagnostics`

## 4. Tool Architecture

The tool runtime has one official facade:

- `src/embedagent/tools/runtime.py`

Harness selects focused tool packs by mode/phase, but execution still flows through one runtime object.

Built-in mode allowed-tool lists are workflow-neutral permission/write contracts. Default C/C++ workflow tools are activated by the harness extension and packs, then passed to runtime schema projection as explicit active tool names.

`ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single runtime schema projection entry point. Without explicit `tool_names`, it projects only the workflow-neutral mode contract; it must not be used to activate the default harness pack implicitly.

### Official Tool Families

#### File / Discovery

- `read_file`
- `list_dir`
- `glob_files`
- `grep_text`
- `write_file`
- `edit_file`

#### Build / Verify

- `list_recipes`
- `run_recipe`
- `report_quality_v2`
- `record_failing_evidence`

#### Workflow / Interaction

- `task_status`
- `ask_user`

#### Supporting Capabilities

- `git_status`
- `git_diff`
- `git_log`
- `run_command` as controlled fallback

## 5. Workflow Extension And Harness Layer

`src/embedagent/extensions.py` owns the local in-process capability extension contract.

The default C/C++ harness extension in `src/embedagent/harness/extension.py` owns:

- mode registry
- discipline defaults
- phase advancement rules
- prompt unit construction
- task graph construction
- session task snapshot persistence

This keeps workflow structure out of the frontend, out of ad-hoc prompt text, and out of the workflow-neutral parts of Agent Core.

## 6. Permission Layer

`src/embedagent/permissions.py` is the only official permission engine.

It owns:

- action category mapping
- rule loading
- rule matching
- stable explanation text
- frontend-visible permission context

The frontend should never infer permission policy from mode alone.

## 7. Context Layer

`src/embedagent/context.py` and `src/embedagent/workspace_intelligence.py` own:

- context budgets
- reducer registry
- tool-result replacement
- summary assembly
- workspace intelligence evidence

The context system is aligned to the official harness vocabulary, especially:

- `build`
- `list_dir`
- `glob_files`
- `grep_text`
- `run_recipe`
- `report_quality_v2`
- `task_status`

## 8. Session / Transcript Truth

Session truth is distributed across:

- live `Session`
- transcript events
- `SessionHistoryAssembler` projections
- tool result storage/projections
- summary store
- task snapshots

No frontend should maintain its own workflow truth separate from session snapshots and replayable events.

Additional ownership rules:

- engine-issued `turn_id` / `step_id` / `step_index` are the only official execution anchors
- resumed interactions must re-enter the same action pipeline used by first execution
- snapshot/bootstrap payloads are projected from session truth and do not own side effects

### Session History Rule

Official session-history ownership is:

- `transcript.jsonl` is the only durable session-history ledger
- `Session` / `session.turns` is the only live structured history state
- `timeline.jsonl` is replay transport only
- GUI activation reads one bootstrap payload that includes snapshot, structured history, plan, permission context, and replay metadata

Historical turns must never be rebuilt from replay-log tails.

## 9. Frontend Contract

The frontend-facing vocabulary is now:

- `build`, not `code`
- `tasks`, not `todos`
- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`

If a frontend change introduces older terms back into the product shell, that is an architectural regression.

## 10. Bundling Model

The shipped product is expected to be a self-contained offline bundle.

The architecture therefore assumes runtime discovery for bundled tools, not global machine dependencies.

## 11. Design Rule

Do not reintroduce parallel V1/V2 execution paths.

When changing architecture:

- promote the new path to the only official path
- then delete or archive the old path
- keep current docs describing only the official architecture
