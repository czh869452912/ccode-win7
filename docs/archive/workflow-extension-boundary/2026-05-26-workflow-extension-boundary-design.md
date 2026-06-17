# Workflow Extension Boundary Design

## Status

Draft for review.

Reviewed once with `claude -p` and revised to close the blocking interface and migration gaps found in that review.

## Context

EmbedAgent has successfully cut over to a single official harness-centered architecture, but the result is now too coupled for continued development and debugging. The current core directly knows about C workflow phases, task graph projection, mode-specific tool packs, frontend task vocabulary, slash-command workflow states, and harness prompt injection.

The desired direction is closer to pi's model:

- keep the agent runtime small
- expose extension points for workflows, tools, prompts, commands, and policy
- ship strong defaults as replaceable built-ins
- let users and projects compose their own outer workflow instead of forcing one permanent product workflow

This design does not remove the existing C/C++ harness behavior immediately. It moves that behavior behind an extension boundary so it can remain the default without being part of the irreducible Agent Core.

## Goals

- Make Agent Core smaller and easier to reason about.
- Move the current harness into a default built-in workflow extension.
- Preserve current user-visible behavior during the first migration slice.
- Keep Windows 7, offline deployment, and Python 3.8 compatibility.
- Avoid introducing Docker, WSL, Node.js-at-runtime, online registries, or npm-based runtime loading.
- Create a path for project-local workflow customization without forking core code.

## Non-Goals

- Do not build a public plugin marketplace.
- Do not adopt pi's TypeScript extension runtime.
- Do not remove C/C++ workflow defaults in the first slice.
- Do not reintroduce long-lived V1/V2 execution paths.
- Do not make MCP, browser automation, or cloud services part of the product baseline.

## Current Coupling

The current codebase treats harness concepts as core concepts:

- `Session` owns `TaskGraph`.
- `QueryEngine` injects harness prompt messages and handles `task_status`.
- `QueryEngine` also creates `TaskGraph` directly from user requests.
- `ToolRuntime` selects schemas through `OfficialRuntimeModes`.
- `InProcessAdapter` creates `HarnessRunner` and refreshes task snapshots.
- `SessionSnapshotProjector` reads `session.task_graph` directly.
- `HarnessStateSynchronizer` is a service-level harness bridge.
- `tooling/packs.py` includes workflow tools such as `run_recipe` and `task_status` in `CORE_PACK`.
- `SessionSnapshot` exposes `current_phase`, `discipline_profile`, `current_activity`, `task_summary`, and `task_items`.
- GUI/TUI treat those fields as official shell vocabulary.
- Source-of-truth docs currently declare harness as the official execution model.

The first extraction must therefore be a boundary change, not a directory move.

The boundary is not valid until all direct core-to-harness access points above are either routed through the extension manager or explicitly documented as temporary compatibility paths with removal tests.

## Proposed Architecture

### Agent Core

Agent Core should own only the durable, workflow-neutral execution substrate:

- session and transcript state
- LLM turn loop
- tool registry and tool execution
- permission evaluation
- context assembly
- summary and tool-result storage
- frontend event/bootstrap projection
- local runtime discovery for bundled tools

Agent Core may expose extension events, but it should not know concrete workflow phase names or built-in C workflow semantics.

### Extension Runtime

Introduce a local Python extension runtime. It should be small and explicit, with no dynamic dependency installation.

Initial extension points:

- `register_tools(registry, context)`
- `register_commands(registry, context)`
- `before_agent_start(event, context) -> PromptPatch`
- `context(event, context) -> ContextPatch`
- `tool_call(event, context) -> ToolCallDecision`
- `tool_result(event, context) -> ToolResultPatch`
- `turn_end(event, context) -> WorkflowPatch`
- `snapshot(event, context) -> Dict[str, Any]`

Events should be synchronous or simple async-free Python call points in the first slice. This keeps Python 3.8 and Win7 behavior predictable.

### Extension Interface Types

Slice 1 must define concrete dataclasses or plain typed dictionaries for every event and patch type before wiring production code.

Initial event fields:

- `session_id`
- `turn_id`
- `step_id`
- `current_mode`
- `workflow_state`
- `user_text`
- `tool_name`
- `tool_arguments`
- `observation`
- `messages`
- `metadata`

Initial context fields:

- `workspace`
- `runtime_environment`
- `tool_registry`
- `permission_policy`
- `session_view`

`session_view` must be read-only from the extension perspective. Extensions request state changes by returning patches; Core applies or rejects those patches.

Initial patch shapes:

- `PromptPatch`: `prompt_units`, `system_prompt_append`, `active_tool_names`, `metadata`
- `ContextPatch`: `messages`, `metadata`
- `ToolCallDecision`: `block`, `reason`, `updated_arguments`, `metadata`
- `ToolResultPatch`: `observation`, `workflow_patch`, `metadata`
- `WorkflowPatch`: `workflow`, `legacy_projection`, `metadata`

`None` means "no change" for every hook.

Hook errors should be fail-closed for built-in extensions during Slice 1, because a broken built-in extension means the bundled product is inconsistent. Project-local extension errors should eventually be recorded and isolated, but project-local extensions are not enabled in the first implementation slice.

### Extension Discovery

Slice 1 should support only built-in Python extensions registered by code. Project-local extension discovery is deliberately deferred.

The first project-local design should prefer a manifest plus Python entry point:

- `.embedagent/extensions/<name>/extension.json`
- `.embedagent/extensions/<name>/extension.py`

The manifest describes name, version, entry point, and enabled resources. The Python module provides a `register(extension_api)` function. No dependency installation is performed at runtime; all dependencies must already be in the offline bundle or project directory.

### Workflow Extension Contract

A workflow extension is a specialized extension that can provide:

- prompt units
- active tool names
- workflow state projection
- task/status tool behavior
- mode or profile metadata if it wants them
- slash commands or command handlers

Core sees workflow output as generic data:

```json
{
  "workflow": {
    "id": "c_harness",
    "label": "C Harness",
    "state": "active",
    "summary": "...",
    "items": [],
    "activity": "...",
    "metadata": {}
  }
}
```

The existing frontend fields can remain as compatibility projections during migration, but the new source should be `workflow`.

`workflow.state` values for the first implementation are:

- `idle`
- `active`
- `waiting`
- `completed`
- `failed`

The C harness extension owns any finer-grained phase names inside `workflow.metadata`.

### Built-In C Harness Extension

Move the existing harness behavior into a default built-in extension:

- `explore`, `spec`, `build`, `debug`, `verify`
- `lite_spec_tdd` and `full_spec_tdd`
- execution phase tracks
- `TaskGraph`
- `task_status`
- `list_recipes`, `run_recipe`, `report_quality_v2`
- C/C++ tool pack defaults
- current GUI task panel projection

The extension can initially reuse the existing `src/embedagent/harness/` implementation internally. The boundary is more important than moving files.

### Tool Registry

Replace mode-owned schema selection with extension-aware tool activation.

Core should maintain:

- all registered tools
- active tool names for the current turn
- tool metadata for frontend rendering and permissions

Built-in core tools should be minimal:

- `read_file`
- `write_file`
- `edit_file`
- `list_dir`
- `grep_text`
- `glob_files`
- `run_command` as controlled fallback

`run_command` already exists as a generic shell tool in the current runtime. It is not the same as `run_recipe`.

The C harness extension registers or activates C workflow tools:

- `list_recipes`
- `run_recipe`
- `report_quality_v2`
- `task_status`
- `record_failing_evidence`

`ask_user` remains Core interaction infrastructure in Slice 1. Workflow extensions may choose when it is active and may add prompt guidance for it, but Core owns interaction suspension and resumption.

### Session State

Core session state should not import harness classes.

Replace:

- `Session.task_graph: TaskGraph`

With:

- `Session.workflow_state: Dict[str, Any]`

For compatibility, the C harness extension can serialize its task graph into that dict and rehydrate it internally.

Slice 1 should introduce `Session.workflow_state` while leaving `Session.task_graph` as a compatibility mirror. Slice 2 removes direct core reads from `task_graph`. Physical deletion of `task_graph` should happen only after compatibility tests prove all projections read `workflow_state`.

### Frontend Projection

Move frontend workflow display toward:

- `snapshot.workflow`

Keep legacy fields temporarily:

- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`

Those fields should become compatibility projections from `workflow` while the GUI/TUI migrate.

## Migration Plan

### Slice 1: Boundary Without Behavior Change

- Add extension contract types.
- Add an in-process extension manager.
- Wrap current harness as a built-in extension object.
- Add `Session.workflow_state` as the generic workflow state carrier while preserving `task_graph` as a compatibility mirror.
- Route prompt units, active tool names, workflow snapshot, and initial user-request task creation through the extension manager.
- Move `QueryEngine` harness injection and `TaskGraph.from_user_request` creation behind extension hooks.
- Route `InProcessAdapter` harness context lookup through the extension manager instead of direct `HarnessRunner` access where possible.
- Add compatibility projection from extension workflow output to existing frontend fields.
- Keep existing frontend fields populated.
- Update `AGENTS.md`, `README.md`, and architecture docs in the same slice to state that harness is becoming a default workflow extension, not irreducible Agent Core.
- Keep tests passing with current behavior.

Slice 1 acceptance tests:

- A fake built-in workflow extension can add prompt units and active tools.
- The C harness extension preserves current prompt and task snapshot behavior.
- `QueryEngine` no longer imports `TaskGraph` directly.
- `InProcessAdapter` no longer constructs `HarnessRunner` directly except through a documented compatibility adapter.
- Legacy snapshot fields still match the current GUI expectations.

### Slice 2: Session Decoupling

- Replace direct `Session.task_graph` ownership with generic workflow state.
- Let the C harness extension serialize and deserialize its task graph.
- Update `task_status` to read workflow state through the extension boundary.
- Keep compatibility projection for current GUI fields.
- Convert `SessionSnapshotProjector` from direct `task_graph` reads to `workflow_state` reads.
- Convert `HarnessStateSynchronizer` into a C harness extension internal helper or remove it.

### Slice 3: Tool Activation Decoupling

- Remove `OfficialRuntimeModes` from `ToolRuntime`.
- Make tool schemas derive from core registry plus active tool set.
- Let workflow extensions choose active tools per turn.
- Keep mode configuration as a C harness extension concern.
- Move `task_status`, `run_recipe`, `list_recipes`, `report_quality_v2`, and `record_failing_evidence` out of `CORE_PACK`.
- Keep `ask_user` in Core but make its active-tool exposure workflow-controlled.

### Slice 4: Adapter And Command Slimming

- Move workflow slash commands into extension registration where possible.
- Keep core commands only for session/runtime shell operations.
- Reduce `InProcessAdapter` ownership of plan/review/workflow details.
- Add a core-without-C-harness test at this point if it cannot pass earlier.

### Slice 5: Documentation Cutover

- Finish source-of-truth docs so they say Agent Core is workflow-neutral.
- Document the built-in C harness as the default workflow extension.
- Archive superseded harness-as-core architecture documents.

## Risks

- The current docs explicitly say harness is the official execution model; changing this must be documented as a deliberate architecture reversal.
- GUI/TUI currently depend on harness-shaped fields; migration must preserve compatibility until UI consumes `workflow`.
- If extension hooks are too broad too early, the system may become harder to debug. Start with narrow events.
- If the C harness extension remains privileged through hidden imports, the boundary will be cosmetic. Tests should prove core can run with a minimal workflow or no workflow.
- Slice 1 and Slice 2 are tightly coupled because `Session.task_graph` is currently both storage and API. Introducing `workflow_state` in Slice 1 reduces the risk of a later big-bang state migration.

## Verification Strategy

- Existing harness tests remain green while wrapped as an extension.
- Add tests that instantiate Agent Core without the C harness extension once `InProcessAdapter` and `ToolRuntime` no longer directly require it.
- Add tests that register a tiny fake workflow extension and confirm prompt/tool/snapshot output.
- Add snapshot compatibility tests for legacy GUI fields.
- Add tests proving `QueryEngine` no longer imports or instantiates `TaskGraph`.
- Add tests proving `task_status` is provided by the workflow extension boundary.
- Run fast suite:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

## Open Decisions

- Whether user-visible `mode` remains a core concept long-term or becomes a workflow-extension concept. For Slice 1, keep it in Core as a compatibility field.
- Whether the default distribution enables C harness by default for all projects or only for detected C/C++ workspaces.
- Whether project-local extensions should be enabled before or after the C harness extraction is complete. Recommendation: after extraction.

## Recommendation

Proceed with the workflow extension boundary. Keep the C harness as the default, but stop treating it as Agent Core. This preserves EmbedAgent's offline C/C++ strength while reducing core coupling and creating a path for users to build their own surrounding workflow.
