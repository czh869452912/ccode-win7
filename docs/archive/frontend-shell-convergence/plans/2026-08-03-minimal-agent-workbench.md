# Minimal Agent Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a stable Pi-like minimal GUI/TUI agent experience while retaining the relevant t3code desktop interaction quality through optional registered contributions.

**Architecture:** The core shell contains only session navigation, timeline, composer, compact status, command/mode selection, and blocking interactions. Files and diffs render inline; terminal, source control, plan/task inspectors, preview, and editor are optional descriptor contributions mounted through generic outlets. GUI copies retained t3code interaction and visual decisions without importing its state/runtime architecture; TUI exposes the same product semantics in a compact terminal-native layout.

**Tech Stack:** React 18, CSS, `lucide-react`, JavaScript ClientRuntime, prompt_toolkit, Rich, Python 3.8 TerminalRuntime, Playwright visual harness, Node test runner, pytest.

---

## Preconditions And File Responsibilities

This is Stage 4 of the frontend convergence design. Start only after `2026-08-03-shared-shell-registration.md` is merged and GUI/TUI consume the same compiled descriptor.

Retained t3code references are read-only design inputs:

- `reference/t3code/apps/web/src/components/AppSidebarLayout.tsx`: collapsible session rail proportions and navigation density.
- `reference/t3code/apps/web/src/components/chat/timelineScrollAnchoring.ts`: follow-output anchoring behavior.
- `reference/t3code/apps/web/src/components/composerFooterLayout.ts`: compact composer footer layout.
- `reference/t3code/apps/web/src/components/chat/ComposerPendingApprovalPanel.tsx`: permission hierarchy and action placement.
- `reference/t3code/apps/web/src/components/chat/ComposerPendingApprovalActions.tsx`: approval action grouping.
- `reference/t3code/apps/web/src/components/chat/ComposerCommandPopover.tsx`: command search interaction.
- `reference/t3code/apps/web/src/index.css`: typography, spacing, focus, loading, and failure-state treatment.

Do not copy t3code's Effect/Atom ownership, remote environment selectors, account state, synchronization, collaboration, mobile architecture, or server orchestration.

New GUI ownership:

- `components/shell/AgentShell.jsx`: minimal shell composition only.
- `components/shell/SessionRail.jsx`: session list and lifecycle actions.
- `components/shell/SessionTimeline.jsx`: central timeline and inline references/diffs.
- `components/shell/SessionComposer.jsx`: composer, modes, commands, stop/send, pending interaction slot.
- `components/shell/SessionStatusFooter.jsx`: compact connection/mode/context/status projection.
- `components/shell/ShellOverlayHost.jsx`: command and interaction overlays.
- `components/contributions/ContributionOutlet.jsx`: generic optional renderer mount.
- `client-runtime/shell-selectors.js`: frozen renderer-ready projections.

New TUI ownership:

- `frontend/tui/contributions.py`: renderer-key to terminal renderer registration.
- `frontend/tui/layout.py`: header, timeline, composer, footer, and overlay placement only.
- `frontend/tui/views.py`: pure text/formatted-control projections.

### Task 1: Freeze The Minimal Core Contract Before Rendering Changes

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/client-runtime/shell-selectors.js`
- Create: `src/embedagent/frontend/gui/webapp/test/shell-selectors.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/tui/state.py`
- Create: `tests/test_minimal_shell_contract.py`

- [ ] **Step 1: Write failing GUI minimal-selector tests**

Build state with an empty optional contribution list and assert the core projection remains complete:

```javascript
const view = selectAgentShellView(stateFixture({ contributions: [] }));

assert.deepEqual(Object.keys(view).sort(), [
  "composer",
  "connection",
  "interaction",
  "modes",
  "sessions",
  "status",
  "timeline",
  "workflow",
]);
assert.equal(view.timeline.items.length > 0, true);
assert.equal(view.composer.canSubmit, true);
assert.equal("terminal" in view, false);
assert.equal("sourceControl" in view, false);
```

Add a freeze assertion and prove selector output does not expose protocol, controller, fetch, socket, or mutable reducer objects.

- [ ] **Step 2: Write failing TUI minimal-state tests**

Define a terminal state constructed from the same empty optional descriptor:

```python
state = TerminalState.from_shell_descriptor(
    workspace="C:/workspace",
    initial_mode="explore",
    descriptor=minimal_descriptor(),
)

assert state.session.current_mode == "explore"
assert state.timeline.items == []
assert state.overlay.active_id == ""
assert state.contributions == {}
```

Assert the core state has no required explorer, editor, inspector, terminal, source-control, task, or preview field.

- [ ] **Step 3: Run both suites and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL because `shell-selectors.js` is absent.

Run: `uv run python scripts/test-suite.py tdd tests/test_minimal_shell_contract.py`

Expected: FAIL because TUI state still assumes workbench auxiliary panels.

- [ ] **Step 4: Implement frozen GUI selectors**

`selectAgentShellView(state)` returns plain frozen records and arrays. It derives timeline, composer, session, mode, workflow summary, current interaction, connection, and status from ClientRuntime state. It may call pure existing activity/composer model functions but cannot mutate state or dispatch.

- [ ] **Step 5: Separate TUI core and contribution state**

Keep `TerminalState` fields for `session`, `timeline`, `composer`, `status`, `overlay`, and `contributions`. Move explorer/editor/inspector-specific values into contribution state keyed by contribution id. `from_shell_descriptor()` initializes only registered contribution states.

- [ ] **Step 6: Run both suites and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS.

Run: `uv run python scripts/test-suite.py tdd tests/test_minimal_shell_contract.py`

Expected: PASS.

- [ ] **Step 7: Commit the minimal core contract**

```bash
git add src/embedagent/frontend/gui/webapp/src/client-runtime/shell-selectors.js src/embedagent/frontend/gui/webapp/test/shell-selectors.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/tui/state.py tests/test_minimal_shell_contract.py
git commit -m "refactor: define minimal agent shell state"
```

### Task 2: Build The GUI Session Rail And Core Layout

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/shell/AgentShell.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/shell/SessionRail.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/shell/SessionStatusFooter.jsx`
- Create: `src/embedagent/frontend/gui/webapp/test/agent-shell-source.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/package.json`
- Modify: `src/embedagent/frontend/gui/webapp/package-lock.json`

- [ ] **Step 1: Add failing composition and accessibility source tests**

Assert `App.jsx` renders only `AgentShell` and passes `view` plus `actions`. Assert `SessionRail` contains a navigation landmark, accessible icon-button labels, session selection, and descriptor-backed lifecycle menu. Assert `AgentShell` has no permanent right panel or bottom drawer.

```javascript
assert.equal(appSource.includes("<AgentShell"), true);
assert.equal(appSource.includes("<RightPanelTabs"), false);
assert.equal(appSource.includes("<BottomDrawer"), false);
assert.equal(railSource.includes('aria-label="Sessions"'), true);
```

- [ ] **Step 2: Run webapp tests and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL because the shell components do not exist and App still composes workbench panels.

- [ ] **Step 3: Install the icon dependency**

Run from `src/embedagent/frontend/gui/webapp`: `npm install lucide-react`

Expected: `lucide-react` is recorded in `package.json` and `package-lock.json`; it is bundled into static GUI assets and adds no runtime Node.js requirement.

- [ ] **Step 4: Implement `SessionRail` from retained t3code behavior**

Copy the interaction decisions, not source architecture:

- stable expanded width `264px`, collapsed width `48px`;
- icon-only collapse control with tooltip and `aria-expanded`;
- current session, status, pending-interaction marker, and concise title;
- one overflow menu for rename/archive/fork;
- new-session command at the rail header;
- keyboard focus remains on the selected session after list refresh;
- narrow viewport uses an overlay drawer and does not reserve horizontal space.

Import familiar controls such as `PanelLeftClose`, `Plus`, and `MoreHorizontal` from `lucide-react`. Do not draw new SVGs or put text into icon-only controls.

- [ ] **Step 5: Implement `AgentShell` and the compact footer**

Use a stable grid:

```css
.agent-shell {
  display: grid;
  grid-template-columns: var(--session-rail-width) minmax(0, 1fr);
  min-height: 100vh;
}

.agent-main {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto 28px;
  min-width: 0;
}
```

The footer shows connection/recovery state, current mode, context usage, and session status. It contains no feature explanation or keyboard-instruction prose.

- [ ] **Step 6: Replace App workbench markup**

`App.jsx` selects the frozen view, passes ClientRuntime actions, and renders `AgentShell`. Delete direct layout decisions, panel state, and controller wiring from the component. Optional contributions are not reintroduced here.

- [ ] **Step 7: Run webapp tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS with no permanent panel composition in `App.jsx`.

- [ ] **Step 8: Commit core GUI layout**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/shell/AgentShell.jsx src/embedagent/frontend/gui/webapp/src/components/shell/SessionRail.jsx src/embedagent/frontend/gui/webapp/src/components/shell/SessionStatusFooter.jsx src/embedagent/frontend/gui/webapp/test/agent-shell-source.test.mjs src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/webapp/package.json src/embedagent/frontend/gui/webapp/package-lock.json
git commit -m "feat: install minimal gui shell layout"
```

### Task 3: Install The Central Timeline And Inline Work Artifacts

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/shell/SessionTimeline.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/ToolDetail.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/ChangedFilesCard.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/DiffView.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/timeline-scroll-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/timeline-scroll-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/right-panel-tabs-source.test.mjs`

- [ ] **Step 1: Add failing timeline behavior tests**

Assert one continuous timeline renders messages, reasoning, tool lifecycle, error, workflow summary, file reference, and inline diff rows. Add scroll tests matching the retained t3code rule: auto-follow only when already near the bottom; streaming updates do not pull a user away from inspected history.

```javascript
controller.onContentChanged({ streaming: true });
assert.equal(harness.scrollToBottomCalls, 0);
harness.setNearBottom(true);
controller.onContentChanged({ streaming: true });
assert.equal(harness.scrollToBottomCalls, 1);
```

- [ ] **Step 2: Run webapp tests and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL until inline file/diff rows and the new timeline owner are wired.

- [ ] **Step 3: Implement one timeline hierarchy**

`SessionTimeline` owns the scroll container, live region, empty state, and row list. Preserve the accepted t3code information hierarchy:

- user and assistant messages are primary;
- reasoning is compact and collapsible;
- running/completed/failed tools share one lifecycle row;
- errors are visible without expanding raw payloads;
- workflow is a generic summary/items block;
- file references open through a runtime action;
- diffs render inline and may open an optional secondary surface when registered.

No row imports protocol adapters, controller factories, application ids, or C/C++ tool names.

- [ ] **Step 4: Move file and diff content inline**

`ChangedFilesCard` and `DiffView` render inside timeline rows with stable max height and explicit expand/collapse. Delete assumptions that a right panel is required. The open-secondary action appears only when a matching descriptor is registered.

- [ ] **Step 5: Run webapp tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS and legacy right-panel source tests now assert absence from core composition.

- [ ] **Step 6: Commit central timeline behavior**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/shell/SessionTimeline.jsx src/embedagent/frontend/gui/webapp/src/components/timeline src/embedagent/frontend/gui/webapp/src/components/DiffView.jsx src/embedagent/frontend/gui/webapp/src/app-runtime/timeline-scroll-controller.js src/embedagent/frontend/gui/webapp/test
git commit -m "feat: render work in the central timeline"
```

### Task 4: Install The Composer, Commands, Modes, And Interactions

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/shell/SessionComposer.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/shell/ShellOverlayHost.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerCommandMenu.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerInteractionPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPendingApprovalPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPendingUserInputPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/composer/composer-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/composer-state.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/composer-components-source.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/composer-integration-source.test.mjs`

- [ ] **Step 1: Add failing core-flow tests**

Cover empty draft, multiline editing, slash command search, mode selection, send, stop, permission, user input, validation failure, and disabled states. Assert one primary action occupies stable dimensions and toggles from send to stop without shifting layout.

```javascript
assert.deepEqual(primaryActionFor({ status: "idle", draft: "hello" }), {
  kind: "send",
  enabled: true,
});
assert.deepEqual(primaryActionFor({ status: "running", draft: "" }), {
  kind: "stop",
  enabled: true,
});
```

- [ ] **Step 2: Run webapp tests and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL until the new shell composer and overlay host own these flows.

- [ ] **Step 3: Implement retained t3code composer behavior**

Copy the retained decisions:

- editor grows between 44px and 180px without resizing adjacent controls;
- command results stay keyboard navigable and preserve query highlight;
- mode is a compact menu/segmented selector from descriptor data;
- file/path tokens remain inline and removable;
- Enter submits when the command menu is closed, Shift+Enter inserts a newline;
- the action button is icon-only with tooltip and accessible label;
- loading, disabled, permission, and error states do not overlap the editor.

Do not import t3code packages or reproduce remote/environment selectors.

- [ ] **Step 4: Unify blocking interactions in one overlay host**

`ShellOverlayHost` selects registered interaction renderer keys. Permission and user-input panels use the same runtime action `respondToInteraction(requestId, response)`. Approval categories remain protocol data; UI cannot grant permissions locally.

- [ ] **Step 5: Run webapp tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS for all composer and interaction paths.

- [ ] **Step 6: Commit composer and interaction flow**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/shell/SessionComposer.jsx src/embedagent/frontend/gui/webapp/src/components/shell/ShellOverlayHost.jsx src/embedagent/frontend/gui/webapp/src/components/Composer.jsx src/embedagent/frontend/gui/webapp/src/components/composer src/embedagent/frontend/gui/webapp/src/composer/composer-state.js src/embedagent/frontend/gui/webapp/test
git commit -m "feat: converge composer and interaction flow"
```

### Task 5: Mount Non-Core Features As Optional Contributions

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/contributions/ContributionOutlet.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/contributions/renderer-registry.js`
- Create: `src/embedagent/frontend/gui/webapp/test/contribution-outlet.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/TerminalShell.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/source-control/SourceControlPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/PreviewSurface.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/client-runtime/client-runtime.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing optionality tests**

Test no-contribution startup and explicit mounts:

```javascript
const empty = projectContributionOutlets(emptyShellDescriptor(), runtimeState);
assert.deepEqual(empty, { overlays: [], secondary: [] });

const terminal = projectContributionOutlets(
  shellDescriptor({ surfaces: [surface("terminal", "secondary", "terminal")] }),
  runtimeState,
);
assert.equal(terminal.secondary[0].rendererKey, "terminal");
```

Assert unknown renderer keys fail during descriptor validation and never reach React.

- [ ] **Step 2: Run webapp tests and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL because optional panels are still tied to fixed workbench locations.

- [ ] **Step 3: Implement a build-time renderer registry**

The registry maps only supported generic keys to imported React components:

```javascript
export const contributionRenderers = Object.freeze({
  terminal: TerminalShell,
  source_control: SourceControlPanel,
  preview: PreviewSurface,
  workflow_summary: WorkflowSummarySurface,
  inline_diff: DiffView,
});
```

It contains no application ids and accepts no runtime JavaScript registration. `ContributionOutlet` receives a validated surface descriptor, renderer data, and runtime actions.

- [ ] **Step 4: Route optional operations through ClientRuntime**

`openContribution(id)` resolves the compiled descriptor, validates availability, loads contribution data through named protocol methods, and dispatches generic `contribution_opened/loaded/failed/closed` actions. Components cannot call terminal, source-control, preview, task, or plan APIs directly.

- [ ] **Step 5: Run webapp tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS; removing all optional surface records still leaves session/timeline/composer tests green.

- [ ] **Step 6: Commit optional GUI contributions**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/contributions src/embedagent/frontend/gui/webapp/src/components/workbench/TerminalShell.jsx src/embedagent/frontend/gui/webapp/src/components/source-control/SourceControlPanel.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/PreviewSurface.jsx src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx src/embedagent/frontend/gui/webapp/src/client-runtime/client-runtime.js src/embedagent/frontend/gui/webapp/test
git commit -m "refactor: mount gui features as contributions"
```

### Task 6: Reduce TUI To The Same Minimal Product Semantics

**Files:**
- Create: `src/embedagent/frontend/tui/contributions.py`
- Modify: `src/embedagent/frontend/tui/layout.py`
- Modify: `src/embedagent/frontend/tui/views.py`
- Modify: `src/embedagent/frontend/tui/controller.py`
- Modify: `src/embedagent/frontend/tui/reducer.py`
- Modify: `src/embedagent/frontend/tui/state.py`
- Modify: `tests/test_terminal_frontend.py`
- Modify: `tests/test_tui_activity_timeline.py`
- Modify: `tests/test_tui_timeline_activities.py`
- Modify: `tests/test_minimal_shell_contract.py`

- [ ] **Step 1: Add failing layout and flow tests**

Assert the default layout has exactly the core bands and that an empty contribution descriptor is usable:

```python
layout = build_layout(app_with_descriptor(minimal_descriptor()))
assert layout.core_region_ids == ("header", "timeline", "composer", "status")
assert layout.secondary_region_ids == ()
```

Exercise new session, resume, timeline streaming, command palette, mode change, permission response, user input, cancel, error, and close through `TerminalRuntime` actions.

- [ ] **Step 2: Run TUI tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_terminal_frontend.py tests/test_tui_activity_timeline.py tests/test_tui_timeline_activities.py tests/test_minimal_shell_contract.py`

Expected: FAIL while layout assumes explorer/editor/inspector panels.

- [ ] **Step 3: Build the four-band terminal layout**

Use prompt_toolkit containers for startup/session header, scrollable transcript, replaceable composer/interaction region, and one-line status/footer. Overlay the command palette and registered secondary views with `FloatContainer`; no optional view consumes permanent width or height.

- [ ] **Step 4: Render registered contributions by key**

`contributions.py` maps validated renderer keys to pure terminal render functions. Terminal, source control, preview, workflow summary, file reference, and inline diff use structured runtime data. Removing their descriptors removes the keybindings, commands, state, and views together.

- [ ] **Step 5: Delete core dependencies on auxiliary workbench services**

`TerminalController.start()`, session activation, and event handling must not call explorer, editor, task, source-control, terminal, or preview refresh functions unless an active registered contribution requests them. Main session operation remains usable with every optional contribution absent.

- [ ] **Step 6: Run TUI tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_terminal_frontend.py tests/test_tui_activity_timeline.py tests/test_tui_timeline_activities.py tests/test_minimal_shell_contract.py`

Expected: PASS.

- [ ] **Step 7: Commit minimal TUI workbench**

```bash
git add src/embedagent/frontend/tui/contributions.py src/embedagent/frontend/tui/layout.py src/embedagent/frontend/tui/views.py src/embedagent/frontend/tui/controller.py src/embedagent/frontend/tui/reducer.py src/embedagent/frontend/tui/state.py tests/test_terminal_frontend.py tests/test_tui_activity_timeline.py tests/test_tui_timeline_activities.py tests/test_minimal_shell_contract.py
git commit -m "feat: converge tui on minimal agent workbench"
```

### Task 7: Verify Rendered Desktop And Narrow-Viewport Experience

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
- Modify: `scripts/gui-visual-debug.mjs`
- Modify: `tests/test_gui_smoke_contract.py`
- Generated: `src/embedagent/frontend/gui/static/*`

- [ ] **Step 1: Define retained core visual scenarios**

Replace broad workbench-first fixtures with these required scenario ids: `empty`, `session`, `streaming`, `tool`, `interaction`, `commands`, `recovery`, `narrow`, `optional-terminal`, and `optional-diff`. Each fixture declares the shell descriptor used; core scenarios use no optional contribution records.

- [ ] **Step 2: Add Playwright assertions before screenshots**

For every core scenario assert:

```javascript
assert.equal(await page.locator("[data-agent-shell]").isVisible(), true);
assert.equal(await page.locator("[data-session-timeline]").isVisible(), true);
assert.equal(await page.locator("[data-session-composer]").isVisible(), true);
assert.equal(await page.locator("[data-permanent-right-panel]").count(), 0);
assert.equal(await page.locator("[data-permanent-bottom-drawer]").count(), 0);
```

For viewport `520x720`, assert the session rail is collapsed or overlayed, timeline and composer widths are positive, and no element exceeds the document width. Add `document.elementsFromPoint()` checks for the composer action and overlay buttons so hidden overlaps fail.

- [ ] **Step 3: Run webapp tests and build static assets**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS.

Run from `src/embedagent/frontend/gui/webapp`: `npm run build`

Expected: exit code 0.

- [ ] **Step 4: Run rendered scenarios across required viewports**

Run from `src/embedagent/frontend/gui/webapp`:

`npm run visual:gui -- --scenario empty,session,streaming,tool,interaction,commands,recovery,narrow --viewports 1280x720,900x640,700x640,520x720 --output ../../../../../build/gui-minimal-shell-visual`

Expected: exit code 0, nonblank screenshots for every scenario/viewport, no Playwright assertion failure, and no browser console error.

- [ ] **Step 5: Inspect the generated screenshots**

Verify the actual screenshots show a visible next-state hint where applicable, no nested cards, no clipped controls, no text overlap, stable composer height, readable tool/error hierarchy, and a single-column narrow layout. Record any failure as a test or CSS correction before proceeding; do not commit the build screenshots.

- [ ] **Step 6: Commit visual harness and generated product assets**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs scripts/gui-visual-debug.mjs tests/test_gui_smoke_contract.py src/embedagent/frontend/gui/static
git commit -m "test: cover minimal gui workbench flows"
```

### Task 8: Close Stage 4 With Optionality Gates And Current Docs

**Files:**
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify: `tests/test_current_architecture_boundaries.py`
- Modify: `docs/platform/frontend-gui.md`
- Modify: `docs/platform/frontend-tui.md`
- Modify: `docs/product/composition.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`

- [ ] **Step 1: Add minimal-shell architecture guards**

Assert `App.jsx` imports only `AgentShell`, selectors, and React/runtime bindings; forbid direct imports of right panel, bottom drawer, terminal, source-control, preview, task, plan, or editor components. Assert TUI core layout has no fixed auxiliary region and optional renderer modules are reached only through contribution registries.

- [ ] **Step 2: Run architecture guards**

Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`

Expected: PASS.

- [ ] **Step 3: Update active authorities in place**

Document the exact minimal core, optional contribution behavior, retained t3code tracking policy, and TUI parity. Replace the Stage 4 blocker with the Stage 5 workflow-boundary/structure cleanup blocker.

- [ ] **Step 4: Run the complete required gates**

Run: `uv run python scripts/test-suite.py full`

Expected: PASS.

Run: `uv run --locked python scripts/lint.py`

Expected: PASS.

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS.

Run from `src/embedagent/frontend/gui/webapp`: `npm run build`

Expected: exit code 0.

- [ ] **Step 5: Verify optional features are absent from core composition**

Run: `rg -n "RightPanelTabs|BottomDrawer|TerminalShell|SourceControlPanel|PreviewSurface|Task|Plan|Editor" src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/components/shell src/embedagent/frontend/tui/layout.py`

Expected: no core-composition matches. Generic contribution outlet references are allowed only in `AgentShell.jsx` and must not name feature implementations.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 6: Commit Stage 4 docs and gates**

```bash
git add tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py docs/platform/frontend-gui.md docs/platform/frontend-tui.md docs/product/composition.md docs/current-status.md docs/implementation-roadmap.md
git commit -m "docs: define the minimal agent workbench"
```

## Stage Exit Criteria

- GUI and TUI are fully usable with all optional contributions removed.
- The required core is session navigation, timeline, composer, status, modes/commands, and blocking interactions.
- Files and diffs render inline; terminal, source control, tasks, plan, preview, and editor mount only through registered optional contributions.
- GUI matches retained t3code density, hierarchy, composer, command, interaction, loading, and failure decisions without importing t3code architecture.
- Narrow viewports are one-column, nonblank, and free of clipping or overlap.
- TUI presents the same product operations through a terminal-native four-band layout.
- Architecture guards, rendered scenarios, full Python tests, lint, webapp tests, and webapp build pass.
