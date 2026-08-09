# Frontend Workflow Boundary And Structure Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove application-specific semantics and migration-era structure from generic Protocol, Host, GUI, and TUI code, leaving mechanically enforced package and frontend ownership boundaries.

**Architecture:** C/C++ keeps `TaskGraph`, phases, disciplines, and task semantics inside `embedagent-workflow-cpp`; generic layers carry only `Session.workflow_state["workflow"]` and generic summary/items/metadata. Frontend code is reorganized by stable ownership around shell runtime, timeline projection, descriptor model, contribution state, and focused style modules. Active names describe EmbedAgent behavior and never encode reference provenance or migration parity.

**Tech Stack:** Python 3.8, all six EmbedAgent distributions, React 18 JavaScript, CSS, pytest, Node test runner, distribution build/check/smoke scripts, PowerShell release tooling.

---

## Preconditions And File Responsibilities

This is Stage 5 and the final stage of `docs/superpowers/specs/2026-08-03-frontend-shell-convergence-design.md`. Start only after `2026-08-03-minimal-agent-workbench.md` is merged and the no-optional-contribution shell is usable in GUI and TUI.

Generic workflow contract:

```json
{
  "workflow": {
    "id": "string",
    "label": "string",
    "state": "string",
    "summary": "string",
    "activity": "string",
    "items": [],
    "metadata": {}
  }
}
```

Generic layers may preserve unknown JSON-safe `items` and `metadata`, but cannot inspect C/C++ keys, make phase decisions, calculate task status, or copy workflow values into sibling snapshot fields.

Structural owners after this plan:

- `session-runtime/timeline/`: activity types, grouping, tool projection, diff projection, and final timeline assembly.
- `app-shell/`: strict validation, model construction, and selectors in separate files.
- `client-runtime/reducers/`: app, session, contribution, and transport reducer domains.
- `components/shell/`: minimal shell composition only.
- `components/contributions/`: optional surface rendering only.
- `styles/`: tokens, base, shell, timeline, composer, overlays, and contributions.

### Task 1: Remove Flattened Workflow Fields From Protocol And Host

**Files:**
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/__init__.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_projector.py`
- Modify: `src/embedagent/core/adapter.py`
- Modify: `tests/test_session_projection_service.py`
- Modify: `tests/test_session_truth_boundaries.py`
- Modify: `tests/test_agent_app_protocol.py`
- Modify: `tests/test_core_adapter_shutdown.py`

- [ ] **Step 1: Write failing workflow-neutral snapshot tests**

Assert a Host snapshot contains only the carrier and never flattened application fields:

```python
snapshot = projector.project(managed_session_with_workflow(workflow_payload()))

assert snapshot["workflow_state"]["workflow"]["summary"] == "Build project"
for retired in (
    "current_phase",
    "discipline_profile",
    "current_activity",
    "task_summary",
    "task_items",
):
    assert retired not in snapshot
```

Construct `SessionSnapshot` with generic fields and assert its dataclass field names do not contain any retired member.

- [ ] **Step 2: Run focused protocol/Host tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_session_projection_service.py tests/test_session_truth_boundaries.py tests/test_agent_app_protocol.py tests/test_core_adapter_shutdown.py`

Expected: FAIL because the five flattened fields still exist.

- [ ] **Step 3: Delete the flattened Protocol fields**

Remove these members from `SessionSnapshot` in `embedagent_protocol.__init__`:

```python
current_phase
discipline_profile
current_activity
task_summary
task_items
```

Do not add aliases, properties, deprecated arguments, `**kwargs`, or migration adapters.

- [ ] **Step 4: Delete Host extraction and product adapter forwarding**

In `session_projector.py`, remove all reads of workflow metadata/items used only to populate sibling snapshot keys. Preserve one JSON-safe copy of `workflow_state`. In `src/embedagent/core/adapter.py`, stop passing the five deleted constructor arguments.

- [ ] **Step 5: Run focused tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_session_projection_service.py tests/test_session_truth_boundaries.py tests/test_agent_app_protocol.py tests/test_core_adapter_shutdown.py`

Expected: PASS with the generic workflow carrier intact.

- [ ] **Step 6: Commit Protocol and Host boundary cleanup**

```bash
git add packages/embedagent-protocol/src/embedagent_protocol/__init__.py packages/embedagent-host/src/embedagent_host/runtime/session_projector.py src/embedagent/core/adapter.py tests/test_session_projection_service.py tests/test_session_truth_boundaries.py tests/test_agent_app_protocol.py tests/test_core_adapter_shutdown.py
git commit -m "refactor: remove workflow fields from generic snapshots"
```

### Task 2: Keep C/C++ Semantics Behind Its Workflow Projection

**Files:**
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/workflow_projection.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py`
- Modify: `tests/test_c_cpp_workflow_task_projection.py`
- Modify: `tests/test_cpp_workflow_distribution.py`
- Modify: `tests/test_non_c_workflow_capabilities.py`
- Modify: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Write failing application-boundary tests**

Assert C/C++ projection remains rich inside the generic carrier:

```python
projection = build_workflow_projection(graph, context)

assert set(projection) == {
    "id",
    "label",
    "state",
    "summary",
    "activity",
    "items",
    "metadata",
}
assert projection["metadata"]["current_phase"] == graph.current_phase
assert projection["metadata"]["discipline_profile"] == context.discipline
assert projection["items"] == graph.to_items()
```

Assert a generic/Python application session has either no workflow record or a workflow record without C/C++ phase/tool vocabulary.

- [ ] **Step 2: Run workflow tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_c_cpp_workflow_task_projection.py tests/test_cpp_workflow_distribution.py tests/test_non_c_workflow_capabilities.py tests/test_workflow_extensions.py`

Expected: FAIL where tests or extension code still rely on generic flattened fields.

- [ ] **Step 3: Make `workflow_projection.py` the only C/C++ shell projection owner**

Return the exact generic record shown in the preconditions. Keep `current_phase` and `discipline_profile` only inside `metadata`; keep tasks only in `items`; derive `summary` and `activity` in the workflow package. Remove frontend-path strings such as `inspector.currentPhase` from the workflow package because renderer placement is descriptor-owned.

- [ ] **Step 4: Emit workflow patches through the extension boundary**

`CHarnessWorkflowExtension` writes the projection to `Session.workflow_state["workflow"]` through its declared workflow patch. It must not mutate Host projection objects or reference GUI/TUI modules. Preserve the package's internal `TaskGraph`, runner, task store, and phase engine APIs.

- [ ] **Step 5: Run workflow tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_c_cpp_workflow_task_projection.py tests/test_cpp_workflow_distribution.py tests/test_non_c_workflow_capabilities.py tests/test_workflow_extensions.py`

Expected: PASS; C/C++ semantics are available only after its extension registration.

- [ ] **Step 6: Commit C/C++ projection ownership**

```bash
git add packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/workflow_projection.py packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py tests/test_c_cpp_workflow_task_projection.py tests/test_cpp_workflow_distribution.py tests/test_non_c_workflow_capabilities.py tests/test_workflow_extensions.py
git commit -m "refactor: contain cpp workflow projection"
```

### Task 3: Remove Flattened Workflow State From Both Frontends

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/client-runtime/runtime-reducer.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/client-runtime/shell-selectors.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/state-helpers.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/runtime-reducer.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/client-runtime-reducers.test.mjs`
- Modify: `src/embedagent/frontend/tui/state.py`
- Modify: `src/embedagent/frontend/tui/reducer.py`
- Modify: `src/embedagent/frontend/tui/views.py`
- Modify: `tests/test_minimal_shell_contract.py`

- [ ] **Step 1: Write failing generic-shell tests**

In JavaScript, install a snapshot with a generic workflow and assert there is no sibling task state:

```javascript
const next = runtimeReducer(initialState, {
  type: "session_activated",
  snapshot: { session_id: "s-1", workflow_state: { workflow: workflowRecord } },
  activities: [],
  capabilities: emptyCapabilities(),
});

assert.deepEqual(next.snapshot.workflow_state.workflow, workflowRecord);
assert.equal(Object.prototype.hasOwnProperty.call(next, "tasks"), false);
assert.equal(Object.prototype.hasOwnProperty.call(next.snapshot, "task_items"), false);
```

In TUI, assert `build_workflow_summary(state)` reads the generic record and never exposes phase/task fields as core state.

- [ ] **Step 2: Run frontend tests and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL because normalizers and reducer still create flattened fields/tasks.

Run: `uv run python scripts/test-suite.py tdd tests/test_minimal_shell_contract.py tests/test_terminal_frontend.py`

Expected: FAIL where TUI core still reads workflow-specific state.

- [ ] **Step 3: Delete GUI serialization and state flattening**

Remove the five retired fields from `serialize_session_snapshot()`. `normalizeSessionPayload()` preserves `workflow_state` as a strict mapping and adds no derived siblings. Delete top-level `tasks` from `initialState`, workspace reset, session activation, and snapshot update branches. Workflow contribution selectors read only `snapshot.workflow_state.workflow`.

- [ ] **Step 4: Delete TUI workflow-specific core state**

Core reducer/view code passes the generic workflow record to the registered `workflow_summary` renderer. Task-list contribution state, when registered, comes from descriptor-driven workflow items rather than `SessionService.list_tasks()` or `.embedagent/memory/sessions/tasks.json`.

- [ ] **Step 5: Run frontend tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS.

Run: `uv run python scripts/test-suite.py tdd tests/test_minimal_shell_contract.py tests/test_terminal_frontend.py`

Expected: PASS.

- [ ] **Step 6: Commit frontend workflow cleanup**

```bash
git add src/embedagent/frontend/gui/backend/protocol_payloads.py src/embedagent/frontend/gui/webapp/src/state-helpers.js src/embedagent/frontend/gui/webapp/src/client-runtime/runtime-reducer.js src/embedagent/frontend/gui/webapp/src/client-runtime/shell-selectors.js src/embedagent/frontend/gui/webapp/test src/embedagent/frontend/tui/state.py src/embedagent/frontend/tui/reducer.py src/embedagent/frontend/tui/views.py tests/test_minimal_shell_contract.py tests/test_terminal_frontend.py
git commit -m "refactor: consume only generic workflow state"
```

### Task 4: Rename Migration-Era Frontend Concepts

**Files:**
- Rename: `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js` to `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline/activity-timeline.js`
- Rename: `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs` to `src/embedagent/frontend/gui/webapp/test/activity-timeline.test.mjs`
- Rename: `src/embedagent/frontend/gui/webapp/src/workbench/workbench-parity-model.js` to `src/embedagent/frontend/gui/webapp/src/components/contributions/contribution-model.js`
- Rename: `src/embedagent/frontend/gui/webapp/test/workbench-parity-model.test.mjs` to `src/embedagent/frontend/gui/webapp/test/contribution-model.test.mjs`
- Rename: `src/embedagent/frontend/gui/webapp/test/right-panel-store-parity.test.mjs` to `src/embedagent/frontend/gui/webapp/test/contribution-surface-store.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/ChangedFilesCard.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`

- [ ] **Step 1: Add a failing source-name guard**

Add a webapp test that walks active source/test file names and file contents:

```javascript
for (const entry of activeFrontendFiles()) {
  assert.equal(/(?:^|[-_.])t3(?:[-_.]|$)/i.test(entry.relativePath), false);
  assert.equal(/(?:^|[-_.])parity(?:[-_.]|$)/i.test(entry.relativePath), false);
  assert.equal(/\bt3[-_]|[-_]parity\b/i.test(entry.source), false);
}
```

Fixture data must use EmbedAgent domain names such as `feature/session-toolbar` and `notes/session-toolbar.md`.

- [ ] **Step 2: Run webapp tests and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL on current file names, imports, class names, fixture strings, and CSS selectors.

- [ ] **Step 3: Perform semantic file and export renames**

Use `git mv` for the listed files. Rename exports and state properties:

```text
buildT3TimelineRows -> buildActivityTimelineRows
t3TimelineRows -> timelineRows
buildWorkbenchParityModel -> buildContributionModel
```

Update every source/test import in the same commit. Do not leave forwarding modules or alias exports at old paths.

- [ ] **Step 4: Rename CSS selectors and fixture values**

Use domain names by responsibility: `.timeline-*`, `.tool-*`, `.reasoning-*`, `.review-*`, `.changed-files-*`, and `.agent-*`. Replace every `t3-*` class and the `T3 VISUAL LANGUAGE OVERRIDES` comment. Replace fixture strings that encode t3code provenance.

- [ ] **Step 5: Run webapp tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS with no active `t3` or `parity` identifiers.

- [ ] **Step 6: Commit semantic renames**

```bash
git add src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/gui/webapp/test
git commit -m "refactor: remove frontend migration naming"
```

### Task 5: Split Timeline Projection Into Focused Modules

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline/activity-types.js`
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline/activity-grouping.js`
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline/tool-activity.js`
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline/diff-activity.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline/activity-timeline.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/activity-timeline.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`

- [ ] **Step 1: Add characterization tests at each new boundary**

Move existing cases into focused test sections and add direct assertions:

```javascript
assert.deepEqual(groupActivitiesByTurn(activities).map((item) => item.turnId), ["turn-1"]);
assert.equal(projectToolActivity(toolStarted, catalog).status, "inProgress");
assert.deepEqual(summarizeChangedFiles(diffText), [
  { path: "demo.c", additions: 1, deletions: 1 },
]);
```

The assembly test asserts row order, ids, and renderer kinds for a mixed turn.

- [ ] **Step 2: Run timeline tests before extraction**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS, establishing characterization before moves.

- [ ] **Step 3: Extract pure ownership modules**

Move constants/types only to `activity-types.js`, turn ordering/deduplication to `activity-grouping.js`, tool lifecycle/catalog projection to `tool-activity.js`, and diff parsing/tree/stat projection to `diff-activity.js`. `activity-timeline.js` imports them and owns only final row assembly.

Do not add index-barrel re-exports; consumers import the owning file directly.

- [ ] **Step 4: Run timeline tests after extraction**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS with identical row output.

- [ ] **Step 5: Commit timeline split**

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/timeline src/embedagent/frontend/gui/webapp/test/activity-timeline.test.mjs src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs
git commit -m "refactor: split timeline projection owners"
```

### Task 6: Split Descriptor Models, Reducers, And Styles

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/app-shell/validation.js`
- Create: `src/embedagent/frontend/gui/webapp/src/app-shell/selectors.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
- Create: `src/embedagent/frontend/gui/webapp/src/client-runtime/reducers/app-reducer.js`
- Create: `src/embedagent/frontend/gui/webapp/src/client-runtime/reducers/session-reducer.js`
- Create: `src/embedagent/frontend/gui/webapp/src/client-runtime/reducers/contribution-reducer.js`
- Create: `src/embedagent/frontend/gui/webapp/src/client-runtime/reducers/transport-reducer.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/client-runtime/runtime-reducer.js`
- Create: `src/embedagent/frontend/gui/webapp/src/styles/tokens.css`
- Create: `src/embedagent/frontend/gui/webapp/src/styles/base.css`
- Create: `src/embedagent/frontend/gui/webapp/src/styles/shell.css`
- Create: `src/embedagent/frontend/gui/webapp/src/styles/timeline.css`
- Create: `src/embedagent/frontend/gui/webapp/src/styles/composer.css`
- Create: `src/embedagent/frontend/gui/webapp/src/styles/overlays.css`
- Create: `src/embedagent/frontend/gui/webapp/src/styles/contributions.css`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/runtime-reducer.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/client-runtime-reducers.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/store-reducer.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add direct ownership tests before moving code**

Test descriptor validation, descriptor selectors, each reducer domain, and root reducer composition independently. Add CSS import assertions:

```javascript
assert.deepEqual(cssImports("styles.css"), [
  "./styles/tokens.css",
  "./styles/base.css",
  "./styles/shell.css",
  "./styles/timeline.css",
  "./styles/composer.css",
  "./styles/overlays.css",
  "./styles/contributions.css",
]);
```

- [ ] **Step 2: Run webapp tests before extraction**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS for existing behavior and FAIL only for new module ownership assertions.

- [ ] **Step 3: Split app-shell validation from model selection**

`validation.js` validates strict wire/view input and throws typed errors. `model.js` constructs the immutable application model. `selectors.js` reads commands, surfaces, keybindings, copy, workspace, and capabilities without defaults. Delete duplicated validation/selection helpers from the original model.

- [ ] **Step 4: Split root reducer domains**

Each reducer accepts its owned state slice and action. `runtime-reducer.js` delegates and owns only cross-slice reset/activation ordering. Contribution-specific actions never enter session reducer; protocol/transport actions never enter presentation contribution reducer.

- [ ] **Step 5: Split CSS by component ownership**

Move tokens and global reset first, then shell layout, timeline, composer, overlays, and optional contribution styles. `styles.css` contains only ordered `@import` statements. Do not duplicate selectors during the move.

- [ ] **Step 6: Run webapp tests after extraction**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS with the same rendered class contracts.

- [ ] **Step 7: Commit structural ownership split**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-shell src/embedagent/frontend/gui/webapp/src/client-runtime/reducers src/embedagent/frontend/gui/webapp/src/client-runtime/runtime-reducer.js src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/src/styles src/embedagent/frontend/gui/webapp/test
git commit -m "refactor: split frontend state and style owners"
```

### Task 7: Delete Superseded Workbench Structure And Add Debt Gates

**Files:**
- Delete: `src/embedagent/frontend/gui/webapp/src/components/workbench/AppSidebarLayout.jsx`
- Delete: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
- Delete: `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
- Delete: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- Delete: `src/embedagent/frontend/gui/webapp/src/workbench/ui-state.js`
- Delete: `src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js`
- Delete: `src/embedagent/frontend/gui/webapp/src/app-runtime/panel-resize-controller.js`
- Delete: `src/embedagent/frontend/gui/webapp/src/app-runtime/surface-panel-controller.js`
- Delete: `src/embedagent/frontend/gui/webapp/src/app-runtime/surface-panel-props.js`
- Delete: `src/embedagent/frontend/gui/webapp/test/right-panel-tabs-source.test.mjs`
- Delete: `src/embedagent/frontend/gui/webapp/test/right-panel-controller.test.mjs`
- Delete: `src/embedagent/frontend/gui/webapp/test/panel-resize-controller.test.mjs`
- Delete: `src/embedagent/frontend/gui/webapp/test/surface-panel-props.test.mjs`
- Delete: `src/embedagent/frontend/gui/webapp/test/workbench-ui-state.test.mjs`
- Delete: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify: `tests/test_current_architecture_boundaries.py`

- [ ] **Step 1: Add failing debt-regression guards**

Walk active source and assert:

```python
for token in (
    "current_phase",
    "discipline_profile",
    "current_activity",
    "task_summary",
    "task_items",
    "t3-",
    "t3_",
    "parity",
):
    assert token not in generic_protocol_host_and_frontend_source
```

Exclude `packages/embedagent-workflow-cpp` from C/C++ vocabulary checks. Also enforce:

- `App.jsx` does not import controllers or optional feature implementations;
- no JavaScript file outside transport owners contains network primitives;
- no generic shell module imports `embedagent_workflow_cpp`;
- root `styles.css` contains imports only;
- retired workbench files do not exist;
- no active JavaScript/JSX source file exceeds 1,000 physical lines;
- no active CSS ownership file exceeds 800 physical lines.

- [ ] **Step 2: Run guards and verify the red state**

Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`

Expected: FAIL while superseded files and forbidden names remain.

- [ ] **Step 3: Delete superseded files and imports**

Delete only files whose behavior is already covered by `components/shell`, `components/contributions`, descriptor selectors, and contribution reducer. Remove their imports and test-runner registrations in the same change. Do not leave re-export facades.

- [ ] **Step 4: Run guards and webapp tests**

Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`

Expected: PASS.

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS.

- [ ] **Step 5: Commit debt guards and deletion**

```bash
git add src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/gui/webapp/test tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py
git commit -m "refactor: delete superseded frontend workbench"
```

### Task 8: Synchronize Durable Documentation And Archive The Slice

**Files:**
- Modify: `docs/platform/protocol.md`
- Modify: `docs/platform/frontend-protocol.md`
- Modify: `docs/platform/frontend-gui.md`
- Modify: `docs/platform/frontend-tui.md`
- Modify: `docs/platform/session-runtime.md`
- Modify: `docs/applications/cpp-workflow.md`
- Modify: `docs/product/composition.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/references/code-doc-matrix.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Create: `docs/archive/frontend-shell-convergence/README.md`
- Move: `docs/superpowers/specs/2026-08-03-frontend-shell-convergence-design.md` to `docs/archive/frontend-shell-convergence/specs/2026-08-03-frontend-shell-convergence-design.md`
- Move: `docs/superpowers/plans/2026-08-03-frontend-transport-correctness.md` to `docs/archive/frontend-shell-convergence/plans/2026-08-03-frontend-transport-correctness.md`
- Move: `docs/superpowers/plans/2026-08-03-strict-frontend-protocol-authority.md` to `docs/archive/frontend-shell-convergence/plans/2026-08-03-strict-frontend-protocol-authority.md`
- Move: `docs/superpowers/plans/2026-08-03-shared-shell-registration.md` to `docs/archive/frontend-shell-convergence/plans/2026-08-03-shared-shell-registration.md`
- Move: `docs/superpowers/plans/2026-08-03-minimal-agent-workbench.md` to `docs/archive/frontend-shell-convergence/plans/2026-08-03-minimal-agent-workbench.md`
- Move: `docs/superpowers/plans/2026-08-03-frontend-workflow-boundary-cleanup.md` to `docs/archive/frontend-shell-convergence/plans/2026-08-03-frontend-workflow-boundary-cleanup.md`
- Modify: `docs/superpowers/README.md`

- [ ] **Step 1: Update each owning authority in place**

Record only current behavior:

- Protocol: strict DTOs, descriptor schema, event cursor.
- Frontend protocol: ClientRuntime/TerminalRuntime effect boundaries.
- GUI/TUI: minimal core and contribution outlets.
- Session runtime: generic workflow carrier only.
- C/C++ workflow: its internal phase/task semantics and generic projection.
- Product composition: one shell compiler and default registration.
- Overall architecture: six distributions remain unchanged.

Remove stale blocker text, old field names, old catalogs, and migration-stage narratives.

- [ ] **Step 2: Update the code/doc matrix and status routing**

Map each new owner to exactly one authority. `docs/current-status.md` states the frontend convergence acceptance result and only remaining genuine blockers; `docs/implementation-roadmap.md` removes finished frontend stages rather than marking a parallel ledger complete.

- [ ] **Step 3: Create an indexed archive package**

Create the archive README only after reading `git rev-parse HEAD`. Write that exact commit id together with the decision date, scope, archived spec/plan list, and links back to current authorities; the committed file must contain no template field.

Use `git mv` to move the design spec and all five plans. Remove the Frontend Shell Convergence section from `docs/superpowers/README.md` because no acceptance condition remains open.

- [ ] **Step 4: Run documentation navigation tests**

Run: `uv run python scripts/test-suite.py tdd tests/test_documentation_navigation.py tests/test_current_architecture_boundaries.py`

Expected: PASS with no active authority linking to the old superpowers paths.

- [ ] **Step 5: Verify active docs contain only current vocabulary**

Run: `rg -n "t3-timeline|workbench-parity|appShell|WORKBENCH_COMMANDS|current_phase.*SessionSnapshot|task_items.*SessionSnapshot" README.md docs --glob '!docs/archive/**'`

Expected: no stale active-document matches. A current C/C++ authority may use `current_phase` as workflow-package vocabulary, but never as a generic `SessionSnapshot` field.

- [ ] **Step 6: Commit durable docs and archive**

```bash
git add docs
git commit -m "docs: close frontend shell convergence"
```

### Task 9: Run Full Product, Distribution, And Release Verification

**Files:**
- Generated: `src/embedagent/frontend/gui/static/*`
- Generated and ignored: `dist/*`, release staging under configured build directories

- [ ] **Step 1: Rebuild GUI static assets**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS.

Run from `src/embedagent/frontend/gui/webapp`: `npm run build`

Expected: exit code 0 with current static assets.

- [ ] **Step 2: Run architecture, full Python, and lint gates**

Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`

Expected: PASS.

Run: `uv run python scripts/test-suite.py full`

Expected: PASS.

Run: `uv run --locked python scripts/lint.py`

Expected: PASS.

- [ ] **Step 3: Build and inspect all six distributions**

Run: `uv run python scripts/build-python-distributions.py --dist-dir dist`

Expected: exactly six current project wheels are produced without deleting an external wheelhouse.

Run: `uv run python scripts/check-python-distributions.py --dist-dir dist`

Expected: PASS for dependency direction, contents, version equality, and wheel count.

Run: `uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe`

Expected: PASS in isolated wheel-only environments for all six distributions.

- [ ] **Step 4: Run offline release assembly and verification**

Run: `powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor`

Expected: PASS for local release prerequisites.

Run: `powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release`

Expected: PASS for dependency preparation, assembly, and verification. This is not Windows 7 acceptance evidence.

- [ ] **Step 5: Run final forbidden-vocabulary and ownership scans**

Run: `rg -n -e current_phase -e discipline_profile -e current_activity -e task_summary -e task_items packages/embedagent-protocol/src packages/embedagent-host/src src/embedagent/frontend`

Expected: no generic-layer matches. C/C++ package matches are intentionally outside this scan.

Run: `rg -n -i -e "t3[-_]" -e parity src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/gui/webapp/test`

Expected: no matches.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 6: Commit generated static assets**

```bash
git add src/embedagent/frontend/gui/static
git commit -m "build: refresh converged gui assets"
```

Skip this commit only when `git status --short` proves the build produced no tracked asset change.

## Program Exit Criteria

- Generic Protocol, Host, product adapter, GUI, and TUI contain no flattened C/C++ workflow fields.
- `embedagent-workflow-cpp` remains the sole owner of TaskGraph, phase, discipline, and task semantics.
- Frontends consume `workflow_state["workflow"]` through registered generic renderers.
- No active source/test file or CSS selector contains `t3`/`parity` migration naming.
- Timeline projection, app-shell model, reducers, and styles have focused owners; superseded workbench files are deleted.
- Architecture guards prevent direct network ownership, fixed catalogs, workflow leakage, migration naming, and oversized ownership files from returning.
- Active documentation records only current truth; the completed spec and five plans are in one indexed archive package.
- Webapp tests/build, architecture guards, full Python tests, lint, six-wheel build/check/smoke, and offline release verification pass.
- Real clean-machine Windows 7/WebView2 acceptance remains a separate external release gate and is not claimed by this plan.
