# Pre-Release Debt Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace transitional Agent Core and GUI compatibility layers with the promoted Pi/T3-shaped architecture while preserving Windows 7, offline deployment, Python 3.8, and the default C/C++ workflow.

**Architecture:** This completed plan followed `docs/pre-release-architecture-debt-audit.md` as the cleanup baseline. Each slice promoted one target path, migrated tests and fixtures to that path, and deleted the old path before completion. The work intentionally did not preserve pre-release internal session, timeline, GUI reducer, or extension-hook state compatibility.

**Tech Stack:** Python 3.8, pytest, React/Vite webapp, Windows 7-compatible GUI backend, bundled MinGit/ripgrep/ctags/LLVM runtime contract.

---

## File Structure

Primary planning and source-of-truth files:

- `docs/pre-release-architecture-debt-audit.md`: debt baseline and completion bar.
- `docs/implementation-roadmap.md`: sequencing and current roadmap summary.
- `docs/development-tracker.md`: current phase, risks, and slice status.
- `docs/design-change-log.md`: durable design-change entries.
- `docs/frontend-protocol.md`: frontend/core contract updates as GUI state moves toward T3 shape.
- `docs/overall-solution-architecture.md`: source-of-truth architecture updates after each slice.

Agent Core target areas:

- `src/embedagent/session_timeline.py`: transport-only timeline behavior to retire or make ephemeral.
- `src/embedagent/services/event_emitter.py`: live event bridge currently writes timeline events.
- `src/embedagent/inprocess_adapter.py`: hosted adapter currently owns too many runtime, GUI projection, timeline, review, and resource concerns.
- `src/embedagent/query_engine.py`: session facade currently retains too much action, prompt, and mutation behavior.
- `src/embedagent/agent_loop.py`: loop orchestration currently carries too many product responsibilities.
- `src/embedagent/agent_tool_action_service.py`: target owner for unified action execution.
- `src/embedagent/agent_extension_host.py` and `src/embedagent/extensions.py`: target owner for explicit extension capability/event contracts.
- `src/embedagent/restoration.py` and `src/embedagent/session.py`: current imperative restore and mutable session projection.

GUI target areas:

- `src/embedagent/frontend/gui/webapp/src/App.jsx`: current large app orchestrator to shrink.
- `src/embedagent/frontend/gui/webapp/src/store.js`: current global reducer to retire in favor of T3-shaped stores.
- `src/embedagent/frontend/gui/webapp/src/session-runtime/`: current runtime projection and T3 timeline translation.
- `src/embedagent/frontend/gui/webapp/src/workbench/`: current workbench surface model.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/`: app-shell helpers and loader effects.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`: dev-only fixture boundary to isolate from product reducer.
- `src/embedagent/frontend/gui/static/assets/`: generated assets to keep out of ordinary source-review signal where possible.

Reference targets:

- `reference/pi/packages/agent/src/agent-loop.ts`: small functional agent loop reference.
- `reference/pi/packages/agent/src/harness/agent-harness.ts`: hosted harness/reference boundary.
- `reference/pi/packages/agent/src/harness/session/session.ts`: durable entry/reducer-style session reference.
- `reference/t3code/apps/web/src/rightPanelStore.ts`: thread-scoped right-panel state shape.
- `reference/t3code/apps/web/src/session-logic.ts`: typed T3 session/timeline work-log model.
- `reference/t3code/packages/client-runtime/src/state/`: small renderer state modules.

---

## Slice 1: Timeline Truth Removal

**Goal:** Make transcript-backed projections the only source for history, review, bootstrap, and replay truth.

**Files:**

- Delete: `src/embedagent/session_timeline.py`
- Modify: `src/embedagent/services/event_emitter.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify tests under `tests/` that reference session timeline replay, review, or bootstrap behavior
- Modify webapp tests under `src/embedagent/frontend/gui/webapp/test/`
- Update: `AGENTS.md`
- Update: `docs/frontend-protocol.md`
- Update: `docs/overall-solution-architecture.md`
- Update: `docs/development-tracker.md`
- Update: `docs/design-change-log.md`

- [x] **Step 1: Inventory timeline readers and writers**

Run:

```bash
rg -n "SessionTimelineStore|timeline_store|get_session_timeline|load_session_events_after|timeline\\.jsonl|/events|bootstrapTimeline|eventLog|build_structured_timeline|latest_assistant_reply" src tests docs
```

Expected: a complete list of code, tests, and docs that still treat timeline as persistent or queryable product state.

- [x] **Step 2: Write focused failing tests for review/bootstrap without timeline**

Add or adjust tests so `/review`, session bootstrap, and GUI history can be built from transcript/session projections after timeline storage is disabled.

Run the narrow tests that cover these routes and projections. Expected before implementation: at least one failure showing timeline dependency.

- [x] **Step 3: Move review payload construction to transcript/session projections**

Change review payload code so it consumes transcript-backed session/history/projection data, not timeline events or trimmed replay windows.

- [x] **Step 4: Make live event replay transcript-derived or ephemeral**

Remove durable product meaning from timeline writes. If a WebSocket replay cache remains, it must be derived from transcript/session state or documented as process-local transport cache only.

- [x] **Step 5: Simplify GUI runtime projection**

Remove frontend merging of independent `snapshot`, `eventLog`, and `bootstrapTimeline` truth sources. GUI runtime should consume the promoted bootstrap/session payload and project T3 rows from that single contract.

- [x] **Step 6: Delete or quarantine unused timeline persistence**

Delete `SessionTimelineStore` if no longer needed. If retained temporarily for live transport, rename/document it so it cannot be mistaken for history.

- [x] **Step 7: Verification**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
node --test src/embedagent/frontend/gui/webapp/test/run-tests.mjs
uv run --locked python scripts/lint.py
```

Expected: fast non-GUI tests and lint pass.

- [x] **Step 8: Docs and commit**

Update source-of-truth docs to state the promoted path and delete references to timeline as queryable history. Commit with a message such as:

```bash
git add src tests docs
git commit -m "refactor: remove timeline as session truth"
```

---

## Slice 2: Unified Interactive Action Pipeline

**Goal:** Move `ask_user`, approvals, pending interactions, and mode-switch proposals into the same action lifecycle as other non-LLM tool actions.

**Files:**

- Modify: `src/embedagent/agent_tool_action_service.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/agent_kernel.py`
- Modify: `src/embedagent/agent_lifecycle.py`
- Modify: `src/embedagent/permissions.py` only if permission category wiring needs clarification
- Modify tests covering pending interaction, permission resume, `ask_user`, and mode switch behavior
- Update: `docs/tool-contracts.md`
- Update: `docs/permission-model.md`
- Update: `docs/overall-solution-architecture.md`
- Update: `docs/development-tracker.md`
- Update: `docs/design-change-log.md`

- [x] **Step 1: Inventory special cases**

Run:

```bash
rg -n "ask_user|propose_mode_switch|pending_interaction|pending_input|mode switch|requires query-engine handling|_execute_action" src tests docs
```

Expected: all special paths in QueryEngine, AgentToolActionService, kernel, lifecycle, tests, and docs are visible.

- [x] **Step 2: Add failing tests for unified ownership**

Write tests proving that interactive actions pass through the action service and lifecycle path instead of QueryEngine-only branches.

Expected before implementation: failures identify the current split path.

- [x] **Step 3: Introduce an interaction action result shape**

Add an internal result type or structured observation path that can represent pending user input, pending approval, and mode switch proposals without bypassing the normal action service.

- [x] **Step 4: Move `ask_user` handling into AgentToolActionService**

The action service should create the pending interaction result through kernel/lifecycle helpers, record the same lifecycle events, and return the same public observation shape currently expected by callers.

- [x] **Step 5: Move mode-switch proposal handling into the same pipeline**

Mode-switch proposal behavior should be modeled as a first-class interaction action, not a QueryEngine branch with custom prompt insertion semantics.

- [x] **Step 6: Delete QueryEngine special cases**

Remove direct branches for interactive tools from QueryEngine after the tests prove the common path works.

- [x] **Step 7: Verification**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

Expected: fast non-GUI tests and lint pass.

- [x] **Step 8: Docs and commit**

Update tool/permission/core docs to describe the unified interaction lifecycle. Commit with a message such as:

```bash
git add src tests docs
git commit -m "refactor: unify interactive action execution"
```

---

## Slice 3: Agent Core Ownership Shrink

**Goal:** Reduce QueryEngine, AgentLoop, and InProcessAdapter into smaller boundaries that mirror Pi's small core plus hosted adapters.

**Files:**

- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/agent_loop.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify or create focused modules under `src/embedagent/` only when extracting a real ownership boundary
- Modify tests for QueryEngine, adapter, loop continuation, session restore, and tool execution
- Update: `docs/overall-solution-architecture.md`
- Update: `docs/implementation-roadmap.md`
- Update: `docs/development-tracker.md`
- Update: `docs/design-change-log.md`

- [x] **Step 1: Measure current ownership**

Run:

```bash
Get-ChildItem src/embedagent/query_engine.py,src/embedagent/agent_loop.py,src/embedagent/inprocess_adapter.py | Select-Object Name,Length
rg -n "self\\._agent_loop|_build_context|_schemas_for_active_tools|_execute_parallel_tool_action|_apply_extension_tool_result_patch|timeline_store|_build_review_payload|refresh_managed_session" src/embedagent/query_engine.py src/embedagent/agent_loop.py src/embedagent/inprocess_adapter.py
```

Expected: current ownership hot spots are visible before edits.

- Initial measurement:
  - `query_engine.py`: 95726 bytes
  - `agent_loop.py`: 34800 bytes
  - `inprocess_adapter.py`: 130521 bytes
  - Hot spots included QueryEngine action/schema forwarding, workflow-patch
    callback wrappers, and adapter-owned `/review` synthesis.
- Final measurement:
  - `query_engine.py`: 88583 bytes
  - `agent_loop.py`: 34685 bytes
  - `inprocess_adapter.py`: 116724 bytes
  - New focused owner: `review_command.py`: 13863 bytes

- [x] **Step 2: Define the promoted ownership map**

Update the plan for this slice with the exact responsibilities that will remain in each owner:

- QueryEngine: session facade and public turn entrypoint only.
- AgentLoop: provider/tool turn-loop state machine only.
- AgentToolActionService: all non-LLM action execution, interactive/resume execution, and workflow-patch capture.
- AgentExtensionHost: extension activation, schemas, hooks, and extension-owned tool handling.
- AgentLifecycleJournal: lifecycle operation writes plus workflow-patch persistence helpers.
- InProcessAdapter: hosted runtime/session manager bridge and command result emission only.
- ReviewCommandService: hosted `/review` finding synthesis, git-diff evidence, and markdown rendering.

- [x] **Step 3: Extract one boundary at a time**

Move one responsibility per commit. Do not create a generic service if the responsibility can be deleted after Slice 1 or Slice 2.

- Extracted:
  - workflow patch snapshot/payload/persistence helpers from QueryEngine into
    `AgentLifecycleJournal`
  - action execution and parallel tool execution forwarding from QueryEngine
    into direct `AgentLoop -> AgentToolActionService` calls
  - active schema projection forwarding from QueryEngine into direct
    `AgentLoop -> AgentExtensionHost` calls
  - hosted `/review` synthesis from `InProcessAdapter` into
    `ReviewCommandService`

- [x] **Step 4: Delete old callback paths**

After each extraction, delete the old callback or compatibility wrapper instead of leaving it as a parallel path.

- Deleted QueryEngine wrappers:
  - `_allowed_tools_for_mode`
  - `_schemas_for_active_tools`
  - `_execute_action`
  - `_execute_parallel_tool_action`
  - `_prepare_extension_tool_call`
  - `_apply_extension_tool_result_patch`
  - `_is_extension_blocked_observation`
- Deleted InProcessAdapter review synthesis methods:
  - `_build_review_payload`
  - `_append_review_section`
  - `_review_finding_from_tool`
  - `_review_kind`
  - `_review_primary_detail`
  - `_review_markdown_lines`

- [x] **Step 5: Verification**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

Expected: fast non-GUI tests and lint pass after each bounded extraction.

- Verification recorded:
  - `uv run pytest tests/test_query_engine_refactor.py tests/test_agent_lifecycle.py tests/test_dynamic_tool_registration.py tests/test_review_command.py tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py tests/test_workflow_extensions.py -v`: 159 passed
  - `uv run pytest tests/ -m "not slow and not gui" -v`: 969 passed, 11 deselected
  - `uv run --locked python scripts/lint.py`: ruff and black check passed

- [x] **Step 6: Docs and commit**

Update architecture docs after the final extraction in this slice. Commit with a message such as:

```bash
git add src tests docs
git commit -m "refactor: shrink agent core ownership boundaries"
```

---

## Slice 4: Explicit Extension Capability Contracts

**Goal:** Replace method-name compatibility hooks with explicit typed capability/event registrations.

**Files:**

- Modify: `src/embedagent/extensions.py`
- Modify: `src/embedagent/agent_extension_host.py`
- Modify: `src/embedagent/default_extensions.py`
- Modify: `src/embedagent/harness/extension.py`
- Modify project-local extension loader tests and harness extension tests
- Update: `docs/tool-contracts.md`
- Update: `docs/overall-solution-architecture.md`
- Update: `docs/agent-harness-v2.md`
- Update: `docs/development-tracker.md`
- Update: `docs/design-change-log.md`

- [x] **Step 1: Inventory extension method hooks**

Run:

```bash
rg -n "hasattr\\(|getattr\\(|register_context_reducers|allowed_tool_names|handle_tool_call|package_manifest|before_tool_call|after_tool_result|discover_resources|describe_prompt|initialize_workflow_state" src/embedagent/extensions.py src/embedagent/agent_extension_host.py src/embedagent/harness src tests docs
```

Expected: all implicit method-name hooks are visible.

- Inventory result:
  - method-name discovery was concentrated in `ExtensionManager`.
  - remaining `getattr(extension, ...)` uses are `extension_id`,
    `builtin_extension`, and the explicit `extension_capabilities()` provider.
  - archived docs still mention historical method-name hooks, but active docs
    now state the explicit capability contract.

- [x] **Step 2: Add tests for explicit registration**

Write tests for a minimal extension that registers capabilities/events explicitly and does not rely on method-name discovery.

- Added tests:
  - `test_extension_manager_registers_explicit_capability_records_only`
  - `test_extension_manager_records_invalid_capability_records`

- [x] **Step 3: Introduce typed registration records**

Add explicit internal records for hook reducers, observers, dynamic tools, resource providers, workflow package manifests, and workflow-owned tool handlers.

- Implemented:
  - `ExtensionCapability`
  - explicit hook-to-event mapping
  - explicit package manifest and context reducer capability stores
  - diagnostics for malformed capability records

- [x] **Step 4: Migrate bundled C/C++ workflow extension**

Move the bundled harness extension onto explicit registration records.

- `CHarnessWorkflowExtension.extension_capabilities()` now declares workflow
  injection, prompt description, workflow initialization, package manifest,
  active tools, tool registration, context reducers, task loading, and
  extension-owned tool handling.

- [x] **Step 5: Remove method-name compatibility**

Delete fallback discovery paths once bundled and project-local extension tests use the explicit registration path.

- Removed:
  - automatic registration based on `context`, `resources_discover`,
    `register_tools`, `tool_call`, `tool_result`, `before_agent_start`,
    `should_inject_workflow`, `describe_prompt`,
    `initialize_workflow_state`, `allowed_tool_names`,
    `load_session_tasks`, `handle_tool_call`, `package_manifest`, and
    `register_context_reducers` method names.

- [x] **Step 6: Verification**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

Expected: fast non-GUI tests and lint pass.

- Verification recorded:
  - Red: `uv run pytest tests/test_capability_extensions.py::test_extension_manager_records_invalid_capability_records -v` failed before diagnostics were added.
  - Green: `uv run pytest tests/test_capability_extensions.py::test_extension_manager_records_invalid_capability_records tests/test_capability_extensions.py::test_extension_manager_registers_explicit_capability_records_only -v` passed.
  - Focused extension suite: `uv run pytest tests/test_capability_extensions.py tests/test_dynamic_tool_registration.py tests/test_project_extensions.py tests/test_workflow_extensions.py -v` passed, 97 tests.
  - Wider extension/resource/self-extension suite: `uv run pytest tests/test_capability_extensions.py tests/test_dynamic_tool_registration.py tests/test_project_extensions.py tests/test_workflow_extensions.py tests/test_local_resources.py tests/test_query_engine_refactor.py tests/test_context_config.py tests/test_workflow_package_manifest.py tests/test_self_extension_authoring.py -v` passed, 230 tests.

- [x] **Step 7: Docs and commit**

Update extension and harness docs. Commit with a message such as:

```bash
git add src tests docs
git commit -m "refactor: make extension capabilities explicit"
```

---

## Slice 5: T3-Native GUI Runtime State

**Goal:** Replace the current global App/reducer plus T3 translation layer with T3-shaped renderer/runtime modules.

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
- Modify or create focused stores under `src/embedagent/frontend/gui/webapp/src/`
- Modify webapp tests and visual debug scripts
- Update: `docs/frontend-protocol.md`
- Update: `docs/modules/frontend-gui.md`
- Update: `docs/development-tracker.md`
- Update: `docs/design-change-log.md`

- [x] **Step 1: Map T3 state modules to EmbedAgent state**

Compare reference T3 modules with current GUI state:

```bash
Get-ChildItem reference/t3code/packages/client-runtime/src/state | Select-Object -ExpandProperty Name
Get-Content reference/t3code/apps/web/src/rightPanelStore.ts -TotalCount 260
Get-Content reference/t3code/apps/web/src/session-logic.ts -TotalCount 260
rg -n "case '|visual_.*fixture|rightPanel|bottomDrawer|session_activated|bootstrapTimeline|eventLog" src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/workbench src/embedagent/frontend/gui/webapp/src/session-runtime
```

Expected: a concrete mapping from current global state to T3-shaped stores.

- Mapping result:
  - T3 `rightPanelStore.ts` maps to the existing
    `webapp/src/workbench/surfaces.js` / `workbench/ui-state.js`
    thread-scoped surface store; deeper right-panel replacement remains a later
    GUI parity cut.
  - T3 session/thread state maps to new
    `webapp/src/session-runtime/thread-state.js`.
  - T3 composer-local state maps to new
    `webapp/src/composer/composer-state.js`.
  - Existing terminal state already lives under `webapp/src/terminal/`, with
    terminal action orchestration in `app-runtime/terminal-controller.js`.

- [x] **Step 2: Start with right-panel state**

Replace the current right-panel reducer shape with a thread-scoped store modeled after T3's right-panel store. Keep only surfaces required for T3 parity and explicitly classify EmbedAgent-only surfaces as deferred or dev-only.

- Status: existing T3-style right-panel persistence from the prior GUI workbench
  slice remains the promoted path; this slice did not add a parallel
  right-panel shape.

- [x] **Step 3: Move terminal/composer/thread UI state out of global reducer**

Create focused renderer stores for terminal UI state, composer local state, and thread selection where T3 has separate state modules.

- Implemented:
  - `composer/composer-state.js` owns draft creation, reads, and reducer
    updates.
  - `session-runtime/thread-state.js` owns session summaries, active thread id,
    and history-integrity display state.
  - `App.jsx`, command palette, terminal controller, workspace reset, and tests
    consume focused read models instead of root-level `sessions`,
    `currentSessionId`, `composer`, or `historyIntegrity`.

- [x] **Step 4: Replace timeline translation with a T3-facing contract**

After Slice 1, consume the promoted session/bootstrap payload directly and remove independent timeline/event-log merge logic.

- Status: Slice 1 already removed timeline-backed history replay. This slice
  preserved the current live display projection while moving history-integrity
  display ownership into `thread-state.js`; full timeline contract slimming is
  still follow-on work.

- [x] **Step 5: Shrink App.jsx**

Move API orchestration and state ownership into focused runtime modules. App should compose providers/surfaces, not own every operation.

- Implemented for this slice: App now consumes thread/composer read models and
  no longer reads root-level thread/composer fields. Broader API orchestration
  extraction remains follow-on work.

- [x] **Step 6: Verification**

Run:

```bash
uv run --locked python scripts/lint.py
```

Run the project's webapp test/build commands documented in `src/embedagent/frontend/gui/webapp/package.json`.

Expected: lint passes, webapp tests/build pass, and relevant visual debug scenarios still render.

- Verification recorded:
  - Red: `npm test` initially failed because
    `src/composer/composer-state.js` did not exist.
  - `npm test`: passed.
  - `npm run build`: passed after `npm ci` restored locked webapp
    dependencies in the worktree.
  - `uv run --locked python scripts/lint.py`: passed.

- [x] **Step 7: Docs and commit**

Update frontend docs to describe the T3-native state shape. Commit with a message such as:

```bash
git add src tests docs
git commit -m "refactor: align gui runtime state with t3"
```

---

## Slice 6: Dev Fixtures And Generated Asset Isolation

**Goal:** Keep visual/debug fixtures and generated frontend assets from polluting production state review.

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
- Modify: `scripts/gui-visual-debug.mjs`
- Modify generated-asset build/package scripts if needed
- Modify docs and tests for visual debug behavior

- [x] **Step 1: Inventory fixture actions and generated asset references**

Run:

```bash
rg -n "visual_.*fixture|visual_debug|static/assets/app\\.js|static/assets/app\\.css|generated static|GUI static asset" src scripts tests docs
```

Expected: all dev fixture and generated asset paths are visible.

- Inventory result:
  - Product `store.js` and `thread-state.js` still had `visual_*fixture` cases.
  - `visual-debug-fixtures.js` was the correct dev-only entry point but
    dispatched visual fixture actions directly into the product reducer.
  - Generated static assets under `src/embedagent/frontend/gui/static/` remain
    the current offline packaging release artifacts.

- [x] **Step 2: Move fixture injection behind a dev-only boundary**

Visual fixtures should enter through a harness-only loader that cannot be dispatched as ordinary product reducer actions.

- Implemented:
  - `visual-debug-fixtures.js` now uses private `dev_fixture_*` descriptors.
  - `dispatchVisualDebugAction(...)` expands those descriptors into ordinary
    product actions before they reach the reducer.

- [x] **Step 3: Remove fixture cases from product reducer**

Delete visual-only reducer actions after the dev harness has its own injection path.

- Deleted:
  - `visual_source_control_fixture_loaded`
  - `visual_composer_file_tree_fixture_loaded`
  - `visual_file_preview_reveal_fixture_loaded`
  - `visual_timeline_fixture_loaded`
  - `visual_interaction_fixture_loaded`
  - `visual_thread_lifecycle_fixture_loaded`
  - visual fixture handling in `thread-state.js`

- [x] **Step 4: Clarify generated asset policy**

Decide whether generated GUI assets remain committed as release artifacts or are generated during packaging only. Document the chosen policy and make normal review paths favor source files.

- Policy: generated GUI static assets remain committed release artifacts for
  the current offline packaging model. Review should focus on `webapp/src/`,
  and webapp source changes should refresh `frontend/gui/static/` through
  `npm run build`.

- [x] **Step 5: Verification**

Run:

```bash
uv run --locked python scripts/lint.py
```

Run relevant visual debug scenarios from the documented GUI visual harness.

Expected: lint passes and visual debug still works through the dev-only path.

- Verification recorded:
  - Red: `npm test` failed while `visual-debug-fixtures.js` still exposed
    `visual_timeline_fixture_loaded`.
  - `npm test`: passed after dev-only expansion.
  - Additional verification before commit: `npm run build` and
    `uv run --locked python scripts/lint.py`.

- [x] **Step 6: Docs and commit**

Commit with a message such as:

```bash
git add src scripts tests docs
git commit -m "refactor: isolate gui dev fixtures"
```

---

## Slice 7: Real Win7 And C/C++ Release Gates

**Goal:** Convert offline/Win7 claims into repeatable release gates.

**Files:**

- Modify: `scripts/offline-runtime-contract.json`
- Modify: `scripts/validate-offline-bundle.ps1`
- Modify: `scripts/check-bundle-dependencies.py`
- Modify: `scripts/validate-gui-smoke.py`
- Modify: `docs/guides/win7-preflight-checklist.md`
- Modify: `docs/guides/win7-gui-validation.md`
- Update: `docs/development-tracker.md`
- Update: `docs/design-change-log.md`

- [x] **Step 1: Inventory release validation**

Run:

```bash
rg -n "allow_system_tool_fallback|offline-runtime-contract|validate-offline-bundle|check-bundle-dependencies|validate-gui-smoke|WebView2|Win7|Windows 7|fallback" src scripts tests docs
```

Expected: all dev fallback and release validation assumptions are visible.

- Inventory result:
  - `package-lib.ps1` release verification was still forcing
    `-SkipDynamicChecks`, even though release profile configured
    `run_dynamic_checks: true`.
  - `offline-runtime-contract.json` covered runtime tools but not release-gate
    metadata.
  - C smoke existed only as workspace-template/manual clang guidance.

- [x] **Step 2: Quarantine development fallback**

Ensure release bundle validation fails when a runtime-invoked tool is missing from the bundle. Development fallback may remain only if explicitly configured and never treated as release proof.

- Implemented:
  - `release_gates` now declare `allow_system_tool_fallback: false`.
  - `package-lib.ps1` honors `run_dynamic_checks`; release profile no longer
    forces `-SkipDynamicChecks`.
  - `validate-cpp-smoke.py` defaults to bundle-local Clang and fails when
    bundled clang is missing unless an explicit development override is passed.

- [x] **Step 3: Add real C/C++ smoke workspace**

Use or create a tiny C/C++ workspace that exercises default inspect/build/verify behavior through bundled tools.

- Implemented:
  - Existing `data/workspace-template/main.c` is now a bundle-local release
    gate, validated by staged `tools/validation/validate-cpp-smoke.py` and
    `validate-cpp-smoke.cmd`.
  - `validate-offline-bundle.ps1` can execute the C smoke gate during dynamic
    release validation.

- [x] **Step 4: Add Win7 GUI smoke procedure**

Document and automate as much as possible for WebView2 109 fixed runtime startup, GUI activation, and default C/C++ workflow execution.

- Implemented:
  - `validate-gui-smoke.cmd` now passes `--require-fixed-webview2` by default.
  - `validate-gui-smoke.py` reports `fixed_webview2` metadata and rejects
    bundle GUI smoke that does not use bundled `edgechromium`.
  - Win7 target-machine windowed smoke remains the external release evidence.

- [x] **Step 5: Verification**

Run repo-side validators locally, then record the manual/VM Win7 evidence in the tracker when available.

- Verification recorded:
  - RED: newly added release-gate, C smoke, GUI fixed-runtime, and
    run-dynamic-checks tests failed against the old implementation.
  - GREEN: `uv run pytest tests/test_cpp_smoke_validator.py
    tests/test_gui_smoke_contract.py tests/test_packaging_control_plane.py -q`
    passed, 44 tests.

- [x] **Step 6: Docs and commit**

Commit with a message such as:

```bash
git add scripts tests docs
git commit -m "test: add real win7 and c workflow release gates"
```

---

## Execution Order

Run the slices in this order:

1. Slice 1: Timeline Truth Removal
2. Slice 2: Unified Interactive Action Pipeline
3. Slice 3: Agent Core Ownership Shrink
4. Slice 4: Explicit Extension Capability Contracts
5. Slice 5: T3-Native GUI Runtime State
6. Slice 6: Dev Fixtures And Generated Asset Isolation
7. Slice 7: Real Win7 And C/C++ Release Gates

Slices 1 and 2 reduce the most dangerous split-brain behavior. Slice 3 becomes
easier once those two branches are gone. Slice 5 should not start before Slice
1 defines the promoted GUI runtime input contract.

## Completion Checklist

- [x] No feature work deepens transitional timeline/session/GUI reducer state.
- [x] Every completed slice deletes the old path or records the slice as
  incomplete.
- [x] Source-of-truth docs are updated in the same change as code.
- [x] Fast non-GUI tests pass after Agent Core slices.
- [x] Webapp tests/build and visual debug pass after GUI slices.
- [x] Release gates are recorded before release claims: repo-side C smoke is
  contract-backed, and clean Win7/WebView2 plus broader real C/C++ validation
  remain explicit release-cut evidence items rather than claimed proof here.

