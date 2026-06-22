# T3 Right Panel File Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add T3 Code-style right-panel `file` surfaces so workspace files open as independent right-panel tabs instead of old Inspector previews.

**Architecture:** Keep the feature entirely in the GUI app shell. `workbench/surfaces.js` owns shallow T3-style surface descriptors, `store.js` owns GUI-local file preview content keyed by path, and `App.jsx` opens file surfaces through the existing `/api/files/{path}` backend route. Agent Core, transcript truth, workflow state, permissions, runtime reducers, providers, extensions, telemetry, and source-control checkpoints remain untouched.

**Tech Stack:** React 18, plain JavaScript modules, existing Node assert helper tests, existing CSS, existing GUI backend routes, existing Playwright visual debug runner. No new runtime dependencies.

---

## Source References

- Spec: `docs/archive/t3code-pi-workbench/2026-06-17-t3-right-panel-file-surface-design.md`
- T3 state reference: `reference/t3code/apps/web/src/rightPanelStore.ts`
- T3 state tests: `reference/t3code/apps/web/src/rightPanelStore.test.ts`
- T3 wiring reference: `reference/t3code/apps/web/src/components/ChatView.tsx`
- T3 file body reference: `reference/t3code/apps/web/src/components/files/FilePreviewPanel.tsx`
- Current state model: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- Current app wiring: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Current GUI store: `src/embedagent/frontend/gui/webapp/src/store.js`

## File Structure

- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  Adds `file` to allowed right-panel kinds, keeps addable surfaces separate, creates stable file surface ids, tracks reveal metadata, and removes the standalone `files` surface when opening a file.
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  Adds red/green coverage for T3-style file open, reuse, reveal request incrementing, replacement of `files`, and unknown-kind rejection.
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
  Adds GUI-local `filePreviewsByPath` state and reducer cases for load started, loaded, and failed.
- Modify: `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`
  Clears `filePreviewsByPath` on workspace switch.
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
  Rewires `openFile(path, line)` to open a `file` surface and then load content into `filePreviewsByPath`.
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx`
  Renders the active file surface body with loading, error, and content states.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  Routes `surface.kind === "file"` to `FilePreviewSurface`.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
  Adds copy/icon support for file tabs while keeping the add menu limited to manually addable surfaces.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  Keeps old Inspector tabs from inheriting `file` by continuing to use the addable surface list only.
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
  Styles the file surface body and keeps file tab text stable at narrow widths.
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  Adds store/source assertions that prove file surfaces are GUI-local and not old Inspector preview loads.
- Modify: `scripts/gui-visual-debug.mjs`
  Adds a `file` scenario that opens the Files surface, clicks `README.md`, and verifies the active file surface.
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`
  Adds parser/source assertions for the new `file` scenario.
- Modify: `docs/development-tracker.md`
  Adds the completed slice note after implementation.
- Modify: `docs/design-change-log.md`
  Adds the design change note after implementation.

---

## Task 1: T3 File Surface State

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`

- [ ] **Step 1: Write failing reducer tests**

Update the imports in `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs` to include `RIGHT_PANEL_KINDS`:

```js
import {
  BOTTOM_DRAWER_SURFACES,
  RIGHT_PANEL_KINDS,
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

At the start of `runWorkbenchStateTests()`, replace the current right-panel kind assertion with:

```js
  assert.deepEqual(RIGHT_PANEL_KINDS, ["diff", "files", "file", "terminal", "plan"]);
  assert.deepEqual(RIGHT_PANEL_SURFACES, ["diff", "files", "terminal", "plan"]);
  assert.equal(BOTTOM_DRAWER_SURFACES.includes("terminal"), true);
  assert.equal(BOTTOM_DRAWER_SURFACES.includes("run_output"), true);
```

After the existing `withFiles` assertions, add this independent file-surface block:

```js
  const withFile = openSurface(withFiles, {
    placement: "right",
    kind: "file",
    filePath: "src/main.c",
  });
  assert.equal(withFile.rightPanel.activeKind, "file");
  assert.equal(withFile.rightPanel.activeSurfaceId, "right:file:src/main.c");
  assert.deepEqual(withFile.rightPanel.surfaces.map((surface) => surface.kind), ["file"]);
  assert.equal(withFile.rightPanel.surfaces[0].title, "main.c");
  assert.equal(withFile.rightPanel.surfaces[0].resourceId, "src/main.c");
  assert.equal(withFile.rightPanel.surfaces[0].filePath, "src/main.c");
  assert.equal(withFile.rightPanel.surfaces[0].revealLine, null);
  assert.equal(withFile.rightPanel.surfaces[0].revealRequestId, 1);

  const revealedFile = openSurface(withFile, {
    placement: "right",
    kind: "file",
    filePath: "src/main.c",
    revealLine: 42,
  });
  assert.equal(revealedFile.rightPanel.surfaces.length, 1);
  assert.equal(revealedFile.rightPanel.surfaces[0].revealLine, 42);
  assert.equal(revealedFile.rightPanel.surfaces[0].revealRequestId, 2);

  const resetRevealFile = openSurface(revealedFile, {
    placement: "right",
    kind: "file",
    filePath: "src/main.c",
  });
  assert.equal(resetRevealFile.rightPanel.surfaces[0].revealLine, null);
  assert.equal(resetRevealFile.rightPanel.surfaces[0].revealRequestId, 3);

  const secondFile = openSurface(resetRevealFile, {
    placement: "right",
    kind: "file",
    filePath: "README.md",
  });
  assert.deepEqual(secondFile.rightPanel.surfaces.map((surface) => surface.id), [
    "right:file:src/main.c",
    "right:file:README.md",
  ]);
  assert.equal(secondFile.rightPanel.activeSurfaceId, "right:file:README.md");
```

After the existing `reduced` assertion block, add an unknown-kind guard:

```js
  const unknownRightSurface = openSurface(initial, {
    placement: "right",
    kind: "settings",
    title: "Settings",
  });
  assert.equal(unknownRightSurface, initial);
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `RIGHT_PANEL_KINDS` is not exported and `file` is not an allowed right-panel kind.

- [ ] **Step 3: Implement allowed kinds and file surface descriptors**

In `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`, keep `RIGHT_PANEL_SURFACES` as the manually addable surface list and add `RIGHT_PANEL_KINDS`:

```js
export const RIGHT_PANEL_KINDS = ["diff", "files", "file", "terminal", "plan"];
export const RIGHT_PANEL_SURFACES = ["diff", "files", "terminal", "plan"];
export const BOTTOM_DRAWER_SURFACES = ["terminal", "run_output", "logs"];
```

Update `allowedKinds(placement)` so right-panel validation uses `RIGHT_PANEL_KINDS`:

```js
function allowedKinds(placement) {
  return placement === "bottom" ? BOTTOM_DRAWER_SURFACES : RIGHT_PANEL_KINDS;
}
```

Add path helpers near the existing normalization helpers:

```js
function normalizeFilePath(path) {
  return String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

function basenameForPath(path) {
  const normalized = normalizeFilePath(path);
  if (!normalized) return "";
  const parts = normalized.split("/");
  return parts[parts.length - 1] || normalized;
}

function normalizeRevealLine(line) {
  const value = Number(line);
  if (!Number.isFinite(value)) return null;
  return Math.max(1, Math.trunc(value));
}
```

Update `surfaceIdFor(input)` so file surfaces derive their resource id from `filePath`:

```js
function surfaceIdFor(input) {
  const placement = normalizePlacement(input && input.placement);
  const kind = String((input && input.kind) || defaultActiveKind(placement));
  const filePath = kind === "file" ? normalizeFilePath(input && (input.filePath || input.resourceId)) : "";
  const resourceId = filePath || String((input && input.resourceId) || "");
  return resourceId ? `${placement}:${kind}:${resourceId}` : `${placement}:${kind}`;
}
```

Update `titleForSurfaceKind(kind)` with a `file` branch:

```js
    case "file":
      return "File";
```

Update `makeSurface(input)` so file surfaces get title, resource id, and reveal metadata:

```js
function makeSurface(input) {
  const placement = normalizePlacement(input && input.placement);
  const kind = String((input && input.kind) || defaultActiveKind(placement));
  const filePath = kind === "file"
    ? normalizeFilePath(input && (input.filePath || input.resourceId))
    : String((input && input.filePath) || "");
  const resourceId = kind === "file"
    ? filePath
    : String((input && input.resourceId) || "");
  return {
    id: String((input && input.surfaceId) || surfaceIdFor({ ...input, filePath, resourceId })),
    placement,
    kind,
    title: String((input && input.title) || (kind === "file" ? basenameForPath(filePath) : titleForSurfaceKind(kind))),
    resourceId,
    filePath,
    terminalId: String((input && input.terminalId) || resourceId || ""),
    revealLine: kind === "file" ? normalizeRevealLine(input && input.revealLine) : null,
    revealRequestId:
      kind === "file" && Number.isSafeInteger(Number(input && input.revealRequestId))
        ? Number(input.revealRequestId)
        : 0,
  };
}
```

Update the right-panel branch in `openSurface(state, input)` so file surfaces reuse existing tabs, increment reveal requests, and remove the standalone `files` surface:

```js
  if (placement === "right") {
    const currentItems = current.rightPanel.surfaces || [];
    const filePath = surface.kind === "file" ? normalizeFilePath(surface.filePath || surface.resourceId) : "";
    const existingFile = filePath
      ? currentItems.find((item) => item.kind === "file" && normalizeFilePath(item.filePath || item.resourceId) === filePath)
      : null;
    const nextSurface = surface.kind === "file"
      ? makeSurface({
          ...input,
          placement: "right",
          kind: "file",
          filePath,
          resourceId: filePath,
          revealRequestId: Number(existingFile && existingFile.revealRequestId || 0) + 1,
        })
      : surface;
    const sourceItems = nextSurface.kind === "file"
      ? currentItems.filter((item) => item.kind !== "files")
      : currentItems;
    const surfaces = upsertSurface(sourceItems, nextSurface);
    return {
      ...current,
      rightPanel: activateRightPanelSurface(
        { ...current.rightPanel, surfaces },
        nextSurface,
      ),
    };
  }
```

- [ ] **Step 4: Run frontend helper tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS for the workbench state tests introduced in this task. Other tests may still fail until later tasks update source assertions and UI routing.

- [ ] **Step 5: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs
git commit -m "gui: add t3 file surface state"
```

---

## Task 2: GUI-Local File Preview State And App Wiring

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`

- [ ] **Step 1: Write failing store and source assertions**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, after the existing `diffSurfaceState` assertions, add reducer assertions for file preview state:

```js
  const filePreviewLoadingState = reducer(initialState, {
    type: "file_preview_load_started",
    path: "src/main.c",
  });
  assert.equal(filePreviewLoadingState.filePreviewsByPath["src/main.c"].status, "loading");
  assert.equal(filePreviewLoadingState.filePreviewsByPath["src/main.c"].path, "src/main.c");
  assert.equal(filePreviewLoadingState.preview, null);

  const filePreviewLoadedState = reducer(filePreviewLoadingState, {
    type: "file_preview_loaded",
    path: "src/main.c",
    preview: { kind: "file", title: "main.c", content: "int main(void) { return 0; }" },
  });
  assert.equal(filePreviewLoadedState.filePreviewsByPath["src/main.c"].status, "loaded");
  assert.equal(filePreviewLoadedState.filePreviewsByPath["src/main.c"].title, "main.c");
  assert.equal(filePreviewLoadedState.filePreviewsByPath["src/main.c"].content.includes("return 0"), true);
  assert.equal(filePreviewLoadedState.preview, null);

  const filePreviewFailedState = reducer(filePreviewLoadedState, {
    type: "file_preview_load_failed",
    path: "src/main.c",
    error: "not found",
  });
  assert.equal(filePreviewFailedState.filePreviewsByPath["src/main.c"].status, "error");
  assert.equal(filePreviewFailedState.filePreviewsByPath["src/main.c"].error, "not found");
```

Near the existing `appSource` assertions, add:

```js
  assert.equal(appSource.includes("file_preview_load_started"), true);
  assert.equal(appSource.includes("file_preview_loaded"), true);
  assert.equal(appSource.includes("file_preview_load_failed"), true);
  assert.equal(appSource.includes('kind: "file"'), true);
  assert.equal(appSource.includes('preview: { kind: "file"'), false);
```

Near the existing `storeSource` assertions, add:

```js
  assert.equal(storeSource.includes("filePreviewsByPath"), true);
  assert.equal(storeSource.includes("file_preview_load_started"), true);
  assert.equal(storeSource.includes("file_preview_loaded"), true);
  assert.equal(storeSource.includes("file_preview_load_failed"), true);
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `filePreviewsByPath` and file preview reducer actions do not exist.

- [ ] **Step 3: Add file preview state to the store**

In `src/embedagent/frontend/gui/webapp/src/store.js`, add the field to `initialState` after `preview: null`:

```js
  filePreviewsByPath: {},
```

Add these reducer cases immediately after `preview_loaded`:

```js
    case "file_preview_load_started": {
      const path = String(action.path || "");
      if (!path) return state;
      return {
        ...state,
        filePreviewsByPath: {
          ...state.filePreviewsByPath,
          [path]: {
            status: "loading",
            path,
            title: path,
            content: "",
            error: "",
          },
        },
      };
    }
    case "file_preview_loaded": {
      const path = String(action.path || "");
      if (!path) return state;
      const preview = action.preview || {};
      return {
        ...state,
        filePreviewsByPath: {
          ...state.filePreviewsByPath,
          [path]: {
            status: "loaded",
            path,
            title: String(preview.title || path),
            content: String(preview.content || ""),
            error: "",
          },
        },
      };
    }
    case "file_preview_load_failed": {
      const path = String(action.path || "");
      if (!path) return state;
      return {
        ...state,
        filePreviewsByPath: {
          ...state.filePreviewsByPath,
          [path]: {
            status: "error",
            path,
            title: path,
            content: "",
            error: String(action.error || "File unavailable"),
          },
        },
      };
    }
```

In `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`, clear the state on workspace switch by adding this field after `preview: null`:

```js
    filePreviewsByPath: {},
```

- [ ] **Step 4: Rewire `App.jsx` file opening**

In `src/embedagent/frontend/gui/webapp/src/App.jsx`, add helpers near `rightPanelSurfaceTitle`:

```js
  function normalizeFileSurfacePath(path) {
    return String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
  }

  function fileSurfaceTitle(path) {
    const normalized = normalizeFileSurfacePath(path);
    if (!normalized) return "File";
    const parts = normalized.split("/");
    return parts[parts.length - 1] || normalized;
  }
```

Replace the current `openFile(path)` implementation with:

```js
  async function openFile(path, line) {
    const filePath = normalizeFileSurfacePath(path);
    if (!filePath) return;
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: "file",
      title: fileSurfaceTitle(filePath),
      resourceId: filePath,
      filePath,
      revealLine: line,
    });
    dispatch({ type: "file_preview_load_started", path: filePath });
    try {
      const payload = await fetchJson(`/api/files/${encodeURIComponent(filePath)}`);
      dispatch({
        type: "file_preview_loaded",
        path: filePath,
        preview: {
          kind: "file",
          title: payload.path || filePath,
          content: payload.content || "",
        },
      });
    } catch (error) {
      dispatch({
        type: "file_preview_load_failed",
        path: filePath,
        error: error.message || "File unavailable",
      });
    }
  }
```

Update `openRightPanelSurface(kind, title = "")` so it does not try to open generic `file` surfaces through the add menu:

```js
    if (surfaceKind === "file") return;
```

Place that guard immediately after `const surfaceKind = String(kind || "");`.

Pass file preview state into `RightPanelSurfaceBody` by adding this prop:

```jsx
            filePreviewsByPath={state.filePreviewsByPath}
```

- [ ] **Step 5: Run frontend helper tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS for store state and source assertions, except any component assertions that are introduced in the next task.

- [ ] **Step 6: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/app-workspaces.js src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "gui: route files into t3 file surfaces"
```

---

## Task 3: File Preview Surface Body

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing source assertions**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, near the existing `rightPanelSurfaceBodySource` assertions, add:

```js
  assert.equal(rightPanelSurfaceBodySource.includes("FilePreviewSurface"), true);
  assert.equal(rightPanelSurfaceBodySource.includes('surface.kind === "file"'), true);
  assert.equal(rightPanelSurfaceBodySource.includes("filePreviewsByPath"), true);
```

After the `rightPanelSurfaceBodySource` assertions, add a new source block:

```js
  const filePreviewSurfaceSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "FilePreviewSurface.jsx"),
    "utf8",
  );
  assert.equal(filePreviewSurfaceSource.includes('data-testid="right-panel-file-surface"'), true);
  assert.equal(filePreviewSurfaceSource.includes("right-panel-file-loading"), true);
  assert.equal(filePreviewSurfaceSource.includes("right-panel-file-error"), true);
  assert.equal(filePreviewSurfaceSource.includes("right-panel-file-content"), true);
```

Near the existing `rightPanelTabsSource` assertions, add:

```js
  assert.equal(rightPanelTabsSource.includes("file:"), true);
  assert.equal(rightPanelTabsSource.includes("right-panel-surface-tab--file"), true);
```

Near the existing `stylesSource` assertions, add:

```js
  assert.equal(stylesSource.includes(".right-panel-file-surface"), true);
  assert.equal(stylesSource.includes(".right-panel-file-content"), true);
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `FilePreviewSurface.jsx` does not exist and `RightPanelSurfaceBody` does not route file surfaces.

- [ ] **Step 3: Create `FilePreviewSurface.jsx`**

Create `src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx`:

```jsx
import React from "react";

function normalizePath(path) {
  return String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

function titleForPath(path) {
  const normalized = normalizePath(path);
  if (!normalized) return "File";
  const parts = normalized.split("/");
  return parts[parts.length - 1] || normalized;
}

function statusForPreview(filePreview) {
  if (!filePreview || !filePreview.status) return "loading";
  return filePreview.status;
}

export default function FilePreviewSurface({ surface, filePreview, onReload }) {
  const filePath = normalizePath(surface?.filePath || surface?.resourceId);
  const status = statusForPreview(filePreview);
  const title = filePreview?.title || surface?.title || titleForPath(filePath);
  return (
    <div className="right-panel-file-surface" data-testid="right-panel-file-surface" data-file-path={filePath}>
      <div className="right-panel-file-header">
        <strong>{title}</strong>
        <span>{filePath}</span>
      </div>
      {status === "loading" ? (
        <div className="right-panel-file-loading">Loading file...</div>
      ) : null}
      {status === "error" ? (
        <div className="right-panel-file-error" role="alert">
          <span>{filePreview?.error || "File unavailable"}</span>
          {onReload ? (
            <button type="button" onClick={() => onReload(filePath)}>
              Retry
            </button>
          ) : null}
        </div>
      ) : null}
      {status === "loaded" ? (
        <pre className="right-panel-file-content" data-testid="right-panel-file-content">
          {filePreview?.content || ""}
        </pre>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Route file surfaces in `RightPanelSurfaceBody.jsx`**

Add this import:

```js
import FilePreviewSurface from "./FilePreviewSurface.jsx";
```

Add `filePreviewsByPath` to the props:

```js
  filePreviewsByPath,
```

Before the terminal branch, add:

```jsx
  if (surface.kind === "file") {
    const filePath = surface.filePath || surface.resourceId || "";
    return (
      <FilePreviewSurface
        surface={surface}
        filePreview={(filePreviewsByPath || {})[filePath]}
        onReload={onOpenFile}
      />
    );
  }
```

- [ ] **Step 5: Add file tab copy without adding file to the add menu**

In `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`, add this entry to `SURFACE_COPY`:

```js
  file: {
    icon: "F",
    label: "File",
    description: "View a workspace file.",
  },
```

Keep `SurfaceAddMenu` and `RightPanelEmptyState` using `RIGHT_PANEL_SURFACES.slice()`. This is intentional: `RIGHT_PANEL_SURFACES` remains the manually addable set and does not include `file`.

- [ ] **Step 6: Keep old Inspector tabs away from `file`**

In `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`, keep the import as `RIGHT_PANEL_SURFACES` and keep:

```js
const ALL_TABS = RIGHT_PANEL_SURFACES;
```

Do not import `RIGHT_PANEL_KINDS` here. This keeps `file` out of the old Inspector tab list.

- [ ] **Step 7: Add CSS**

Append the file surface styles near the existing right-panel styles in `src/embedagent/frontend/gui/webapp/src/styles.css`:

```css
.right-panel-file-surface {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-panel);
}

.right-panel-file-header {
  flex: 0 0 auto;
  min-width: 0;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.right-panel-file-header strong,
.right-panel-file-header span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.right-panel-file-header strong {
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
}

.right-panel-file-header span {
  color: var(--text-muted);
  font-size: 11px;
  font-family: var(--font-mono);
}

.right-panel-file-loading,
.right-panel-file-error {
  padding: 12px;
  color: var(--text-muted);
  font-size: 12px;
}

.right-panel-file-error {
  color: var(--danger);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.right-panel-file-error button {
  border: 1px solid var(--border-default);
  background: transparent;
  color: var(--text-primary);
  border-radius: var(--r-sm);
  padding: 4px 8px;
}

.right-panel-file-content {
  flex: 1;
  min-height: 0;
  margin: 0;
  padding: 12px;
  overflow: auto;
  border: 0;
  border-radius: 0;
  background: #0d1117;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
  white-space: pre;
}
```

- [ ] **Step 8: Run frontend helper tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS for component/source assertions.

- [ ] **Step 9: Build the webapp**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: PASS and static assets rebuilt.

- [ ] **Step 10: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/static
git commit -m "gui: render t3 file preview surfaces"
```

---

## Task 4: Visual Debug File Scenario

**Files:**
- Modify: `scripts/gui-visual-debug.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`

- [ ] **Step 1: Write failing visual runner tests**

In `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`, update the scenario assertions:

```js
  assert.deepEqual(runner.parseScenarioList("load,file"), ["load", "file"]);
  assert.deepEqual(runner.parseScenarioList("all"), ["app", "load", "chat", "diff", "file", "responsive", "thread", "timeline", "interaction"]);
```

Add source assertions near the existing right-panel assertions:

```js
  assert.equal(runnerSource.includes("runFileScenario"), true);
  assert.equal(runnerSource.includes("right-panel-file-surface"), true);
  assert.equal(runnerSource.includes("right-panel-surface-tab--file"), true);
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `file` is not in `SCENARIOS` and `runFileScenario` does not exist.

- [ ] **Step 3: Add the file scenario to `scripts/gui-visual-debug.mjs`**

Update the exported scenario list:

```js
export const SCENARIOS = ["load", "chat", "diff", "file", "responsive", "app", "thread", "timeline", "interaction"];
```

Add `runFileScenario(page)` after `runDiffScenario(page)`:

```js
async function runFileScenario(page) {
  await page.waitForSelector('[data-testid="right-panel-empty-surface--files"]', { timeout: 10000 });
  await page.click('[data-testid="right-panel-empty-surface--files"]');
  await page.waitForSelector('[data-testid="right-panel-files-surface"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="right-panel-file-node--README.md"]', { timeout: 10000 });
  await page.click('[data-testid="right-panel-file-node--README.md"]');
  await page.waitForSelector('[data-testid="right-panel-file-surface"]', { timeout: 15000 });
  await page.waitForSelector('[data-testid="right-panel-file-content"]', { timeout: 15000 });
  const panelText = await page.locator('[data-testid="right-panel-file-surface"]').innerText();
  const activeTab = await page.locator('[data-testid="right-panel-surface-tab--file"] [role="tab"]').getAttribute("aria-selected");
  const filesTabs = await page.locator('[data-testid="right-panel-surface-tab--files"]').count();
  const noOverlap = await assertNoOverlap(page);
  if (activeTab !== "true") throw new Error("File tab did not become active");
  if (filesTabs !== 0) throw new Error("Standalone files surface was not replaced by file surface");
  if (!panelText.includes("Visual Debug Workspace")) {
    throw new Error("File surface did not show README.md fixture content");
  }
  if (!noOverlap) throw new Error("Right panel tabs overlap in file scenario");
  return {
    activeTab: activeTab === "true",
    filesSurfaceReplaced: filesTabs === 0,
    hasReadmeContent: panelText.includes("Visual Debug Workspace"),
    rightTabsDoNotOverlap: noOverlap,
  };
}
```

Wire it into `runScenarios(...)`:

```js
      } else if (scenario === "file") {
        results.file = await runFileScenario(page);
```

Update the help text line:

```text
  --scenario load|chat|diff|file|responsive|app|thread|timeline|interaction|all
```

- [ ] **Step 4: Run frontend helper tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS for visual runner parsing/source assertions.

- [ ] **Step 5: Run visual verification**

Run from the repo root:

```bash
node scripts/gui-visual-debug.mjs --scenario file --no-build --output "$env:TEMP\embedagent-t3-file-surface" --viewports 1280x720,700x640
```

Expected: PASS. `summary.json` should include:

```json
{
  "activeTab": true,
  "filesSurfaceReplaced": true,
  "hasReadmeContent": true,
  "rightTabsDoNotOverlap": true
}
```

- [ ] **Step 6: Commit**

```bash
git add scripts/gui-visual-debug.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs
git commit -m "gui: add t3 file surface visual check"
```

---

## Task 5: Documentation And Final Verification

**Files:**
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Update development tracker**

Add a completed entry to `docs/development-tracker.md` in the current GUI/T3 work area:

```markdown
### 2026-06-17 - T3 Right Panel File Surface

- Added T3 Code-style `file` surfaces to the GUI right panel.
- Files now open as peer right-panel tabs with path/reveal metadata while file contents remain GUI-local display state.
- Kept `file` out of the generic add-surface menu; file surfaces are opened by file actions.
- Preserved the app-shell boundary: no Agent Core, transcript, workflow, permission, runtime reducer, provider, extension, telemetry, or source-control checkpoint changes.
```

- [ ] **Step 2: Update design change log**

Add a design-change entry to `docs/design-change-log.md`:

```markdown
## 2026-06-17 - GUI T3 File Surface

The GUI right panel now treats opened workspace files as T3 Code-style `file` surfaces. A file surface stores only shallow path/reveal metadata in the workbench surface model, while file contents remain GUI-local preview state loaded through the existing app-shell file route. This continues separating the independent GUI app experience from Agent Core and keeps the default offline C/C++ runtime unchanged.
```

- [ ] **Step 3: Run frontend tests**

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected:

```text
frontend helper checks passed
```

- [ ] **Step 4: Build frontend static assets**

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: build exits with code 0.

- [ ] **Step 5: Run focused GUI backend tests**

Run from the repo root:

```bash
uv run pytest tests/test_gui_app_shell.py tests/test_gui_source_control_api.py tests/test_gui_terminal_api.py -v
```

Expected:

```text
10 passed
```

- [ ] **Step 6: Run visual checks**

Run from the repo root:

```bash
node scripts/gui-visual-debug.mjs --scenario file,diff --no-build --output "$env:TEMP\embedagent-t3-file-surface-final" --viewports 1280x720,700x640
```

Expected:

- `file.activeTab` is `true`
- `file.filesSurfaceReplaced` is `true`
- `file.hasReadmeContent` is `true`
- `diff.activeTab` is `true`
- console warning/error count is `0`

- [ ] **Step 7: Inspect changed files**

```bash
git status --short
git diff --check
```

Expected:

- `git diff --check` exits with code 0.
- Changed files are limited to this GUI file-surface slice, rebuilt static assets, and the two docs files.

- [ ] **Step 8: Commit final docs and any remaining verified changes**

```bash
git add docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: record t3 file surface slice"
```

If implementation files remain uncommitted because a previous task intentionally batched commits differently, include them in a final implementation commit before this docs commit.

---

## Self-Review Checklist

- The `file` surface is in `RIGHT_PANEL_KINDS`, not in `RIGHT_PANEL_SURFACES`.
- `RightPanelTabs` can render file tabs but does not show file in the add menu or empty-state cards.
- Opening a file from `FilesSurface` removes the standalone `files` surface, matching T3 behavior.
- Reopening the same file increments `revealRequestId` and does not duplicate tabs.
- File content is stored in `filePreviewsByPath`, not inside workbench surface descriptors.
- `preview_loaded` remains available for artifacts and non-file preview compatibility, but `openFile` no longer dispatches old file preview state.
- No Agent Core, transcript, workflow state, permission policy, runtime reducer, provider, extension, telemetry, source-control checkpoint, or backend route behavior was changed.
- All frontend helper tests, build, focused GUI backend tests, and visual debug file/diff scenarios pass before merge.
