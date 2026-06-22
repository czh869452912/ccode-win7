# T3 GUI Parity Shell Design

## Goal

Move the GUI workbench from incremental T3-inspired fixes to a maintainable T3 Code parity architecture for the shell, while keeping Agent Core small, Pi-like, offline-first, and fully separated from GUI display state.

This design covers the next GUI stabilization program:

- restore usable terminal panel behavior;
- make right-panel surface tabs and add menus behave like T3 Code;
- replace the current timeline patchwork with a T3-shaped frontend row model;
- stop context/compact boxes from appearing unpredictably in the middle of the timeline;
- keep all work inside the GUI app shell unless an existing backend app-shell route is explicitly consumed.

## User Direction

The approved direction is to copy T3 Code's interaction and architecture shape directly, not to patch symptoms one at a time.

Engineering adaptation is allowed only where EmbedAgent's product constraints require it:

- Windows 7 compatibility;
- offline deployment;
- Python `>=3.8,<3.9`;
- no runtime Docker, WSL, VS Code, Electron, Node runtime, online service, or T3 package dependency;
- Agent Core remains workflow-neutral and minimal.

## Source References

Use these T3 files as the primary source of truth for GUI behavior and architecture:

- `reference/t3code/apps/web/src/rightPanelStore.ts`
- `reference/t3code/apps/web/src/rightPanelStore.test.ts`
- `reference/t3code/apps/web/src/components/RightPanelTabs.tsx`
- `reference/t3code/apps/web/src/components/ThreadTerminalDrawer.tsx`
- `reference/t3code/apps/web/src/terminalUiStateStore.ts`
- `reference/t3code/apps/web/src/session-logic.ts`
- `reference/t3code/apps/web/src/components/chat/MessagesTimeline.logic.ts`
- `reference/t3code/apps/web/src/components/chat/MessagesTimeline.tsx`

Existing EmbedAgent files to replace or reshape around those references:

- `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
- `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
- `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
- `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTerminalSurface.jsx`
- `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
- `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
- `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`
- `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
- `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
- `src/embedagent/frontend/gui/webapp/src/styles.css`

## Current Root Causes

### Right-Panel Add Menu

The add-surface popup is currently rendered inside `.right-panel-tab-scroll`. That scroll container uses horizontal overflow, so the menu is clipped into the tabbar and can create an unusable scrollbar. T3 renders menu popups as floating UI outside the scroll content.

### Terminal Panel

The GUI has two terminal surfaces: bottom drawer and right-panel surface. Both share terminal runtime state, but the current controller still dispatches legacy inspector state for right-panel terminal actions. This mixes the new T3 surface model with the old inspector tab model.

The bottom drawer is also still a small fixed-height EmbedAgent surface rather than a T3-style terminal drawer/panel shell. The next work must verify whether the reported "terminal panel cannot open" failure is in the bottom drawer path, the right-panel terminal path, or both.

### Timeline And Context Rows

The current T3 timeline projector has grown by adding row kinds for reasoning, compact, command, review, and system notices, but its organization is still not T3's main timeline architecture. Context and compact rows are projected as independent timeline rows, which can make context boxes appear in surprising positions between ordinary message/work rows.

T3's model derives a main row stream from messages, work entries, proposed plans, turn folds, and working state. Settled turn internals fold behind a stable turn fold row. Display semantics live in the frontend row model rather than in backend/Core protocol.

## Architecture Principles

1. **GUI app shell owns display state.** Right-panel surfaces, terminal grouping, menu openness, row expansion, fold state, and visual context placement are frontend-local state.
2. **Agent Core is not changed.** No `QueryEngine`, reducer, workflow package, permission policy, runtime config, transcript, or provider behavior changes are part of this program.
3. **Existing backend app-shell routes may be consumed.** Terminal open/write/clear/restart/close, local file tree, preview, source-control read-only, and session bootstrap routes remain explicit GUI app-shell APIs.
4. **No display truth enters transcript.** GUI surface state and row expansion state must not write `transcript.jsonl`, workflow state, runtime reducers, telemetry, source-control checkpoints, or extension loading state.
5. **T3 architecture shape wins.** When current EmbedAgent patterns conflict with the T3 reference for GUI shell behavior, prefer a small replacement of the GUI-local model over local patches.
6. **No dependency copying.** Copy concepts and component boundaries, not T3's dependency stack. Keep React/CSS/plain JS and existing local test harnesses.

## Design

### 1. Right-Panel Surface Store

`workbench/surfaces.js` should be reshaped to mirror T3's `rightPanelStore.ts` semantics:

- thread/session-scoped surface state;
- `isOpen` / `open`, `activeSurfaceId`, ordered `surfaces`;
- singleton surfaces for `diff`, `files`, `plan`, `source_control`, `settings`, and `diagnostics`;
- resource-specific surfaces for `file`, `preview`, and `terminal`;
- one terminal surface per first terminal id: `terminal:<id>` style in concept, adapted to current id format only where existing tests or persistence require it;
- pure actions for open, activate, close, close others, close to right, close all, open file, open preview, open terminal, split terminal, activate terminal pane, close terminal pane;
- reconciliation helpers for stale file/preview/terminal references.

The model should remove right-panel behavior that exists only to support the old inspector tab pattern.

### 2. Floating Menu Boundary

`RightPanelTabs.jsx` should follow T3's component shape:

- tabbar shell owns horizontal scroll only for tabs;
- add menu and tab context menus render as floating popups outside tab scroll clipping;
- tabs use fixed compact sizing with `shrink: 0`, truncation, and active-state styling;
- add menu remains clickable when there are many panels;
- context actions match T3: close, close others, close to right, close all, plus copy path for file surfaces when implemented;
- empty state offers available local surfaces with disabled reasons where applicable.

Because no new UI library is being added, implement a tiny local floating menu primitive under the GUI webapp. It should compute viewport-safe coordinates from the trigger button, close on outside click/Escape, and never live inside a scroll container that clips it.

### 3. Terminal Drawer And Panel

Create one T3-shaped terminal shell component that can render in two owners:

- bottom drawer owner;
- right-panel owner.

The shared component should consume terminal runtime state and a surface/group descriptor, not Agent Core state. It should support:

- no-session empty state with a new-terminal action;
- one active terminal viewport when unsplit;
- split panes when a right-panel terminal surface has multiple `terminalIds`;
- horizontal and vertical split layout;
- compact action buttons for new, split horizontal, split vertical, clear/restart/close;
- active pane selection;
- close-final-pane behavior that removes the right-panel surface while keeping state consistent;
- bottom drawer behavior that does not automatically open when a right-panel terminal opens, and right-panel behavior that does not automatically open the bottom drawer.

The current terminal rendering remains plain WebView2-compatible React/CSS over the Python stdlib subprocess backend. Do not introduce xterm.js, PTY dependencies, Electron APIs, or runtime Node.

The terminal controller should stop dispatching old inspector state for right-panel terminal actions. Surface activation should be enough.

### 4. Timeline Row Model

`session-runtime/t3-timeline.js` should be rewritten around T3's `deriveMessagesTimelineRows(...)` architecture:

- derive a flat ordered row stream from existing session runtime turn groups;
- keep row kinds focused on `message`, `work`, `turn_fold`, `diff_summary`, `interaction`, `proposed_plan` if needed, and `working`;
- keep reasoning and compact/context details as turn-associated work/commentary metadata unless there is a stable T3-style row reason to surface them;
- fold settled turn internals behind one stable turn fold row;
- never fold running, failed, interrupted, discarded, or active-turn work by default;
- keep the terminal assistant message visible outside a settled fold;
- group consecutive work rows like T3's work log grouping;
- keep active working/thinking state at the end of the stream instead of inserting ad hoc rows in the middle.

Context/compact display should change from "boxes inserted wherever event order happens to put them" to one of two stable placements:

- inside the turn fold body when the compaction/context event belongs to a folded turn;
- as a subdued system row adjacent to the active turn boundary only when it is the latest active context transition.

This is a GUI projection rule only. It must not alter compaction reducers, transcript semantics, or context assembly.

### 5. Timeline Rendering

`TimelineRows.jsx` should become a focused row renderer for the rewritten model:

- message rows;
- work groups;
- turn fold summary/body;
- changed files summary;
- interaction row;
- working row;
- stable compact/context display only through the rules above.

`WorkRow.jsx` should remain focused on one tool/work entry and structured details. It should not become a generic system/context renderer.

`Timeline.jsx` should stop carrying a parallel legacy grouped renderer once the T3 row renderer has equivalent behavior. The product should have one official GUI timeline rendering path.

### 6. Layout And Scroll Containers

The workbench CSS should be tightened around explicit scroll regions:

- tab scroll containers scroll only horizontally and do not contain popups;
- right-panel body, terminal panel, timeline, file tree, and bottom drawer each have explicit `min-height: 0` and controlled overflow;
- bottom drawer height should become state-driven or otherwise T3-like, not a hidden fixed value that ignores `bottomDrawer.height`;
- responsive layout should keep timeline/composer/right panel usable at narrow widths without overlapping controls.

No marketing-style layout or decorative redesign is part of this work.

## Data Flow

1. Existing backend/Core emits session bootstrap, snapshots, WebSocket events, terminal events, file tree data, preview state, and source-control read-only data.
2. `App.jsx` keeps bridging those app-shell APIs into GUI-local reducers.
3. `workbench/surfaces.js` owns right-panel and terminal grouping descriptors.
4. `terminal/terminal-state.js` owns terminal runtime summaries, buffers, and active terminal id.
5. The terminal controller coordinates existing backend routes with GUI-local surface actions.
6. `t3-timeline.js` derives display rows from existing frontend session runtime groups.
7. React components render display rows and surfaces from GUI-local models.
8. No GUI display state is sent back to Agent Core or transcript history.

## Implementation Slices

### Slice 1: Right-Panel Floating Menus And Surface Store Alignment

Replace clipped tabbar menu behavior with a T3-shaped floating menu boundary and align surface reducer semantics with `rightPanelStore.ts`.

Success criteria:

- add menu is clickable with many surfaces open;
- popup is not clipped by the tabbar;
- surface close actions match T3 tests;
- no old inspector tab dependency is required for right-panel activation.

### Slice 2: Terminal Drawer/Panel Rebuild

Rebuild terminal UI around one T3-shaped terminal shell with bottom drawer and right-panel owners.

Success criteria:

- bottom terminal opens reliably from the header/drawer controls;
- right-panel Terminal opens a terminal surface without opening the drawer;
- split horizontal and split vertical work in the right panel;
- closing panes and final panes matches T3 behavior;
- no right-panel terminal action dispatches legacy inspector state.

### Slice 3: T3 Timeline Row Model Replacement

Replace the current patched timeline projection with a T3-shaped derivation and one renderer path.

Success criteria:

- settled turns fold behind stable "Worked for ..." rows;
- active/running/failed/interrupted work remains visible;
- terminal assistant message stays visible outside settled folds;
- context/compact boxes no longer jump through the middle of the timeline;
- reasoning/thinking remains visible only in stable turn-associated placement;
- legacy grouped renderer is removed or made unreachable after equivalent coverage lands.

### Slice 4: Layout And Visual QA

Harden scroll regions, tab overflow, drawer sizing, and narrow-width behavior.

Success criteria:

- no horizontal page overflow in normal desktop and narrow viewport scenarios;
- tabbar overflow does not make popups unusable;
- timeline/composer/right panel/bottom drawer remain independently scrollable;
- visual debug scenarios cover panel overflow, terminal, timeline, and responsive widths.

## Testing Strategy

### Webapp Model Tests

Add or replace tests under `src/embedagent/frontend/gui/webapp/test/`:

- right-panel surface store mirrors T3 close/open behavior;
- add menu source test verifies the popup is not rendered inside the tab scroll element;
- terminal controller no longer dispatches `set_inspector` for right-panel terminal paths;
- terminal split/activate/close behavior follows T3 `rightPanelStore.test.ts`;
- timeline projector folds settled turns and leaves active/error/interrupted work visible;
- compact/context placement is stable and turn-associated;
- timeline renderer handles every exported row kind.

### Visual Debug Scenarios

Extend `scripts/gui-visual-debug.mjs` scenarios:

- many right-panel tabs plus add menu open;
- right-panel terminal unsplit/split-horizontal/split-vertical;
- bottom terminal drawer open;
- timeline with settled fold, active work, failed work, compact/context events;
- narrow and zoom-like viewport sizes.

### Backend Tests

Run focused Python tests only when existing backend terminal or GUI app-shell routes are touched:

```bash
uv run pytest tests/test_gui_terminal_api.py tests/test_gui_terminal_service.py tests/test_gui_app_shell.py -v
```

### Webapp Verification

For each slice:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Rebuild static assets whenever webapp source changes.

## Documentation

After implementation, update durable docs that track GUI app-shell behavior:

- `docs/modules/frontend-gui.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

Global Agent Core architecture docs should not need semantic changes unless implementation unexpectedly changes a protocol or backend boundary. If that happens, stop and re-review the design before proceeding.

## Non-Goals

- No Agent Core changes.
- No backend-enriched display timeline protocol.
- No transcript, reducer, permission, workflow package, provider, or extension-loading changes.
- No online browser automation or web search system.
- No source-control staging, commit, push, pull, checkpoint mutation, or PR workflow.
- No T3 dependency imports, Tailwind migration, Electron dependency, xterm.js, runtime Node, Docker, WSL, or VS Code requirement.
- No new public plugin marketplace or remote extension behavior.

## Risks And Mitigations

### Risk: "Copy T3" Becomes Dependency Creep

Mitigation: copy architecture shape and behavior only. Keep the dependency surface unchanged.

### Risk: Timeline Projection Becomes Second Session Truth

Mitigation: rows are derived display state only. They do not persist, execute, authorize, or select runtime context.

### Risk: Terminal UI Rebuild Leaks Into Core

Mitigation: terminal remains GUI app-shell hosted over existing backend terminal routes. No Agent Core route, tool, permission, transcript, or workflow state changes.

### Risk: Too Much Changes At Once

Mitigation: implement in the four slices above. Each slice should leave the product runnable and testable.

## Approval

The user approved the direction on 2026-06-22: proceed toward a maintainable T3 Code copy rather than symptom patches, while keeping Agent Core separate and minimal.
