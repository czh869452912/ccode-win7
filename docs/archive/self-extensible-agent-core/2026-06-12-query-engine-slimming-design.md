# QueryEngine Slimming Slice 5 Design

## 1. Background

Slice 5 continues the self-extensible Agent Core work after the extension boundary, local resource reload, dynamic in-process tool registration, and manifest-gated project-local Python extension slices.

The current architecture already keeps the default C/C++ harness behind `ExtensionManager`, and hosted product paths assemble bundled extensions through `src/embedagent/default_extensions.py`. However, `src/embedagent/query_engine.py` still owns too many responsibilities at once:

- turn loop orchestration
- workflow prompt injection
- workflow state initialization
- context hook dispatch
- active extension tool resolution
- extension dynamic tool registration
- tool-call and tool-result hook dispatch
- permission-gated tool execution
- transcript and interaction mutation

The design goal is not to change user-visible behavior. The goal is to make the engine smaller and more extensible by introducing explicit agent-core subcomponents while preserving transcript, permission, mode, and workflow semantics.

## 2. Goals

Slice 5 must achieve the following outcomes:

1. Extract a smaller agent loop from `QueryEngine`.
2. Move extension hook dispatch out of ad hoc `QueryEngine` call sites and into a dedicated host/boundary object.
3. Keep transcript behavior unchanged.
4. Keep `PermissionPolicy` behavior unchanged.
5. Keep hosted default C/C++ behavior unchanged.
6. Add tests proving core execution works without installing the default C harness extension.
7. Update source-of-truth docs to describe the slimmer execution spine.

## 3. Non-Goals

Slice 5 does not introduce:

- remote extension registries
- dependency installation
- Python 3.9+ syntax
- Docker, WSL, VS Code, Node.js, or online runtime dependencies
- multi-agent orchestration
- frontend vocabulary changes
- a new permission engine
- a new session-history ledger

## 4. Current Findings

`QueryEngine` is currently the only session-scoped owner of turn execution and session mutation, which remains correct. The problem is that it also directly performs workflow-extension dispatch in many unrelated methods.

Important direct coupling points include:

- workflow prompt injection through `ExtensionManager.describe_prompt(...)`
- workflow state initialization through `ExtensionManager.initialize_workflow_state(...)`
- context patching through `ExtensionManager.context(...)`
- active tool resolution through `ExtensionManager.allowed_tool_names(...)`
- dynamic tool registration through `ExtensionManager.register_tools(...)`
- pre-tool hooks through `ExtensionManager.before_tool_call(...)`
- post-tool hooks through `ExtensionManager.after_tool_result(...)`
- extension-owned tool execution through `ExtensionManager.handle_tool_call(...)`

There is already a `src/embedagent/strategies/turn_orchestrator.py`, but the current `QueryEngine` path contains richer transcript, interaction, tool batching, and resume behavior. Slice 5 should reuse ideas from that strategy layer without forcing a risky one-step hard cutover.

## 5. Chosen Approach

Use a staged extraction:

1. Create an extension host boundary.
2. Extract tool action execution behind a service object.
3. Extract the turn loop behind a slim agent loop.
4. Update tests and source-of-truth docs.

This sequence keeps behavior observable at each stage. It also lets transcript/session mutation stay under `QueryEngine` until the service interfaces are proven by tests.

Alternative approaches considered:

- Loop-first extraction: moves more code early, but makes behavior drift harder to isolate.
- Direct `TurnOrchestrator` hard cutover: potentially clean, but too risky because existing `QueryEngine` carries more production behavior than the current strategy tests cover.

## 6. Target Architecture

After Slice 5, the execution spine should read as:

```text
InProcessAdapter
  -> QueryEngine
      -> AgentLoop
          -> AgentToolActionService
              -> AgentExtensionHost
              -> ToolRuntime
              -> PermissionPolicy
      -> Session / TranscriptStore
      -> ContextBuilder
```

### 6.1 `QueryEngine`

`QueryEngine` remains session-scoped and remains the public engine facade for:

- session initialization
- user turn submission
- resume/cancel/stop operations
- transcript-backed interaction state
- compatibility properties used by hosted adapters and tests

It should no longer directly scatter extension hook dispatch across the turn loop and tool execution path.

### 6.2 `AgentExtensionHost`

`AgentExtensionHost` is the single `QueryEngine`-side boundary for extension-manager behavior.

Responsibilities:

- build extension contexts and workflow events
- describe workflow prompt fragments
- initialize workflow state
- apply extension context patches
- compute active tool names
- register dynamic in-process tools into `ToolRuntime`
- expose active schemas through `ToolRuntime.schemas_for(...)`
- run before-tool-call hooks
- run after-tool-result hooks
- handle extension-owned tool calls
- expose extension diagnostics when needed by snapshots

Compatibility note: `QueryEngine.extension_manager` may remain as a read-only compatibility attribute or property, but direct `extension_manager.*` calls should move behind `AgentExtensionHost`.

### 6.3 `AgentToolActionService`

`AgentToolActionService` owns the non-LLM action execution pipeline.

Responsibilities:

- verify that a requested tool is active for the current mode/workflow state
- apply extension before-call hooks
- evaluate permission policy through the existing `PermissionPolicy`
- dispatch extension-owned tools through `AgentExtensionHost`
- dispatch runtime tools through `ToolRuntime`
- apply extension after-result patches
- return the same observation/action payload shape that `QueryEngine` currently expects

Transcript event writing and pending interaction storage may remain callback-driven through `QueryEngine` so durable history behavior does not change during this slice.

### 6.4 `AgentLoop`

`AgentLoop` owns the user-turn control flow.

Responsibilities:

- build or request turn context
- request active tool schemas
- invoke the LLM adapter
- execute tool calls through `AgentToolActionService`
- preserve existing retry, continue, and tool-batch behavior
- report events back to `QueryEngine` through narrow callbacks

The loop should be small enough to test independently with fake context/schema/action dependencies.

## 7. Subphase Plan

### Subphase A: Extension Host

Add focused tests first, then create `src/embedagent/agent_extension_host.py`.

Expected end state:

- active tool resolution moves into the host
- extension dynamic tool registration moves into the host
- context and prompt hook dispatch move into the host
- tool-call and tool-result hooks move into the host
- `QueryEngine` keeps behavior but stops directly calling extension-manager hook methods

### Subphase B: Tool Action Service

Add tests for permission preservation, extension pre/post hook ordering, extension-owned tool execution, and interaction-compatible return values.

Expected end state:

- most of `_execute_action` moves out of `QueryEngine`
- permission decisions still come from `src/embedagent/permissions.py`
- transcript and pending-interaction behavior stay compatible
- resumed tool actions continue to use the same action pipeline

### Subphase C: Agent Loop

Add tests for a bare core loop and loop dependency boundaries.

Expected end state:

- `QueryEngine` delegates turn-loop execution to `AgentLoop`
- `QueryEngine` remains the session facade
- the core loop can run with an empty `ExtensionManager`
- default C/C++ harness behavior still works when hosted paths install bundled extensions

### Subphase D: Docs, Guards, and Archive Readiness

Update long-lived docs and add regression guards.

Expected end state:

- source-of-truth docs describe `AgentLoop`, `AgentToolActionService`, and `AgentExtensionHost`
- Slice 5 plan/spec materials are archive-ready after implementation
- tests guard against direct harness imports and ad hoc extension-manager call regressions

## 8. Test Strategy

The implementation must follow TDD:

- write focused failing tests before each extraction
- run the focused test and confirm the expected failure
- implement the smallest passing change
- rerun focused tests
- rerun broader affected tests after each subphase

Required focused coverage:

- `AgentExtensionHost` computes active tools from mode contracts plus extension activation.
- `AgentExtensionHost` registers dynamic tools and returns explicit active schemas.
- `AgentExtensionHost` applies context patches and workflow-state patches.
- `AgentToolActionService` preserves inactive-tool rejection behavior.
- `AgentToolActionService` preserves permission denial / pending interaction behavior.
- `AgentToolActionService` preserves extension-owned `task_status` behavior.
- `AgentLoop` can run without a default C harness extension.
- `QueryEngine` construction and simple runs do not import harness task graph internals.

Required verification before claiming Slice 5 complete:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Focused tests should include the current extension, dynamic tool, workflow, strategy, and query-engine orchestration tests.

## 9. Documentation Impact

Durable conclusions must be synchronized into:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/tool-contracts.md`
- `docs/agent-harness-v2.md`

Documentation should state that:

- `QueryEngine` is still the session-scoped facade.
- extension hook dispatch is owned by `AgentExtensionHost`.
- non-LLM tool action execution is owned by `AgentToolActionService`.
- turn-loop orchestration is owned by `AgentLoop`.
- the default C/C++ harness still enters through `default_extensions.py` and `ExtensionManager`.

## 10. Acceptance Criteria

Slice 5 is complete when:

1. `QueryEngine` is visibly smaller and delegates extension host, tool action, and loop responsibilities.
2. `QueryEngine` no longer directly dispatches extension-manager hooks.
3. `QueryEngine` can still be constructed bare without installing the default C harness extension.
4. Hosted product paths still receive default C/C++ behavior through the shared `ExtensionManager`.
5. Transcript and permission tests remain green.
6. Focused tests prove the core loop can run without default C harness internals.
7. Source-of-truth docs are updated.
8. Full fast verification passes.

## 11. Risk Controls

Primary risks:

- changing transcript event order
- bypassing permission interaction persistence
- exposing default harness tools from the wrong boundary
- breaking resumed interactions
- introducing a second unofficial execution path

Controls:

- keep `QueryEngine` as the session mutation facade
- use callback-style transcript integration during extraction
- avoid direct runtime schema projection without explicit active tool names
- add regression tests before moving behavior
- keep each subphase independently testable and committable

