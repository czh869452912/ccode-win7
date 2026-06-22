# T3 GUI Parity Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the GUI shell around T3 Code-style right-panel surfaces, terminal panels, and timeline rows without changing Agent Core.

**Architecture:** The work stays inside the GUI app shell. `workbench/surfaces.js`, terminal GUI components, and `session-runtime/t3-timeline.js` become the frontend-local read models that copy T3 Code's architecture shape. Backend/Core contracts remain existing app-shell routes and session bootstrap/WebSocket payloads only.

**Tech Stack:** React 18, plain JavaScript ES modules, CSS, existing Node test runner, existing Python GUI backend tests, existing visual debug harness.

---

## Source Spec

Approved design: `docs/superpowers/specs/2026-06-22-t3-gui-parity-shell-design.md`

Primary T3 references:

- `reference/t3code/apps/web/src/rightPanelStore.ts`
- `reference/t3code/apps/web/src/rightPanelStore.test.ts`
- `reference/t3code/apps/web/src/components/RightPanelTabs.tsx`
- `reference/t3code/apps/web/src/components/ThreadTerminalDrawer.tsx`
- `reference/t3code/apps/web/src/components/chat/MessagesTimeline.logic.ts`
- `reference/t3code/apps/web/src/components/chat/MessagesTimeline.tsx`

## File Structure

GUI-only files to modify:

- `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`  
  Owns T3-style thread/session-scoped surface descriptors and pure reducers.
- `src/embedagent/frontend/gui/webapp/src/workbench/ui-state.js`  
  Persists sanitized GUI surface state only.
- `src/embedagent/frontend/gui/webapp/src/components/workbench/FloatingMenu.jsx`  
  New tiny local floating menu primitive for tabbar menus.
- `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`  
  Renders T3-style tabs and floating menus.
- `src/embedagent/frontend/gui/webapp/src/components/workbench/TerminalShell.jsx`  
  New shared terminal shell for bottom drawer and right panel.
- `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`  
  Uses `TerminalShell` as drawer owner.
- `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTerminalSurface.jsx`  
  Remove after `RightPanelSurfaceBody.jsx` uses `TerminalShell` directly.
- `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`  
  Routes terminal surfaces to `TerminalShell`.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`  
  Coordinates app-shell terminal APIs with surface actions; stops dispatching legacy inspector state for right-panel terminal.
- `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`  
  Becomes the single T3-style timeline row projector.
- `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`  
  Tracks only row expansion state for the new row kinds.
- `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`  
  Removes legacy grouped renderer path after T3 renderer parity.
- `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`  
  Renders the new row model.
- `src/embedagent/frontend/gui/webapp/src/styles.css`  
  Defines floating menu, tab overflow, terminal shell, and scroll-region layout.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`  
  Adds fixtures for many tabs, terminal split, and stable context placement.
- `scripts/gui-visual-debug.mjs`  
  Adds rendered checks for panel overflow, terminal, and timeline context placement.

Tests to modify or create:

- `src/embedagent/frontend/gui/webapp/test/right-panel-store-parity.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/right-panel-tabs-source.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/terminal-controller.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/terminal-shell-source.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/timeline-ui-state.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

Documentation to update in the final slice:

- `docs/modules/frontend-gui.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

Files that must not change for this GUI program:

- `src/embedagent/query_engine.py`
- `src/embedagent/agent_kernel.py`
- `src/embedagent/agent_loop.py`
- `src/embedagent/agent_tool_action_service.py`
- `src/embedagent/context.py`
- `src/embedagent/compaction_state.py`
- `src/embedagent/recovery_state.py`
- `src/embedagent/runtime_config.py`
- `src/embedagent/permissions.py`
- `src/embedagent/harness/**`

## Task 1: Right-Panel Surface Store Parity

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/test/right-panel-store-parity.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/ui-state.js`

- [ ] **Step 1: Write failing right-panel store parity tests**

Create `src/embedagent/frontend/gui/webapp/test/right-panel-store-parity.test.mjs`:

```javascript
import assert from "node:assert/strict";

import {
  activateSurface,
  closeAllSurfaces,
  closeOtherSurfaces,
  closeSurface,
  closeSurfacesToRight,
  createWorkbenchState,
  openFileSurface,
  openPreviewSurface,
  openSurface,
  openTerminalSurface,
  splitTerminalSurfaceForWorkbench,
  activateTerminalPaneForWorkbench,
  closeTerminalPaneForWorkbench,
} from "../src/workbench/surfaces.js";

function surfaceIds(state) {
  return state.workbench ? state.workbench.rightPanel.surfaces.map((surface) => surface.id) : state.rightPanel.surfaces.map((surface) => surface.id);
}

function rightPanel(state) {
  return state.workbench ? state.workbench.rightPanel : state.rightPanel;
}

export function runRightPanelStoreParityTests() {
  let state = createWorkbenchState();

  state = openSurface(state, { placement: "right", kind: "files", sessionId: "thread-a" });
  state = openSurface(state, { placement: "right", kind: "files", sessionId: "thread-a" });
  assert.deepEqual(surfaceIds(state), ["right:files"]);
  assert.equal(rightPanel(state).activeSurfaceId, "right:files");
  assert.equal(rightPanel(state).open, true);

  state = openFileSurface(state, { sessionId: "thread-a", filePath: "src/main.c", revealLine: 12 });
  assert.deepEqual(surfaceIds(state), ["right:file:src/main.c"]);
  assert.equal(rightPanel(state).activeSurfaceId, "right:file:src/main.c");
  assert.equal(rightPanel(state).surfaces[0].revealLine, 12);
  assert.equal(rightPanel(state).surfaces[0].revealRequestId, 1);

  state = openFileSurface(state, { sessionId: "thread-a", filePath: "src/main.c", revealLine: 24 });
  assert.deepEqual(surfaceIds(state), ["right:file:src/main.c"]);
  assert.equal(rightPanel(state).surfaces[0].revealLine, 24);
  assert.equal(rightPanel(state).surfaces[0].revealRequestId, 2);

  state = openPreviewSurface(state, { sessionId: "thread-a", previewId: "preview-a" });
  state = openPreviewSurface(state, { sessionId: "thread-a", previewId: "preview-b" });
  assert.deepEqual(surfaceIds(state), [
    "right:file:src/main.c",
    "right:preview:preview-a",
    "right:preview:preview-b",
  ]);
  assert.equal(rightPanel(state).activeSurfaceId, "right:preview:preview-b");

  state = openTerminalSurface(state, { sessionId: "thread-a", terminalId: "term-1" });
  state = openTerminalSurface(state, { sessionId: "thread-a", terminalId: "term-2" });
  assert.deepEqual(surfaceIds(state).slice(-2), ["right:terminal:term-1", "right:terminal:term-2"]);
  assert.deepEqual(rightPanel(state).surfaces.at(-1), {
    id: "right:terminal:term-2",
    placement: "right",
    kind: "terminal",
    title: "Terminal",
    resourceId: "term-2",
    filePath: "",
    terminalId: "term-2",
    revealLine: null,
    revealRequestId: 0,
    terminalIds: ["term-2"],
    activeTerminalId: "term-2",
  });

  state = splitTerminalSurfaceForWorkbench(state, {
    sessionId: "thread-a",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-3",
    splitDirection: "vertical",
  });
  const splitSurface = rightPanel(state).surfaces.find((surface) => surface.id === "right:terminal:term-1");
  assert.deepEqual(splitSurface.terminalIds, ["term-1", "term-3"]);
  assert.equal(splitSurface.activeTerminalId, "term-3");
  assert.equal(splitSurface.splitDirection, "vertical");

  state = activateTerminalPaneForWorkbench(state, {
    sessionId: "thread-a",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-1",
  });
  assert.equal(
    rightPanel(state).surfaces.find((surface) => surface.id === "right:terminal:term-1").activeTerminalId,
    "term-1",
  );

  state = closeTerminalPaneForWorkbench(state, {
    sessionId: "thread-a",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-1",
  });
  assert.deepEqual(
    rightPanel(state).surfaces.find((surface) => surface.id === "right:terminal:term-1").terminalIds,
    ["term-3"],
  );

  state = closeTerminalPaneForWorkbench(state, {
    sessionId: "thread-a",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-3",
  });
  assert.equal(surfaceIds(state).includes("right:terminal:term-1"), false);
  assert.equal(rightPanel(state).open, true);

  state = activateSurface(state, { placement: "right", sessionId: "thread-a", surfaceId: "right:file:src/main.c" });
  state = closeOtherSurfaces(state, { placement: "right", sessionId: "thread-a", surfaceId: "right:file:src/main.c" });
  assert.deepEqual(surfaceIds(state), ["right:file:src/main.c"]);
  assert.equal(rightPanel(state).activeSurfaceId, "right:file:src/main.c");

  state = closeSurface(state, {
    placement: "right",
    sessionId: "thread-a",
    surfaceId: "right:file:src/main.c",
    kind: "file",
    resourceId: "src/main.c",
  });
  assert.deepEqual(surfaceIds(state), []);
  assert.equal(rightPanel(state).activeSurfaceId, null);
  assert.equal(rightPanel(state).open, false);

  state = openSurface(state, { placement: "right", sessionId: "thread-a", kind: "diff", resourceId: "current" });
  state = openSurface(state, { placement: "right", sessionId: "thread-a", kind: "plan" });
  state = openSurface(state, { placement: "right", sessionId: "thread-a", kind: "source_control" });
  state = closeSurfacesToRight(state, { placement: "right", sessionId: "thread-a", surfaceId: "right:diff:current" });
  assert.deepEqual(surfaceIds(state), ["right:diff:current"]);
  assert.equal(rightPanel(state).activeSurfaceId, "right:diff:current");

  state = closeAllSurfaces(state, { placement: "right", sessionId: "thread-a" });
  assert.equal(rightPanel(state).open, false);
  assert.deepEqual(surfaceIds(state), []);
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
import { runRightPanelStoreParityTests } from "./right-panel-store-parity.test.mjs";
```

Add the invocation near the existing workbench tests:

```javascript
  runWorkbenchStateTests();
  runWorkbenchUiStateTests();
  runRightPanelStoreParityTests();
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with an import error for `openFileSurface`, `openPreviewSurface`, `openTerminalSurface`, `splitTerminalSurfaceForWorkbench`, `activateTerminalPaneForWorkbench`, or `closeTerminalPaneForWorkbench`, and existing close-final-surface behavior may also fail because the panel currently remains open.

- [ ] **Step 3: Implement T3-style surface store helpers**

Modify `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`.

Add exported helper wrappers after `openSurface(...)`:

```javascript
export function openFileSurface(state, input = {}) {
  const filePath = normalizeFilePath(input.filePath || input.resourceId);
  if (!filePath) return state || createWorkbenchState();
  return openSurface(state, {
    ...input,
    placement: "right",
    kind: "file",
    filePath,
    resourceId: filePath,
    title: basenameForPath(filePath) || "File",
  });
}

export function openPreviewSurface(state, input = {}) {
  const previewId = String(input.previewId || input.resourceId || "").trim();
  return openSurface(state, {
    ...input,
    placement: "right",
    kind: "preview",
    resourceId: previewId,
    title: input.title || "Preview",
  });
}

export function openTerminalSurface(state, input = {}) {
  const terminalId = String(input.terminalId || input.resourceId || "").trim();
  if (!terminalId) return state || createWorkbenchState();
  return openSurface(state, {
    ...input,
    placement: "right",
    kind: "terminal",
    title: input.title || "Terminal",
    resourceId: terminalId,
    terminalId,
    terminalIds: [terminalId],
    activeTerminalId: terminalId,
  });
}

export function splitTerminalSurfaceForWorkbench(state, input = {}) {
  return splitTerminalSurface(state, {
    ...input,
    placement: "right",
  });
}

export function activateTerminalPaneForWorkbench(state, input = {}) {
  return activateTerminalPane(state, {
    ...input,
    placement: "right",
  });
}

export function closeTerminalPaneForWorkbench(state, input = {}) {
  return closeTerminalPane(state, {
    ...input,
    placement: "right",
  });
}
```

Change `activateRightPanelSurface(...)` so closing the final surface closes the panel, while explicit `workbench_right_panel_toggled` remains the empty-panel opener:

```javascript
function activateRightPanelSurface(panel, surface) {
  const surfaces = Array.isArray(panel && panel.surfaces) ? panel.surfaces : [];
  return {
    ...panel,
    open: surface ? true : surfaces.length > 0 && panel.open === true,
    activeKind: surface ? surface.kind : "",
    activeSurfaceId: surface ? surface.id : null,
  };
}
```

Change `closeAllSurfaces(...)` to close the panel:

```javascript
  const nextPanel = {
    ...current.rightPanel,
    open: false,
    activeKind: "",
    activeSurfaceId: null,
    surfaces: [],
  };
```

Ensure `openSurface(...)` uses the explicit helper behavior for files and preview placeholders:

```javascript
    const hasPreviewResource = nextSurface.kind === "preview" && Boolean(nextSurface.resourceId);
    const sourceItems =
      nextSurface.kind === "file"
        ? currentItems.filter((item) => item.kind !== "files")
        : hasPreviewResource
          ? currentItems.filter((item) => !(item.kind === "preview" && !item.resourceId))
          : currentItems;
```

Keep the current `surfaceIdFor(...)` format (`right:<kind>[:resource]`) for this repository; it is the persisted local format and does not affect Agent Core.

- [ ] **Step 4: Update persistence sanitization for helper parity**

Modify `src/embedagent/frontend/gui/webapp/src/workbench/ui-state.js` so sanitized terminal surfaces always include `terminalIds` and `activeTerminalId`:

```javascript
  if (kind !== "terminal") return base;
  const normalizedTerminalIds = terminalIds.length > 0 ? terminalIds : [terminalId].filter(Boolean);
  const activeTerminalId = asString(source.activeTerminalId);
  return {
    ...base,
    terminalIds: normalizedTerminalIds,
    activeTerminalId: normalizedTerminalIds.includes(activeTerminalId)
      ? activeTerminalId
      : normalizedTerminalIds[0] || terminalId,
    ...(source.splitDirection === "vertical" ? { splitDirection: "vertical" } : {}),
  };
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js src/embedagent/frontend/gui/webapp/src/workbench/ui-state.js src/embedagent/frontend/gui/webapp/test/right-panel-store-parity.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat(gui): align right panel surface store with t3"
```

## Task 2: Floating Menus And Right-Panel Tabs

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/FloatingMenu.jsx`
- Create: `src/embedagent/frontend/gui/webapp/test/right-panel-tabs-source.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing source tests for floating menu boundary**

Create `src/embedagent/frontend/gui/webapp/test/right-panel-tabs-source.test.mjs`:

```javascript
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readSource(...parts) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", ...parts), "utf8").replace(/\r\n?/g, "\n");
}

export function runRightPanelTabsSourceTests() {
  const tabsSource = readSource("components", "workbench", "RightPanelTabs.jsx");
  const floatingMenuSource = readSource("components", "workbench", "FloatingMenu.jsx");
  const cssSource = readSource("styles.css");

  assert.equal(tabsSource.includes("FloatingMenu"), true);
  assert.equal(tabsSource.includes("right-panel-add-menu-popup"), true);
  assert.equal(tabsSource.includes("right-panel-tab-menu-popup"), true);
  assert.equal(tabsSource.includes("createPortal"), false);
  assert.equal(floatingMenuSource.includes("createPortal"), true);
  assert.equal(floatingMenuSource.includes("document.body"), true);
  assert.equal(floatingMenuSource.includes("Escape"), true);
  assert.equal(floatingMenuSource.includes("getBoundingClientRect"), true);

  const tabScrollRule = /\.right-panel-tab-scroll\s*\{[\s\S]*?\}/.exec(cssSource)?.[0] || "";
  assert.equal(tabScrollRule.includes("overflow-y: hidden"), true);
  assert.equal(tabScrollRule.includes("overflow-y: visible"), false);
  assert.equal(cssSource.includes(".floating-menu-layer"), true);
  assert.equal(cssSource.includes(".right-panel-tab-strip"), true);
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
import { runRightPanelTabsSourceTests } from "./right-panel-tabs-source.test.mjs";
```

Invoke after `runWorkbenchUiStateTests()`:

```javascript
  runRightPanelTabsSourceTests();
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `FloatingMenu.jsx` does not exist and `RightPanelTabs.jsx` still renders popups inside the tab scroll.

- [ ] **Step 3: Create local floating menu primitive**

Create `src/embedagent/frontend/gui/webapp/src/components/workbench/FloatingMenu.jsx`:

```javascript
import React from "react";
import { createPortal } from "react-dom";

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function menuPosition(anchor, menu) {
  const viewportWidth = window.innerWidth || 1024;
  const viewportHeight = window.innerHeight || 768;
  const anchorRect = anchor.getBoundingClientRect();
  const menuWidth = menu?.offsetWidth || 176;
  const menuHeight = menu?.offsetHeight || 220;
  const left = clamp(anchorRect.left, 8, Math.max(8, viewportWidth - menuWidth - 8));
  const below = anchorRect.bottom + 6;
  const above = anchorRect.top - menuHeight - 6;
  const top = below + menuHeight <= viewportHeight - 8 ? below : clamp(above, 8, viewportHeight - menuHeight - 8);
  return { left: Math.round(left), top: Math.round(top) };
}

export default function FloatingMenu({
  open,
  anchorRef,
  onClose,
  className = "",
  children,
  role = "menu",
}) {
  const menuRef = React.useRef(null);
  const [position, setPosition] = React.useState({ left: 0, top: 0 });

  React.useLayoutEffect(() => {
    if (!open) return undefined;
    const anchor = anchorRef && anchorRef.current;
    const menu = menuRef.current;
    if (!anchor || !menu) return undefined;

    function updatePosition() {
      setPosition(menuPosition(anchor, menu));
    }

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [anchorRef, open]);

  React.useEffect(() => {
    if (!open) return undefined;
    function onPointerDown(event) {
      const anchor = anchorRef && anchorRef.current;
      const menu = menuRef.current;
      if (menu && menu.contains(event.target)) return;
      if (anchor && anchor.contains(event.target)) return;
      onClose && onClose();
    }
    function onKeyDown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose && onClose();
      }
    }
    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [anchorRef, onClose, open]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      ref={menuRef}
      className={`floating-menu-layer ${className}`.trim()}
      role={role}
      style={{ left: `${position.left}px`, top: `${position.top}px` }}
    >
      {children}
    </div>,
    document.body,
  );
}
```

- [ ] **Step 4: Refactor RightPanelTabs menus to use FloatingMenu**

Modify `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`.

Add import:

```javascript
import FloatingMenu from "./FloatingMenu.jsx";
```

Replace `SurfaceTabMenu(...)` with:

```javascript
function SurfaceTabMenu({
  surface,
  onCloseSurface,
  onCloseOtherSurfaces,
  onCloseSurfacesToRight,
  onCloseAllSurfaces,
}) {
  const [open, setOpen] = React.useState(false);
  const buttonRef = React.useRef(null);
  return (
    <span className="right-panel-tab-menu">
      <button
        ref={buttonRef}
        type="button"
        className="right-panel-tab-menu-button"
        aria-label={`Surface actions for ${surfaceTitle(surface)}`}
        aria-expanded={open}
        onClick={(event) => {
          event.stopPropagation();
          setOpen((value) => !value);
        }}
      >
        ...
      </button>
      <FloatingMenu
        open={open}
        anchorRef={buttonRef}
        onClose={() => setOpen(false)}
        className="right-panel-tab-menu-popup"
      >
        <button type="button" role="menuitem" onClick={() => { setOpen(false); onCloseSurface(surface); }}>
          Close
        </button>
        <button type="button" role="menuitem" onClick={() => { setOpen(false); onCloseOtherSurfaces(surface); }}>
          Close others
        </button>
        <button type="button" role="menuitem" onClick={() => { setOpen(false); onCloseSurfacesToRight(surface); }}>
          Close to the right
        </button>
        <button type="button" role="menuitem" onClick={() => { setOpen(false); onCloseAllSurfaces(); }}>
          Close all
        </button>
      </FloatingMenu>
    </span>
  );
}
```

Replace `SurfaceAddMenu(...)` with:

```javascript
function SurfaceAddMenu({ onAddSurface }) {
  const [open, setOpen] = React.useState(false);
  const buttonRef = React.useRef(null);
  const availableSurfaces = RIGHT_PANEL_SURFACES.slice();
  return (
    <span className="right-panel-add-menu">
      <button
        ref={buttonRef}
        type="button"
        className="right-panel-add-surface"
        aria-label="Add panel surface"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        title="Add panel surface"
      >
        +
      </button>
      <FloatingMenu
        open={open}
        anchorRef={buttonRef}
        onClose={() => setOpen(false)}
        className="right-panel-add-menu-popup"
      >
        {availableSurfaces.map((kind) => {
          const copy = SURFACE_COPY[kind];
          return (
            <button
              key={kind}
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onAddSurface(kind);
              }}
            >
              <SurfaceIcon kind={kind} />
              <span>{copy.label}</span>
            </button>
          );
        })}
      </FloatingMenu>
    </span>
  );
}
```

Update the `SurfaceTabMenu` call:

```javascript
                <SurfaceTabMenu
                  surface={surface}
                  onCloseSurface={onCloseSurface}
                  onCloseOtherSurfaces={onCloseOtherSurfaces}
                  onCloseSurfacesToRight={onCloseSurfacesToRight}
                  onCloseAllSurfaces={onCloseAllSurfaces}
                />
```

Wrap tab items in a strip inside the scroll container:

```jsx
        <div className="right-panel-tab-scroll" ref={tabListRef} data-right-panel-tab-list>
          <div className="right-panel-tab-strip">
            {items.map((surface) => {
              /* existing tab item rendering */
            })}
            {items.length > 0 ? <SurfaceAddMenu onAddSurface={onAddSurface} /> : null}
          </div>
        </div>
```

- [ ] **Step 5: Update CSS for unclipped floating menus and T3 tab sizing**

Modify `src/embedagent/frontend/gui/webapp/src/styles.css`.

Replace the `.right-panel-tab-scroll` block with:

```css
.right-panel-tab-scroll {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--border-focus) transparent;
}
```

Add:

```css
.right-panel-tab-strip {
  width: max-content;
  min-width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  gap: 4px;
}

.floating-menu-layer {
  position: fixed;
  z-index: 1000;
}
```

Change `.right-panel-surface-tab` sizing:

```css
.right-panel-surface-tab {
  position: relative;
  flex: 0 0 auto;
  width: clamp(96px, 13vw, 176px);
  min-width: 96px;
  height: 28px;
  max-width: 176px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 6px 0 8px;
  border: 0;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
}
```

Remove `position: absolute`, `top`, and `right` from `.right-panel-tab-menu-popup, .right-panel-add-menu-popup` so the floating layer positions them:

```css
.right-panel-tab-menu-popup,
.right-panel-add-menu-popup {
  min-width: 150px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 5px;
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  background: var(--bg-elevated);
  box-shadow: var(--surface-shadow);
}
```

- [ ] **Step 6: Run focused tests and build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/FloatingMenu.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/right-panel-tabs-source.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/static/index.html src/embedagent/frontend/gui/static/assets/app.js src/embedagent/frontend/gui/static/assets/app.css
git commit -m "feat(gui): render right panel menus as floating surfaces"
```

## Task 3: Terminal Controller Boundary

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/test/terminal-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`

- [ ] **Step 1: Write failing terminal controller assertions**

Modify the existing `openRightPanelSurface()` test in `src/embedagent/frontend/gui/webapp/test/terminal-controller.test.mjs`.

Replace this assertion block:

```javascript
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_snapshot_loaded",
      "terminal_active_set",
      "workbench_surface_opened",
      "set_inspector",
    ]);
    assert.equal(harness.actions[2].kind, "terminal");
    assert.deepEqual(harness.actions[2].terminalIds, ["term-3"]);
    assert.deepEqual(harness.actions[3], { type: "set_inspector", value: "terminal" });
```

with:

```javascript
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_snapshot_loaded",
      "terminal_active_set",
      "workbench_surface_opened",
    ]);
    assert.equal(harness.actions[2].kind, "terminal");
    assert.equal(harness.actions[2].placement, "right");
    assert.deepEqual(harness.actions[2].terminalIds, ["term-3"]);
    assert.equal(harness.actions.some((action) => action.type === "set_inspector"), false);
```

Add a new test block after `selectBottomDrawerKind("terminal")`:

```javascript
  {
    const harness = createHarness();
    await harness.controller.selectBottomDrawerKind("terminal");
    assert.equal(harness.apiCalls[0].name, "openTerminal");
    assert.deepEqual(harness.actions.at(-1), {
      type: "workbench_surface_activated",
      placement: "bottom",
      kind: "terminal",
    });
    assert.equal(harness.actions.some((action) => action.placement === "right"), false);
  }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `openRightPanelSurface()` still dispatches `{ type: "set_inspector", value: "terminal" }`.

- [ ] **Step 3: Remove legacy inspector dispatch from right-panel terminal**

Modify `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`.

In `openRightPanelSurface(...)`, remove:

```javascript
    dispatch({ type: "set_inspector", value: "terminal" });
```

Keep this full function shape:

```javascript
  async function openRightPanelSurface(preferredId = "") {
    const state = getState();
    const terminalId = normalizeTerminalId(preferredId) || nextId(deps, allKnownTerminalIds(state));
    const openedTerminalId = await openSession(terminalId);
    if (!openedTerminalId) return null;
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: "terminal",
      title: "Terminal",
      resourceId: openedTerminalId,
      terminalId: openedTerminalId,
      terminalIds: [openedTerminalId],
      activeTerminalId: openedTerminalId,
    });
    return openedTerminalId;
  }
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js src/embedagent/frontend/gui/webapp/test/terminal-controller.test.mjs
git commit -m "fix(gui): decouple terminal surface from inspector state"
```

## Task 4: Shared T3-Style Terminal Shell

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/TerminalShell.jsx`
- Create: `src/embedagent/frontend/gui/webapp/test/terminal-shell-source.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
- Delete: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTerminalSurface.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing terminal shell source tests**

Create `src/embedagent/frontend/gui/webapp/test/terminal-shell-source.test.mjs`:

```javascript
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readSource(...parts) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", ...parts), "utf8").replace(/\r\n?/g, "\n");
}

export function runTerminalShellSourceTests() {
  const shellSource = readSource("components", "workbench", "TerminalShell.jsx");
  const bottomDrawerSource = readSource("components", "workbench", "BottomDrawer.jsx");
  const surfaceBodySource = readSource("components", "workbench", "RightPanelSurfaceBody.jsx");
  const cssSource = readSource("styles.css");

  assert.equal(shellSource.includes("export default function TerminalShell"), true);
  assert.equal(shellSource.includes("owner === \"right-panel\""), true);
  assert.equal(shellSource.includes("owner === \"drawer\""), true);
  assert.equal(shellSource.includes("splitDirection === \"vertical\""), true);
  assert.equal(shellSource.includes("terminal-shell-pane"), true);
  assert.equal(shellSource.includes("onSplitVertical"), true);
  assert.equal(shellSource.includes("onClose(terminalId)"), true);
  assert.equal(bottomDrawerSource.includes("TerminalShell"), true);
  assert.equal(bottomDrawerSource.includes("export function TerminalSurface"), false);
  assert.equal(surfaceBodySource.includes("TerminalShell"), true);
  assert.equal(surfaceBodySource.includes("RightPanelTerminalSurface"), false);
  assert.equal(cssSource.includes(".terminal-shell"), true);
  assert.equal(cssSource.includes(".terminal-shell-panes.split-vertical"), true);
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
import { runTerminalShellSourceTests } from "./terminal-shell-source.test.mjs";
```

Invoke after `runTerminalControllerTests()`:

```javascript
  runTerminalShellSourceTests();
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `TerminalShell.jsx` does not exist.

- [ ] **Step 3: Create TerminalShell component**

Create `src/embedagent/frontend/gui/webapp/src/components/workbench/TerminalShell.jsx`:

```javascript
import React, { useMemo, useState } from "react";

function sessionFor(terminal, terminalId) {
  return (terminal && terminal.sessions && terminal.sessions[terminalId]) || null;
}

function terminalLabel(session, terminalId) {
  return (session && session.label) || terminalId || "Terminal";
}

function terminalStatus(session) {
  return (session && session.status) || "closed";
}

function terminalIdsFor(owner, surface, terminal) {
  if (owner === "right-panel") {
    return Array.isArray(surface && surface.terminalIds)
      ? surface.terminalIds
      : [surface && (surface.activeTerminalId || surface.terminalId)].filter(Boolean);
  }
  return (terminal && terminal.terminalIds) || [];
}

function activeTerminalFor(owner, surface, terminal, ids) {
  if (owner === "right-panel") return String((surface && surface.activeTerminalId) || ids[0] || "");
  return String((terminal && terminal.activeTerminalId) || ids[0] || "");
}

function TerminalPane({
  terminalId,
  session,
  active,
  draft,
  setDraft,
  onSelect,
  onSend,
  onClear,
  onRestart,
  onClose,
}) {
  const status = terminalStatus(session);
  return (
    <section
      className={`terminal-shell-pane${active ? " active" : ""}`}
      data-testid={`terminal-shell-pane--${terminalId}`}
      onMouseDown={() => onSelect && onSelect(terminalId)}
    >
      <header className="terminal-shell-pane-header">
        <button
          type="button"
          className="terminal-shell-pane-title"
          onClick={() => onSelect && onSelect(terminalId)}
          title={(session && session.cwd) || terminalId}
        >
          <span>{terminalLabel(session, terminalId)}</span>
          <span className={`terminal-status-dot ${status}`} />
        </button>
        <span className="terminal-shell-pane-status">{status}</span>
        <button type="button" onClick={() => onClear(terminalId)} disabled={!session}>Clear</button>
        <button type="button" onClick={() => onRestart(terminalId)} disabled={!session}>Restart</button>
        <button type="button" onClick={() => onClose(terminalId)}>Close</button>
      </header>
      <pre className="terminal-shell-buffer">{session ? session.buffer || "" : "Terminal session is unavailable."}</pre>
      <form
        className="terminal-shell-input-row"
        onSubmit={(event) => {
          event.preventDefault();
          const text = draft || "";
          if (!text.trim()) return;
          setDraft("");
          onSelect && onSelect(terminalId);
          onSend(terminalId, `${text}\n`);
        }}
      >
        <span>&gt;</span>
        <input
          value={draft}
          onFocus={() => onSelect && onSelect(terminalId)}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type a command"
          disabled={!session || status === "closed"}
        />
      </form>
    </section>
  );
}

export default function TerminalShell({
  owner,
  surface = null,
  terminal,
  onNew,
  onSplit,
  onSplitVertical,
  onSelect,
  onSend,
  onClear,
  onRestart,
  onClose,
}) {
  const [draftsById, setDraftsById] = useState({});
  const terminalIds = terminalIdsFor(owner, surface, terminal);
  const activeTerminalId = activeTerminalFor(owner, surface, terminal, terminalIds);
  const splitDirection = surface && surface.splitDirection === "vertical" ? "vertical" : "horizontal";
  const panes = useMemo(
    () => terminalIds.map((terminalId) => ({ terminalId, session: sessionFor(terminal, terminalId) })),
    [terminal, terminalIds],
  );
  const isRightPanel = owner === "right-panel";

  return (
    <section
      className={`terminal-shell owner-${owner}`}
      data-terminal-owner={owner}
      data-testid={isRightPanel ? "right-panel-terminal-surface" : "terminal-drawer"}
    >
      <header className="terminal-shell-toolbar">
        <button type="button" onClick={onNew} title="New terminal">New</button>
        {isRightPanel ? (
          <>
            <button type="button" onClick={onSplit} disabled={!activeTerminalId} title="Split terminal horizontally">
              Split
            </button>
            <button type="button" onClick={onSplitVertical} disabled={!activeTerminalId} title="Split terminal vertically">
              Split V
            </button>
          </>
        ) : null}
      </header>
      {panes.length > 0 ? (
        <div
          className={`terminal-shell-panes split-${splitDirection}`}
          data-testid="terminal-shell-panes"
        >
          {panes.map(({ terminalId, session }) => (
            <TerminalPane
              key={terminalId}
              terminalId={terminalId}
              session={session}
              active={terminalId === activeTerminalId}
              draft={draftsById[terminalId] || ""}
              setDraft={(value) => setDraftsById((current) => ({ ...current, [terminalId]: value }))}
              onSelect={onSelect}
              onSend={onSend}
              onClear={onClear}
              onRestart={onRestart}
              onClose={onClose}
            />
          ))}
        </div>
      ) : (
        <div className="terminal-shell-empty">
          <p>No terminal sessions for this thread yet.</p>
          <button type="button" onClick={onNew}>New terminal</button>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Route bottom drawer through TerminalShell**

Modify `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`.

Replace the file contents with:

```javascript
import React from "react";
import TerminalShell from "./TerminalShell.jsx";

function RunOutputDrawer({ eventLog, terminationReason, terminationMessage }) {
  const entries = Array.isArray(eventLog) ? eventLog.slice(-80) : [];
  return (
    <>
      {terminationReason ? (
        <div className="drawer-line">
          reason={terminationReason} {terminationMessage || ""}
        </div>
      ) : null}
      {entries.length > 0 ? (
        entries.map((entry) => (
          <div className="drawer-line" key={`${entry.ts}-${entry.label}`}>
            <span className="drawer-label">{entry.label}</span>
            <span>{entry.detail || ""}</span>
          </div>
        ))
      ) : (
        <div className="drawer-line muted">No run output yet.</div>
      )}
    </>
  );
}

export default function BottomDrawer({
  activeKind,
  eventLog,
  terminationReason,
  terminationMessage,
  terminal,
  onKindSelect,
  onTerminalNew,
  onTerminalSelect,
  onTerminalSend,
  onTerminalClear,
  onTerminalRestart,
  onTerminalClose,
}) {
  return (
    <section className="bottom-drawer" aria-label="Bottom drawer" data-testid="bottom-drawer">
      <div className="bottom-drawer-tabs" role="tablist">
        <button className={`bottom-drawer-tab${activeKind === "terminal" ? " active" : ""}`} type="button" onClick={() => onKindSelect("terminal")}>
          Terminal
        </button>
        <button className={`bottom-drawer-tab${activeKind === "run_output" ? " active" : ""}`} type="button" onClick={() => onKindSelect("run_output")}>
          Run Output
        </button>
        <button className={`bottom-drawer-tab${activeKind === "logs" ? " active" : ""}`} type="button" onClick={() => onKindSelect("logs")}>
          Logs
        </button>
      </div>
      <div className="bottom-drawer-body">
        {activeKind === "terminal" ? (
          <TerminalShell
            owner="drawer"
            terminal={terminal}
            onNew={onTerminalNew}
            onSelect={onTerminalSelect}
            onSend={(terminalId, text) => {
              onTerminalSelect(terminalId);
              onTerminalSend(text);
            }}
            onClear={(terminalId) => {
              onTerminalSelect(terminalId);
              onTerminalClear();
            }}
            onRestart={(terminalId) => {
              onTerminalSelect(terminalId);
              onTerminalRestart();
            }}
            onClose={(terminalId) => {
              onTerminalSelect(terminalId);
              onTerminalClose();
            }}
          />
        ) : (
          <RunOutputDrawer eventLog={eventLog} terminationReason={terminationReason} terminationMessage={terminationMessage} />
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Route right-panel terminal through TerminalShell**

Modify `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`.

Replace:

```javascript
import RightPanelTerminalSurface from "./RightPanelTerminalSurface.jsx";
```

with:

```javascript
import TerminalShell from "./TerminalShell.jsx";
```

Replace the terminal branch with:

```javascript
  if (surface.kind === "terminal") {
    return (
      <TerminalShell
        owner="right-panel"
        surface={surface}
        terminal={terminal}
        onNew={onTerminalNew}
        onSplit={onTerminalSplit}
        onSplitVertical={onTerminalSplitVertical}
        onSelect={onTerminalSelect}
        onSend={onTerminalSend}
        onClear={onTerminalClear}
        onRestart={onTerminalRestart}
        onClose={onTerminalClose}
      />
    );
  }
```

Delete `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTerminalSurface.jsx`.

- [ ] **Step 6: Replace terminal CSS with shared shell classes**

Modify `src/embedagent/frontend/gui/webapp/src/styles.css`.

Keep old `.terminal-status-dot` rules. Add:

```css
.terminal-shell {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-default);
}

.terminal-shell-toolbar {
  min-height: 30px;
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  border-bottom: 1px solid var(--border-subtle);
  padding: 0 var(--sp-2);
  flex-shrink: 0;
}

.terminal-shell-toolbar button,
.terminal-shell-pane-header button,
.terminal-shell-empty button {
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  background: var(--bg-panel);
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 10px;
  min-height: 22px;
  cursor: pointer;
}

.terminal-shell-panes {
  min-height: 0;
  min-width: 0;
  flex: 1;
  display: grid;
  overflow: hidden;
}

.terminal-shell-panes.split-horizontal {
  grid-auto-flow: column;
  grid-auto-columns: minmax(0, 1fr);
}

.terminal-shell-panes.split-vertical {
  grid-auto-flow: row;
  grid-auto-rows: minmax(0, 1fr);
}

.terminal-shell-pane {
  min-height: 0;
  min-width: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  border-left: 1px solid var(--border-subtle);
  overflow: hidden;
}

.terminal-shell-pane:first-child {
  border-left: 0;
}

.terminal-shell-panes.split-vertical .terminal-shell-pane {
  border-left: 0;
  border-top: 1px solid var(--border-subtle);
}

.terminal-shell-panes.split-vertical .terminal-shell-pane:first-child {
  border-top: 0;
}

.terminal-shell-pane.active {
  background: rgba(255,255,255,.018);
}

.terminal-shell-pane-header {
  min-height: 28px;
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  border-bottom: 1px solid rgba(139,148,158,.12);
  padding: 0 var(--sp-2);
}

.terminal-shell-pane-title {
  min-width: 0;
  flex: 1;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-align: left;
}

.terminal-shell-buffer {
  min-height: 0;
  margin: 0;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  padding: var(--sp-2);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1.5;
}

.terminal-shell-input-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  border-top: 1px solid rgba(139,148,158,.12);
  padding: var(--sp-2);
}

.terminal-shell-input-row input {
  min-width: 0;
  flex: 1;
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  background: var(--bg-panel);
  color: var(--text-primary);
  padding: 5px 7px;
  font-family: var(--font-mono);
  font-size: 11px;
}

.terminal-shell-empty {
  min-height: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  color: var(--text-muted);
  text-align: center;
}
```

After adding the shared shell classes, remove obsolete `.right-panel-terminal-*` rules once no source references remain.

- [ ] **Step 7: Run tests, build, and Python terminal tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../../
uv run pytest tests/test_gui_terminal_api.py tests/test_gui_terminal_service.py tests/test_gui_app_shell.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/TerminalShell.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/terminal-shell-source.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/static/index.html src/embedagent/frontend/gui/static/assets/app.js src/embedagent/frontend/gui/static/assets/app.css
git rm src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTerminalSurface.jsx
git commit -m "feat(gui): share terminal shell across drawer and panel"
```

## Task 5: T3 Timeline Projector Tests

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/timeline-ui-state.test.mjs`

- [ ] **Step 1: Add failing timeline projector tests**

Modify `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`.

Add these tests inside `runT3TimelineTests()`:

```javascript
  {
    const rows = projectT3TimelineRows({
      currentStatus: "idle",
      activeTurnId: "",
      turnGroups: [
        {
          turnId: "turn-settled",
          startedAt: "2026-06-22T00:00:00.000Z",
          completedAt: "2026-06-22T00:00:08.000Z",
          userItem: {
            id: "user-settled",
            kind: "user",
            role: "user",
            content: "inspect",
            createdAt: "2026-06-22T00:00:00.000Z",
            turnId: "turn-settled",
          },
          steps: [
            {
              activityItems: [
                {
                  id: "reasoning-settled",
                  kind: "reasoning",
                  content: "I will inspect files.",
                  createdAt: "2026-06-22T00:00:01.000Z",
                  turnId: "turn-settled",
                },
                {
                  id: "tool-read",
                  kind: "tool",
                  toolName: "read_file",
                  label: "Read File",
                  status: "success",
                  createdAt: "2026-06-22T00:00:02.000Z",
                  completedAt: "2026-06-22T00:00:03.000Z",
                  args: { path: "src/main.c" },
                  turnId: "turn-settled",
                },
                {
                  id: "compact-settled",
                  kind: "compact",
                  content: "Context compacted",
                  summarizedTurns: 4,
                  recentTurns: 2,
                  createdAt: "2026-06-22T00:00:04.000Z",
                  turnId: "turn-settled",
                },
              ],
              assistantItem: {
                id: "assistant-settled",
                kind: "assistant",
                role: "assistant",
                content: "done",
                createdAt: "2026-06-22T00:00:08.000Z",
                completedAt: "2026-06-22T00:00:08.000Z",
                turnId: "turn-settled",
              },
            },
          ],
        },
      ],
    });
    assert.deepEqual(rows.map((row) => row.kind), ["message", "turn_fold", "message"]);
    const fold = rows.find((row) => row.kind === "turn_fold");
    assert.equal(fold.label, "Worked for 8s");
    assert.equal(fold.entries.some((entry) => entry.kind === "work"), true);
    assert.equal(fold.entries.some((entry) => entry.kind === "context_summary"), true);
    assert.equal(rows.some((row) => row.kind === "compact"), false);
  }

  {
    const rows = projectT3TimelineRows({
      currentStatus: "running",
      activeTurnId: "turn-active",
      thinkingActive: true,
      turnGroups: [
        {
          turnId: "turn-active",
          startedAt: "2026-06-22T00:01:00.000Z",
          userItem: {
            id: "user-active",
            kind: "user",
            role: "user",
            content: "build",
            createdAt: "2026-06-22T00:01:00.000Z",
            turnId: "turn-active",
          },
          steps: [
            {
              activityItems: [
                {
                  id: "tool-running",
                  kind: "tool",
                  toolName: "run_recipe",
                  label: "Run Recipe",
                  status: "running",
                  tone: "running",
                  createdAt: "2026-06-22T00:01:03.000Z",
                  turnId: "turn-active",
                },
                {
                  id: "compact-active",
                  kind: "compact",
                  content: "Context compacted",
                  createdAt: "2026-06-22T00:01:04.000Z",
                  turnId: "turn-active",
                },
              ],
            },
          ],
        },
      ],
    });
    assert.deepEqual(rows.map((row) => row.kind), ["message", "work", "system_notice", "working"]);
    assert.equal(rows.find((row) => row.kind === "system_notice").placement, "active_turn_boundary");
    assert.equal(rows.find((row) => row.kind === "work").status, "running");
  }

  {
    const rows = projectT3TimelineRows({
      currentStatus: "idle",
      activeTurnId: "",
      turnGroups: [
        {
          turnId: "turn-failed",
          userItem: {
            id: "user-failed",
            kind: "user",
            role: "user",
            content: "verify",
            createdAt: "2026-06-22T00:02:00.000Z",
            turnId: "turn-failed",
          },
          steps: [
            {
              activityItems: [
                {
                  id: "tool-failed",
                  kind: "tool",
                  toolName: "run_recipe",
                  label: "Run Recipe",
                  status: "error",
                  tone: "error",
                  createdAt: "2026-06-22T00:02:02.000Z",
                  turnId: "turn-failed",
                },
              ],
              assistantItem: {
                id: "assistant-failed",
                kind: "assistant",
                role: "assistant",
                content: "build failed",
                createdAt: "2026-06-22T00:02:05.000Z",
                turnId: "turn-failed",
              },
            },
          ],
        },
      ],
    });
    assert.deepEqual(rows.map((row) => row.kind), ["message", "work", "message"]);
    assert.equal(rows.some((row) => row.kind === "turn_fold"), false);
  }
```

Modify `src/embedagent/frontend/gui/webapp/test/timeline-ui-state.test.mjs` with:

```javascript
  {
    const key = rowUiKey({ kind: "context_summary", id: "ctx-1", turnId: "turn-1" });
    assert.equal(key, "context_summary:turn-1:ctx-1");
    assert.equal(isRowExpandedByDefault({ kind: "context_summary" }), false);
  }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `compact` currently projects as a standalone row kind and `context_summary` is not a supported row kind.

- [ ] **Step 3: Keep the failing tests unstaged until Task 6**

Do not commit the red tests separately. Leave the test edits in the worktree and continue directly to Task 6 so the timeline projector change and its tests land in one task-scoped commit.

## Task 6: T3 Timeline Row Model And Renderer

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`

- [ ] **Step 1: Add context summary row kind and UI state key**

Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`.

Change `T3_ROW_KINDS`:

```javascript
export const T3_ROW_KINDS = Object.freeze({
  MESSAGE: "message",
  WORK: "work",
  TURN_FOLD: "turn_fold",
  INTERACTION: "interaction",
  DIFF_SUMMARY: "diff_summary",
  CONTEXT_SUMMARY: "context_summary",
  COMMAND_RESULT: "command_result",
  REVIEW_RESULT: "review_result",
  WORKING: "working",
  SYSTEM_NOTICE: "system_notice",
});
```

Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`.

Ensure key and default expansion support:

```javascript
export function rowUiKey(row) {
  const kind = String(row?.kind || "row");
  const turnId = String(row?.turnId || row?.turn_id || "");
  const id = String(row?.id || "");
  if (turnId && id) return `${kind}:${turnId}:${id}`;
  if (id) return `${kind}:${id}`;
  return `${kind}:unknown`;
}

export function isRowExpandedByDefault(row) {
  const kind = String(row?.kind || "");
  if (kind === "work") return row?.status === "error" || row?.tone === "error";
  if (kind === "command_result" || kind === "review_result") return row?.success === false;
  if (kind === "turn_fold") return Boolean(row?.defaultOpen);
  if (kind === "context_summary") return false;
  return false;
}
```

- [ ] **Step 2: Replace compact row projection with context summary projection**

Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`.

Replace `compactRow(...)` with:

```javascript
function contextSummaryRow(item, placement = "fold_body") {
  return {
    id: stringValue(item?.id || `context-${item?.turnId || item?.turn_id || "row"}`),
    kind: T3_ROW_KINDS.CONTEXT_SUMMARY,
    turnId: stringValue(item?.turnId || item?.turn_id),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    placement,
    tone: "context",
    label: stringValue(item?.label || "Context"),
    content: stringValue(item?.content || item?.summary || "Context compacted"),
    summarizedTurns:
      item?.summarizedTurns !== undefined
        ? numberValue(item.summarizedTurns)
        : item?.summarized_turns !== undefined
          ? numberValue(item.summarized_turns)
          : undefined,
    recentTurns:
      item?.recentTurns !== undefined
        ? numberValue(item.recentTurns)
        : item?.recent_turns !== undefined
          ? numberValue(item.recent_turns)
          : undefined,
    approxTokensAfter:
      item?.approxTokensAfter !== undefined
        ? numberValue(item.approxTokensAfter)
        : item?.approx_tokens_after !== undefined
          ? numberValue(item.approx_tokens_after)
          : undefined,
    rawItem: item || {},
  };
}
```

Change `activityRowForItem(...)` so compact maps to context summary:

```javascript
  if (item.kind === "compact") return contextSummaryRow(item);
```

Remove the standalone `COMPACT` handling from `TimelineRows.jsx` after renderer support lands.

- [ ] **Step 3: Rework fold decision around T3-style settled turns**

Modify `isTurnFoldedByDefault(...)`:

```javascript
export function isTurnFoldedByDefault(group, context = {}) {
  const entries = turnActivityEntries(group);
  const foldEntries = foldEntriesForTurn(group);
  const workEntries = entries.filter((entry) => entry.kind === T3_ROW_KINDS.WORK);
  if (foldEntries.length === 0) return false;
  if (group?.turnId && group.turnId === context.activeTurnId && context.currentStatus === "running") return false;
  if (hasInterruptedWork(workEntries)) return false;
  if (workEntries.some((entry) => entry.status === "running" || entry.tone === "running")) return false;
  if (workEntries.some((entry) => entry.status === "error" || entry.tone === "error")) return false;
  return assistantRowsForTurn(group).length > 0;
}
```

Modify `turnActivityEntries(...)` so reasoning rows are included only inside fold entries, not standalone main rows:

```javascript
function turnActivityEntries(group) {
  const entries = [];
  function pushActivity(item) {
    const row = activityRowForItem(item);
    if (row) entries.push(row);
  }
  for (const step of group?.steps || []) {
    for (const item of step?.activityItems || []) {
      if (item?.kind === "reasoning") continue;
      pushActivity(item);
    }
  }
  for (const item of group?.trailingTurnItems || []) {
    if (item?.kind === "tool" || item?.kind === "compact" || item?.kind === "interaction_requested" || item?.kind === "interaction_resolved") {
      pushActivity(item);
    }
  }
  for (const item of group?.detachedItems || []) {
    if (item?.kind === "tool" || item?.kind === "compact" || item?.kind === "interaction_requested" || item?.kind === "interaction_resolved") {
      pushActivity(item);
    }
  }
  return entries;
}
```

Modify `orderedOpenRowsForTurn(...)` so active compact/context becomes an adjacent system notice instead of a compact box:

```javascript
function orderedOpenRowsForTurn(group, context = {}) {
  const rows = [];
  for (const step of group?.steps || []) {
    for (const item of step?.activityItems || []) {
      if (item?.kind === "reasoning") continue;
      const row = activityRowForItem(item);
      if (!row) continue;
      if (row.kind === T3_ROW_KINDS.CONTEXT_SUMMARY) {
        rows.push({ ...row, kind: T3_ROW_KINDS.SYSTEM_NOTICE, placement: "active_turn_boundary" });
      } else {
        rows.push(row);
      }
    }
    if (step?.assistantItem) rows.push(messageRow(step.assistantItem, "assistant"));
  }
  for (const item of (group?.trailingTurnItems || []).concat(group?.detachedItems || [])) {
    if (item?.kind === "tool" || item?.kind === "compact" || item?.kind === "interaction_requested" || item?.kind === "interaction_resolved") {
      const row = activityRowForItem(item);
      if (!row) continue;
      rows.push(row.kind === T3_ROW_KINDS.CONTEXT_SUMMARY ? { ...row, kind: T3_ROW_KINDS.SYSTEM_NOTICE, placement: "active_turn_boundary" } : row);
    }
  }
  return rows;
}
```

Modify calls to pass context:

```javascript
for (const row of orderedOpenRowsForTurn(group, context)) pushRow(row);
```

Keep `foldEntriesForTurn(...)` using `orderedOpenRowsForTurn(group)` without active placement conversion for folded bodies:

```javascript
function foldEntriesForTurn(group) {
  const terminalAssistantItem = terminalAssistantItemForTurn(group);
  return orderedOpenRowsForTurn(group).filter((row) => {
    if (row.kind !== T3_ROW_KINDS.MESSAGE || row.role !== "assistant") return true;
    return row.id !== stringValue(terminalAssistantItem?.id);
  });
}
```

- [ ] **Step 4: Render context summary rows in fold body**

Modify `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`.

Replace `CompactRow(...)` with:

```javascript
function ContextSummaryRow({ row }) {
  const parts = [];
  if (row.summarizedTurns !== undefined) parts.push(`${row.summarizedTurns} summarized`);
  if (row.recentTurns !== undefined) parts.push(`${row.recentTurns} retained`);
  if (row.approxTokensAfter !== undefined) parts.push(`~${Number(row.approxTokensAfter).toLocaleString()} tokens`);
  return (
    <div className="t3-context-summary-row system-card context" data-testid="timeline-context-summary-row" data-row-kind="context_summary" role="status">
      <span>{row.content || "Context updated"}</span>
      {parts.length > 0 ? <span className="t3-rich-row-meta">{parts.join(" / ")}</span> : null}
    </div>
  );
}
```

Change switch handling:

```javascript
  if (row.kind === "context_summary") return <ContextSummaryRow row={row} />;
```

Remove:

```javascript
  if (row.kind === "compact") return <CompactRow row={row} />;
```

- [ ] **Step 5: Remove legacy timeline renderer fallback**

Modify `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`.

Keep the T3 rows path as the only product renderer:

```jsx
      <TimelineRows
        rows={t3Rows}
        onOpenDiff={onOpenDiff}
        onOpenFile={onOpenFile}
        markdownComponents={markdownComponents}
        rowUiState={rowUiState}
        onToggleRow={toggleRow}
        rowKeyFor={rowUiKey}
      />
```

Remove the branch that renders legacy grouped timeline items when `t3Rows.length > 0`. Keep the empty state and error/notice wrappers. After the branch is removed, run `npm run build`; delete any now-unused helper functions or imports that the build reports in `Timeline.jsx`.

- [ ] **Step 6: Update CSS class names**

Modify `src/embedagent/frontend/gui/webapp/src/styles.css`.

Replace `.t3-compact-row` usages with:

```css
.t3-context-summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  min-width: 0;
  font-family: var(--font-mono);
  font-size: 10px;
}
```

Keep `.system-card.context` styling.

- [ ] **Step 7: Run tests and build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 8: Commit Task 6**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs src/embedagent/frontend/gui/webapp/test/timeline-ui-state.test.mjs src/embedagent/frontend/gui/static/index.html src/embedagent/frontend/gui/static/assets/app.js src/embedagent/frontend/gui/static/assets/app.css
git commit -m "feat(gui): replace timeline projection with t3 row model"
```

## Task 7: Layout, Visual QA, And Documentation

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
- Modify: `scripts/gui-visual-debug.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Write failing CSS/source assertions**

Modify `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`.

Add assertions:

```javascript
  assert.equal(css.includes(".workbench-layout.drawer-open .workbench-center"), true);
  assert.equal(css.includes("var(--bottom-drawer-h-raw"), true);
  assert.equal(css.includes(".right-panel-tab-strip"), true);
  assert.equal(css.includes(".floating-menu-layer"), true);
  assert.equal(css.includes(".terminal-shell-panes.split-horizontal"), true);
  assert.equal(css.includes(".terminal-shell-panes.split-vertical"), true);
```

Modify `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`.

Add:

```javascript
  assert.equal(source.includes("loadPanelOverflowFixture"), true);
  assert.equal(source.includes("loadTerminalSplitFixture"), true);
  assert.equal(source.includes("loadTimelineContextFixture"), true);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because the fixture helpers and CSS variable are not present.

- [ ] **Step 3: Make bottom drawer height state-ready without adding resize UI**

Modify `src/embedagent/frontend/gui/webapp/src/styles.css`.

At the variable block near the top, add:

```css
  --bottom-drawer-h-raw: 220px;
```

Change:

```css
.workbench-layout.drawer-open .workbench-center {
  grid-template-rows: minmax(0, 1fr) 220px;
}
```

to:

```css
.workbench-layout.drawer-open .workbench-center {
  grid-template-rows: minmax(0, 1fr) clamp(160px, var(--bottom-drawer-h-raw), 520px);
}
```

Do not add a new bottom-drawer resize handle in this task. Instead, add `bottomDrawerHeight` to `AppSidebarLayout.jsx` props and set the variable from persisted workbench state on the root `.workbench-layout` element:

```jsx
style={{
  "--bottom-drawer-h-raw": `${Number(bottomDrawerHeight || 220)}px`,
}}
```

Pass `bottomDrawerHeight={state.workbench.bottomDrawer.height}` from `App.jsx` into `AppSidebarLayout`.

This makes the layout consume persisted drawer height without introducing a new drag interaction.

- [ ] **Step 4: Add visual debug fixture helpers**

Modify `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`.

Add exports:

```javascript
export function loadPanelOverflowFixture(dispatch) {
  dispatch({ type: "visual_thread_lifecycle_fixture_loaded", sessionId: "visual-panel-overflow", sessions: [{ session_id: "visual-panel-overflow", user_goal: "Panel overflow fixture" }] });
  for (const surface of [
    { kind: "files" },
    { kind: "diff", resourceId: "current" },
    { kind: "plan" },
    { kind: "source_control" },
    { kind: "settings" },
    { kind: "diagnostics" },
    { kind: "preview", resourceId: "preview-a" },
    { kind: "terminal", resourceId: "term-a", terminalId: "term-a", terminalIds: ["term-a"], activeTerminalId: "term-a" },
  ]) {
    dispatch({ type: "workbench_surface_opened", placement: "right", ...surface });
  }
}

export function loadTerminalSplitFixture(dispatch) {
  dispatch({ type: "visual_thread_lifecycle_fixture_loaded", sessionId: "visual-terminal-split", sessions: [{ session_id: "visual-terminal-split", user_goal: "Terminal split fixture" }] });
  dispatch({
    type: "terminal_snapshot_loaded",
    snapshot: { session_id: "visual-terminal-split", terminal_id: "term-a", status: "running", history: "term-a ready\\n", cols: 100, rows: 30 },
  });
  dispatch({
    type: "terminal_snapshot_loaded",
    snapshot: { session_id: "visual-terminal-split", terminal_id: "term-b", status: "running", history: "term-b ready\\n", cols: 100, rows: 30 },
  });
  dispatch({
    type: "workbench_surface_opened",
    placement: "right",
    kind: "terminal",
    resourceId: "term-a",
    terminalId: "term-a",
    terminalIds: ["term-a", "term-b"],
    activeTerminalId: "term-b",
    splitDirection: "vertical",
  });
}

export function loadTimelineContextFixture(dispatch) {
  dispatch({
    type: "visual_timeline_fixture_loaded",
    sessionId: "visual-timeline-context",
    activeTurnId: "turn-context-active",
    thinkingActive: true,
    timeline: [
      { id: "user-context", kind: "user", role: "user", content: "Build the project", turnId: "turn-context-active" },
      { id: "tool-running", kind: "tool", toolName: "run_recipe", label: "Run Recipe", status: "running", tone: "running", turnId: "turn-context-active" },
      { id: "compact-active", kind: "compact", content: "Context compacted", summarizedTurns: 5, recentTurns: 2, turnId: "turn-context-active" },
    ],
  });
}
```

Wire these helpers into `installVisualDebugFixtures(...)` in the same file by adding:

```javascript
    loadPanelOverflowFixture() {
      loadPanelOverflowFixture(dispatch);
    },
    loadTerminalSplitFixture() {
      loadTerminalSplitFixture(dispatch);
    },
    loadTimelineContextFixture() {
      loadTimelineContextFixture(dispatch);
    },
```

- [ ] **Step 5: Extend visual debug runner scenarios**

Modify `scripts/gui-visual-debug.mjs`.

Extend the exported `SCENARIOS` array at the top:

```javascript
export const SCENARIOS = ["load", "chat", "composer", "palette", "preview", "diff", "file", "terminal", "responsive", "app", "thread", "timeline", "interaction", "panel-overflow", "terminal-split", "timeline-context"];
```

Add runner functions near the existing scenario functions:

```javascript
async function runPanelOverflowScenario(page, outputDir) {
  await page.evaluate(() => window.__EMBEDAGENT_VISUAL_DEBUG__?.loadPanelOverflowFixture?.());
  await page.getByTestId("right-panel-surface-tabs").waitFor();
  await page.getByLabel("Add panel surface").click();
  const menuVisible = await page.locator(".right-panel-add-menu-popup").isVisible();
  assert.equal(menuVisible, true);
  const menuBox = await page.locator(".right-panel-add-menu-popup").boundingBox();
  const tabsBox = await page.getByTestId("right-panel-surface-tabs").boundingBox();
  assert.equal(Boolean(menuBox && tabsBox && menuBox.height > tabsBox.height), true);
  return { menuEscapesTabbar: true };
}

async function runTerminalSplitScenario(page) {
  await page.evaluate(() => window.__EMBEDAGENT_VISUAL_DEBUG__?.loadTerminalSplitFixture?.());
  await page.getByTestId("right-panel-terminal-surface").waitFor();
  const paneCount = await page.locator(".terminal-shell-pane").count();
  assert.equal(paneCount, 2);
  return { paneCount };
}

async function runTimelineContextScenario(page) {
  await page.evaluate(() => window.__EMBEDAGENT_VISUAL_DEBUG__?.loadTimelineContextFixture?.());
  await page.getByTestId("timeline-root").waitFor();
  const compactRows = await page.locator('[data-row-kind="compact"]').count();
  assert.equal(compactRows, 0);
  const contextRows = await page.locator('[data-row-kind="context_summary"], [data-row-kind="system_notice"]').count();
  return { compactRows, contextRows };
}
```

Add branches in `runScenarios(...)` beside the existing scenario switch:

```javascript
      } else if (scenario === "panel-overflow") {
        results[scenario] = await runPanelOverflowScenario(page, outputDir);
      } else if (scenario === "terminal-split") {
        results[scenario] = await runTerminalSplitScenario(page);
      } else if (scenario === "timeline-context") {
        results[scenario] = await runTimelineContextScenario(page);
```

Do not add a separate screenshot helper. The existing `captureScenario({ page, scenario, outputDir })` call at the end of each non-responsive scenario will capture these new scenarios automatically.

- [ ] **Step 6: Update durable docs**

Modify `docs/modules/frontend-gui.md` with a short section:

```markdown
### T3-Style GUI Shell Parity

The GUI workbench now treats right-panel surfaces, terminal grouping, floating menus, and timeline row expansion as app-shell display state. These models are derived in the webapp and do not write transcript history, workflow state, permission policy, runtime reducers, extension loading state, telemetry, or source-control checkpoints.

The right panel follows the T3 Code surface model: ordered surface descriptors, an active surface id, resource-specific file/preview/terminal surfaces, singleton local surfaces, and floating tab menus outside tab-scroll clipping. Terminal UI uses one shared shell for bottom drawer and right-panel owners while continuing to consume the existing GUI terminal backend service. Timeline rows are projected through the frontend-local T3 row model; compact/context display is turn-associated display metadata, not Agent Core context policy.
```

Modify `docs/development-tracker.md` with an entry under the current GUI section:

```markdown
- 2026-06-22: Planned and implemented T3 GUI parity shell stabilization for right-panel floating menus, surface-store parity, shared terminal shell, and frontend-local timeline row model. Agent Core, transcript truth, reducers, workflow packages, permission policy, and backend protocol semantics remain unchanged.
```

Modify `docs/design-change-log.md` with:

```markdown
## 2026-06-22 - T3 GUI Parity Shell

- Copied T3 Code's GUI shell architecture shape for right-panel surfaces, floating tab menus, terminal drawer/panel ownership, and timeline row projection.
- Kept all display state in the GUI app shell.
- Preserved the minimal Agent Core boundary: no QueryEngine, transcript, permission, workflow package, reducer, provider, or extension-loading changes.
```

- [ ] **Step 7: Run full verification for GUI slice**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../../
uv run pytest tests/test_gui_terminal_api.py tests/test_gui_terminal_service.py tests/test_gui_app_shell.py tests/test_gui_backend_api.py -v
node scripts/gui-visual-debug.mjs --scenario panel-overflow,terminal-split,timeline-context,responsive --no-build --output "$env:TEMP\embedagent-t3-gui-parity-shell"
```

Expected: PASS. If the visual harness cannot launch a browser in the local environment, record the exact command output and keep `npm test`, `npm run build`, and Python tests as required passing gates.

- [ ] **Step 8: Commit Task 7**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js scripts/gui-visual-debug.mjs src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs docs/modules/frontend-gui.md docs/development-tracker.md docs/design-change-log.md src/embedagent/frontend/gui/static/index.html src/embedagent/frontend/gui/static/assets/app.js src/embedagent/frontend/gui/static/assets/app.css
git commit -m "test(gui): cover t3 shell visual parity"
```

## Final Verification

- [ ] **Step 1: Run webapp tests**

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 2: Build webapp and static assets**

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: PASS and refreshed `src/embedagent/frontend/gui/static/` assets.

- [ ] **Step 3: Run focused Python GUI tests**

```bash
uv run pytest tests/test_gui_terminal_api.py tests/test_gui_terminal_service.py tests/test_gui_app_shell.py tests/test_gui_backend_api.py -v
```

Expected: PASS.

- [ ] **Step 4: Run visual debug scenarios**

```bash
node scripts/gui-visual-debug.mjs --scenario panel-overflow,terminal-split,timeline-context,responsive --no-build --output "$env:TEMP\embedagent-t3-gui-parity-shell"
```

Expected: PASS with screenshots in the output directory.

- [ ] **Step 5: Confirm Agent Core isolation**

Run:

```bash
git diff --name-only main...HEAD
```

Expected: changed files are limited to GUI webapp, GUI static assets, visual debug script, GUI docs, and tests listed in this plan. No files under `src/embedagent/harness/`, `src/embedagent/query_engine.py`, `src/embedagent/agent_*.py`, `src/embedagent/context.py`, `src/embedagent/permissions.py`, `src/embedagent/runtime_config.py`, `src/embedagent/compaction_state.py`, or `src/embedagent/recovery_state.py` should appear.

## Execution Notes

- Keep commits task-scoped.
- Do not add npm dependencies.
- Do not modify `uv.lock`.
- Do not modify `config/config.json`.
- Do not change Agent Core, workflow packages, permission policy, transcript truth, runtime reducers, or backend protocol semantics for display-only behavior.
- Preserve official vocabulary: `build`, `tasks`, `current_phase`, `discipline_profile`; do not reintroduce `code` or `todos`.
