# T3 Branch Toolbar Run Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a T3 Code-style branch/run-context toolbar directly below the GUI composer using existing read-only workspace and source-control state.

**Architecture:** Keep the feature in the GUI app shell. Add one pure source-control read model, one React presentation component, small App wiring, CSS, visual fixture checks, and tracker docs; do not change Agent Core or backend source-control mutation semantics.

**Tech Stack:** React 18, plain JavaScript ES modules, plain CSS, existing Node helper tests, existing Playwright visual harness, Python 3.8-compatible backend unchanged.

---

## File Structure

- Create: `src/embedagent/frontend/gui/webapp/src/source-control/branch-toolbar-model.js`
  - Pure GUI read model copied from the relevant T3 `BranchToolbar.logic.ts` semantics.
  - Inputs: `activeWorkspace`, `sourceControl`.
  - Outputs: labels, tones, disabled flags, compact dirty-count text.
- Create: `src/embedagent/frontend/gui/webapp/test/branch-toolbar-model.test.mjs`
  - Focused tests for labels, branch fallback, dirty counts, Git unavailable, non-repo, and normalization compatibility.
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Import and run the new model test.
  - Add source checks for the new component and App wiring.
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/BranchToolbar.jsx`
  - Presentation-only toolbar below composer.
  - No fetch calls and no mutation commands.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
  - Accept `branchToolbar` and `onRefreshSourceControl`.
  - Render `BranchToolbar` after the composer hint bar.
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Derive toolbar view state via `buildBranchToolbarModel(...)`.
  - Pass toolbar state and existing `loadSourceControlStatus(true)` refresh callback to `Composer`.
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Add T3-like compact toolbar styles with wrapping guardrails.
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
  - Add source-control fixture state for visual debug.
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
  - Add a dev-only fixture reducer action to load source-control status for toolbar visual checks.
- Modify: `scripts/gui-visual-debug.mjs`
  - Verify toolbar visibility in `chat` and responsive scenarios.
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
  - Lock the fixture action shape if needed.
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`
  - Lock the runner selector checks.
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`
  - Lock the toolbar CSS selectors.
- Modify: `docs/development-tracker.md`
  - Add current slice status.
- Modify: `docs/design-change-log.md`
  - Add design-change entry.

---

### Task 1: Branch Toolbar Read Model

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/test/branch-toolbar-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Create: `src/embedagent/frontend/gui/webapp/src/source-control/branch-toolbar-model.js`

- [ ] **Step 1: Write the failing test**

Create `src/embedagent/frontend/gui/webapp/test/branch-toolbar-model.test.mjs`:

```js
import assert from "node:assert/strict";

import {
  buildBranchToolbarModel,
  resolveBranchLabel,
  summarizeBranchToolbarChanges,
} from "../src/source-control/branch-toolbar-model.js";
import { normalizeSourceControlStatus } from "../src/source-control/source-control-state.js";

export function runBranchToolbarModelTests() {
  assert.equal(
    summarizeBranchToolbarChanges({ staged: 0, unstaged: 0, untracked: 0, conflicted: 0 }),
    "Clean",
  );
  assert.equal(
    summarizeBranchToolbarChanges({ staged: 2, unstaged: 3, untracked: 1, conflicted: 0 }),
    "6 changes",
  );
  assert.equal(
    summarizeBranchToolbarChanges({ staged: 0, unstaged: 0, untracked: 0, conflicted: 2 }),
    "2 conflicts",
  );

  assert.deepEqual(
    resolveBranchLabel({ branch: "main", head: "abc1234", isRepo: true }),
    { label: "main", tone: "branch" },
  );
  assert.deepEqual(
    resolveBranchLabel({ branch: "", head: "abc1234567", isRepo: true }),
    { label: "detached abc1234", tone: "detached" },
  );
  assert.deepEqual(
    resolveBranchLabel({ branch: "", head: "", isRepo: false }),
    { label: "No repository", tone: "disabled" },
  );

  const ready = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-1", path: "D:/work/demo", label: "demo", exists: true },
    sourceControl: {
      status: "ready",
      data: normalizeSourceControlStatus({
        is_repo: true,
        git_available: true,
        branch: "feature/parser",
        head: "1234567",
        provider: { kind: "github", name: "GitHub" },
        counts: { staged: 1, unstaged: 2, untracked: 1, conflicted: 0, total: 4 },
      }),
    },
  });
  assert.equal(ready.visible, true);
  assert.equal(ready.workspaceLabel, "demo");
  assert.equal(ready.modeLabel, "Current checkout");
  assert.equal(ready.branchLabel, "feature/parser");
  assert.equal(ready.providerLabel, "GitHub");
  assert.equal(ready.changeCountLabel, "4 changes");
  assert.equal(ready.repoState, "repo");
  assert.equal(ready.disabled, false);

  const unavailable = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-1", path: "D:/work/demo", label: "", exists: true },
    sourceControl: {
      status: "ready",
      data: normalizeSourceControlStatus({
        is_repo: false,
        git_available: false,
      }),
    },
  });
  assert.equal(unavailable.visible, true);
  assert.equal(unavailable.workspaceLabel, "demo");
  assert.equal(unavailable.branchLabel, "Git unavailable");
  assert.equal(unavailable.repoState, "git_unavailable");
  assert.equal(unavailable.disabled, true);
  assert.equal(unavailable.disabledReason, "Git is unavailable in this offline bundle or workspace.");

  const nonRepo = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-2", path: "D:/plain", label: "plain", exists: true },
    sourceControl: {
      status: "ready",
      data: normalizeSourceControlStatus({
        is_repo: false,
        git_available: true,
      }),
    },
  });
  assert.equal(nonRepo.branchLabel, "No repository");
  assert.equal(nonRepo.repoState, "not_repo");
  assert.equal(nonRepo.disabled, true);

  const loading = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-3", path: "D:/loading", label: "loading", exists: true },
    sourceControl: { status: "loading", data: normalizeSourceControlStatus() },
  });
  assert.equal(loading.branchLabel, "Checking Git...");
  assert.equal(loading.repoState, "loading");

  const hidden = buildBranchToolbarModel({
    activeWorkspace: null,
    sourceControl: { status: "ready", data: normalizeSourceControlStatus() },
  });
  assert.equal(hidden.visible, false);
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```js
import { runBranchToolbarModelTests } from "./branch-toolbar-model.test.mjs";
```

Add this call near the other focused model tests:

```js
  runBranchToolbarModelTests();
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with a module-not-found error for `../src/source-control/branch-toolbar-model.js`.

- [ ] **Step 3: Write the minimal implementation**

Create `src/embedagent/frontend/gui/webapp/src/source-control/branch-toolbar-model.js`:

```js
import { normalizeSourceControlStatus } from "./source-control-state.js";
import { providerLabel } from "./source-control-presentation.js";

function basenameFromPath(pathValue = "") {
  const parts = String(pathValue || "").replace(/\\/g, "/").split("/").filter(Boolean);
  return parts.length ? parts[parts.length - 1] : "";
}

function safeCounts(counts = {}) {
  return {
    staged: Number(counts.staged || 0),
    unstaged: Number(counts.unstaged || 0),
    untracked: Number(counts.untracked || 0),
    conflicted: Number(counts.conflicted || 0),
    total: Number(counts.total || 0),
  };
}

export function summarizeBranchToolbarChanges(counts = {}) {
  const safe = safeCounts(counts);
  if (safe.conflicted > 0) {
    return `${safe.conflicted} ${safe.conflicted === 1 ? "conflict" : "conflicts"}`;
  }
  const total = safe.total || safe.staged + safe.unstaged + safe.untracked + safe.conflicted;
  if (total <= 0) return "Clean";
  return `${total} ${total === 1 ? "change" : "changes"}`;
}

export function resolveBranchLabel({ branch = "", head = "", isRepo = false, gitAvailable = true } = {}) {
  if (!gitAvailable) return { label: "Git unavailable", tone: "disabled" };
  if (!isRepo) return { label: "No repository", tone: "disabled" };
  const branchText = String(branch || "").trim();
  if (branchText) return { label: branchText, tone: "branch" };
  const headText = String(head || "").trim();
  if (headText) return { label: `detached ${headText.slice(0, 7)}`, tone: "detached" };
  return { label: "Unknown ref", tone: "muted" };
}

export function buildBranchToolbarModel({ activeWorkspace = null, sourceControl = null } = {}) {
  if (!activeWorkspace) {
    return { visible: false };
  }
  const data = normalizeSourceControlStatus(sourceControl?.data || {});
  const status = String(sourceControl?.status || "idle");
  const workspaceLabel =
    String(activeWorkspace.label || "").trim() ||
    basenameFromPath(activeWorkspace.path || "") ||
    "Workspace";
  const loading = status === "loading";
  const error = status === "error";
  const branch = loading
    ? { label: "Checking Git...", tone: "muted" }
    : error
      ? { label: "Git status unavailable", tone: "disabled" }
      : resolveBranchLabel({
          branch: data.branch,
          head: data.head,
          isRepo: data.isRepo,
          gitAvailable: data.gitAvailable,
        });
  const repoState = loading
    ? "loading"
    : error
      ? "error"
      : !data.gitAvailable
        ? "git_unavailable"
        : data.isRepo
          ? "repo"
          : "not_repo";
  const disabled = repoState !== "repo";
  const disabledReason =
    repoState === "git_unavailable"
      ? "Git is unavailable in this offline bundle or workspace."
      : repoState === "not_repo"
        ? "This workspace is not a Git repository."
        : repoState === "error"
          ? String(sourceControl?.error || "Git status is unavailable.")
          : "";
  return {
    visible: true,
    workspaceLabel,
    modeLabel: "Current checkout",
    modeDescription: "Run in the active workspace checkout.",
    branchLabel: branch.label,
    branchTone: branch.tone,
    providerLabel: providerLabel(data.provider),
    changeCountLabel: summarizeBranchToolbarChanges(data.counts),
    repoState,
    disabled,
    disabledReason,
    canRefresh: true,
  };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 5: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/source-control/branch-toolbar-model.js src/embedagent/frontend/gui/webapp/test/branch-toolbar-model.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "test: add branch toolbar read model"
```

---

### Task 2: Toolbar Component And Static Source Checks

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/BranchToolbar.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write static checks first**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, add these source checks near the other component source checks:

```js
  const branchToolbarSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "BranchToolbar.jsx"),
    "utf8",
  );
  assert.equal(branchToolbarSource.includes('data-testid="branch-toolbar"'), true);
  assert.equal(branchToolbarSource.includes('data-testid="branch-toolbar-mode"'), true);
  assert.equal(branchToolbarSource.includes('data-testid="branch-toolbar-branch"'), true);
  assert.equal(branchToolbarSource.includes("onRefresh"), true);
  assert.equal(branchToolbarSource.includes("fetch("), false);
  assert.equal(branchToolbarSource.includes("transcript"), false);
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `BranchToolbar.jsx` does not exist.

- [ ] **Step 3: Create the component**

Create `src/embedagent/frontend/gui/webapp/src/components/workbench/BranchToolbar.jsx`:

```jsx
import React from "react";

function ToolbarButton({ children, title, disabled = false, onClick, testId }) {
  return (
    <button
      type="button"
      className="branch-toolbar-button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      data-testid={testId}
    >
      {children}
    </button>
  );
}

export default function BranchToolbar({ model, onRefresh }) {
  if (!model?.visible) return null;
  const disabledTitle = model.disabledReason || "This action is read-only in the current GUI shell.";
  return (
    <div className={`branch-toolbar repo-${model.repoState || "unknown"}`} data-testid="branch-toolbar">
      <div className="branch-toolbar-context" data-testid="branch-toolbar-mode">
        <span className="branch-toolbar-icon" aria-hidden="true">⌁</span>
        <span className="branch-toolbar-main">
          <span className="branch-toolbar-label">{model.modeLabel}</span>
          <span className="branch-toolbar-subtle">{model.workspaceLabel}</span>
        </span>
      </div>
      <div className="branch-toolbar-spacer" />
      <div
        className={`branch-toolbar-branch tone-${model.branchTone || "muted"}`}
        data-testid="branch-toolbar-branch"
        title={model.disabled ? disabledTitle : model.branchLabel}
      >
        <span className="branch-toolbar-icon" aria-hidden="true">⑂</span>
        <span className="branch-toolbar-main">
          <span className="branch-toolbar-label">{model.branchLabel}</span>
          <span className="branch-toolbar-subtle">
            {model.providerLabel} · {model.changeCountLabel}
          </span>
        </span>
      </div>
      <ToolbarButton title={disabledTitle} disabled testId="branch-toolbar-worktree">
        Worktree
      </ToolbarButton>
      <ToolbarButton title={disabledTitle} disabled testId="branch-toolbar-actions">
        Branch
      </ToolbarButton>
      {model.canRefresh ? (
        <ToolbarButton title="Refresh local Git status" onClick={onRefresh} testId="branch-toolbar-refresh">
          Refresh
        </ToolbarButton>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 5: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/BranchToolbar.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat: add branch toolbar component"
```

---

### Task 3: Composer And App Wiring

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add source checks for wiring**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, extend the existing `App.jsx` and `Composer.jsx` source checks:

```js
  assert.equal(appSource.includes("buildBranchToolbarModel"), true);
  assert.equal(appSource.includes("branchToolbarModel"), true);
  assert.equal(appSource.includes("onRefreshSourceControl"), true);
```

Extend the existing `composerSource` checks:

```js
  assert.equal(composerSource.includes("BranchToolbar"), true);
  assert.equal(composerSource.includes("branchToolbar"), true);
  assert.equal(composerSource.includes("onRefreshSourceControl"), true);
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because the new wiring strings are not present.

- [ ] **Step 3: Wire `Composer.jsx`**

Modify imports in `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`:

```jsx
import BranchToolbar from "./workbench/BranchToolbar.jsx";
```

Add props:

```jsx
  branchToolbar = null,
  onRefreshSourceControl,
```

Render after the hint bar:

```jsx
      <BranchToolbar
        model={branchToolbar}
        onRefresh={onRefreshSourceControl}
      />
```

- [ ] **Step 4: Wire `App.jsx`**

Add import:

```jsx
import { buildBranchToolbarModel } from "./source-control/branch-toolbar-model.js";
```

Add memo near other derived models:

```jsx
  const branchToolbarModel = useMemo(
    () =>
      buildBranchToolbarModel({
        activeWorkspace: state.app.activeWorkspace,
        sourceControl: state.sourceControl,
      }),
    [state.app.activeWorkspace, state.sourceControl],
  );
```

Pass props to `Composer`:

```jsx
              branchToolbar={branchToolbarModel}
              onRefreshSourceControl={() => loadSourceControlStatus(true)}
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 6: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/components/Composer.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat: wire branch toolbar under composer"
```

---

### Task 4: T3-Like CSS And Visual Language Checks

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`

- [ ] **Step 1: Add CSS checks first**

In `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`, add:

```js
  assertIncludes(styles, ".branch-toolbar", "branch toolbar should be styled");
  assertIncludes(styles, ".branch-toolbar-context", "branch toolbar context group should be styled");
  assertIncludes(styles, ".branch-toolbar-branch", "branch toolbar branch group should be styled");
  assertIncludes(styles, ".branch-toolbar-button", "branch toolbar controls should be styled");
  assertIncludes(styles, "@media (max-width: 720px)", "mobile guardrails should exist");
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `.branch-toolbar` styles do not exist.

- [ ] **Step 3: Add styles**

Append near composer styles in `src/embedagent/frontend/gui/webapp/src/styles.css`:

```css
.branch-toolbar {
  width: min(860px, calc(100% - 32px));
  margin: 7px auto 0;
  min-height: 34px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
  background: rgba(255,255,255,.018);
  color: var(--text-secondary);
}

.branch-toolbar-context,
.branch-toolbar-branch {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 26px;
  padding: 0 8px;
  border-radius: var(--r-sm);
}

.branch-toolbar-context {
  background: rgba(255,255,255,.025);
}

.branch-toolbar-branch {
  border: 1px solid var(--border-subtle);
  background: var(--bg-default);
}

.branch-toolbar-spacer {
  flex: 1 1 auto;
}

.branch-toolbar-main {
  min-width: 0;
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}

.branch-toolbar-label,
.branch-toolbar-subtle {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.branch-toolbar-label {
  color: var(--text-primary);
  font-size: 11px;
  font-weight: 600;
}

.branch-toolbar-subtle {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.branch-toolbar-icon {
  flex: 0 0 auto;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 12px;
}

.branch-toolbar-branch.tone-branch .branch-toolbar-icon {
  color: var(--color-success);
}

.branch-toolbar-branch.tone-detached .branch-toolbar-icon {
  color: var(--color-warning);
}

.branch-toolbar-branch.tone-disabled,
.branch-toolbar.repo-git_unavailable,
.branch-toolbar.repo-not_repo,
.branch-toolbar.repo-error {
  opacity: .72;
}

.branch-toolbar-button {
  height: 26px;
  flex: 0 0 auto;
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 0 8px;
}

.branch-toolbar-button:not(:disabled):hover {
  border-color: var(--border-focus);
  color: var(--text-primary);
  background: rgba(255,255,255,.035);
}

.branch-toolbar-button:disabled {
  cursor: not-allowed;
  color: var(--text-muted);
}

@media (max-width: 720px) {
  .branch-toolbar {
    width: calc(100% - 20px);
    align-items: stretch;
    flex-wrap: wrap;
  }

  .branch-toolbar-context,
  .branch-toolbar-branch {
    flex: 1 1 180px;
  }

  .branch-toolbar-spacer {
    display: none;
  }

  .branch-toolbar-button {
    flex: 1 1 78px;
  }
}
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 5: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs
git commit -m "style: add t3 branch toolbar chrome"
```

---

### Task 5: Visual Debug Fixture And Runner Checks

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `scripts/gui-visual-debug.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`

- [ ] **Step 1: Add test expectations first**

In `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`, add assertions that source includes the fixture action:

```js
  assert.equal(source.includes("buildSourceControlFixtureAction"), true);
  assert.equal(source.includes("loadSourceControlFixture"), true);
  assert.equal(source.includes("visual_source_control_fixture_loaded"), true);
```

In `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`, add:

```js
  assert.equal(runnerSource.includes("branch-toolbar"), true);
  assert.equal(runnerSource.includes("loadSourceControlFixture"), true);
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because fixture and runner checks do not exist yet.

- [ ] **Step 3: Add visual fixture action**

In `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`, add:

```js
export function buildSourceControlFixtureAction() {
  return {
    type: "visual_source_control_fixture_loaded",
    status: {
      workspace_root: "D:/visual-debug",
      is_repo: true,
      git_available: true,
      branch: "feature/t3-toolbar",
      head: "1234567",
      provider: { kind: "github", name: "GitHub" },
      counts: { staged: 1, unstaged: 2, untracked: 1, conflicted: 0, total: 4 },
      files: [],
      updated_at: "2026-06-18T00:00:00Z",
    },
  };
}
```

Add to `windowObject.__EMBEDAGENT_VISUAL_DEBUG__`:

```js
    loadSourceControlFixture() {
      dispatch(buildSourceControlFixtureAction());
    },
```

In `src/embedagent/frontend/gui/webapp/src/store.js`, add reducer case:

```js
    case "visual_source_control_fixture_loaded":
      return {
        ...state,
        sourceControl: reduceSourceControlState(state.sourceControl, {
          type: "source_control_status_loaded",
          status: action.status || {},
        }),
      };
```

- [ ] **Step 4: Add runner checks**

In `scripts/gui-visual-debug.mjs`, update `runChatScenario` after the assistant reply settles:

```js
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__?.loadSourceControlFixture?.();
  });
  await page.waitForSelector('[data-testid="branch-toolbar"]', { timeout: 10000 });
  const toolbarText = await page.locator('[data-testid="branch-toolbar"]').innerText();
  if (!toolbarText.includes("feature/t3-toolbar") || !toolbarText.includes("4 changes")) {
    throw new Error(`Branch toolbar did not show fixture source-control state: ${toolbarText}`);
  }
```

Return it in the scenario result:

```js
  return { assistantText, branchToolbar: toolbarText };
```

In `measureResponsiveLayout`, include:

```js
      branchToolbar: rect('[data-testid="branch-toolbar"]'),
```

In `runResponsiveScenario`, load the fixture before measuring each viewport:

```js
    await page.evaluate(() => {
      window.__EMBEDAGENT_VISUAL_DEBUG__?.loadSourceControlFixture?.();
    });
    await page.waitForSelector('[data-testid="branch-toolbar"]', { timeout: 10000 });
```

Add a responsive assertion:

```js
    if (!metrics.branchToolbar || metrics.branchToolbar.width < 260) {
      throw new Error(
        `Branch toolbar too narrow or missing at ${viewport.name}: ${metrics.branchToolbar ? metrics.branchToolbar.width : "missing"}`,
      );
    }
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 6: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js src/embedagent/frontend/gui/webapp/src/store.js scripts/gui-visual-debug.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs
git commit -m "test: cover branch toolbar visual fixture"
```

---

### Task 6: Build, Docs, And Final Verification

**Files:**
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Generated: `src/embedagent/frontend/gui/static/assets/app.js`
- Generated: `src/embedagent/frontend/gui/static/assets/app.css`
- Generated: `src/embedagent/frontend/gui/static/index.html` only if the build updates it

- [ ] **Step 1: Update tracker docs**

At the top of `docs/development-tracker.md` current phase entries, add:

```md
### 2026-06-18 - T3 Branch Toolbar Run Context

- GUI composer now has a T3 Code-style run-context toolbar directly underneath the input surface.
- The toolbar derives workspace, current checkout, branch, provider, and dirty-count labels from existing GUI app-shell and read-only source-control state.
- Source-control mutation affordances are intentionally read-only/disabled in this first parity slice; checkout, branch creation, PR checkout, staging, commit, push, pull, checkpoint, provider, and worktree mutation remain out of scope.
- This slice stays in the GUI app shell: no Agent Core, transcript, workflow state, permission/runtime reducers, provider configuration, extension loading, telemetry, source-control checkpoint truth, or C/C++ workflow package semantics changed.
```

Add a matching dated entry to `docs/design-change-log.md`:

```md
## 2026-06-18 - T3 Branch Toolbar Run Context

- Added a GUI-only T3 Code-style branch/run-context toolbar under the composer.
- Kept the first slice read-only over existing local source-control status so Agent Core stays minimal and source-control mutation/checkpoint semantics remain outside this change.
```

- [ ] **Step 2: Run full webapp helper tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 3: Build GUI static assets**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: PASS and updated static assets under `src/embedagent/frontend/gui/static/`.

- [ ] **Step 4: Run visual harness**

Run:

```bash
node scripts/gui-visual-debug.mjs --scenario chat,responsive --no-build --output "$env:TEMP\embedagent-t3-branch-toolbar" --viewports 1280x720,700x640,520x720
```

Expected: PASS; summary JSON has no console warning/error messages and screenshots show the toolbar under the composer.

- [ ] **Step 5: Check diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; changed files match this plan.

- [ ] **Step 6: Commit**

```bash
git add docs/development-tracker.md docs/design-change-log.md src/embedagent/frontend/gui/static src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/gui/webapp/test scripts/gui-visual-debug.mjs
git commit -m "feat: add t3 branch toolbar run context"
```

---

## Self-Review

Spec coverage:

- T3 source files are represented by a GUI `BranchToolbar` component plus T3-derived helper semantics.
- Toolbar placement below composer is covered in Tasks 3, 4, and 5.
- Workspace/local checkout/branch/provider/dirty-count state is covered in Task 1.
- Disabled mutation affordances are covered in Task 2 and Task 4.
- Narrow viewport wrapping is covered in Task 4 and Task 5.
- GUI-only architecture and no Agent Core/backend mutation changes are preserved by the file structure and docs task.
- Tests, build, visual harness, and docs are covered in Tasks 1 through 6.

Placeholder scan:

- No `TBD`, `TODO`, `implement later`, or "similar to" placeholders are used as required plan steps.

Type consistency:

- `buildBranchToolbarModel`, `resolveBranchLabel`, and `summarizeBranchToolbarChanges` are defined in Task 1 and reused consistently.
- Component prop names are `model` and `onRefresh`.
- App/Composer prop names are `branchToolbar` and `onRefreshSourceControl`.
