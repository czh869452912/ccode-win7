# T3 Visual Language Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the GUI visual language closer to T3 Code while preserving the existing Windows 7 compatible React/CSS shell.

**Architecture:** This is a GUI-shell-only slice. The implementation changes design tokens and component-level CSS for the workbench, timeline, composer, right panel, and diff surface without touching Agent Core, protocol vocabulary, runtime behavior, or introducing Tailwind/shadcn dependencies.

**Tech Stack:** React 18, Vite, plain CSS, Node-based helper tests, existing GUI visual debug harness.

---

### Task 1: Add Visual Language CSS Contract

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write a failing CSS contract test**

Create `visual-language-css.test.mjs` with assertions that require neutral T3-style tokens and class rules:

```js
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STYLES_PATH = path.join(WEBAPP_ROOT, "src", "styles.css");

function readStyles() {
  return fs.readFileSync(STYLES_PATH, "utf8");
}

function extractRootBlock(source) {
  const match = source.match(/:root\s*\{([\s\S]*?)\n\}/);
  return match ? match[1] : "";
}

function assertIncludes(source, needle, label) {
  assert.equal(source.includes(needle), true, label);
}

function assertNotIncludes(source, needle, label) {
  assert.equal(source.includes(needle), false, label);
}

export function runVisualLanguageCssTests() {
  const styles = readStyles();
  const root = extractRootBlock(styles);

  assertIncludes(root, "--bg-canvas: #0f0f10;", "canvas should use T3 neutral dark");
  assertIncludes(root, "--bg-default: #151516;", "default surface should use T3 neutral dark");
  assertIncludes(root, "--bg-subtle: #1c1c1e;", "subtle surface should use T3 neutral dark");
  assertIncludes(root, "--border-default: rgba(255,255,255,.08);", "border should be soft");
  assertIncludes(root, "--border-focus: rgba(255,255,255,.24);", "focus should be neutral");
  assertIncludes(root, "--r-lg: 18px;", "large radius should match T3 composer language");
  assertIncludes(root, "--surface-shadow:", "surface shadow token should exist");
  assertNotIncludes(root, "#0d1117", "root should no longer use GitHub canvas token");
  assertNotIncludes(root, "#161b22", "root should no longer use GitHub default token");

  assertIncludes(styles, ".timeline-shell", "timeline shell should constrain chat column");
  assertIncludes(styles, "max-width: 860px;", "timeline shell should use a T3-like centered width");
  assertIncludes(styles, ".composer::before", "composer should have a top fade like T3");
  assertIncludes(styles, "border-radius: var(--r-lg);", "composer should use the large radius token");
  assertIncludes(styles, ".right-panel-tab.active", "right panel active tab styling should remain explicit");
  assertIncludes(styles, ".diff-panel", "diff panel should keep a dedicated shell");
  assertIncludes(styles, "background: color-mix(in srgb, var(--bg-default) 92%, var(--bg-canvas));", "panel shells should use mixed neutral surfaces");
}
```

Modify `run-tests.mjs` to import and call `runVisualLanguageCssTests()`.

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because the current CSS still uses GitHub-dark tokens and lacks the new visual-language rules.

- [ ] **Step 3: Commit is not allowed yet**

Do not commit while the test is red.

### Task 2: Apply T3 Visual Language To GUI CSS

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`

- [ ] **Step 1: Replace root design tokens**

Change the root palette to neutral T3-style dark surfaces, softer borders, compact typography, and larger composer radius. Keep semantic colors for success/warning/error/info/diff states.

- [ ] **Step 2: Restyle workbench shell**

Make app/workbench background neutral, soften side panels, reduce hard separators, and make tabs use understated active states rather than bright GitHub-style accents.

- [ ] **Step 3: Restyle timeline and work rows**

Center timeline content with `.timeline-shell`, reduce card borders, make user/assistant rows closer to T3 chat spacing, and make `.t3-work-row` rows compact with subtle hover/expand states.

- [ ] **Step 4: Restyle composer and pending panels**

Make composer a rounded neutral panel with a soft top fade, subtle shadow, compact toolbar controls, and pending panels that feel embedded inside the composer instead of modal-like cards.

- [ ] **Step 5: Restyle right panel and diff surface**

Make right-panel tabs, diff file list, and diff viewport use the same neutral panel language with softer borders and restrained status color.

- [ ] **Step 6: Run the CSS contract test and verify it passes**

Run:

```powershell
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs docs/superpowers/plans/2026-06-15-t3-visual-language.md
git commit -m "style(gui): align visual language with t3 code"
```

### Task 3: Rendered Visual QA And Documentation Closeout

**Files:**
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Move: `docs/superpowers/plans/2026-06-15-t3-visual-language.md` to `docs/archive/t3-parity-gui-debug/2026-06-15-t3-visual-language.md`

- [ ] **Step 1: Build static GUI assets**

Run:

```powershell
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: build succeeds and static assets are updated.

- [ ] **Step 2: Run visual GUI harness**

Run:

```powershell
cd src/embedagent/frontend/gui/webapp
npm run visual:gui -- --scenario all --bundle-root D:\Claude-project\ccode-win7\build\offline-dist\embedagent-win7-x64 --output $env:TEMP\embedagent-gui-t3-visual-language
```

Expected: summary reports zero console warnings/errors, chat response renders once, diff panel opens, and right tabs do not overlap.

- [ ] **Step 3: Update docs**

Record that the GUI shell now follows a T3-inspired neutral workbench visual language and that visual QA should use the GUI harness for future polish changes.

- [ ] **Step 4: Archive the plan**

Move the plan into `docs/archive/t3-parity-gui-debug/`.

- [ ] **Step 5: Final verification**

Run:

```powershell
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
uv run pytest tests/test_llm_resilience.py -q
git diff --check
```

Expected: all commands exit 0; `git diff --check` may report only existing CRLF warnings.

- [ ] **Step 6: Commit**

```powershell
git add src/embedagent/frontend/gui/webapp docs
git commit -m "docs(gui): document t3 visual language alignment"
```

---

## Self-Review

- The plan is scoped to GUI visual language only and does not touch Agent Core.
- The first task creates a red CSS contract before production CSS changes.
- Rendered QA uses the existing Codex-operable GUI visual debug harness.
- No new runtime dependency, online service, Docker, WSL, VS Code, or Python 3.9+ syntax is introduced.
