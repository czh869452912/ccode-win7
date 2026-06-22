# T3 Right Panel Editor/Diff Chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Copy T3 Code's right-panel file and diff surface chrome into the GUI app shell without changing Agent Core.

**Architecture:** Keep all behavior in the React GUI app-shell. `FilePreviewSurface` owns file preview header/actions and content mode; `DiffPanel` owns diff header controls, file rail state, and viewport presentation; `RightPanelSurfaceBody` only passes existing app-shell callbacks.

**Tech Stack:** React 18, existing CSS, existing webapp helper tests, Playwright visual debug script, Python 3.8 GUI backend tests.

---

## File Structure

- Modify `src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx`: add T3-style `surface-subheader`, icon action buttons, horizontal breadcrumb scrolling, and explorer/open callbacks.
- Modify `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`: pass `onOpenFile` and a new `onOpenFilesSurface` callback into `FilePreviewSurface`.
- Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`: provide the existing right-panel surface opener as `onOpenFilesSurface`.
- Modify `src/embedagent/frontend/gui/webapp/src/components/diff/DiffPanel.jsx`: add T3-style `surface-subheader`, selection chips, stacked/split/wrap/whitespace controls, collapsible rail, and focused-file scrolling.
- Modify `src/embedagent/frontend/gui/webapp/src/styles.css`: add shared `surface-subheader`, file chrome, diff chrome, icon button, chip strip, and responsive rules.
- Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`: add source assertions for T3 file/diff chrome.
- Modify `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`: assert visual runner checks file/diff chrome selectors.
- Modify `scripts/gui-visual-debug.mjs`: extend file and diff scenarios to verify the new controls and scrolling.
- Modify `src/embedagent/frontend/gui/static/assets/app.js` and `src/embedagent/frontend/gui/static/assets/app.css`: rebuild static GUI assets.
- Modify docs after code lands: `docs/modules/frontend-gui.md`, `docs/development-tracker.md`, `docs/design-change-log.md`.

## Task 1: Lock T3 Chrome Source Contracts

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`

- [ ] **Step 1: Add failing source assertions**

Add assertions that fail until the implementation contains these exact surface contracts:

```js
assert.equal(filePreviewSurfaceSource.includes("surface-subheader"), true);
assert.equal(filePreviewSurfaceSource.includes('data-testid="file-preview-open-action"'), true);
assert.equal(filePreviewSurfaceSource.includes('data-testid="file-preview-explorer-toggle"'), true);
assert.equal(filePreviewSurfaceSource.includes("file-preview-action-icon"), true);
assert.equal(filePreviewSurfaceSource.includes("breadcrumbRef"), true);
assert.equal(filePreviewSurfaceSource.includes("onOpenFilesSurface"), true);

assert.equal(diffPanelSource.includes("surface-subheader"), true);
assert.equal(diffPanelSource.includes('data-testid="diff-mode-toggle--stacked"'), true);
assert.equal(diffPanelSource.includes('data-testid="diff-mode-toggle--split"'), true);
assert.equal(diffPanelSource.includes('data-testid="diff-wrap-toggle"'), true);
assert.equal(diffPanelSource.includes('data-testid="diff-whitespace-toggle"'), true);
assert.equal(diffPanelSource.includes("collapsedDiffFilePaths"), true);
assert.equal(diffPanelSource.includes("diff-selection-chip-strip"), true);
```

In `visual-debug-runner.test.mjs`, assert the runner checks:

```js
assert.equal(source.includes("filePreviewChromeState"), true);
assert.equal(source.includes("diffChromeState"), true);
assert.equal(source.includes("file-preview-open-action"), true);
assert.equal(source.includes("diff-mode-toggle--split"), true);
```

- [ ] **Step 2: Run red test**

Run:

```bash
npm test
```

Expected: FAIL because the new source selectors and visual runner checks are missing.

- [ ] **Step 3: Commit the failing contract**

```bash
git add src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs
git commit -m "test: lock T3 right panel chrome contracts"
```

## Task 2: Copy T3 File Surface Chrome

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`

- [ ] **Step 1: Implement file surface callbacks**

Thread `onOpenFilesSurface` through `RightPanelSurfaceBody` and `App.jsx`:

```jsx
<RightPanelSurfaceBody
  ...
  onOpenFile={openFile}
  onOpenFilesSurface={() => openRightPanelSurface("files")}
/>
```

- [ ] **Step 2: Implement T3-style file subheader**

In `FilePreviewSurface.jsx`, add:

```jsx
const breadcrumbRef = useRef(null);

useEffect(() => {
  const currentCrumb = breadcrumbRef.current?.querySelector("[data-current-file-crumb='true']");
  currentCrumb?.scrollIntoView({ block: "nearest", inline: "end" });
}, [filePath]);
```

Render a `surface-subheader file-preview-subheader` containing scrollable breadcrumbs plus icon actions:

```jsx
<div className="surface-subheader file-preview-subheader" data-surface-subheader>
  <div ref={breadcrumbRef} className="file-preview-breadcrumb-scroll" data-file-breadcrumbs>
    <FilePreviewBreadcrumbs projectName={projectName} filePath={filePath} />
  </div>
  <button data-testid="file-preview-open-action" className="file-preview-action-icon">...</button>
  <button data-testid="file-preview-explorer-toggle" className="file-preview-action-icon">...</button>
</div>
```

Keep the existing markdown mode toggle, but render it as an icon-style button in the subheader with `data-testid="file-preview-mode-toggle"`.

- [ ] **Step 3: Style file chrome**

Add CSS for:

```css
.surface-subheader { ... }
.file-preview-subheader { ... }
.file-preview-breadcrumb-scroll { ... }
.file-preview-action-icon { ... }
```

The content area must remain the only vertical scroll region for file content.

- [ ] **Step 4: Run green test**

Run:

```bash
npm test
```

Expected: PASS for source/helper tests.

- [ ] **Step 5: Commit file chrome**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/styles.css
git commit -m "feat: copy T3 file surface chrome"
```

## Task 3: Copy T3 Diff Surface Chrome

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/diff/DiffPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`

- [ ] **Step 1: Implement diff UI state**

Add local state:

```jsx
const [diffRenderMode, setDiffRenderMode] = React.useState("stacked");
const [diffWordWrap, setDiffWordWrap] = React.useState(false);
const [diffIgnoreWhitespace, setDiffIgnoreWhitespace] = React.useState(false);
const [collapsedDiffFilePaths, setCollapsedDiffFilePaths] = React.useState(() => new Set());
const patchViewportRef = React.useRef(null);
```

- [ ] **Step 2: Implement T3-style diff subheader**

Render:

```jsx
<header className="surface-subheader diff-panel-subheader" data-surface-subheader>
  <div className="diff-selection-chip-strip">...</div>
  <div className="diff-panel-controls">...</div>
</header>
```

Controls must include:

```jsx
data-testid="diff-mode-toggle--stacked"
data-testid="diff-mode-toggle--split"
data-testid="diff-wrap-toggle"
data-testid="diff-whitespace-toggle"
```

- [ ] **Step 3: Implement collapsible file rail**

Each file row should expose a small collapse button and hide the focused patch when collapsed:

```jsx
data-testid={`diff-file-collapse--${file.path}`}
```

Clicking a file row still calls `onFocusFile(file.path)`.

- [ ] **Step 4: Style diff chrome**

Add CSS for:

```css
.diff-panel-subheader { ... }
.diff-selection-chip-strip { ... }
.diff-panel-control { ... }
.diff-panel-viewport.word-wrap { ... }
.diff-panel-viewport.split { ... }
```

- [ ] **Step 5: Run green test**

Run:

```bash
npm test
```

Expected: PASS.

- [ ] **Step 6: Commit diff chrome**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/diff/DiffPanel.jsx src/embedagent/frontend/gui/webapp/src/styles.css
git commit -m "feat: copy T3 diff surface chrome"
```

## Task 4: Add Visual Verification

**Files:**
- Modify: `scripts/gui-visual-debug.mjs`

- [ ] **Step 1: Extend file scenario**

After loading the file reveal fixture, measure:

```js
const filePreviewChromeState = await page.evaluate(() => ({
  hasSubheader: Boolean(document.querySelector(".right-panel-file-surface [data-surface-subheader]")),
  hasOpenAction: Boolean(document.querySelector('[data-testid="file-preview-open-action"]')),
  hasExplorerToggle: Boolean(document.querySelector('[data-testid="file-preview-explorer-toggle"]')),
  hasBreadcrumbs: Boolean(document.querySelector("[data-file-breadcrumbs]")),
}));
```

Throw if any field is false.

- [ ] **Step 2: Extend diff scenario**

After opening the diff fixture, measure:

```js
const diffChromeState = await page.evaluate(() => ({
  hasSubheader: Boolean(document.querySelector(".diff-panel [data-surface-subheader]")),
  hasChipStrip: Boolean(document.querySelector(".diff-selection-chip-strip")),
  hasStacked: Boolean(document.querySelector('[data-testid="diff-mode-toggle--stacked"]')),
  hasSplit: Boolean(document.querySelector('[data-testid="diff-mode-toggle--split"]')),
  hasWrap: Boolean(document.querySelector('[data-testid="diff-wrap-toggle"]')),
  hasWhitespace: Boolean(document.querySelector('[data-testid="diff-whitespace-toggle"]')),
}));
```

Click split and wrap toggles, then assert the viewport has the expected class names.

- [ ] **Step 3: Run visual red/green**

Run:

```bash
node scripts\gui-visual-debug.mjs --scenario diff,file --output "$env:TEMP\embedagent-t3-right-panel-chrome"
```

Expected after implementation: PASS, console count 0, screenshots emitted.

- [ ] **Step 4: Commit visual verification**

```bash
git add scripts/gui-visual-debug.mjs
git commit -m "test: verify T3 right panel chrome visually"
```

## Task 5: Rebuild Assets And Sync Docs

**Files:**
- Modify: `src/embedagent/frontend/gui/static/assets/app.js`
- Modify: `src/embedagent/frontend/gui/static/assets/app.css`
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Rebuild static assets**

Run:

```bash
npm run build
```

from `src/embedagent/frontend/gui/webapp`.

- [ ] **Step 2: Update docs**

Record that the GUI app shell now copies T3 Code right-panel file/diff surface chrome while keeping Agent Core unchanged.

- [ ] **Step 3: Run final verification**

Run:

```bash
npm test
uv run pytest tests/test_gui_backend_api.py tests/test_gui_runtime.py -v
node scripts\gui-visual-debug.mjs --scenario diff,file --output "$env:TEMP\embedagent-t3-right-panel-chrome-final"
```

Expected: all pass.

- [ ] **Step 4: Commit docs/assets**

```bash
git add src/embedagent/frontend/gui/static/assets/app.js src/embedagent/frontend/gui/static/assets/app.css docs/modules/frontend-gui.md docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: record T3 right panel chrome parity"
```

