# T3 GUI Experience And Architecture Guards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the GUI closer to a T3 Code-style workbench experience while adding durable architecture guards that prevent future features from bypassing Agent Core extension, permission, and workflow-package boundaries.

**Architecture:** Split the work into two coordinated tracks. The GUI track improves real interaction behavior, workbench surface ergonomics, visual density, and visual-debug evidence without moving product truth into the renderer. The guard track expands source scans and behavioral tests so new work must use `ExtensionManager` / `AgentExtensionHost`, `PermissionPolicy`, `ToolRuntime` metadata, and workflow-package boundaries instead of hard-coded or patch-style shortcuts.

**Tech Stack:** Python 3.8, pytest, React 18, Vite, plain CSS, Node test runner, Playwright-backed visual debug harness, FastAPI backend routes, project-local architecture guard tests.

---

## Current Baseline

- `main` is clean at `87d1cf0 Merge Pi T3 residual debt cleanup`.
- GUI runtime state is already split across `session-runtime`, `app-runtime`, `composer`, `terminal`, `workbench`, and app-shell modules.
- Existing GUI verification lives in `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` plus `scripts/gui-visual-debug.mjs`.
- Existing architecture guards live mainly in `tests/test_pre_release_architecture_guards.py` and `tests/test_current_architecture_boundaries.py`.
- Generated GUI static assets under `src/embedagent/frontend/gui/static/` must be rebuilt whenever webapp source changes.

## Non-Goals

- Do not add online services, Docker, WSL, VS Code, Electron, ConPTY, or runtime Node requirements.
- Do not turn GUI state into session history, workflow truth, provider policy, permission policy, or extension loading policy.
- Do not preserve pre-release internal compatibility paths when a current-contract replacement is available.
- Do not add public extension APIs beyond the existing explicit `ExtensionCapability` records.

---

## Track A: T3-Style GUI Experience

### Task A1: Define A T3 Workbench Interaction Contract

**Purpose:** Create a small, testable read model for expected workbench density and surface behavior before touching visual components.

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/workbench/workbench-parity-model.js`
- Create: `src/embedagent/frontend/gui/webapp/test/workbench-parity-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] Write `buildWorkbenchParityModel(state, viewport)` with these output fields:
  - `centerColumn.maxWidth`
  - `rightPanel.mode`
  - `rightPanel.surfaceCount`
  - `bottomDrawer.mode`
  - `composer.mode`
  - `timeline.density`
  - `commandPalette.availableSurfaceCommands`
- [ ] Add tests for desktop, narrow desktop, and mobile viewports.
- [ ] Ensure the model reads existing state only; it must not mutate reducer state or call backend APIs.
- [ ] Run `npm test` from `src/embedagent/frontend/gui/webapp`.
- [ ] Commit: `gui: add workbench parity read model`.

**Acceptance:**
- The model can describe whether the current workbench is in T3-like centered, right-panel, bottom-drawer, and compact modes without inspecting DOM.
- `run-tests.mjs` imports and executes the new test module.

### Task A2: Tighten Composer Interaction Details

**Purpose:** Make the composer feel like a command-aware workbench input instead of a plain chat box.

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerCommandMenu.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPrimaryActions.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/composer/composer-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/composer-*.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Rebuild if source changes: `src/embedagent/frontend/gui/static/`

- [ ] Add tests for keyboard traversal through slash commands, file references, and send/stop action state.
- [ ] Keep composer draft text only in `composer/composer-state.js`.
- [ ] Ensure command suggestions use the existing command registry and do not hard-code backend routes in UI components.
- [ ] Add CSS assertions that composer controls do not overflow at 520px width.
- [ ] Run `npm test`.
- [ ] Run `npm run build` and commit generated static assets.
- [ ] Commit: `gui: tighten composer workbench interactions`.

**Acceptance:**
- Composer supports dense keyboard-first interaction.
- No root-level `composer` subfields are reintroduced beyond the existing module mount.

### Task A3: Improve Timeline Operational Density

**Purpose:** Make timeline rows scan like a work log: compact by default, expandable where needed, and clear for tool/result/review/context events.

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/ToolDetail.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/ChangedFilesCard.jsx`
- Modify tests: `src/embedagent/frontend/gui/webapp/test/activity-state.test.mjs`, `t3-timeline.test.mjs`, `timeline-ui-state.test.mjs`

- [ ] Add fixture coverage for long tool batches, review findings, context compaction, permission/user-input interactions, and file links.
- [ ] Keep durable history input as `history.activities`; do not reproject `history.turns`.
- [ ] Add row density states: `compact`, `normal`, and `expanded`, stored only as UI state.
- [ ] Ensure raw `permission_request` and `user_input_request` messages still drive blocking UI only, not durable activity records.
- [ ] Run `npm test`.
- [ ] Run `npm run build`.
- [ ] Commit: `gui: improve timeline density`.

**Acceptance:**
- Timeline remains activity-driven and session-scoped.
- Dense rows show enough state for scanning without nested cards or duplicate history streams.

### Task A4: Finish Right Panel Workbench Surface Behavior

**Purpose:** Make Files, File Preview, Diff, Preview, Terminal, Source Control, Settings, and Diagnostics behave like replaceable workbench surfaces.

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/FilesSurface.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/diff/DiffPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/source-control/SourceControlPanel.jsx`
- Modify tests: `workbench-state.test.mjs`, `right-panel-tabs-source.test.mjs`, `right-panel-store-parity.test.mjs`

- [ ] Add a single surface registry that declares `kind`, `title`, `placement`, `resourceId`, and close/persist behavior.
- [ ] Make command palette surface commands consume that registry.
- [ ] Keep source control read-only and local/offline; do not add staging, commit, push, pull, or remote providers.
- [ ] Add tests that persisted right-panel state excludes raw file content, diff content, terminal output, tool payloads, and secrets.
- [ ] Run `npm test`.
- [ ] Run `npm run build`.
- [ ] Commit: `gui: unify right panel surfaces`.

**Acceptance:**
- Right-panel behavior is registry-driven and session-scoped.
- No app-shell surface writes transcript, workflow state, permission state, or telemetry.

### Task A5: Expand Visual Debug Scenario Evidence

**Purpose:** Turn GUI visual parity from subjective review into repeatable evidence across interaction-heavy scenarios.

**Files:**
- Modify: `scripts/gui-visual-debug.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`

- [ ] Add scenarios for composer command search, right-panel surface switching, source-control diff browsing, multi-step timeline scanning, interaction pending state, and mobile/narrow panel behavior.
- [ ] For each scenario, assert required selectors are visible and key regions do not overlap.
- [ ] Keep `?visual_debug=1` dev-only; fixtures must expand to ordinary product reducer actions.
- [ ] Run `npm test`.
- [ ] Run `node scripts/gui-visual-debug.mjs --scenario composer,palette,diff,file,terminal,thread,timeline,interaction,panel-overflow,terminal-split,timeline-context --no-build` from repo root.
- [ ] Commit: `test: expand gui visual parity scenarios`.

**Acceptance:**
- Visual debug output can support a release-readiness discussion without relying on ad hoc screenshots.
- Product reducers do not gain `visual_*fixture` action cases.

---

## Track B: Architecture Guards Against Patch-Style Drift

### Task B1: Expand Source Guard Coverage

**Purpose:** Catch direct imports/calls that bypass the official Agent Core and workflow boundaries.

**Files:**
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify: `tests/test_current_architecture_boundaries.py`

- [ ] Add source scans with allowlists for these rules:
  - `QueryEngine` must not directly dispatch `ExtensionManager` hooks; use `AgentExtensionHost`.
  - New product code must not import `CHarnessWorkflowExtension` outside `default_extensions.py` and harness-owned modules.
  - Product code must not call `ToolRuntime.execute(...)` outside `AgentToolActionService`, `HostedCommandService`, tests, or runtime internals.
  - Product code must not maintain hard-coded tool-name refresh lists; use catalog/event `read_model_invalidations`.
  - GUI code must not synthesize durable interaction activity from raw `permission_request` or `user_input_request`.
  - GUI code must not reintroduce `timelineFromTurns`, `timelineFromEvents`, `projector.js`, `FlatTimelineView`, root-level `sessions`, root-level `currentSessionId`, or root-level `connectionState`.
- [ ] Keep tests path-based and Python 3.8-compatible.
- [ ] Run `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`.
- [ ] Commit: `test: expand architecture drift guards`.

**Acceptance:**
- A future shortcut around extension host, permission, workflow, or GUI runtime boundaries fails fast in local tests.

### Task B2: Add Behavioral Permission And Capability Boundary Tests

**Purpose:** Prove dynamic tools and optional capabilities remain visible/executable only through official activation and permission paths.

**Files:**
- Modify: `tests/test_dynamic_tool_registration.py`
- Modify: `tests/test_project_extensions.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `tests/test_capability_extensions.py`

- [ ] Add a dynamic extension tool with explicit `network` permission metadata.
- [ ] Assert frontend catalog sees the tool only when active through the shared `ExtensionManager`.
- [ ] Assert `PermissionPolicy` uses runtime catalog metadata for the permission category.
- [ ] Assert missing/invalid metadata falls back to ask-by-default `other`.
- [ ] Assert execution still flows through `AgentToolActionService` and cannot bypass pre/post extension hooks.
- [ ] Run the four modified test files.
- [ ] Commit: `test: guard dynamic capability permissions`.

**Acceptance:**
- Optional network/telemetry/intranet-style capabilities cannot become hidden Core calls.

### Task B3: Guard Workflow Package Ownership

**Purpose:** Prevent C/C++ workflow behavior from leaking back into generic Core, mode contracts, or GUI state.

**Files:**
- Modify: `tests/test_workflow_extensions.py`
- Modify: `tests/test_tools_package.py`
- Modify: `tests/test_pre_release_architecture_guards.py`

- [ ] Add assertions that default C/C++ recipe, quality, evidence, and task-status tools are activated by the default workflow extension, not by mode schema defaults.
- [ ] Assert `ToolRuntime.schemas_for(mode, workflow_state)` without explicit `tool_names` remains workflow-neutral.
- [ ] Assert GUI task APIs consume `Session.workflow_state["workflow"]` and do not import harness task graph/store internals.
- [ ] Assert active source has no `embedagent.tooling.packs` import or package-root pack alias.
- [ ] Run `uv run pytest tests/test_workflow_extensions.py tests/test_tools_package.py tests/test_pre_release_architecture_guards.py -v`.
- [ ] Commit: `test: guard workflow package ownership`.

**Acceptance:**
- Default C/C++ workflow remains replaceable and does not thicken Agent Core.

### Task B4: Add Documentation Drift Guard

**Purpose:** Keep active source-of-truth docs aligned with the current architecture vocabulary.

**Files:**
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify if needed: `AGENTS.md`, `README.md`, `docs/overall-solution-architecture.md`, `docs/frontend-protocol.md`, `docs/modules/agent-core.md`, `docs/modules/frontend-gui.md`

- [ ] Add a guard that scans active docs, excluding `docs/archive/**`, for forbidden current-contract phrases:
  - `manage_todos`
  - `mode=code`
  - `timeline replay`
  - `legacy harness_prompt compatibility`
  - `SessionTimelineStore`
  - `HarnessStateSynchronizer`
  - `embedagent.tooling.packs`
- [ ] Allow historical mentions only when the text clearly says the path is removed or forbidden.
- [ ] Run `uv run pytest tests/test_pre_release_architecture_guards.py -v`.
- [ ] Commit: `docs: guard architecture vocabulary drift`.

**Acceptance:**
- Active docs cannot quietly make old compatibility surfaces look supported again.

### Task B5: Define A Pre-Merge Architecture Gate Command

**Purpose:** Give future work a short, repeatable command set before merge.

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/development-tracker.md`

- [ ] Add a "Pre-Merge Architecture Gate" section with these commands:
  - `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`
  - `uv run pytest tests/ -m "not slow and not gui" -v`
  - `uv run --locked python scripts/lint.py`
  - `npm test` from `src/embedagent/frontend/gui/webapp`
  - `npm run build` from `src/embedagent/frontend/gui/webapp` when webapp source changes
- [ ] State that GUI static assets must be committed after webapp builds.
- [ ] State that Win7/offline claims require real bundle smoke evidence, not local dev tests.
- [ ] Run `uv run pytest tests/test_pre_release_architecture_guards.py -v`.
- [ ] Commit: `docs: define pre-merge architecture gate`.

**Acceptance:**
- Future contributors have one obvious gate before merging GUI/Core architecture changes.

---

## Execution Order

1. Task B1 first, because it reduces regression risk before GUI work resumes.
2. Task A1, then A2-A4, because the GUI needs a measurable interaction contract before component polish.
3. Task A5 after the main GUI behavior is in place.
4. Tasks B2-B4 after the first expanded guard lands, so behavior guards and doc guards can reuse the same vocabulary.
5. Task B5 last, after the command set reflects the new tests.

## Full Verification Before Final Merge

Run from repo root unless noted:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run pytest tests/ -m harness -v
uv run --locked python scripts/lint.py
```

Run from `src/embedagent/frontend/gui/webapp`:

```bash
npm test
npm run build
```

Run visual evidence from repo root when Playwright/browser dependencies are available:

```bash
node scripts/gui-visual-debug.mjs --scenario all --no-build
```

## Completion Criteria

- GUI behavior has repeatable model tests and visual debug evidence for command palette, composer, timeline, right-panel surfaces, terminal, source control, interaction pending states, and narrow viewports.
- Product code continues to satisfy Windows 7, offline, Python 3.8, and no-runtime-Node constraints.
- New capabilities cannot bypass `ExtensionManager` / `AgentExtensionHost`, `PermissionPolicy`, `AgentToolActionService`, or workflow-package activation.
- Active docs and tests describe only current product vocabulary; historical compatibility appears only in archive material or explicit removed-path guardrails.
- Each task is committed separately with a focused commit message.
