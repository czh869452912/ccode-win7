# T3 Right Panel Surface Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed GUI right-panel inspector tab strip with a T3 Code-style open surface tab model for `diff`, `files`, `terminal`, and `plan`.

**Architecture:** Keep the feature entirely in the GUI app shell. `workbench/surfaces.js` owns pure GUI-local surface state, `RightPanelTabs.jsx` renders the T3-style tab chrome, and `App.jsx` maps the active surface to existing local panes without changing Agent Core, transcript truth, workflow state, permissions, or backend contracts.

**Tech Stack:** React 18, plain JavaScript modules, existing Node assert helper tests, existing CSS, existing GUI backend routes. No new runtime dependencies.

---

## File Structure

- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  Owns T3-style right-panel surface records, active surface selection, close behavior, and bottom drawer compatibility.
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  Adds red/green coverage for right-panel surface open, activate, close, close others, close to right, and close all.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
  Replaces the old fixed right-panel tab list with T3-style open surface tabs, add button, close controls, and empty state.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
  Exports the existing `TerminalSurface` so the same GUI-local terminal display can be hosted in the right panel.
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/FilesSurface.jsx`
  Hosts the existing workspace file tree behavior in the right panel.
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  Maps active right-panel surfaces to `Inspector`, `FilesSurface`, or `TerminalSurface`.
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
  Passes surface list props into `RightPanelTabs`, dispatches T3-style surface actions, and renders `RightPanelSurfaceBody`.
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
  Keeps `inspectorTab` compatible with opened right-panel surfaces and opens a `diff` surface when diffs arrive.
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
  Keeps command palette actions routed to surface opening while preserving existing command names.
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js`
  Maps `mod+1`, `mod+2`, and `mod+3` to T3-style `files`, `terminal`, and `diff` surfaces.
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
  Restyles the right panel tabbar, empty state, add menu, file surface, and terminal-in-panel host using existing tokens.
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  Updates source assertions from old fixed tabs to T3-style surface tabs.
- Modify: `docs/development-tracker.md`
  Adds the completed GUI T3 right-panel surface-tabs slice.
- Modify: `docs/design-change-log.md`
  Adds a DC entry for the GUI-local T3 surface tab model.

---

## Task 1: T3 Right-Panel Surface State

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`

- [x] **Step 1: Write the failing reducer tests**

Replace the right-panel surface section in `runWorkbenchStateTests()` with these assertions, leaving command/keybinding assertions below it in place:

```js
  assert.deepEqual(RIGHT_PANEL_SURFACES, ["diff", "files", "terminal", "plan"]);
  assert.equal(BOTTOM_DRAWER_SURFACES.includes("terminal"), true);
  assert.equal(BOTTOM_DRAWER_SURFACES.includes("run_output"), true);

  const initial = createWorkbenchState();
  assert.equal(initial.rightPanel.open, true);
  assert.equal(initial.rightPanel.activeSurfaceId, null);
  assert.equal(initial.rightPanel.activeKind, "");
  assert.deepEqual(initial.rightPanel.surfaces, []);
  assert.equal(initial.bottomDrawer.open, false);

  const withFiles = openSurface(initial, {
    placement: "right",
    kind: "files",
    title: "Files",
  });
  assert.notEqual(withFiles, initial);
  assert.equal(withFiles.rightPanel.open, true);
  assert.equal(withFiles.rightPanel.activeKind, "files");
  assert.equal(withFiles.rightPanel.activeSurfaceId, "right:files");
  assert.equal(withFiles.rightPanel.surfaces.length, 1);
  assert.equal(withFiles.rightPanel.surfaces[0].id, "right:files");

  const withDiff = openSurface(withFiles, {
    placement: "right",
    kind: "diff",
    title: "Diff",
    resourceId: "current",
  });
  assert.equal(withDiff.rightPanel.activeKind, "diff");
  assert.equal(withDiff.rightPanel.activeSurfaceId, "right:diff:current");
  assert.deepEqual(withDiff.rightPanel.surfaces.map((surface) => surface.kind), ["files", "diff"]);

  const reusedDiff = openSurface(withDiff, {
    placement: "right",
    kind: "diff",
    title: "Diff",
    resourceId: "current",
  });
  assert.equal(reusedDiff.rightPanel.surfaces.length, 2);
  assert.equal(reusedDiff.rightPanel.activeSurfaceId, "right:diff:current");

  const activatedFiles = activateSurface(reusedDiff, {
    placement: "right",
    surfaceId: "right:files",
  });
  assert.equal(activatedFiles.rightPanel.activeKind, "files");
  assert.equal(activatedFiles.rightPanel.activeSurfaceId, "right:files");

  const withTerminal = openSurface(activatedFiles, {
    placement: "right",
    kind: "terminal",
    title: "Terminal",
    resourceId: "terminal-1",
  });
  const withPlan = openSurface(withTerminal, {
    placement: "right",
    kind: "plan",
    title: "Plan",
  });
  assert.deepEqual(withPlan.rightPanel.surfaces.map((surface) => surface.kind), [
    "files",
    "diff",
    "terminal",
    "plan",
  ]);

  const closedPlan = closeSurface(withPlan, {
    placement: "right",
    surfaceId: "right:plan",
  });
  assert.equal(closedPlan.rightPanel.activeKind, "terminal");
  assert.equal(closedPlan.rightPanel.activeSurfaceId, "right:terminal:terminal-1");

  const onlyTerminal = closeOtherSurfaces(withPlan, {
    placement: "right",
    surfaceId: "right:terminal:terminal-1",
  });
  assert.deepEqual(onlyTerminal.rightPanel.surfaces.map((surface) => surface.kind), ["terminal"]);
  assert.equal(onlyTerminal.rightPanel.activeKind, "terminal");

  const leftPair = closeSurfacesToRight(withPlan, {
    placement: "right",
    surfaceId: "right:diff:current",
  });
  assert.deepEqual(leftPair.rightPanel.surfaces.map((surface) => surface.kind), ["files", "diff"]);
  assert.equal(leftPair.rightPanel.activeKind, "diff");

  const emptyRight = closeAllSurfaces(withPlan, { placement: "right" });
  assert.deepEqual(emptyRight.rightPanel.surfaces, []);
  assert.equal(emptyRight.rightPanel.activeSurfaceId, null);
  assert.equal(emptyRight.rightPanel.activeKind, "");
  assert.equal(emptyRight.rightPanel.open, true);

  const withRunOutput = openSurface(withFiles, {
    sessionId: "sess-1",
    placement: "bottom",
    kind: "run_output",
    title: "Build Output",
  });
  assert.equal(withRunOutput.bottomDrawer.open, true);
  assert.equal(withRunOutput.bottomDrawer.activeKind, "run_output");
  assert.equal(withRunOutput.surfacesBySession["sess-1"].bottom[0].kind, "run_output");
```

Update the imports at the top of `workbench-state.test.mjs`:

```js
import {
  BOTTOM_DRAWER_SURFACES,
  RIGHT_PANEL_SURFACES,
  activateSurface,
  closeAllSurfaces,
  closeOtherSurfaces,
  closeSurface,
  closeSurfacesToRight,
  createWorkbenchState,
  openSurface,
  reduceWorkbenchState,
} from "../src/workbench/surfaces.js";
```

- [x] **Step 2: Run the focused test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
node test/run-tests.mjs
```

Expected: FAIL with an assertion showing the old right-panel defaults, or an import error for `closeOtherSurfaces`, `closeSurfacesToRight`, or `closeAllSurfaces`.

- [x] **Step 3: Implement the surface reducer**

In `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`, replace the old right-panel surface implementation with this model while keeping bottom drawer compatibility:

```js
export const RIGHT_PANEL_SURFACES = ["diff", "files", "terminal", "plan"];
export const BOTTOM_DRAWER_SURFACES = ["terminal", "run_output", "logs"];

const DEFAULT_SESSION_KEY = "__global__";

function normalizeSessionId(sessionId) {
  const value = String(sessionId || "").trim();
  return value || DEFAULT_SESSION_KEY;
}

function normalizePlacement(placement) {
  return placement === "bottom" ? "bottom" : "right";
}

function defaultActiveKind(placement) {
  return placement === "bottom" ? "run_output" : "";
}

function allowedKinds(placement) {
  return placement === "bottom" ? BOTTOM_DRAWER_SURFACES : RIGHT_PANEL_SURFACES;
}

function surfaceIdFor(input) {
  const placement = normalizePlacement(input && input.placement);
  const kind = String((input && input.kind) || defaultActiveKind(placement));
  const resourceId = String((input && input.resourceId) || "");
  return resourceId ? `${placement}:${kind}:${resourceId}` : `${placement}:${kind}`;
}

function makeSurface(input) {
  const placement = normalizePlacement(input && input.placement);
  const kind = String((input && input.kind) || defaultActiveKind(placement));
  return {
    id: String((input && input.surfaceId) || surfaceIdFor(input)),
    placement,
    kind,
    title: String((input && input.title) || titleForSurfaceKind(kind)),
    resourceId: String((input && input.resourceId) || ""),
    filePath: String((input && input.filePath) || ""),
    terminalId: String((input && input.terminalId) || (input && input.resourceId) || ""),
  };
}

export function titleForSurfaceKind(kind) {
  switch (kind) {
    case "diff":
      return "Diff";
    case "files":
      return "Files";
    case "terminal":
      return "Terminal";
    case "plan":
      return "Plan";
    default:
      return String(kind || "");
  }
}

function emptySessionSurfaces() {
  return {
    right: [],
    bottom: [],
  };
}

function sessionSurfaces(state, sessionId) {
  const key = normalizeSessionId(sessionId);
  return state.surfacesBySession[key] || emptySessionSurfaces();
}

function upsertSurface(items, nextSurface) {
  const existingIndex = items.findIndex((item) => item.id === nextSurface.id);
  if (existingIndex < 0) {
    return items.concat(nextSurface);
  }
  return items.map((item, index) => (index === existingIndex ? nextSurface : item));
}

function removeSurface(items, surfaceId) {
  return items.filter((item) => item.id !== surfaceId);
}

function activeSurfaceFrom(items, activeSurfaceId) {
  return items.find((item) => item.id === activeSurfaceId) || null;
}

function activateRightPanelSurface(panel, surface) {
  return {
    ...panel,
    open: true,
    activeKind: surface ? surface.kind : "",
    activeSurfaceId: surface ? surface.id : null,
  };
}

function nextActiveAfterClose(items, closedIndex) {
  if (items.length === 0) return null;
  const boundedIndex = Math.max(0, Math.min(closedIndex, items.length - 1));
  return items[boundedIndex] || items[items.length - 1] || null;
}

export function createWorkbenchState() {
  return {
    sidebar: {
      activeSection: "threads",
      projectSection: "files",
    },
    rightPanel: {
      open: true,
      activeKind: "",
      activeSurfaceId: null,
      surfaces: [],
      width: 320,
    },
    bottomDrawer: {
      open: false,
      activeKind: "run_output",
      height: 220,
    },
    commandPalette: {
      open: false,
      query: "",
      selectedIndex: 0,
    },
    layout: {
      density: "compact",
      narrow: false,
    },
    surfacesBySession: {},
  };
}

export function getSessionSurfaces(state, sessionId) {
  return sessionSurfaces(state || createWorkbenchState(), sessionId);
}

export function openSurface(state, input) {
  const current = state || createWorkbenchState();
  const surface = makeSurface(input || {});
  const placement = normalizePlacement(surface.placement);
  if (!allowedKinds(placement).includes(surface.kind)) {
    return current;
  }
  if (placement === "right") {
    const surfaces = upsertSurface(current.rightPanel.surfaces || [], surface);
    return {
      ...current,
      rightPanel: activateRightPanelSurface(
        { ...current.rightPanel, surfaces },
        surface,
      ),
    };
  }
  const key = normalizeSessionId(input && input.sessionId);
  const existing = sessionSurfaces(current, key);
  const nextSessionSurfaces = {
    ...existing,
    bottom: upsertSurface(existing.bottom, surface),
  };
  return {
    ...current,
    surfacesBySession: {
      ...current.surfacesBySession,
      [key]: nextSessionSurfaces,
    },
    bottomDrawer: { ...current.bottomDrawer, open: true, activeKind: surface.kind },
  };
}

export function activateSurface(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  if (placement === "bottom") {
    const kind = String((input && input.kind) || defaultActiveKind(placement));
    if (!allowedKinds(placement).includes(kind)) return current;
    return {
      ...current,
      bottomDrawer: { ...current.bottomDrawer, open: true, activeKind: kind },
    };
  }
  const surfaceId = String((input && input.surfaceId) || "");
  const existing = surfaceId
    ? activeSurfaceFrom(current.rightPanel.surfaces || [], surfaceId)
    : null;
  if (existing) {
    return {
      ...current,
      rightPanel: activateRightPanelSurface(current.rightPanel, existing),
    };
  }
  return openSurface(current, {
    placement: "right",
    kind: input && input.kind,
    title: input && input.title,
    resourceId: input && input.resourceId,
    filePath: input && input.filePath,
    terminalId: input && input.terminalId,
  });
}

export function closeSurface(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  const surface = makeSurface(input || {});
  if (placement === "bottom") {
    const key = normalizeSessionId(input && input.sessionId);
    const existing = sessionSurfaces(current, key);
    const nextItems = removeSurface(existing.bottom, surface.id);
    const nextSessionSurfaces = { ...existing, bottom: nextItems };
    return {
      ...current,
      surfacesBySession: {
        ...current.surfacesBySession,
        [key]: nextSessionSurfaces,
      },
      bottomDrawer: {
        ...current.bottomDrawer,
        open: nextItems.length > 0,
        activeKind: nextItems.length > 0 ? nextItems[0].kind : defaultActiveKind(placement),
      },
    };
  }
  const items = current.rightPanel.surfaces || [];
  const closedIndex = Math.max(0, items.findIndex((item) => item.id === surface.id));
  const nextItems = removeSurface(items, surface.id);
  const shouldReplaceActive = current.rightPanel.activeSurfaceId === surface.id;
  const nextActive = shouldReplaceActive
    ? nextActiveAfterClose(nextItems, closedIndex)
    : activeSurfaceFrom(nextItems, current.rightPanel.activeSurfaceId);
  return {
    ...current,
    rightPanel: activateRightPanelSurface(
      { ...current.rightPanel, surfaces: nextItems },
      nextActive,
    ),
  };
}

export function closeOtherSurfaces(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  if (placement !== "right") return current;
  const surfaceId = String((input && input.surfaceId) || "");
  const active = activeSurfaceFrom(current.rightPanel.surfaces || [], surfaceId);
  if (!active) return current;
  return {
    ...current,
    rightPanel: activateRightPanelSurface(
      { ...current.rightPanel, surfaces: [active] },
      active,
    ),
  };
}

export function closeSurfacesToRight(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  if (placement !== "right") return current;
  const surfaceId = String((input && input.surfaceId) || "");
  const items = current.rightPanel.surfaces || [];
  const index = items.findIndex((item) => item.id === surfaceId);
  if (index < 0) return current;
  const nextItems = items.slice(0, index + 1);
  const active = activeSurfaceFrom(nextItems, surfaceId) || nextItems[nextItems.length - 1] || null;
  return {
    ...current,
    rightPanel: activateRightPanelSurface(
      { ...current.rightPanel, surfaces: nextItems },
      active,
    ),
  };
}

export function closeAllSurfaces(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  if (placement !== "right") return current;
  return {
    ...current,
    rightPanel: activateRightPanelSurface(
      { ...current.rightPanel, surfaces: [] },
      null,
    ),
  };
}

export function reduceWorkbenchState(state, action) {
  const current = state || createWorkbenchState();
  switch (action.type) {
    case "workbench_surface_opened":
      return openSurface(current, action);
    case "workbench_surface_activated":
      return activateSurface(current, action);
    case "workbench_surface_closed":
      return closeSurface(current, action);
    case "workbench_surface_close_others":
      return closeOtherSurfaces(current, action);
    case "workbench_surface_close_to_right":
      return closeSurfacesToRight(current, action);
    case "workbench_surface_close_all":
      return closeAllSurfaces(current, action);
    case "workbench_command_palette_opened":
      return {
        ...current,
        commandPalette: { ...current.commandPalette, open: true, query: "", selectedIndex: 0 },
      };
    case "workbench_command_palette_closed":
      return {
        ...current,
        commandPalette: { ...current.commandPalette, open: false, query: "", selectedIndex: 0 },
      };
    case "workbench_command_palette_query_changed":
      return {
        ...current,
        commandPalette: {
          ...current.commandPalette,
          query: String(action.query || ""),
          selectedIndex: 0,
        },
      };
    case "workbench_right_panel_toggled":
      return {
        ...current,
        rightPanel: { ...current.rightPanel, open: !current.rightPanel.open },
      };
    case "workbench_bottom_drawer_toggled":
      return {
        ...current,
        bottomDrawer: { ...current.bottomDrawer, open: !current.bottomDrawer.open },
      };
    default:
      return current;
  }
}
```

- [x] **Step 4: Run the focused test to verify it passes**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
node test/run-tests.mjs
```

Expected: remaining failures may come from `run-tests.mjs` source assertions that still expect the old fixed right-panel tab component. Reducer assertions from `runWorkbenchStateTests()` should pass.

- [x] **Step 5: Commit Task 1**

```bash
git add src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs
git commit -m "gui: add t3 right panel surface state"
```

---

## Task 2: T3 Right-Panel Tab Chrome

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`

- [x] **Step 1: Write the failing source assertions**

In `run-tests.mjs`, replace the current `rightPanelTabsSource` assertions with:

```js
  const rightPanelTabsSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "RightPanelTabs.jsx"),
    "utf8",
  );
  assert.equal(rightPanelTabsSource.includes("right-panel-empty-state"), true);
  assert.equal(rightPanelTabsSource.includes("right-panel-add-surface"), true);
  assert.equal(rightPanelTabsSource.includes("onCloseOtherSurfaces"), true);
  assert.equal(rightPanelTabsSource.includes("onCloseSurfacesToRight"), true);
  assert.equal(rightPanelTabsSource.includes("onCloseAllSurfaces"), true);
  assert.equal(rightPanelTabsSource.includes("RIGHT_PANEL_SURFACES.map"), false);
  assert.equal(rightPanelTabsSource.includes("source_control: \"Source\""), false);
  assert.equal(rightPanelTabsSource.includes("todos"), false);
```

- [x] **Step 2: Run the focused test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
node test/run-tests.mjs
```

Expected: FAIL because `RightPanelTabs.jsx` still maps `RIGHT_PANEL_SURFACES` as fixed inspector tabs.

- [x] **Step 3: Replace `RightPanelTabs.jsx` with T3-style surface tabs**

Use this component:

```jsx
import React from "react";
import { RIGHT_PANEL_SURFACES, titleForSurfaceKind } from "../../workbench/surfaces.js";

const SURFACE_COPY = {
  diff: {
    icon: "D",
    label: "Diff",
    description: "Review local changes.",
  },
  files: {
    icon: "F",
    label: "Files",
    description: "Browse workspace files.",
  },
  terminal: {
    icon: "T",
    label: "Terminal",
    description: "Use a shell in this workspace.",
  },
  plan: {
    icon: "P",
    label: "Plan",
    description: "Inspect the current plan.",
  },
};

function surfaceTitle(surface) {
  if (!surface) return "";
  if (surface.title) return surface.title;
  return titleForSurfaceKind(surface.kind);
}

function SurfaceIcon({ kind }) {
  const copy = SURFACE_COPY[kind] || { icon: "S" };
  return <span className="right-panel-surface-icon" aria-hidden="true">{copy.icon}</span>;
}

function SurfaceTabMenu({
  surface,
  onCloseOtherSurfaces,
  onCloseSurfacesToRight,
  onCloseAllSurfaces,
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <span className="right-panel-tab-menu">
      <button
        type="button"
        className="right-panel-tab-menu-button"
        aria-label={`Surface actions for ${surfaceTitle(surface)}`}
        onClick={(event) => {
          event.stopPropagation();
          setOpen((value) => !value);
        }}
      >
        ...
      </button>
      {open ? (
        <span className="right-panel-tab-menu-popup" role="menu">
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onCloseOtherSurfaces(surface);
            }}
          >
            Close others
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onCloseSurfacesToRight(surface);
            }}
          >
            Close to the right
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onCloseAllSurfaces();
            }}
          >
            Close all
          </button>
        </span>
      ) : null}
    </span>
  );
}

function RightPanelEmptyState({ onAddSurface }) {
  return (
    <div className="right-panel-empty-state" data-testid="right-panel-empty-state">
      <div className="right-panel-empty-copy">
        <h3>Open a surface</h3>
        <p>Choose what to show in the right panel.</p>
      </div>
      <div className="right-panel-empty-grid">
        {RIGHT_PANEL_SURFACES.map((kind) => {
          const copy = SURFACE_COPY[kind];
          return (
            <button
              key={kind}
              type="button"
              className="right-panel-empty-card"
              onClick={() => onAddSurface(kind)}
              data-testid={`right-panel-empty-surface--${kind}`}
            >
              <SurfaceIcon kind={kind} />
              <span>{copy.label}</span>
              <small>{copy.description}</small>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function RightPanelTabs({
  surfaces,
  activeSurfaceId,
  onActivateSurface,
  onCloseSurface,
  onCloseOtherSurfaces,
  onCloseSurfacesToRight,
  onCloseAllSurfaces,
  onAddSurface,
  children,
}) {
  const items = Array.isArray(surfaces) ? surfaces : [];
  const activeSurface = items.find((surface) => surface.id === activeSurfaceId) || null;
  return (
    <aside className="right-panel" role="complementary" aria-label="Right panel" data-testid="right-panel">
      <div className="right-panel-tabs" role="tablist" data-testid="right-panel-surface-tabs">
        <div className="right-panel-tab-scroll">
          {items.map((surface) => {
            const active = surface.id === activeSurfaceId;
            const title = surfaceTitle(surface);
            return (
              <div
                key={surface.id}
                className={`right-panel-surface-tab${active ? " active" : ""}`}
                data-active-tab={active ? "true" : "false"}
                data-testid={`right-panel-surface-tab--${surface.kind}`}
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={active}
                  className="right-panel-surface-tab-main"
                  title={title}
                  onClick={() => onActivateSurface(surface)}
                >
                  <SurfaceIcon kind={surface.kind} />
                  <span>{title}</span>
                </button>
                <SurfaceTabMenu
                  surface={surface}
                  onCloseOtherSurfaces={onCloseOtherSurfaces}
                  onCloseSurfacesToRight={onCloseSurfacesToRight}
                  onCloseAllSurfaces={onCloseAllSurfaces}
                />
                <button
                  type="button"
                  className="right-panel-tab-close"
                  aria-label={`Close ${title}`}
                  onClick={() => onCloseSurface(surface)}
                >
                  x
                </button>
              </div>
            );
          })}
          <button
            type="button"
            className="right-panel-add-surface"
            aria-label="Add panel surface"
            onClick={() => onAddSurface("files")}
            title="Add panel surface"
          >
            +
          </button>
        </div>
      </div>
      <div className="right-panel-body">
        {activeSurface ? children : <RightPanelEmptyState onAddSurface={onAddSurface} />}
      </div>
    </aside>
  );
}
```

- [x] **Step 4: Run the focused test to verify it passes**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
node test/run-tests.mjs
```

Expected: component source assertions pass. App integration assertions may fail because `App.jsx` still passes old props.

- [x] **Step 5: Commit Task 2**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "gui: render t3 right panel surface tabs"
```

---

## Task 3: Right-Panel Surface Bodies

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/FilesSurface.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [x] **Step 1: Write failing source assertions for body components**

Add these assertions after the `bottomDrawerSource` assertions in `run-tests.mjs`:

```js
  assert.equal(bottomDrawerSource.includes("export function TerminalSurface"), true);

  const filesSurfaceSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "FilesSurface.jsx"),
    "utf8",
  );
  assert.equal(filesSurfaceSource.includes("react-arborist"), true);
  assert.equal(filesSurfaceSource.includes('data-testid="right-panel-files-surface"'), true);
  assert.equal(filesSurfaceSource.includes("onLoadFileChildren"), true);

  const rightPanelSurfaceBodySource = fs.readFileSync(
    webappSourcePath("components", "workbench", "RightPanelSurfaceBody.jsx"),
    "utf8",
  );
  assert.equal(rightPanelSurfaceBodySource.includes("FilesSurface"), true);
  assert.equal(rightPanelSurfaceBodySource.includes("TerminalSurface"), true);
  assert.equal(rightPanelSurfaceBodySource.includes("Inspector"), true);
  assert.equal(rightPanelSurfaceBodySource.includes("surface.kind === \"terminal\""), true);
```

- [x] **Step 2: Run the focused test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
node test/run-tests.mjs
```

Expected: FAIL because `FilesSurface.jsx` and `RightPanelSurfaceBody.jsx` do not exist and `TerminalSurface` is not exported.

- [x] **Step 3: Export `TerminalSurface` from `BottomDrawer.jsx`**

Change:

```jsx
function TerminalSurface({ terminal, onNew, onSelect, onSend, onClear, onRestart, onClose }) {
```

to:

```jsx
export function TerminalSurface({ terminal, onNew, onSelect, onSend, onClear, onRestart, onClose }) {
```

- [x] **Step 4: Create `FilesSurface.jsx`**

Add `src/embedagent/frontend/gui/webapp/src/components/workbench/FilesSurface.jsx`:

```jsx
import React from "react";
import { Tree } from "react-arborist";

export default function FilesSurface({
  fileTree,
  treeHeight,
  onOpenFile,
  onLoadFileChildren,
}) {
  const nodes = Array.isArray(fileTree) ? fileTree : [];
  return (
    <div className="right-panel-files-surface" data-testid="right-panel-files-surface">
      <div className="right-panel-files-header">
        <strong>Files</strong>
        <span>{nodes.length}</span>
      </div>
      <Tree
        data={nodes}
        width={320}
        height={treeHeight || 640}
        rowHeight={30}
        indent={18}
        onActivate={(node) => {
          if (node.data.kind === "file") {
            onOpenFile(node.data.path);
          } else if (!node.data.childrenLoaded && node.data.hasChildren) {
            onLoadFileChildren(node.data.path);
          }
        }}
      >
        {({ node, style }) => (
          <div
            style={style}
            className={`tree-row ${node.data.kind}`}
            role="treeitem"
            aria-expanded={node.data.kind === "dir" ? node.isOpen : undefined}
            onClick={() => {
              if (node.data.kind === "dir") {
                if (!node.data.childrenLoaded && node.data.hasChildren) {
                  onLoadFileChildren(node.data.path);
                }
                node.toggle();
              } else {
                onOpenFile(node.data.path);
              }
            }}
            data-testid={`right-panel-file-node--${node.data.path}`}
          >
            <span className="tree-icon" aria-hidden="true">
              {node.data.kind === "dir" ? (node.isOpen ? "v" : ">") : "."}
            </span>
            <span className="tree-label">{node.data.name}</span>
          </div>
        )}
      </Tree>
    </div>
  );
}
```

- [x] **Step 5: Create `RightPanelSurfaceBody.jsx`**

Add `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`:

```jsx
import React from "react";
import Inspector from "../Inspector.jsx";
import FilesSurface from "./FilesSurface.jsx";
import { TerminalSurface } from "./BottomDrawer.jsx";

function inspectorKindForSurface(surface) {
  if (!surface) return "";
  if (surface.kind === "diff") return "diff";
  if (surface.kind === "plan") return "plan";
  return surface.kind;
}

export default function RightPanelSurfaceBody({
  surface,
  inspectorProps,
  fileTree,
  treeHeight,
  onOpenFile,
  onLoadFileChildren,
  terminal,
  onTerminalNew,
  onTerminalSelect,
  onTerminalSend,
  onTerminalClear,
  onTerminalRestart,
  onTerminalClose,
}) {
  if (!surface) {
    return null;
  }
  if (surface.kind === "files") {
    return (
      <FilesSurface
        fileTree={fileTree}
        treeHeight={treeHeight}
        onOpenFile={onOpenFile}
        onLoadFileChildren={onLoadFileChildren}
      />
    );
  }
  if (surface.kind === "terminal") {
    return (
      <TerminalSurface
        terminal={terminal}
        onNew={onTerminalNew}
        onSelect={onTerminalSelect}
        onSend={onTerminalSend}
        onClear={onTerminalClear}
        onRestart={onTerminalRestart}
        onClose={onTerminalClose}
      />
    );
  }
  return (
    <Inspector
      {...inspectorProps}
      inspectorTab={inspectorKindForSurface(surface)}
      showTabs={false}
    />
  );
}
```

- [x] **Step 6: Run the focused test to verify it passes**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
node test/run-tests.mjs
```

Expected: body source assertions pass. App integration assertions may still fail until Task 4.

- [x] **Step 7: Commit Task 3**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/FilesSurface.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "gui: add right panel surface bodies"
```

---

## Task 4: App Wiring And Command Routing

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`

- [x] **Step 1: Write failing App/source assertions**

Update `run-tests.mjs` App source assertions:

```js
  assert.equal(appSource.includes("RightPanelSurfaceBody"), true);
  assert.equal(appSource.includes("activeRightPanelSurface"), true);
  assert.equal(appSource.includes("workbench_surface_close_others"), true);
  assert.equal(appSource.includes("workbench_surface_close_to_right"), true);
  assert.equal(appSource.includes("workbench_surface_close_all"), true);
  assert.equal(appSource.includes("showTabs={false}"), false);
  assert.equal(appSource.includes("activeKind={state.inspectorTab}"), false);
```

Update the reducer assertions around `diff_surface_opened`:

```js
  assert.equal(diffSurfaceState.inspectorTab, "diff");
  assert.equal(diffSurfaceState.workbench.rightPanel.activeKind, "diff");
  assert.equal(diffSurfaceState.workbench.rightPanel.activeSurfaceId, "right:diff:current");
```

Update keybinding assertions in `workbench-state.test.mjs`:

```js
  assert.equal(DEFAULT_KEYBINDINGS.some((item) => item.key === "mod+1" && item.commandId === "surface.files"), true);
  assert.equal(DEFAULT_KEYBINDINGS.some((item) => item.key === "mod+2" && item.commandId === "surface.terminal"), true);
  assert.equal(DEFAULT_KEYBINDINGS.some((item) => item.key === "mod+3" && item.commandId === "surface.diff"), true);
```

- [x] **Step 2: Run the focused test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
node test/run-tests.mjs
```

Expected: FAIL because `App.jsx` still renders `Inspector` directly under old `RightPanelTabs` props.

- [x] **Step 3: Update command and keybinding surface list**

In `commands.js`, replace fixed inspector-oriented surface commands with:

```js
  { id: "surface.files", group: "surface", label: "Open Files", slash: "/workspace", surface: "files", visibleWhen: "always" },
  { id: "surface.terminal", group: "surface", label: "Open Terminal", slash: "", surface: "terminal", visibleWhen: "has_session" },
  { id: "surface.diff", group: "surface", label: "Open Diff", slash: "/diff", surface: "diff", visibleWhen: "always", keywords: ["git", "changes", "diff"] },
  { id: "surface.plan", group: "surface", label: "Open Plan", slash: "/plan", surface: "plan", visibleWhen: "always" },
```

Keep app, session, message, mode, workspace, workflow, view, and drawer commands intact.

In `keybindings.js`, replace:

```js
  { key: "mod+1", commandId: "surface.tasks", when: "always" },
  { key: "mod+2", commandId: "surface.plan", when: "always" },
  { key: "mod+3", commandId: "surface.preview", when: "always" },
```

with:

```js
  { key: "mod+1", commandId: "surface.files", when: "always" },
  { key: "mod+2", commandId: "surface.terminal", when: "always" },
  { key: "mod+3", commandId: "surface.diff", when: "always" },
```

- [x] **Step 4: Update store actions that open right-panel surfaces**

In `store.js`, change `diff_surface_opened` to open a real surface:

```js
    case "diff_surface_opened":
      return {
        ...state,
        diffSurface: action.diffSurface || null,
        inspectorTab: "diff",
        workbench: reduceWorkbenchState(state.workbench, {
          type: "workbench_surface_opened",
          placement: "right",
          kind: "diff",
          title: action.diffSurface?.title || "Diff",
          resourceId: "current",
        }),
      };
```

Add the new reducer action cases:

```js
    case "workbench_surface_close_others":
    case "workbench_surface_close_to_right":
    case "workbench_surface_close_all":
```

to the existing workbench action group.

- [x] **Step 5: Import the surface body in `App.jsx`**

Add:

```jsx
import RightPanelSurfaceBody from "./components/workbench/RightPanelSurfaceBody.jsx";
```

- [x] **Step 6: Add active surface helpers in `App.jsx`**

Before `return`, add:

```jsx
  const rightPanelSurfaces = state.workbench.rightPanel.surfaces || [];
  const activeRightPanelSurface =
    rightPanelSurfaces.find((surface) => surface.id === state.workbench.rightPanel.activeSurfaceId) || null;
```

- [x] **Step 7: Replace the old `RightPanelTabs` usage in `App.jsx`**

Replace the current `rightPanel={<RightPanelTabs ...>...` block with:

```jsx
      rightPanel={
        <RightPanelTabs
          surfaces={rightPanelSurfaces}
          activeSurfaceId={state.workbench.rightPanel.activeSurfaceId}
          onActivateSurface={(surface) => {
            dispatch({
              type: "workbench_surface_activated",
              placement: "right",
              surfaceId: surface.id,
            });
            dispatch({ type: "set_inspector", value: surface.kind });
          }}
          onCloseSurface={(surface) => {
            dispatch({
              type: "workbench_surface_closed",
              placement: "right",
              surfaceId: surface.id,
              kind: surface.kind,
              resourceId: surface.resourceId,
            });
          }}
          onCloseOtherSurfaces={(surface) => {
            dispatch({
              type: "workbench_surface_close_others",
              placement: "right",
              surfaceId: surface.id,
            });
          }}
          onCloseSurfacesToRight={(surface) => {
            dispatch({
              type: "workbench_surface_close_to_right",
              placement: "right",
              surfaceId: surface.id,
            });
          }}
          onCloseAllSurfaces={() => {
            dispatch({ type: "workbench_surface_close_all", placement: "right" });
          }}
          onAddSurface={(kind) => {
            dispatch({
              type: "workbench_surface_opened",
              placement: "right",
              kind,
              title: kind === "diff" ? "Diff" : kind === "files" ? "Files" : kind === "terminal" ? "Terminal" : "Plan",
              resourceId: kind === "diff" ? "current" : kind === "terminal" ? state.terminal.activeTerminalId || "terminal" : "",
            });
            dispatch({ type: "set_inspector", value: kind });
            if (kind === "terminal") {
              void ensureTerminalOpen(state.terminal.activeTerminalId || nextTerminalId(state.terminal.terminalIds));
            }
          }}
        >
          <RightPanelSurfaceBody
            surface={activeRightPanelSurface}
            inspectorProps={{
              tasks: state.tasks,
              artifacts: state.artifacts,
              plan: state.plan,
              review: state.review,
              recipes: state.recipes,
              timeline: runtimeState.timelineItems,
              currentInteraction: runtimeState.currentInteraction,
              interactionNotice,
              permissionContext: state.permissionContext,
              preview: state.preview,
              diffSurface: state.diffSurface,
              sourceControl: state.sourceControl,
              snapshot: state.snapshot,
              appShell: state.app,
              userAnswer,
              eventLog: state.eventLog,
              onTabChange: (v) => dispatch({ type: "set_inspector", value: v }),
              onOpenArtifact: openArtifact,
              onOpenReviewEvidence: openReviewEvidence,
              onRunRecipe: runRecipe,
              onFocusDiffFile: (filePath) => dispatch({ type: "diff_file_focused", filePath }),
              onRefreshSourceControl: () => loadSourceControlStatus(true),
              onSelectSourceControlFile: openSourceControlFile,
              onAppSettingsChange: (patch) => dispatch({ type: "app_shell_settings_changed", patch }),
              onUserAnswerChange: setUserAnswer,
              onRespondInteraction: respondToInteraction,
            }}
            fileTree={state.fileTree}
            treeHeight={treeHeight}
            onOpenFile={openFile}
            onLoadFileChildren={loadFileChildren}
            terminal={state.terminal}
            onTerminalNew={() => ensureTerminalOpen(nextTerminalId(state.terminal.terminalIds))}
            onTerminalSelect={(terminalId) => dispatch({ type: "terminal_active_set", terminalId })}
            onTerminalSend={sendTerminalInput}
            onTerminalClear={clearActiveTerminal}
            onTerminalRestart={restartActiveTerminal}
            onTerminalClose={closeActiveTerminal}
          />
        </RightPanelTabs>
      }
```

- [x] **Step 8: Update `executeWorkbenchCommand()` in `App.jsx`**

Replace the old `command.surface` branch with:

```jsx
    if (command.surface) {
      dispatch({
        type: "workbench_surface_opened",
        placement: "right",
        kind: command.surface,
        title: command.label.replace(/^Open\s+/, ""),
        resourceId: command.surface === "diff" ? "current" : command.surface === "terminal" ? state.terminal.activeTerminalId || "terminal" : "",
      });
      dispatch({ type: "set_inspector", value: command.surface });
      if (command.surface === "terminal") {
        await ensureTerminalOpen(state.terminal.activeTerminalId || nextTerminalId(state.terminal.terminalIds));
      }
      return;
    }
```

Remove the special `surface.source_control` branch because this slice's T3 surface set uses `diff` for change review.

- [x] **Step 9: Run the focused test to verify it passes**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
node test/run-tests.mjs
```

Expected: all helper checks pass.

- [x] **Step 10: Commit Task 4**

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/workbench/commands.js src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs
git commit -m "gui: wire t3 right panel surfaces"
```

---

## Task 5: CSS, Documentation, And Verification

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [x] **Step 1: Write failing CSS/source assertions**

In `run-tests.mjs`, add these style assertions near the existing style checks:

```js
  assert.equal(stylesSource.includes(".right-panel-surface-tab"), true);
  assert.equal(stylesSource.includes(".right-panel-empty-state"), true);
  assert.equal(stylesSource.includes(".right-panel-files-surface"), true);
  assert.equal(stylesSource.includes(".right-panel-tab-menu-popup"), true);
```

- [x] **Step 2: Run the focused test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
node test/run-tests.mjs
```

Expected: FAIL because the new classes are not styled yet.

- [x] **Step 3: Add CSS for T3-style surface tabs**

Add this CSS near the existing right-panel rules:

```css
.right-panel-tab-scroll {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  width: 100%;
  overflow-x: auto;
  scrollbar-width: none;
}

.right-panel-tab-scroll::-webkit-scrollbar {
  display: none;
}

.right-panel-surface-tab {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  min-width: 96px;
  max-width: 176px;
  height: 28px;
  border-radius: 6px;
  color: var(--muted);
}

.right-panel-surface-tab:hover {
  background: var(--hover);
  color: var(--text);
}

.right-panel-surface-tab.active {
  background: var(--panel-strong);
  color: var(--text);
}

.right-panel-surface-tab-main {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
  height: 100%;
  border: 0;
  background: transparent;
  color: inherit;
  padding: 0 4px 0 8px;
  text-align: left;
}

.right-panel-surface-tab-main span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.right-panel-surface-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid var(--border);
  font-size: 10px;
  line-height: 1;
  color: var(--muted);
}

.right-panel-tab-close,
.right-panel-tab-menu-button,
.right-panel-add-surface {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: inherit;
}

.right-panel-tab-close:hover,
.right-panel-tab-menu-button:hover,
.right-panel-add-surface:hover {
  background: var(--hover);
  color: var(--text);
}

.right-panel-tab-menu {
  position: relative;
  display: inline-flex;
}

.right-panel-tab-menu-popup {
  position: absolute;
  top: 28px;
  right: 0;
  z-index: 50;
  display: grid;
  min-width: 148px;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--panel);
  box-shadow: var(--surface-shadow);
}

.right-panel-tab-menu-popup button {
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--text);
  padding: 6px 8px;
  text-align: left;
}

.right-panel-tab-menu-popup button:hover {
  background: var(--hover);
}

.right-panel-empty-state {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  justify-content: center;
  gap: 16px;
  padding: 24px;
}

.right-panel-empty-copy {
  text-align: center;
}

.right-panel-empty-copy h3 {
  margin: 0;
  font-size: 14px;
}

.right-panel-empty-copy p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 12px;
}

.right-panel-empty-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.right-panel-empty-card {
  display: flex;
  min-height: 104px;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel);
  color: var(--text);
  padding: 12px;
  text-align: left;
}

.right-panel-empty-card:hover {
  background: var(--hover);
}

.right-panel-empty-card small {
  color: var(--muted);
  line-height: 1.35;
}

.right-panel-files-surface {
  min-height: 0;
  height: 100%;
  padding: 10px;
}

.right-panel-files-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  color: var(--muted);
  font-size: 12px;
}
```

- [x] **Step 4: Add development tracker note**

At the top of `docs/development-tracker.md`, add a new current-stage entry:

```md
### 2026-06-17 - T3 Right Panel Surface Tabs

- GUI right panel now uses a T3 Code-style open surface tab model for `diff`, `files`, `terminal`, and `plan` instead of a fixed inspector tab list.
- Surface state remains GUI-local app-shell state and does not write transcript history, workflow state, permission policy, runtime reducers, telemetry, source-control checkpoints, extension loading state, or Agent Core behavior.
- Existing local body panes are reused for the first slice: Diff maps to the current diff view, Files hosts the workspace tree, Terminal reuses the GUI-local terminal display, and Plan maps to the existing plan panel.
```

- [x] **Step 5: Add design change log entry**

At the top of `docs/design-change-log.md` current records, add:

```md
### DC-168

- 日期：2026-06-17
- 变更主题：GUI T3-style right-panel surface tabs
- 变更摘要：
  - GUI right panel 从固定 inspector tab list 改为 T3 Code-style open surface tab model，首批 surface 为 `diff`、`files`、`terminal`、`plan`。
  - Surface open/activate/close/close-others/close-to-right/close-all 均由 GUI-local `workbench/surfaces.js` pure reducer 管理。
  - Right-panel body 复用现有本地 pane：Diff、workspace file tree、GUI terminal display 和 Plan，不新增 backend contract 或 Agent Core behavior。
  - 该切片继续保持 GUI app-shell 与 Agent Core 分离；surface state 不进入 transcript、workflow state、permission policy、runtime reducers、telemetry、source-control checkpoints 或 extension loading。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/FilesSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `src/embedagent/frontend/gui/webapp/test/`
- 关联文档：
  - `docs/superpowers/specs/2026-06-17-t3-right-panel-surface-tabs-design.md`
  - `docs/superpowers/plans/2026-06-17-t3-right-panel-surface-tabs.md`
- 是否需要 ADR：否；该变化在既有 GUI app-shell boundary 内实现，不改变 Agent Core 架构、公开 extension API、permission policy 或离线 bundle runtime contract。
- 后续动作：
  - 继续按 T3 Code 参考实现 right-panel terminal split/file preview/browser preview 能力，但每个能力必须保持 Windows 7/offline constraints 和 GUI/Core 边界。
```

- [x] **Step 6: Run focused webapp tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: `frontend helper checks passed`.

- [x] **Step 7: Build GUI assets**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: Vite build succeeds and updates `src/embedagent/frontend/gui/static/assets/app.js` and `src/embedagent/frontend/gui/static/assets/app.css`.

- [x] **Step 8: Run focused Python GUI tests**

Run:

```bash
uv run pytest tests/test_gui_app_shell.py tests/test_gui_source_control_api.py tests/test_gui_terminal_api.py -v
```

Expected: all selected tests pass. These are guard tests confirming app-shell, source-control, and terminal backend contracts did not move.

- [x] **Step 9: Commit Task 5**

```bash
git add src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs docs/development-tracker.md docs/design-change-log.md src/embedagent/frontend/gui/static/assets/app.js src/embedagent/frontend/gui/static/assets/app.css
git commit -m "gui: polish t3 right panel surface tabs"
```

---

## Self-Review

Spec coverage:

- T3-style open surfaces: Task 1 and Task 2.
- Supported surfaces `diff`, `files`, `terminal`, `plan`: Task 1 through Task 4.
- No fixed inspector tab list: Task 2 and Task 4.
- Existing pane reuse: Task 3 and Task 4.
- GUI-local state only: Task 1, Task 4, and docs in Task 5.
- No backend or Agent Core contract changes: File structure and verification steps keep backend work out of scope.

Placeholder scan:

- The plan contains no `TBD`, `TODO`, or unspecified implementation steps.
- Each code-changing step names exact files and code snippets.
- Every task has a red test step, green implementation step, verification command, and commit command.

Type and name consistency:

- `activeSurfaceId`, `surfaces`, and `activeKind` are introduced in Task 1 and consumed in Task 4.
- Reducer actions use one naming family: `workbench_surface_opened`, `workbench_surface_activated`, `workbench_surface_closed`, `workbench_surface_close_others`, `workbench_surface_close_to_right`, and `workbench_surface_close_all`.
- Component props use `surfaces`, `activeSurfaceId`, `onActivateSurface`, `onCloseSurface`, `onCloseOtherSurfaces`, `onCloseSurfacesToRight`, `onCloseAllSurfaces`, and `onAddSurface` consistently.
