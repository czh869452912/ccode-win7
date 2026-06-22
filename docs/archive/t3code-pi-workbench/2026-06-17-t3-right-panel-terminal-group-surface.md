# T3 Right Panel Terminal Group Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement T3 Code-style right-panel terminal surfaces that own `terminalIds`, `activeTerminalId`, split direction, pane activation, and pane close behavior.

**Architecture:** Keep the feature entirely in the GUI app shell. `workbench/surfaces.js` owns shallow right-panel terminal surface layout state, `terminal/terminal-state.js` continues to own terminal runtime snapshots and buffers, and `App.jsx` bridges right-panel actions to existing terminal backend routes without opening the bottom drawer.

**Tech Stack:** React, plain JavaScript ES modules, Node-based webapp tests, existing Python GUI terminal backend, Playwright visual debug harness.

---

## File Structure

- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - Add T3-style terminal surface normalization and pure reducer operations.
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - Add reducer tests matching `reference/t3code/apps/web/src/rightPanelStore.test.ts` terminal semantics.
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTerminalSurface.jsx`
  - Render a terminal surface-scoped pane group from `surface.terminalIds`.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - Render `RightPanelTerminalSurface` for right-panel terminal surfaces.
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Add right-panel terminal open/split/activate/send/clear/restart/close handlers that accept explicit terminal ids.
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Add source assertions for the new component and app wiring.
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Add WebView2-compatible right-panel terminal group and split-pane styling.
- Modify: `scripts/gui-visual-debug.mjs`
  - Add a `terminal` scenario.
- Modify: `docs/development-tracker.md`
  - Record slice completion after implementation.
- Modify: `docs/design-change-log.md`
  - Record durable design change after implementation.

## Task 1: Add Terminal Surface Reducer Semantics

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`

- [ ] **Step 1: Write failing reducer tests**

Append these assertions in `runWorkbenchStateTests()` after the existing `withTerminal` / `withPlan` surface setup and before command assertions:

```javascript
  const terminalOne = openSurface(initial, {
    placement: "right",
    kind: "terminal",
    terminalId: "term-1",
    resourceId: "term-1",
  });
  const terminalTwo = openSurface(terminalOne, {
    placement: "right",
    kind: "terminal",
    terminalId: "term-2",
    resourceId: "term-2",
  });
  assert.deepEqual(terminalTwo.rightPanel.surfaces, [
    {
      id: "right:terminal:term-1",
      placement: "right",
      kind: "terminal",
      title: "Terminal",
      resourceId: "term-1",
      filePath: "",
      terminalId: "term-1",
      terminalIds: ["term-1"],
      activeTerminalId: "term-1",
      revealLine: null,
      revealRequestId: 0,
    },
    {
      id: "right:terminal:term-2",
      placement: "right",
      kind: "terminal",
      title: "Terminal",
      resourceId: "term-2",
      filePath: "",
      terminalId: "term-2",
      terminalIds: ["term-2"],
      activeTerminalId: "term-2",
      revealLine: null,
      revealRequestId: 0,
    },
  ]);
  assert.equal(terminalTwo.rightPanel.activeSurfaceId, "right:terminal:term-2");

  const splitTerminal = reduceWorkbenchState(terminalOne, {
    type: "workbench_terminal_surface_split",
    placement: "right",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-2",
  });
  assert.deepEqual(splitTerminal.rightPanel.surfaces[0].terminalIds, ["term-1", "term-2"]);
  assert.equal(splitTerminal.rightPanel.surfaces[0].activeTerminalId, "term-2");
  assert.equal(splitTerminal.rightPanel.surfaces[0].splitDirection, undefined);
  assert.equal(splitTerminal.rightPanel.activeSurfaceId, "right:terminal:term-1");

  const activatedPane = reduceWorkbenchState(splitTerminal, {
    type: "workbench_terminal_surface_terminal_activated",
    placement: "right",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-1",
  });
  assert.equal(activatedPane.rightPanel.surfaces[0].activeTerminalId, "term-1");

  const closedPane = reduceWorkbenchState(activatedPane, {
    type: "workbench_terminal_surface_terminal_closed",
    placement: "right",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-1",
  });
  assert.deepEqual(closedPane.rightPanel.surfaces[0].terminalIds, ["term-2"]);
  assert.equal(closedPane.rightPanel.surfaces[0].activeTerminalId, "term-2");

  const verticalSplit = reduceWorkbenchState(terminalOne, {
    type: "workbench_terminal_surface_split",
    placement: "right",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-2",
    splitDirection: "vertical",
  });
  assert.equal(verticalSplit.rightPanel.surfaces[0].splitDirection, "vertical");

  const finalClosedPane = reduceWorkbenchState(terminalOne, {
    type: "workbench_terminal_surface_terminal_closed",
    placement: "right",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-1",
  });
  assert.deepEqual(finalClosedPane.rightPanel.surfaces, []);
  assert.equal(finalClosedPane.rightPanel.activeSurfaceId, null);
  assert.equal(finalClosedPane.rightPanel.activeKind, "");
  assert.equal(finalClosedPane.rightPanel.open, true);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because terminal surfaces do not yet contain `terminalIds` / `activeTerminalId`, and `workbench_terminal_surface_*` actions are ignored.

- [ ] **Step 3: Implement terminal surface shape and reducers**

In `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`, update `makeSurface(input)` so terminal surfaces normalize the T3 fields:

```javascript
function uniqueTerminalIds(ids) {
  const result = [];
  for (const id of ids || []) {
    const value = String(id || "").trim();
    if (value && !result.includes(value)) result.push(value);
  }
  return result;
}

function makeSurface(input) {
  const placement = normalizePlacement(input && input.placement);
  const kind = String((input && input.kind) || defaultActiveKind(placement));
  const filePath =
    kind === "file"
      ? normalizeFilePath(input && (input.filePath || input.resourceId))
      : String((input && input.filePath) || "");
  const resourceId =
    kind === "file" ? filePath : String((input && input.resourceId) || "");
  const terminalIds =
    kind === "terminal"
      ? uniqueTerminalIds(
          Array.isArray(input && input.terminalIds)
            ? input.terminalIds
            : [input && (input.terminalId || input.resourceId)],
        )
      : [];
  const activeTerminalId =
    kind === "terminal"
      ? String((input && input.activeTerminalId) || terminalIds[0] || "")
      : "";
  const terminalId =
    kind === "terminal"
      ? String((input && input.terminalId) || resourceId || terminalIds[0] || activeTerminalId)
      : String((input && input.terminalId) || resourceId || "");
  const base = {
    id: String((input && input.surfaceId) || surfaceIdFor({ ...input, filePath, resourceId: kind === "terminal" ? terminalId : resourceId })),
    placement,
    kind,
    title: String(
      (input && input.title) ||
        (kind === "file" ? basenameForPath(filePath) : titleForSurfaceKind(kind)),
    ),
    resourceId: kind === "terminal" ? terminalId : resourceId,
    filePath,
    terminalId,
    revealLine: kind === "file" ? normalizeRevealLine(input && input.revealLine) : null,
    revealRequestId:
      kind === "file" && Number.isSafeInteger(Number(input && input.revealRequestId))
        ? Number(input.revealRequestId)
        : 0,
  };
  if (kind !== "terminal") return base;
  return {
    ...base,
    terminalIds: terminalIds.length > 0 ? terminalIds : [terminalId].filter(Boolean),
    activeTerminalId: activeTerminalId || terminalId,
    ...(input && input.splitDirection === "vertical" ? { splitDirection: "vertical" } : {}),
  };
}
```

Add these pure helpers near the existing close helpers:

```javascript
function splitTerminalSurface(state, input) {
  const current = state || createWorkbenchState();
  if (normalizePlacement(input && input.placement) !== "right") return current;
  const surfaceId = String((input && input.surfaceId) || "");
  const terminalId = String((input && input.terminalId) || "").trim();
  if (!surfaceId || !terminalId) return current;
  const surfaces = (current.rightPanel.surfaces || []).map((surface) => {
    if (surface.id !== surfaceId || surface.kind !== "terminal") return surface;
    const terminalIds = uniqueTerminalIds([...(surface.terminalIds || []), terminalId]);
    const nextSurface = {
      ...surface,
      terminalIds,
      activeTerminalId: terminalId,
    };
    if (input && input.splitDirection === "vertical") {
      return { ...nextSurface, splitDirection: "vertical" };
    }
    const { splitDirection, ...withoutDirection } = nextSurface;
    return withoutDirection;
  });
  const active = activeSurfaceFrom(surfaces, surfaceId);
  if (!active) return current;
  return {
    ...current,
    rightPanel: activateRightPanelSurface({ ...current.rightPanel, surfaces }, active),
  };
}

function activateTerminalPane(state, input) {
  const current = state || createWorkbenchState();
  if (normalizePlacement(input && input.placement) !== "right") return current;
  const surfaceId = String((input && input.surfaceId) || "");
  const terminalId = String((input && input.terminalId) || "").trim();
  if (!surfaceId || !terminalId) return current;
  const surfaces = (current.rightPanel.surfaces || []).map((surface) =>
    surface.id === surfaceId &&
    surface.kind === "terminal" &&
    Array.isArray(surface.terminalIds) &&
    surface.terminalIds.includes(terminalId)
      ? { ...surface, activeTerminalId: terminalId }
      : surface,
  );
  const active = activeSurfaceFrom(surfaces, surfaceId);
  if (!active) return current;
  return {
    ...current,
    rightPanel: activateRightPanelSurface({ ...current.rightPanel, surfaces }, active),
  };
}

function closeTerminalPane(state, input) {
  const current = state || createWorkbenchState();
  if (normalizePlacement(input && input.placement) !== "right") return current;
  const surfaceId = String((input && input.surfaceId) || "");
  const terminalId = String((input && input.terminalId) || "").trim();
  const items = current.rightPanel.surfaces || [];
  const index = items.findIndex((surface) => surface.id === surfaceId && surface.kind === "terminal");
  if (index < 0 || !terminalId) return current;
  const surface = items[index];
  const terminalIds = (surface.terminalIds || []).filter((id) => id !== terminalId);
  if (terminalIds.length === 0) {
    return closeSurface(current, {
      placement: "right",
      surfaceId,
      kind: "terminal",
      resourceId: surface.resourceId,
    });
  }
  const nextSurface = {
    ...surface,
    terminalIds,
    activeTerminalId:
      surface.activeTerminalId === terminalId
        ? terminalIds[terminalIds.length - 1] || terminalIds[0]
        : surface.activeTerminalId,
  };
  const surfaces = items.map((item, itemIndex) => (itemIndex === index ? nextSurface : item));
  return {
    ...current,
    rightPanel: activateRightPanelSurface({ ...current.rightPanel, surfaces }, nextSurface),
  };
}
```

Wire the actions in `reduceWorkbenchState()`:

```javascript
    case "workbench_terminal_surface_split":
      return splitTerminalSurface(current, action);
    case "workbench_terminal_surface_terminal_activated":
      return activateTerminalPane(current, action);
    case "workbench_terminal_surface_terminal_closed":
      return closeTerminalPane(current, action);
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs
git commit -m "gui: add t3 terminal surface state"
```

## Task 2: Add Right-Panel Terminal Group Component

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTerminalSurface.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`

- [ ] **Step 1: Write failing source assertions**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, after the `rightPanelSurfaceBodySource` assertions, add:

```javascript
  const rightPanelTerminalSurfaceSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "RightPanelTerminalSurface.jsx"),
    "utf8",
  );
  assert.equal(rightPanelTerminalSurfaceSource.includes('data-testid="right-panel-terminal-surface"'), true);
  assert.equal(rightPanelTerminalSurfaceSource.includes("surface.terminalIds"), true);
  assert.equal(rightPanelTerminalSurfaceSource.includes("splitDirection"), true);
  assert.equal(rightPanelTerminalSurfaceSource.includes("onSplitVertical"), true);
  assert.equal(rightPanelSurfaceBodySource.includes("RightPanelTerminalSurface"), true);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `RightPanelTerminalSurface.jsx` does not exist.

- [ ] **Step 3: Create component**

Create `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTerminalSurface.jsx`:

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

export default function RightPanelTerminalSurface({
  surface,
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
  const terminalIds = Array.isArray(surface && surface.terminalIds)
    ? surface.terminalIds
    : [];
  const activeTerminalId = String((surface && surface.activeTerminalId) || terminalIds[0] || "");
  const splitDirection = surface && surface.splitDirection === "vertical" ? "vertical" : "horizontal";
  const panes = useMemo(
    () =>
      terminalIds.map((terminalId) => ({
        terminalId,
        session: sessionFor(terminal, terminalId),
      })),
    [terminal, terminalIds],
  );

  return (
    <div
      className={`right-panel-terminal-surface split-${splitDirection}`}
      data-testid="right-panel-terminal-surface"
      data-split-direction={splitDirection}
    >
      <div className="right-panel-terminal-toolbar">
        <button type="button" onClick={onNew} title="New terminal">New</button>
        <button type="button" onClick={onSplit} disabled={!activeTerminalId} title="Split terminal horizontally">
          Split
        </button>
        <button type="button" onClick={onSplitVertical} disabled={!activeTerminalId} title="Split terminal vertically">
          Split vertical
        </button>
      </div>
      <div className="right-panel-terminal-panes" data-testid="right-panel-terminal-panes">
        {panes.length > 0 ? (
          panes.map(({ terminalId, session }) => {
            const active = terminalId === activeTerminalId;
            const draft = draftsById[terminalId] || "";
            return (
              <section
                key={terminalId}
                className={`right-panel-terminal-pane${active ? " active" : ""}`}
                data-testid={`right-panel-terminal-pane--${terminalId}`}
              >
                <div className="right-panel-terminal-pane-header">
                  <button
                    type="button"
                    className="right-panel-terminal-pane-title"
                    onClick={() => onSelect(terminalId)}
                    aria-pressed={active}
                    title={(session && session.cwd) || terminalId}
                  >
                    <span>{terminalLabel(session, terminalId)}</span>
                    <span className={`terminal-status-dot ${terminalStatus(session)}`} />
                  </button>
                  <span className="right-panel-terminal-pane-status">{terminalStatus(session)}</span>
                  <button type="button" onClick={() => onClear(terminalId)} disabled={!session}>
                    Clear
                  </button>
                  <button type="button" onClick={() => onRestart(terminalId)} disabled={!session}>
                    Restart
                  </button>
                  <button type="button" onClick={() => onClose(terminalId)}>
                    Close
                  </button>
                </div>
                <pre className="right-panel-terminal-buffer">
                  {session ? session.buffer || "" : "Terminal unavailable."}
                </pre>
                <form
                  className="right-panel-terminal-input-row"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const text = draft;
                    if (!text.trim()) return;
                    setDraftsById((current) => ({ ...current, [terminalId]: "" }));
                    onSend(terminalId, `${text}\n`);
                  }}
                >
                  <span>&gt;</span>
                  <input
                    value={draft}
                    onFocus={() => onSelect(terminalId)}
                    onChange={(event) =>
                      setDraftsById((current) => ({
                        ...current,
                        [terminalId]: event.target.value,
                      }))
                    }
                    placeholder="Type a command"
                    disabled={!session || terminalStatus(session) === "closed"}
                  />
                </form>
              </section>
            );
          })
        ) : (
          <div className="right-panel-terminal-empty">
            <button type="button" onClick={onNew}>New terminal</button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Render component from surface body**

Modify `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`:

```javascript
import RightPanelTerminalSurface from "./RightPanelTerminalSurface.jsx";
```

Replace the `surface.kind === "terminal"` branch with:

```javascript
  if (surface.kind === "terminal") {
    return (
      <RightPanelTerminalSurface
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

Add `onTerminalSplit` and `onTerminalSplitVertical` to the function parameter list after `onTerminalNew`.

- [ ] **Step 5: Add CSS**

Append to `src/embedagent/frontend/gui/webapp/src/styles.css`:

```css
.right-panel-terminal-surface {
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-default);
}

.right-panel-terminal-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px;
  border-bottom: 1px solid var(--border-default);
}

.right-panel-terminal-toolbar button,
.right-panel-terminal-pane-header button,
.right-panel-terminal-empty button {
  border: 1px solid var(--border-default);
  background: var(--bg-panel);
  color: var(--text-primary);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
}

.right-panel-terminal-toolbar button:disabled,
.right-panel-terminal-pane-header button:disabled {
  opacity: 0.45;
}

.right-panel-terminal-panes {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 1px;
  background: var(--border-default);
}

.right-panel-terminal-surface.split-horizontal .right-panel-terminal-panes {
  flex-direction: column;
}

.right-panel-terminal-surface.split-vertical .right-panel-terminal-panes {
  flex-direction: row;
}

.right-panel-terminal-pane {
  min-width: 0;
  min-height: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-default);
  border: 1px solid transparent;
}

.right-panel-terminal-pane.active {
  border-color: var(--color-accent);
}

.right-panel-terminal-pane-header {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 6px;
  border-bottom: 1px solid var(--border-default);
  overflow: hidden;
}

.right-panel-terminal-pane-title {
  min-width: 0;
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
}

.right-panel-terminal-pane-title span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.right-panel-terminal-pane-status {
  color: var(--text-muted);
  font-size: 11px;
}

.right-panel-terminal-buffer {
  flex: 1;
  min-height: 0;
  margin: 0;
  padding: 10px;
  overflow: auto;
  color: var(--text-primary);
  background: var(--bg-default);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.right-panel-terminal-input-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-top: 1px solid var(--border-default);
  color: var(--text-muted);
}

.right-panel-terminal-input-row input {
  min-width: 0;
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 12px;
}

.right-panel-terminal-empty {
  flex: 1;
  display: grid;
  place-items: center;
  background: var(--bg-default);
}
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTerminalSurface.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "gui: render t3 terminal surface panes"
```

## Task 3: Wire App-Level Right-Panel Terminal Actions

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing source assertions**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, near the existing `appSource` assertions, add:

```javascript
  assert.equal(appSource.includes("openRightPanelTerminalSurface"), true);
  assert.equal(appSource.includes("splitRightPanelTerminalSurface"), true);
  assert.equal(appSource.includes("closeRightPanelTerminalPane"), true);
  assert.equal(appSource.includes("workbench_terminal_surface_split"), true);
  assert.equal(appSource.includes("workbench_surface_activated\", placement: \"bottom\", kind: \"terminal\""), true);
```

The final assertion intentionally remains true for the bottom drawer path; the new right-panel path must not call that bottom-drawer activation in its own helper.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because the new handler names do not exist.

- [ ] **Step 3: Add explicit terminal-id helpers**

In `src/embedagent/frontend/gui/webapp/src/App.jsx`, keep `ensureTerminalOpen()` for bottom drawer compatibility, then add these helpers near it:

```javascript
  async function openTerminalSession(terminalId) {
    if (!state.currentSessionId) {
      dispatch({ type: "interaction_notice_set", notice: "Open a session before using the terminal." });
      return null;
    }
    const targetTerminalId = String(terminalId || nextTerminalId(state.terminal.terminalIds));
    try {
      const payload = await openTerminal(state.currentSessionId, targetTerminalId, { cols: 100, rows: 30 });
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      return targetTerminalId;
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal failed to open." });
      return null;
    }
  }

  async function sendTerminalInputTo(terminalId, text) {
    const targetTerminalId = String(terminalId || "");
    if (!state.currentSessionId || !targetTerminalId) return;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      await writeTerminal(state.currentSessionId, targetTerminalId, text);
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal write failed." });
    }
  }

  async function clearTerminalById(terminalId) {
    const targetTerminalId = String(terminalId || "");
    if (!state.currentSessionId || !targetTerminalId) return;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      const payload = await clearTerminal(state.currentSessionId, targetTerminalId);
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal clear failed." });
    }
  }

  async function restartTerminalById(terminalId) {
    const targetTerminalId = String(terminalId || "");
    if (!state.currentSessionId || !targetTerminalId) return;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      const payload = await restartTerminal(state.currentSessionId, targetTerminalId, { cols: 100, rows: 30 });
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal restart failed." });
    }
  }
```

Then simplify the existing active helpers so they call the explicit-id helpers:

```javascript
  async function sendTerminalInput(text) {
    await sendTerminalInputTo(state.terminal.activeTerminalId, text);
  }

  async function clearActiveTerminal() {
    await clearTerminalById(state.terminal.activeTerminalId);
  }

  async function restartActiveTerminal() {
    await restartTerminalById(state.terminal.activeTerminalId);
  }
```

- [ ] **Step 4: Add right-panel open/split/activate/close helpers**

Add these functions near `openRightPanelSurface()`:

```javascript
  function allKnownTerminalIds() {
    const panelIds = (state.workbench.rightPanel.surfaces || [])
      .filter((surface) => surface.kind === "terminal")
      .flatMap((surface) => surface.terminalIds || [surface.terminalId].filter(Boolean));
    return Array.from(new Set([...(state.terminal.terminalIds || []), ...panelIds]));
  }

  async function openRightPanelTerminalSurface(preferredId = "") {
    const terminalId = String(preferredId || nextTerminalId(allKnownTerminalIds()));
    const openedTerminalId = await openTerminalSession(terminalId);
    if (!openedTerminalId) return;
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
    dispatch({ type: "set_inspector", value: "terminal" });
  }

  async function splitRightPanelTerminalSurface(surface, splitDirection = "horizontal") {
    if (!surface || surface.kind !== "terminal") return;
    const terminalId = nextTerminalId(allKnownTerminalIds());
    const openedTerminalId = await openTerminalSession(terminalId);
    if (!openedTerminalId) return;
    dispatch({
      type: "workbench_terminal_surface_split",
      placement: "right",
      surfaceId: surface.id,
      terminalId: openedTerminalId,
      splitDirection,
    });
  }

  function activateRightPanelTerminalPane(surface, terminalId) {
    if (!surface || surface.kind !== "terminal") return;
    dispatch({
      type: "workbench_terminal_surface_terminal_activated",
      placement: "right",
      surfaceId: surface.id,
      terminalId,
    });
    dispatch({ type: "terminal_active_set", terminalId });
  }

  async function closeRightPanelTerminalPane(surface, terminalId) {
    if (!surface || surface.kind !== "terminal") return;
    const targetTerminalId = String(terminalId || "");
    if (!targetTerminalId) return;
    if (!state.currentSessionId) {
      dispatch({ type: "interaction_notice_set", notice: "Open a session before using the terminal." });
      return;
    }
    try {
      await closeTerminal(state.currentSessionId, targetTerminalId);
      dispatch({
        type: "terminal_event",
        event: { type: "closed", session_id: state.currentSessionId, terminal_id: targetTerminalId },
      });
      dispatch({
        type: "workbench_terminal_surface_terminal_closed",
        placement: "right",
        surfaceId: surface.id,
        terminalId: targetTerminalId,
      });
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal close failed." });
    }
  }
```

- [ ] **Step 5: Keep bottom drawer activation out of right-panel terminal opens**

Change `openRightPanelSurface(kind, title = "")` so terminal delegates to the new helper before dispatching generic surface open:

```javascript
  function openRightPanelSurface(kind, title = "") {
    const surfaceKind = String(kind || "");
    if (surfaceKind === "file") return;
    if (surfaceKind === "terminal") {
      void openRightPanelTerminalSurface();
      return;
    }
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: surfaceKind,
      title: rightPanelSurfaceTitle(surfaceKind, title),
      resourceId: surfaceKind === "diff" ? "current" : "",
    });
    dispatch({ type: "set_inspector", value: surfaceKind });
  }
```

Update right-panel activation so terminal surfaces open the referenced backend terminal without opening the bottom drawer:

```javascript
            if (surface.kind === "terminal" && surface.activeTerminalId) {
              void openTerminalSession(surface.activeTerminalId);
            }
```

- [ ] **Step 6: Pass handlers into `RightPanelSurfaceBody`**

Update the right-panel props in `App.jsx`:

```javascript
            onTerminalNew={() => openRightPanelTerminalSurface()}
            onTerminalSplit={() => splitRightPanelTerminalSurface(activeRightPanelSurface)}
            onTerminalSplitVertical={() => splitRightPanelTerminalSurface(activeRightPanelSurface, "vertical")}
            onTerminalSelect={(terminalId) => activateRightPanelTerminalPane(activeRightPanelSurface, terminalId)}
            onTerminalSend={sendTerminalInputTo}
            onTerminalClear={clearTerminalById}
            onTerminalRestart={restartTerminalById}
            onTerminalClose={(terminalId) => closeRightPanelTerminalPane(activeRightPanelSurface, terminalId)}
```

Leave bottom drawer props using the existing active helpers:

```javascript
          onTerminalNew={() => ensureTerminalOpen(nextTerminalId(state.terminal.terminalIds))}
          onTerminalSelect={(terminalId) => dispatch({ type: "terminal_active_set", terminalId })}
          onTerminalSend={sendTerminalInput}
          onTerminalClear={clearActiveTerminal}
          onTerminalRestart={restartActiveTerminal}
          onTerminalClose={closeActiveTerminal}
```

- [ ] **Step 7: Run tests and build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both PASS.

- [ ] **Step 8: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "gui: route right panel terminal actions"
```

## Task 4: Add Terminal Visual Debug Scenario

**Files:**
- Modify: `scripts/gui-visual-debug.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing source assertions**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, near existing visual debug source checks if present, or after `runTerminalStateTests()`, add:

```javascript
  const repoRoot = path.resolve(WEBAPP_ROOT, "..", "..", "..", "..", "..");
  const visualDebugSource = fs.readFileSync(
    path.join(repoRoot, "scripts", "gui-visual-debug.mjs"),
    "utf8",
  );
  assert.equal(visualDebugSource.includes('"terminal"'), true);
  assert.equal(visualDebugSource.includes("runTerminalScenario"), true);
  assert.equal(visualDebugSource.includes("right-panel-terminal-surface"), true);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because the visual debug script does not list or run a terminal scenario.

- [ ] **Step 3: Add scenario to visual debug script**

In `scripts/gui-visual-debug.mjs`, extend `SCENARIOS`:

```javascript
export const SCENARIOS = ["load", "chat", "diff", "file", "terminal", "responsive", "app", "thread", "timeline", "interaction"];
```

Add this function after `runFileScenario(page)`:

```javascript
async function runTerminalScenario(page) {
  await page.waitForSelector('[data-testid="new-session-btn"]', { timeout: 10000 });
  if (await page.locator(".thread-card.selected").count() === 0) {
    await page.click('[data-testid="new-session-btn"]');
    await page.waitForSelector(".thread-card.selected", { timeout: 15000 });
  }
  await page.waitForSelector('[data-testid="right-panel-empty-surface--terminal"]', { timeout: 10000 });
  await page.click('[data-testid="right-panel-empty-surface--terminal"]');
  await page.waitForSelector('[data-testid="right-panel-terminal-surface"]', { timeout: 15000 });
  await page.waitForSelector('[data-testid^="right-panel-terminal-pane--"]', { timeout: 15000 });
  await page.click('[data-testid="right-panel-terminal-surface"] button[title="Split terminal horizontally"]');
  await page.waitForFunction(() => {
    return document.querySelectorAll('[data-testid^="right-panel-terminal-pane--"]').length >= 2;
  }, null, { timeout: 15000 });
  const activeTab = await page.locator('[data-testid="right-panel-surface-tab--terminal"] [role="tab"]').getAttribute("aria-selected");
  const paneCount = await page.locator('[data-testid^="right-panel-terminal-pane--"]').count();
  const splitDirection = await page.locator('[data-testid="right-panel-terminal-surface"]').getAttribute("data-split-direction");
  const noOverlap = await assertNoOverlap(page);
  if (activeTab !== "true") throw new Error("Terminal tab did not become active");
  if (paneCount < 2) throw new Error(`Expected split terminal panes, saw ${paneCount}`);
  if (splitDirection !== "horizontal") throw new Error(`Expected horizontal split, saw ${splitDirection}`);
  if (!noOverlap) throw new Error("Right panel tabs overlap in terminal scenario");
  return {
    activeTab: activeTab === "true",
    paneCount,
    splitDirection,
    rightTabsDoNotOverlap: noOverlap,
  };
}
```

Wire it in `runScenarios()`:

```javascript
      } else if (scenario === "terminal") {
        results.terminal = await runTerminalScenario(page);
```

Update the help text:

```text
  --scenario load|chat|diff|file|terminal|responsive|app|thread|timeline|interaction|all
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 5: Run visual terminal scenario**

Run from repo root after `npm run build` or with existing static assets:

```bash
node scripts/gui-visual-debug.mjs --scenario terminal --no-build --output "$env:TEMP\embedagent-t3-terminal-surface" --viewports 1280x720,700x640
```

Expected: exit code 0, console count 0, result includes `activeTab: true`, `paneCount` at least 2, `splitDirection: "horizontal"`, and `rightTabsDoNotOverlap: true`.

- [ ] **Step 6: Commit**

```bash
git add scripts/gui-visual-debug.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "gui: add t3 terminal surface visual check"
```

## Task 5: Update Slice Documentation

**Files:**
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Update development tracker**

At the top of `docs/development-tracker.md`, change the update label to:

```markdown
> 更新日期：2026-06-17（T3 right-panel terminal group surface）
```

Add a new current-stage section before the file surface section:

```markdown
### 2026-06-17 - T3 Right-Panel Terminal Group Surface

- GUI right panel 已新增 T3 Code-style terminal group surface：terminal surface descriptor 现在拥有 `terminalIds`、`activeTerminalId` 和可选 `splitDirection`，可在同一 right-panel terminal tab 内 split、activate 和 close pane。
- 右侧 terminal surface 现在按 surface-scoped terminal ids 渲染 panes，不再直接展示全局 active terminal；bottom drawer terminal 保持独立入口和既有行为。
- right-panel terminal actions 继续复用现有 GUI terminal backend routes，terminal process state/output buffer 仍属于 GUI-local terminal runtime state。
- 该切片继续保持 GUI app-shell 与 Agent Core 分离：不写 transcript、workflow state、permission/runtime reducers、telemetry、provider config、extension loading、source-control checkpoints 或 Agent Core policy。
```

- [ ] **Step 2: Update design change log**

At the top of `docs/design-change-log.md` under `## 3. 当前变更记录`, add:

```markdown
### DC-170

- 日期：2026-06-17
- 变更主题：GUI T3 Code-style right-panel terminal group surfaces
- 变更摘要：
  - React webapp right panel 的 `terminal` surface 现在复制 T3 Code terminal surface model，保存 `terminalIds`、`activeTerminalId` 和可选 `splitDirection`。
  - right-panel terminal body 渲染 surface-scoped terminal panes，并支持 new、split horizontal、split vertical、activate、clear、restart 和 close pane。
  - bottom drawer terminal 与 right-panel terminal 共用现有 GUI terminal backend/runtime state，但 UI surface state 分离，打开 right-panel terminal 不再顺手打开 bottom drawer。
  - 该变更只影响 GUI-local state、presentation、visual debug harness 和既有 terminal backend route 消费路径，不写 transcript、workflow state、permission/runtime reducers、telemetry、provider config、extension loading、source-control checkpoints 或 Agent Core policy。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTerminalSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
- 关联文档：
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/archive/t3code-pi-workbench/2026-06-17-t3-right-panel-terminal-group-surface-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-17-t3-right-panel-terminal-group-surface.md`
- 是否需要 ADR：否；属于已批准的 GUI standalone app-shell / T3 Code parity program 内部 surface parity 切片，不改变 Agent Core public architecture。
- 后续动作：
  - 继续按 `reference/t3code` 规划 browser preview、deeper file/editor parity 或 source-control checkpoint/diff 后续 slices，每项继续保持 Win7/offline 和 GUI/Core separation 约束。
```

- [ ] **Step 3: Run docs diff check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 4: Commit**

```bash
git add docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: record t3 terminal surface slice"
```

## Task 6: Final Verification

**Files:**
- No direct edits unless verification reveals a defect.

- [ ] **Step 1: Run JavaScript tests**

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 2: Run frontend build**

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: PASS with Vite build output and no build errors.

- [ ] **Step 3: Run focused Python GUI tests**

```bash
uv run pytest tests/test_gui_terminal_api.py tests/test_gui_app_shell.py -v
```

Expected: PASS for all selected tests.

- [ ] **Step 4: Run visual regression scenarios**

```bash
node scripts/gui-visual-debug.mjs --scenario terminal,file,diff --no-build --output "$env:TEMP\embedagent-t3-terminal-surface" --viewports 1280x720,700x640
```

Expected: exit code 0, console count 0, terminal result with at least 2 panes, file result with file surface replacing files surface, diff result with file rail visible, and all right-panel tab overlap checks true.

- [ ] **Step 5: Run git whitespace check**

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 6: Report final status**

Include:

- Commit hashes created by each task.
- Exact verification commands and pass/fail results.
- Any skipped verification with the concrete reason.
- Confirmation that no Agent Core, transcript, workflow, permission/runtime reducer, provider, extension, telemetry, or source-control checkpoint behavior was changed.
