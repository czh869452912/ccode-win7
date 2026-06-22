# T3 Composer Command Menu Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the GUI composer slash hint bar with a T3 Code-style composer-owned command menu, context path menu, and compact primary action controls while keeping submitted prompts as plain text.

**Architecture:** This is a frontend-only GUI app-shell slice. Pure composer model helpers detect triggers, rank slash commands, and project loaded file-tree nodes into path candidates; `Composer.jsx` wires those helpers to focused React menu/action components and receives all command/file data through existing app state props.

**Tech Stack:** React 18, Vite static build, plain JavaScript ES modules, CSS in `styles.css`, Node-based webapp tests, Playwright visual debug runner.

---

## Constraints

- Do not touch Agent Core, backend routes, transcript reducers, permission policy, provider configuration, source-control mutation, or workflow state.
- Preserve Windows 7 and offline deployment constraints. Do not add runtime dependencies.
- Keep prompt submission plain text. File context selection inserts text such as `@src/parser.c ` into the textarea.
- Keep existing `ComposerInteractionPanel` and `BranchToolbar`.
- Use official product vocabulary: `build`, `tasks`, `current_phase`, `discipline_profile`.
- Keep browser code compatible with WebView2 109-era APIs. Use React state, refs, and CSS only.

## File Structure

Create:

- `src/embedagent/frontend/gui/webapp/src/composer/composer-trigger.js`
  - Pure trigger range detection for `/` and `@`.
  - Pure text replacement helper for menu selection.
- `src/embedagent/frontend/gui/webapp/src/composer/composer-command-search.js`
  - Converts existing workbench commands into composer slash items.
  - Ranks exact, prefix, word-boundary, keyword, and substring matches.
- `src/embedagent/frontend/gui/webapp/src/composer/composer-path-context.js`
  - Flattens currently loaded GUI file-tree nodes into file context candidates.
  - Ranks path/name matches and builds plain-text context insertion.
- `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerCommandMenu.jsx`
  - T3-style grouped floating menu owned by the composer.
- `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPrimaryActions.jsx`
  - Compact send/stop controls.
- `src/embedagent/frontend/gui/webapp/test/composer-trigger.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/composer-command-search.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/composer-path-context.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/composer-components-source.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/composer-integration-source.test.mjs`

Modify:

- `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
  - Replace inline hint bar logic with trigger-driven menu state.
  - Wire keyboard navigation and menu selection.
  - Keep command-palette opener, interaction panel, and branch toolbar.
- `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Pass visible workbench commands and `state.fileTree` to `Composer`.
- `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Remove obsolete `.composer-hints` / `.composer-hint` styling.
  - Add command menu and primary action styling.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
  - Add composer file-tree fixture for stable path menu visual checks.
- `src/embedagent/frontend/gui/webapp/src/store.js`
  - Reduce composer fixture file-tree action into GUI state.
- `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Register new composer tests.
- `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`
  - Assert T3 composer menu/action classes and removal of old hint classes.
- `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
  - Assert composer fixture action and installed debug helper.
- `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`
  - Assert visual runner supports the `composer` scenario.
- `scripts/gui-visual-debug.mjs`
  - Add `composer` scenario for slash menu, path menu, keyboard selection, and viewport overflow checks.
- `docs/development-tracker.md`
- `docs/design-change-log.md`

---

## Task 1: Composer Trigger Model

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/test/composer-trigger.test.mjs`
- Create: `src/embedagent/frontend/gui/webapp/src/composer/composer-trigger.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write the failing trigger tests**

Create `src/embedagent/frontend/gui/webapp/test/composer-trigger.test.mjs`:

```javascript
import assert from "node:assert/strict";

import {
  composerTriggerKey,
  detectComposerTrigger,
  replaceComposerTrigger,
} from "../src/composer/composer-trigger.js";

export function runComposerTriggerTests() {
  assert.deepEqual(detectComposerTrigger("/mo", 3), {
    kind: "slash",
    marker: "/",
    query: "mo",
    start: 0,
    end: 3,
    text: "/mo",
  });

  assert.deepEqual(detectComposerTrigger("please /di", 10), {
    kind: "slash",
    marker: "/",
    query: "di",
    start: 7,
    end: 10,
    text: "/di",
  });

  assert.equal(detectComposerTrigger("src/parser.c", 6), null);
  assert.equal(detectComposerTrigger("http://localhost", 7), null);
  assert.equal(detectComposerTrigger("email/name", 7), null);

  assert.deepEqual(detectComposerTrigger("@src/pa", 7), {
    kind: "path",
    marker: "@",
    query: "src/pa",
    start: 0,
    end: 7,
    text: "@src/pa",
  });

  assert.deepEqual(detectComposerTrigger("inspect @parser", 15), {
    kind: "path",
    marker: "@",
    query: "parser",
    start: 8,
    end: 15,
    text: "@parser",
  });

  assert.equal(detectComposerTrigger("mail@example.com", 7), null);
  assert.equal(detectComposerTrigger("ask @", 5)?.query, "");

  const replacement = replaceComposerTrigger(
    "run /di now",
    detectComposerTrigger("run /di now", 7),
    "/diff ",
  );
  assert.deepEqual(replacement, {
    text: "run /diff  now",
    cursor: 10,
  });

  assert.equal(
    composerTriggerKey(detectComposerTrigger("ask @parser", 11)),
    "path:4:11:@parser",
  );
  assert.equal(composerTriggerKey(null), "");
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` imports near the other model tests:

```javascript
import { runComposerTriggerTests } from "./composer-trigger.test.mjs";
```

Call it near `runBranchToolbarModelTests()`:

```javascript
  runBranchToolbarModelTests();
  runComposerTriggerTests();
```

- [ ] **Step 2: Run the trigger test and verify it fails**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/composer-trigger.test.mjs').then((m) => { m.runComposerTriggerTests(); console.log('composer trigger checks passed'); })"
```

Expected: fail with `ERR_MODULE_NOT_FOUND` for `src/composer/composer-trigger.js`.

- [ ] **Step 3: Implement the trigger helper**

Create `src/embedagent/frontend/gui/webapp/src/composer/composer-trigger.js`:

```javascript
function clampCursor(text, cursor) {
  const source = String(text || "");
  const raw = Number.isFinite(cursor) ? cursor : source.length;
  return Math.max(0, Math.min(source.length, raw));
}

function isBoundary(source, index) {
  if (index <= 0) return true;
  return /\s/.test(source.charAt(index - 1));
}

function findTokenStart(source, cursor) {
  let index = cursor;
  while (index > 0 && !/\s/.test(source.charAt(index - 1))) {
    index -= 1;
  }
  return index;
}

export function detectComposerTrigger(text = "", cursor = undefined) {
  const source = String(text || "");
  const end = clampCursor(source, cursor);
  const start = findTokenStart(source, end);
  if (!isBoundary(source, start)) return null;

  const token = source.slice(start, end);
  if (!token) return null;

  if (token.charAt(0) === "/") {
    return {
      kind: "slash",
      marker: "/",
      query: token.slice(1),
      start,
      end,
      text: token,
    };
  }

  if (token.charAt(0) === "@") {
    return {
      kind: "path",
      marker: "@",
      query: token.slice(1),
      start,
      end,
      text: token,
    };
  }

  return null;
}

export function composerTriggerKey(trigger) {
  if (!trigger) return "";
  return `${trigger.kind}:${trigger.start}:${trigger.end}:${trigger.text}`;
}

export function replaceComposerTrigger(text, trigger, replacement) {
  const source = String(text || "");
  const insertion = String(replacement || "");
  if (!trigger || trigger.start < 0 || trigger.end < trigger.start || trigger.end > source.length) {
    const cursor = source.length + insertion.length;
    return { text: `${source}${insertion}`, cursor };
  }
  const before = source.slice(0, trigger.start);
  const after = source.slice(trigger.end);
  const nextText = `${before}${insertion}${after}`;
  return {
    text: nextText,
    cursor: before.length + insertion.length,
  };
}
```

- [ ] **Step 4: Run the trigger test and full webapp tests**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/composer-trigger.test.mjs').then((m) => { m.runComposerTriggerTests(); console.log('composer trigger checks passed'); })"
npm test
```

Expected:

- First command prints `composer trigger checks passed`.
- `npm test` prints `frontend helper checks passed`.

- [ ] **Step 5: Commit Task 1**

Run from repo root:

```bash
git add src/embedagent/frontend/gui/webapp/src/composer/composer-trigger.js src/embedagent/frontend/gui/webapp/test/composer-trigger.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "test: add composer trigger model"
```

---

## Task 2: Composer Slash Command Search Model

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/test/composer-command-search.test.mjs`
- Create: `src/embedagent/frontend/gui/webapp/src/composer/composer-command-search.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write the failing command search tests**

Create `src/embedagent/frontend/gui/webapp/test/composer-command-search.test.mjs`:

```javascript
import assert from "node:assert/strict";

import {
  buildComposerCommandItems,
  groupComposerCommandItems,
  searchComposerCommandItems,
} from "../src/composer/composer-command-search.js";

const COMMANDS = [
  { id: "session.resume", group: "session", label: "Resume Session", slash: "/resume", visibleWhen: "always" },
  { id: "surface.diff", group: "surface", label: "Open Diff", slash: "/diff", visibleWhen: "always", keywords: ["git", "changes"] },
  { id: "workflow.diff", group: "workflow", label: "Review Diff", slash: "/diff", visibleWhen: "has_session" },
  { id: "mode.build", group: "mode", label: "Mode: Build", slash: "/mode build", visibleWhen: "has_session" },
  { id: "mode.debug", group: "mode", label: "Mode: Debug", slash: "/mode debug", visibleWhen: "has_session" },
  { id: "message.stop", group: "message", label: "Stop Running Turn", slash: "", visibleWhen: "running" },
];

export function runComposerCommandSearchTests() {
  const items = buildComposerCommandItems(COMMANDS);
  assert.deepEqual(
    items.map((item) => item.id),
    ["slash:session.resume", "slash:surface.diff", "slash:mode.build", "slash:mode.debug"],
  );
  assert.equal(items[1].insertion, "/diff ");
  assert.equal(items[1].detail, "/diff");
  assert.equal(items[1].type, "slash-command");

  assert.deepEqual(
    searchComposerCommandItems(items, "diff").map((item) => item.slash),
    ["/diff"],
  );

  assert.deepEqual(
    searchComposerCommandItems(items, "/mode d").map((item) => item.slash),
    ["/mode debug"],
  );

  assert.equal(searchComposerCommandItems(items, "git")[0].slash, "/diff");
  assert.equal(searchComposerCommandItems(items, "build")[0].slash, "/mode build");
  assert.equal(searchComposerCommandItems(items, "sess")[0].slash, "/resume");

  const grouped = groupComposerCommandItems(searchComposerCommandItems(items, "mode"));
  assert.deepEqual(
    grouped.map((group) => group.label),
    ["Mode"],
  );
  assert.deepEqual(
    grouped[0].items.map((item) => item.slash),
    ["/mode build", "/mode debug"],
  );
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
import { runComposerCommandSearchTests } from "./composer-command-search.test.mjs";
```

Call it after `runComposerTriggerTests()`:

```javascript
  runComposerTriggerTests();
  runComposerCommandSearchTests();
```

- [ ] **Step 2: Run the command search test and verify it fails**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/composer-command-search.test.mjs').then((m) => { m.runComposerCommandSearchTests(); console.log('composer command search checks passed'); })"
```

Expected: fail with `ERR_MODULE_NOT_FOUND` for `src/composer/composer-command-search.js`.

- [ ] **Step 3: Implement the command search helper**

Create `src/embedagent/frontend/gui/webapp/src/composer/composer-command-search.js`:

```javascript
const GROUP_LABELS = {
  app: "App",
  session: "Session",
  message: "Message",
  mode: "Mode",
  surface: "Surface",
  workspace: "Workspace",
  workflow: "Workflow",
  view: "View",
  command: "Command",
};

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function normalizeCommandQuery(query) {
  const normalized = normalizeText(query);
  return normalized.charAt(0) === "/" ? normalized.slice(1) : normalized;
}

function compactSlash(value) {
  const raw = String(value || "").trim();
  return raw.charAt(0) === "/" ? raw : `/${raw}`;
}

function wordBoundaryMatch(value, query) {
  if (!query) return false;
  return normalizeText(value)
    .split(/[^a-z0-9_./-]+/i)
    .filter(Boolean)
    .some((part) => part.startsWith(query));
}

function keywordMatch(keywords, query) {
  return (Array.isArray(keywords) ? keywords : []).some((keyword) => {
    const normalized = normalizeText(keyword);
    return normalized === query || normalized.startsWith(query) || normalized.includes(query);
  });
}

function scoreItem(item, query) {
  if (!query) return 100 + item.order;

  const slash = normalizeText(item.slash);
  const slashBare = slash.charAt(0) === "/" ? slash.slice(1) : slash;
  const label = normalizeText(item.label);

  if (slashBare === query || slash === `/${query}`) return 0;
  if (label === query) return 4;
  if (slashBare.startsWith(query)) return 10;
  if (slash.startsWith(`/${query}`)) return 12;
  if (label.startsWith(query)) return 20;
  if (wordBoundaryMatch(label, query)) return 30;
  if (keywordMatch(item.keywords, query)) return 40;
  if (slashBare.includes(query) || label.includes(query)) return 50;
  return Number.POSITIVE_INFINITY;
}

export function buildComposerCommandItems(commands = []) {
  const seenSlash = new Set();
  const items = [];
  for (const command of Array.isArray(commands) ? commands : []) {
    if (!command || !command.slash) continue;
    const slash = compactSlash(command.slash);
    const normalizedSlash = normalizeText(slash);
    if (seenSlash.has(normalizedSlash)) continue;
    seenSlash.add(normalizedSlash);
    items.push({
      type: "slash-command",
      id: `slash:${command.id || normalizedSlash}`,
      commandId: command.id || "",
      group: command.group || "command",
      groupLabel: GROUP_LABELS[command.group] || "Command",
      label: command.label || slash,
      detail: slash,
      slash,
      insertion: `${slash} `,
      keywords: Array.isArray(command.keywords) ? command.keywords : [],
      order: items.length,
    });
  }
  return items;
}

export function searchComposerCommandItems(items = [], query = "", limit = 8) {
  const normalizedQuery = normalizeCommandQuery(query);
  const ranked = (Array.isArray(items) ? items : [])
    .map((item) => ({ item, score: scoreItem(item, normalizedQuery) }))
    .filter((entry) => Number.isFinite(entry.score))
    .sort((left, right) => {
      if (left.score !== right.score) return left.score - right.score;
      return left.item.order - right.item.order;
    })
    .map((entry) => entry.item);
  return ranked.slice(0, Math.max(0, limit));
}

export function groupComposerCommandItems(items = []) {
  const groups = [];
  const byGroup = new Map();
  for (const item of Array.isArray(items) ? items : []) {
    const groupId = item.group || "command";
    if (!byGroup.has(groupId)) {
      const group = {
        id: `command-group:${groupId}`,
        label: item.groupLabel || GROUP_LABELS[groupId] || "Command",
        items: [],
      };
      byGroup.set(groupId, group);
      groups.push(group);
    }
    byGroup.get(groupId).items.push(item);
  }
  return groups;
}
```

- [ ] **Step 4: Run the command search test and full webapp tests**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/composer-command-search.test.mjs').then((m) => { m.runComposerCommandSearchTests(); console.log('composer command search checks passed'); })"
npm test
```

Expected:

- First command prints `composer command search checks passed`.
- `npm test` prints `frontend helper checks passed`.

- [ ] **Step 5: Commit Task 2**

Run from repo root:

```bash
git add src/embedagent/frontend/gui/webapp/src/composer/composer-command-search.js src/embedagent/frontend/gui/webapp/test/composer-command-search.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat: add composer command search model"
```

---

## Task 3: Composer Path Context Model

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/test/composer-path-context.test.mjs`
- Create: `src/embedagent/frontend/gui/webapp/src/composer/composer-path-context.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write the failing path context tests**

Create `src/embedagent/frontend/gui/webapp/test/composer-path-context.test.mjs`:

```javascript
import assert from "node:assert/strict";

import {
  buildPathContextInsertion,
  flattenComposerPathCandidates,
  groupComposerPathCandidates,
  searchComposerPathCandidates,
} from "../src/composer/composer-path-context.js";

const FILE_TREE = [
  {
    id: "src",
    path: "src",
    name: "src",
    kind: "dir",
    childrenLoaded: true,
    children: [
      { id: "src/main.c", path: "src/main.c", name: "main.c", kind: "file" },
      { id: "src/parser.c", path: "src/parser.c", name: "parser.c", kind: "file" },
      {
        id: "src/include",
        path: "src/include",
        name: "include",
        kind: "dir",
        childrenLoaded: true,
        children: [
          { id: "src/include/parser.h", path: "src/include/parser.h", name: "parser.h", kind: "file" },
        ],
      },
    ],
  },
  { id: "README.md", path: "README.md", name: "README.md", kind: "file" },
  { id: "broken", name: "broken", kind: "file" },
];

export function runComposerPathContextTests() {
  const candidates = flattenComposerPathCandidates(FILE_TREE);
  assert.deepEqual(
    candidates.map((candidate) => candidate.path),
    ["README.md", "src/include/parser.h", "src/main.c", "src/parser.c"],
  );
  assert.equal(candidates.every((candidate) => candidate.type === "path-context"), true);
  assert.equal(candidates.every((candidate) => candidate.id.startsWith("path:")), true);

  assert.deepEqual(
    searchComposerPathCandidates(candidates, "par").map((candidate) => candidate.path),
    ["src/parser.c", "src/include/parser.h"],
  );

  assert.equal(searchComposerPathCandidates(candidates, "read")[0].path, "README.md");
  assert.equal(searchComposerPathCandidates(candidates, "include")[0].path, "src/include/parser.h");
  assert.equal(searchComposerPathCandidates(candidates, "missing").length, 0);

  assert.equal(buildPathContextInsertion(candidates.find((candidate) => candidate.path === "src/parser.c")), "@src/parser.c ");

  const grouped = groupComposerPathCandidates(searchComposerPathCandidates(candidates, "parser"));
  assert.equal(grouped.length, 1);
  assert.equal(grouped[0].label, "Files");
  assert.deepEqual(
    grouped[0].items.map((candidate) => candidate.path),
    ["src/parser.c", "src/include/parser.h"],
  );
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
import { runComposerPathContextTests } from "./composer-path-context.test.mjs";
```

Call it after `runComposerCommandSearchTests()`:

```javascript
  runComposerCommandSearchTests();
  runComposerPathContextTests();
```

- [ ] **Step 2: Run the path context test and verify it fails**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/composer-path-context.test.mjs').then((m) => { m.runComposerPathContextTests(); console.log('composer path context checks passed'); })"
```

Expected: fail with `ERR_MODULE_NOT_FOUND` for `src/composer/composer-path-context.js`.

- [ ] **Step 3: Implement the path context helper**

Create `src/embedagent/frontend/gui/webapp/src/composer/composer-path-context.js`:

```javascript
function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function normalizePath(value) {
  return String(value || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

function fileNameFromPath(path) {
  const normalized = normalizePath(path);
  const parts = normalized.split("/").filter(Boolean);
  return parts[parts.length - 1] || normalized;
}

function collectFileNodes(nodes, output) {
  for (const node of Array.isArray(nodes) ? nodes : []) {
    if (!node || typeof node !== "object") continue;
    const path = normalizePath(node.path || "");
    const kind = String(node.kind || "").toLowerCase();
    if (kind === "file" && path) {
      const name = node.name || fileNameFromPath(path);
      output.push({
        type: "path-context",
        id: `path:${path}`,
        label: name,
        detail: path,
        path,
        name,
        order: output.length,
      });
    }
    if (Array.isArray(node.children)) {
      collectFileNodes(node.children, output);
    }
  }
}

function scoreCandidate(candidate, query) {
  if (!query) return 100 + candidate.order;
  const path = normalizeText(candidate.path);
  const name = normalizeText(candidate.name);
  if (name === query) return 0;
  if (path === query) return 2;
  if (name.startsWith(query)) return 8;
  if (path.startsWith(query)) return 12;
  if (path.split("/").some((part) => part.startsWith(query))) return 20;
  if (name.includes(query)) return 30;
  if (path.includes(query)) return 40;
  return Number.POSITIVE_INFINITY;
}

export function flattenComposerPathCandidates(nodes = []) {
  const output = [];
  collectFileNodes(nodes, output);
  return output.sort((left, right) => left.path.localeCompare(right.path));
}

export function searchComposerPathCandidates(candidates = [], query = "", limit = 8) {
  const normalizedQuery = normalizeText(query);
  const ranked = (Array.isArray(candidates) ? candidates : [])
    .map((candidate) => ({ candidate, score: scoreCandidate(candidate, normalizedQuery) }))
    .filter((entry) => Number.isFinite(entry.score))
    .sort((left, right) => {
      if (left.score !== right.score) return left.score - right.score;
      const leftDepth = left.candidate.path.split("/").length;
      const rightDepth = right.candidate.path.split("/").length;
      if (leftDepth !== rightDepth) return leftDepth - rightDepth;
      return left.candidate.path.localeCompare(right.candidate.path);
    })
    .map((entry) => entry.candidate);
  return ranked.slice(0, Math.max(0, limit));
}

export function groupComposerPathCandidates(items = []) {
  return [
    {
      id: "path-group:files",
      label: "Files",
      items: Array.isArray(items) ? items : [],
    },
  ].filter((group) => group.items.length > 0);
}

export function buildPathContextInsertion(candidate) {
  if (!candidate || !candidate.path) return "";
  return `@${candidate.path} `;
}
```

- [ ] **Step 4: Run the path context test and full webapp tests**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/composer-path-context.test.mjs').then((m) => { m.runComposerPathContextTests(); console.log('composer path context checks passed'); })"
npm test
```

Expected:

- First command prints `composer path context checks passed`.
- `npm test` prints `frontend helper checks passed`.

- [ ] **Step 5: Commit Task 3**

Run from repo root:

```bash
git add src/embedagent/frontend/gui/webapp/src/composer/composer-path-context.js src/embedagent/frontend/gui/webapp/test/composer-path-context.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat: add composer path context model"
```

---

## Task 4: Composer Menu And Primary Action Components

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/test/composer-components-source.test.mjs`
- Create: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerCommandMenu.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPrimaryActions.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write the failing component source tests**

Create `src/embedagent/frontend/gui/webapp/test/composer-components-source.test.mjs`:

```javascript
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readSource(...parts) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", ...parts), "utf8").replace(/\r\n?/g, "\n");
}

function assertNoCoreBoundaryLeak(source, label) {
  assert.equal(source.includes("fetch("), false, `${label} must not fetch`);
  assert.equal(source.includes("transcript"), false, `${label} must not mention transcript state`);
  assert.equal(source.includes("PermissionPolicy"), false, `${label} must not import permission policy`);
  assert.equal(source.includes("embedagent"), false, `${label} must stay in GUI frontend modules`);
}

export function runComposerComponentsSourceTests() {
  const menuSource = readSource("components", "composer", "ComposerCommandMenu.jsx");
  assert.equal(menuSource.includes('data-testid="composer-command-menu"'), true);
  assert.equal(menuSource.includes("composer-menu-group"), true);
  assert.equal(menuSource.includes("composer-menu-item"), true);
  assert.equal(menuSource.includes("composer-menu-empty"), true);
  assert.equal(menuSource.includes("onMouseDown"), true);
  assertNoCoreBoundaryLeak(menuSource, "ComposerCommandMenu");

  const actionsSource = readSource("components", "composer", "ComposerPrimaryActions.jsx");
  assert.equal(actionsSource.includes('data-testid="composer-primary-action"'), true);
  assert.equal(actionsSource.includes('data-testid="composer-stop-action"'), true);
  assert.equal(actionsSource.includes("composer-primary-action"), true);
  assert.equal(actionsSource.includes("composer-stop-action"), true);
  assertNoCoreBoundaryLeak(actionsSource, "ComposerPrimaryActions");
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
import { runComposerComponentsSourceTests } from "./composer-components-source.test.mjs";
```

Call it after `runComposerPathContextTests()`:

```javascript
  runComposerPathContextTests();
  runComposerComponentsSourceTests();
```

- [ ] **Step 2: Run the component source test and verify it fails**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/composer-components-source.test.mjs').then((m) => { m.runComposerComponentsSourceTests(); console.log('composer component source checks passed'); })"
```

Expected: fail with `ENOENT` for `ComposerCommandMenu.jsx`.

- [ ] **Step 3: Implement `ComposerCommandMenu.jsx`**

Create `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerCommandMenu.jsx`:

```javascript
import React from "react";

export default function ComposerCommandMenu({
  open,
  trigger,
  groups = [],
  activeItemId = "",
  onSelect,
  onHighlight,
  emptyText = "No matches",
}) {
  if (!open) return null;

  const safeGroups = Array.isArray(groups) ? groups : [];
  const itemCount = safeGroups.reduce((count, group) => count + (Array.isArray(group.items) ? group.items.length : 0), 0);

  return (
    <div
      id="composer-command-menu"
      className="composer-command-menu"
      role="listbox"
      aria-label={trigger?.kind === "path" ? "File context suggestions" : "Slash command suggestions"}
      data-trigger-kind={trigger?.kind || ""}
      data-testid="composer-command-menu"
    >
      {itemCount === 0 && (
        <div className="composer-menu-empty" data-testid="composer-menu-empty">
          {emptyText}
        </div>
      )}
      {safeGroups.map((group) => (
        <section className="composer-menu-group" key={group.id || group.label}>
          <div className="composer-menu-group-label">{group.label}</div>
          <div className="composer-menu-group-items">
            {(Array.isArray(group.items) ? group.items : []).map((item) => {
              const active = item.id === activeItemId;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="option"
                  aria-selected={active}
                  className={`composer-menu-item${active ? " active" : ""}`}
                  data-testid={`composer-menu-item--${item.id}`}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseMove={() => {
                    if (typeof onHighlight === "function") onHighlight(item);
                  }}
                  onClick={() => {
                    if (typeof onSelect === "function") onSelect(item);
                  }}
                >
                  <span className="composer-menu-item-main">
                    <span className="composer-menu-item-label">{item.label}</span>
                    {item.detail && <span className="composer-menu-item-detail">{item.detail}</span>}
                  </span>
                  {item.type === "path-context" && <span className="composer-menu-item-kind">file</span>}
                  {item.type === "slash-command" && <span className="composer-menu-item-kind">command</span>}
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Implement `ComposerPrimaryActions.jsx`**

Create `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPrimaryActions.jsx`:

```javascript
import React from "react";

export default function ComposerPrimaryActions({
  isRunning,
  disabled,
  canSend,
  onSend,
  onStop,
  sendLabel = "Send",
  stopLabel = "Stop",
}) {
  if (isRunning) {
    return (
      <button
        className="composer-stop-action"
        type="button"
        onClick={onStop}
        aria-label={stopLabel}
        title={stopLabel}
        data-testid="composer-stop-action"
      >
        <span aria-hidden="true">■</span>
      </button>
    );
  }

  return (
    <button
      className="composer-primary-action"
      type="button"
      onClick={onSend}
      disabled={Boolean(disabled || !canSend)}
      aria-label={sendLabel}
      title={sendLabel}
      data-testid="composer-primary-action"
    >
      <span aria-hidden="true">↑</span>
    </button>
  );
}
```

- [ ] **Step 5: Run component source and full webapp tests**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/composer-components-source.test.mjs').then((m) => { m.runComposerComponentsSourceTests(); console.log('composer component source checks passed'); })"
npm test
```

Expected:

- First command prints `composer component source checks passed`.
- `npm test` prints `frontend helper checks passed`.

- [ ] **Step 6: Commit Task 4**

Run from repo root:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/composer/ComposerCommandMenu.jsx src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPrimaryActions.jsx src/embedagent/frontend/gui/webapp/test/composer-components-source.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat: add composer menu components"
```

---

## Task 5: Wire Composer Behavior To App State

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/test/composer-integration-source.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write the failing composer integration source tests**

Create `src/embedagent/frontend/gui/webapp/test/composer-integration-source.test.mjs`:

```javascript
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readSource(...parts) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", ...parts), "utf8").replace(/\r\n?/g, "\n");
}

export function runComposerIntegrationSourceTests() {
  const composerSource = readSource("components", "Composer.jsx");
  assert.equal(composerSource.includes("detectComposerTrigger"), true);
  assert.equal(composerSource.includes("replaceComposerTrigger"), true);
  assert.equal(composerSource.includes("buildComposerCommandItems"), true);
  assert.equal(composerSource.includes("searchComposerCommandItems"), true);
  assert.equal(composerSource.includes("flattenComposerPathCandidates"), true);
  assert.equal(composerSource.includes("searchComposerPathCandidates"), true);
  assert.equal(composerSource.includes("ComposerCommandMenu"), true);
  assert.equal(composerSource.includes("ComposerPrimaryActions"), true);
  assert.equal(composerSource.includes("BranchToolbar"), true);
  assert.equal(composerSource.includes("ComposerInteractionPanel"), true);
  assert.equal(composerSource.includes("dismissedTriggerKey"), true);
  assert.equal(composerSource.includes("composer-hints"), false);
  assert.equal(composerSource.includes('className="composer-hint"'), false);
  assert.equal(composerSource.includes("fetch("), false);
  assert.equal(composerSource.includes("transcript"), false);
  assert.equal(composerSource.includes("PermissionPolicy"), false);

  const appSource = readSource("App.jsx");
  assert.equal(appSource.includes("visibleCommands"), true);
  assert.equal(appSource.includes("composerCommands"), true);
  assert.equal(appSource.includes("commands={composerCommands}"), true);
  assert.equal(appSource.includes("fileTree={state.fileTree}"), true);
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
import { runComposerIntegrationSourceTests } from "./composer-integration-source.test.mjs";
```

Call it after `runComposerComponentsSourceTests()`:

```javascript
  runComposerComponentsSourceTests();
  runComposerIntegrationSourceTests();
```

- [ ] **Step 2: Run the composer integration source test and verify it fails**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/composer-integration-source.test.mjs').then((m) => { m.runComposerIntegrationSourceTests(); console.log('composer integration source checks passed'); })"
```

Expected: fail because `Composer.jsx` does not import the trigger/search helpers and still contains `composer-hints`.

- [ ] **Step 3: Replace `Composer.jsx` with the wired T3-style composer**

Replace `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx` with:

```javascript
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";
import {
  buildComposerCommandItems,
  groupComposerCommandItems,
  searchComposerCommandItems,
} from "../composer/composer-command-search.js";
import {
  buildPathContextInsertion,
  flattenComposerPathCandidates,
  groupComposerPathCandidates,
  searchComposerPathCandidates,
} from "../composer/composer-path-context.js";
import {
  composerTriggerKey,
  detectComposerTrigger,
  replaceComposerTrigger,
} from "../composer/composer-trigger.js";
import ComposerCommandMenu from "./composer/ComposerCommandMenu.jsx";
import ComposerInteractionPanel from "./composer/ComposerInteractionPanel.jsx";
import ComposerPrimaryActions from "./composer/ComposerPrimaryActions.jsx";
import BranchToolbar from "./workbench/BranchToolbar.jsx";

function flattenGroups(groups) {
  return (Array.isArray(groups) ? groups : []).reduce((items, group) => {
    return items.concat(Array.isArray(group.items) ? group.items : []);
  }, []);
}

function commandsFromHints(commandHints) {
  return (Array.isArray(commandHints) ? commandHints : [])
    .filter(Boolean)
    .map((slash) => ({
      id: `hint.${String(slash).replace(/[^a-z0-9]+/gi, ".")}`,
      group: "command",
      label: slash,
      slash,
      visibleWhen: "always",
    }));
}

export default function Composer({
  value,
  onChange,
  onSend,
  onStop,
  isRunning,
  currentMode,
  commandHints = [],
  commands = [],
  fileTree = [],
  onOpenCommandPalette,
  interaction = null,
  interactionNotice = null,
  answerValue = "",
  onAnswerChange,
  onRespondInteraction,
  branchToolbar = null,
  onRefreshSourceControl,
}) {
  const lang = useLang();
  const textareaRef = useRef(null);
  const [cursor, setCursor] = useState(String(value || "").length);
  const [activeIndex, setActiveIndex] = useState(0);
  const [dismissedTriggerKey, setDismissedTriggerKey] = useState("");

  const hasInteraction = Boolean(interaction || interactionNotice);
  const composerDisabled = Boolean(isRunning || hasInteraction);
  const textValue = String(value || "");
  const trigger = useMemo(() => detectComposerTrigger(textValue, cursor), [textValue, cursor]);
  const triggerKey = composerTriggerKey(trigger);

  const commandSource = commands.length > 0 ? commands : commandsFromHints(commandHints);
  const slashItems = useMemo(() => buildComposerCommandItems(commandSource), [commandSource]);
  const pathCandidates = useMemo(() => flattenComposerPathCandidates(fileTree), [fileTree]);
  const menuOpen = Boolean(!composerDisabled && trigger && triggerKey !== dismissedTriggerKey);

  const menuGroups = useMemo(() => {
    if (!menuOpen || !trigger) return [];
    if (trigger.kind === "slash") {
      return groupComposerCommandItems(searchComposerCommandItems(slashItems, trigger.query, 8));
    }
    if (trigger.kind === "path") {
      return groupComposerPathCandidates(searchComposerPathCandidates(pathCandidates, trigger.query, 8));
    }
    return [];
  }, [menuOpen, pathCandidates, slashItems, trigger]);

  const menuItems = useMemo(() => flattenGroups(menuGroups), [menuGroups]);
  const activeItem = menuItems[Math.min(activeIndex, Math.max(0, menuItems.length - 1))] || null;

  useEffect(() => {
    setActiveIndex(0);
  }, [triggerKey]);

  useEffect(() => {
    if (cursor > textValue.length) {
      setCursor(textValue.length);
    }
  }, [cursor, textValue.length]);

  useEffect(() => {
    if (composerDisabled) {
      setDismissedTriggerKey(triggerKey);
    }
  }, [composerDisabled, triggerKey]);

  function recordCursor(target) {
    if (!target) return;
    const nextCursor = typeof target.selectionStart === "number" ? target.selectionStart : String(target.value || "").length;
    setCursor(nextCursor);
  }

  function focusAt(nextCursor) {
    window.requestAnimationFrame(() => {
      const target = textareaRef.current;
      if (!target) return;
      target.focus();
      target.setSelectionRange(nextCursor, nextCursor);
      setCursor(nextCursor);
    });
  }

  function handleChange(event) {
    setDismissedTriggerKey("");
    recordCursor(event.target);
    onChange(event.target.value);
  }

  function selectMenuItem(item) {
    if (!trigger || !item) return;
    const insertion = item.type === "path-context"
      ? buildPathContextInsertion(item)
      : item.insertion || item.slash || "";
    if (!insertion) return;
    const next = replaceComposerTrigger(textValue, trigger, insertion);
    setDismissedTriggerKey("");
    onChange(next.text);
    focusAt(next.cursor);
  }

  function handleKeyDown(event) {
    if (menuOpen) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((index) => (menuItems.length === 0 ? 0 : (index + 1) % menuItems.length));
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((index) => (menuItems.length === 0 ? 0 : (index - 1 + menuItems.length) % menuItems.length));
        return;
      }
      if ((event.key === "Enter" || event.key === "Tab") && activeItem) {
        event.preventDefault();
        selectMenuItem(activeItem);
        return;
      }
      if (event.key === "Enter" && !activeItem) {
        event.preventDefault();
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setDismissedTriggerKey(triggerKey);
        return;
      }
    }

    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!composerDisabled) onSend();
    }
  }

  function handleHighlight(item) {
    const index = menuItems.findIndex((entry) => entry.id === item.id);
    if (index >= 0) setActiveIndex(index);
  }

  return (
    <footer className="composer">
      <ComposerInteractionPanel
        interaction={interaction}
        notice={interactionNotice}
        answerValue={answerValue}
        onAnswerChange={onAnswerChange}
        onRespond={onRespondInteraction}
      />
      <div className="composer-inner">
        <ComposerCommandMenu
          open={menuOpen}
          trigger={trigger}
          groups={menuGroups}
          activeItemId={activeItem?.id || ""}
          onHighlight={handleHighlight}
          onSelect={selectMenuItem}
          emptyText={trigger?.kind === "path" ? "No files found" : "No commands found"}
        />
        {currentMode && (
          <span className={`composer-mode-badge mode-${currentMode}`}>
            {currentMode}
          </span>
        )}
        <textarea
          ref={textareaRef}
          value={textValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onClick={(event) => recordCursor(event.target)}
          onKeyUp={(event) => recordCursor(event.target)}
          onSelect={(event) => recordCursor(event.target)}
          placeholder={t("composer.placeholder", lang)}
          aria-label={t("composer.placeholder", lang)}
          aria-expanded={menuOpen}
          aria-controls={menuOpen ? "composer-command-menu" : undefined}
          disabled={composerDisabled}
          rows={1}
          data-testid="composer-input"
        />
        <button
          className="composer-tool"
          type="button"
          onClick={onOpenCommandPalette}
          aria-label="Open command palette"
          disabled={composerDisabled}
          data-testid="composer-command-palette"
        >
          /
        </button>
        <ComposerPrimaryActions
          isRunning={isRunning}
          disabled={composerDisabled}
          canSend={Boolean(textValue.trim())}
          onSend={onSend}
          onStop={onStop}
          sendLabel={t("composer.send", lang)}
          stopLabel={t("composer.stop", lang)}
        />
      </div>
      <div className="composer-hint-bar" aria-hidden="true">
        <span className="hint-text">/ 命令</span>
        <span className="hint-text">@ 文件</span>
        <span className="hint-text">↑↓ 选择</span>
        <span className="hint-text">Shift+Enter 换行</span>
        {isRunning && (
          <span className="hint-text running-hint">● running 时禁用</span>
        )}
        {hasInteraction && !isRunning && (
          <span className="hint-text running-hint">● interaction pending</span>
        )}
      </div>
      <BranchToolbar model={branchToolbar} onRefresh={onRefreshSourceControl} />
    </footer>
  );
}
```

- [ ] **Step 4: Pass commands and file tree from `App.jsx`**

Modify imports in `src/embedagent/frontend/gui/webapp/src/App.jsx`:

```javascript
import { commandById, visibleCommands } from "./workbench/commands.js";
```

Add this after `const currentStatus = state.snapshot?.status || "idle";`:

```javascript
  const commandContext = useMemo(() => ({
    hasSession: Boolean(state.currentSessionId),
    hasWorkspace: Boolean(state.app.hasActiveWorkspace),
    isRunning: currentStatus === "running" || currentStatus === "waiting_user_input",
    paletteOpen: state.workbench.commandPalette.open,
  }), [
    currentStatus,
    state.app.hasActiveWorkspace,
    state.currentSessionId,
    state.workbench.commandPalette.open,
  ]);
  const composerCommands = useMemo(() => visibleCommands(commandContext), [commandContext]);
```

Modify the `Composer` props:

```jsx
              commandHints={SLASH_COMMAND_HINTS}
              commands={composerCommands}
              fileTree={state.fileTree}
              onOpenCommandPalette={() => dispatch({ type: "workbench_command_palette_opened" })}
```

Modify `CommandPalette` props to reuse the same context:

```jsx
      context={commandContext}
```

- [ ] **Step 5: Run integration source and full webapp tests**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/composer-integration-source.test.mjs').then((m) => { m.runComposerIntegrationSourceTests(); console.log('composer integration source checks passed'); })"
npm test
```

Expected:

- First command prints `composer integration source checks passed`.
- `npm test` prints `frontend helper checks passed`.

- [ ] **Step 6: Commit Task 5**

Run from repo root:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/Composer.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test/composer-integration-source.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat: wire composer command menu state"
```

---

## Task 6: T3 Composer Menu Styling

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`

- [ ] **Step 1: Add failing CSS visual language assertions**

Modify `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs` inside `runVisualLanguageCssTests()` after the existing composer assertions:

```javascript
  assertIncludes(styles, ".composer-command-menu", "composer command menu should be styled");
  assertIncludes(styles, ".composer-menu-group", "composer menu groups should be styled");
  assertIncludes(styles, ".composer-menu-item", "composer menu items should be styled");
  assertIncludes(styles, ".composer-menu-item.active", "composer active item should be styled");
  assertIncludes(styles, ".composer-primary-action", "composer primary action should be styled");
  assertIncludes(styles, ".composer-stop-action", "composer stop action should be styled");
  assertNotIncludes(styles, ".composer-hints", "old slash hint container should be removed");
  assertNotIncludes(styles, ".composer-hint {", "old slash hint button should be removed");
```

- [ ] **Step 2: Run CSS test and verify it fails**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/visual-language-css.test.mjs').then((m) => { m.runVisualLanguageCssTests(); console.log('visual language css checks passed'); })"
```

Expected: fail because `styles.css` still contains `.composer-hints` and lacks new menu/action styles.

- [ ] **Step 3: Replace old hint CSS and add menu/action styles**

In `src/embedagent/frontend/gui/webapp/src/styles.css`:

1. Remove both `.composer-hints` blocks and the `.composer-hint` / `.composer-hint:hover` blocks.
2. Add this CSS near the current composer section:

```css
.composer-command-menu {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 8px);
  z-index: 70;
  max-height: min(320px, 52vh);
  overflow-y: auto;
  overflow-x: hidden;
  padding: 6px;
  border: 1px solid var(--border-default);
  border-radius: 14px;
  background: var(--bg-elevated);
  box-shadow: var(--surface-shadow);
}

.composer-menu-empty {
  padding: 10px 12px;
  color: var(--text-muted);
  font-size: 12px;
}

.composer-menu-group + .composer-menu-group {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--border-subtle);
}

.composer-menu-group-label {
  padding: 4px 8px 5px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  text-transform: uppercase;
}

.composer-menu-group-items {
  display: grid;
  gap: 2px;
}

.composer-menu-item {
  display: grid;
  grid-template-columns: minmax(0,1fr) auto;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 34px;
  padding: 7px 8px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  cursor: pointer;
}

.composer-menu-item:hover,
.composer-menu-item.active {
  border-color: var(--border-default);
  background: rgba(255,255,255,.055);
  color: var(--text-primary);
}

.composer-menu-item-main {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.composer-menu-item-label,
.composer-menu-item-detail {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.composer-menu-item-label {
  font-size: 12px;
  font-weight: 600;
}

.composer-menu-item-detail {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.composer-menu-item-kind {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.composer-primary-action,
.composer-stop-action {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-default);
  border-radius: 10px;
  background: rgba(255,255,255,.045);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  transition-property: background, border-color, color, transform;
  transition-duration: .14s;
}

.composer-primary-action:not(:disabled):hover,
.composer-stop-action:hover {
  border-color: var(--border-focus);
  background: rgba(255,255,255,.075);
}

.composer-primary-action:active,
.composer-stop-action:active {
  transform: scale(.96);
}

.composer-primary-action:disabled {
  cursor: not-allowed;
  opacity: .42;
}

.composer-stop-action {
  border-color: rgba(255,123,114,.35);
  background: rgba(255,123,114,.1);
  color: var(--color-error);
}
```

Add this inside the existing `@media (max-width: 720px)` block:

```css
  .composer-command-menu {
    bottom: calc(100% + 6px);
    max-height: min(280px, 46vh);
  }

  .composer-menu-item {
    grid-template-columns: minmax(0,1fr);
  }

  .composer-menu-item-kind {
    display: none;
  }
```

- [ ] **Step 4: Run CSS and full webapp tests**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/visual-language-css.test.mjs').then((m) => { m.runVisualLanguageCssTests(); console.log('visual language css checks passed'); })"
npm test
```

Expected:

- First command prints `visual language css checks passed`.
- `npm test` prints `frontend helper checks passed`.

- [ ] **Step 5: Commit Task 6**

Run from repo root:

```bash
git add src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs
git commit -m "style: add t3 composer command menu"
```

---

## Task 7: Composer Visual Debug Scenario And Fixture

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`
- Modify: `scripts/gui-visual-debug.mjs`

- [ ] **Step 1: Add failing visual fixture tests**

Modify imports in `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`:

```javascript
  buildComposerFileTreeFixtureAction,
```

Add this after the source control fixture assertions:

```javascript
  const composerAction = buildComposerFileTreeFixtureAction();
  assert.equal(composerAction.type, "visual_composer_file_tree_fixture_loaded");
  assert.equal(composerAction.nodes[0].path, "src");
  assert.equal(composerAction.nodes[0].children.some((node) => node.path === "src/parser.c"), true);
```

Add this call before `openDiffFixture` in the installed helper section:

```javascript
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadComposerFileTreeFixture();
```

Update the expected dispatched action type list:

```javascript
    [
      "visual_timeline_fixture_loaded",
      "visual_source_control_fixture_loaded",
      "visual_interaction_fixture_loaded",
      "visual_thread_lifecycle_fixture_loaded",
      "visual_composer_file_tree_fixture_loaded",
    ],
```

- [ ] **Step 2: Add failing visual runner tests**

Modify `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`:

```javascript
  assert.deepEqual(runner.parseScenarioList("composer"), ["composer"]);
  assert.deepEqual(runner.parseScenarioList("load,composer"), ["load", "composer"]);
  assert.deepEqual(runner.parseScenarioList("all"), ["app", "load", "chat", "composer", "diff", "file", "terminal", "responsive", "thread", "timeline", "interaction"]);
```

Add source assertions near the existing runner source assertions:

```javascript
  assert.equal(runnerSource.includes("runComposerScenario"), true);
  assert.equal(runnerSource.includes("loadComposerFileTreeFixture"), true);
  assert.equal(runnerSource.includes("composer-command-menu"), true);
  assert.equal(runnerSource.includes("composer-primary-action"), true);
  assert.equal(runnerSource.includes("@src/parser.c"), true);
```

- [ ] **Step 3: Run visual fixture and runner tests and verify they fail**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/visual-debug-fixtures.test.mjs').then((m) => { m.runVisualDebugFixturesTests(); console.log('visual debug fixture checks passed'); })"
node -e "import('./test/visual-debug-runner.test.mjs').then((m) => m.runVisualDebugRunnerTests().then(() => console.log('visual debug runner checks passed')))"
```

Expected:

- First command fails because `buildComposerFileTreeFixtureAction` is not exported.
- Second command fails because `composer` is not a known scenario.

- [ ] **Step 4: Add the composer file-tree visual fixture**

In `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`, add after `buildSourceControlFixtureAction()`:

```javascript
export function buildComposerFileTreeFixtureAction() {
  return {
    type: "visual_composer_file_tree_fixture_loaded",
    nodes: [
      {
        id: "src",
        path: "src",
        name: "src",
        kind: "dir",
        has_children: true,
        childrenLoaded: true,
        children: [
          { id: "src/main.c", path: "src/main.c", name: "main.c", kind: "file", has_children: false },
          { id: "src/parser.c", path: "src/parser.c", name: "parser.c", kind: "file", has_children: false },
          {
            id: "src/include",
            path: "src/include",
            name: "include",
            kind: "dir",
            has_children: true,
            childrenLoaded: true,
            children: [
              { id: "src/include/parser.h", path: "src/include/parser.h", name: "parser.h", kind: "file", has_children: false },
            ],
          },
        ],
      },
      { id: "README.md", path: "README.md", name: "README.md", kind: "file", has_children: false },
    ],
  };
}
```

In `installVisualDebugFixtures()`, add this helper after `loadSourceControlFixture()`:

```javascript
    loadComposerFileTreeFixture() {
      dispatch(buildComposerFileTreeFixtureAction());
    },
```

- [ ] **Step 5: Reduce the visual fixture into GUI state**

In `src/embedagent/frontend/gui/webapp/src/store.js`, add a reducer case near the other visual fixture cases:

```javascript
    case "visual_composer_file_tree_fixture_loaded":
      return {
        ...state,
        fileTree: Array.isArray(action.nodes) ? action.nodes : [],
        app: {
          ...state.app,
          bootstrapLoaded: true,
          hasActiveWorkspace: true,
          activeWorkspace: state.app.activeWorkspace || {
            id: "visual-debug-workspace",
            path: "D:/visual-debug",
            label: "visual-debug",
            exists: true,
            created_at: "",
            last_opened_at: "",
          },
          workspaceError: "",
          activatingWorkspace: false,
        },
      };
```

Add an assertion to `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` near the existing visual fixture reducer assertions:

```javascript
  const composerFixtureState = reducer(initialState, {
    type: "visual_composer_file_tree_fixture_loaded",
    nodes: [
      {
        id: "src",
        path: "src",
        name: "src",
        kind: "dir",
        childrenLoaded: true,
        children: [{ id: "src/parser.c", path: "src/parser.c", name: "parser.c", kind: "file" }],
      },
    ],
  });
  assert.equal(composerFixtureState.fileTree[0].children[0].path, "src/parser.c");
  assert.equal(composerFixtureState.app.hasActiveWorkspace, true);
```

- [ ] **Step 6: Add the composer visual runner scenario**

Modify `scripts/gui-visual-debug.mjs` scenario list:

```javascript
export const SCENARIOS = ["load", "chat", "composer", "diff", "file", "terminal", "responsive", "app", "thread", "timeline", "interaction"];
```

Update `runChatScenario()` to click the new composer primary action:

```javascript
  await page.click('[data-testid="composer-primary-action"]');
```

Add this helper near the scenario functions:

```javascript
async function composerMenuMetrics(page) {
  return await page.evaluate(() => {
    const menu = document.querySelector('[data-testid="composer-command-menu"]');
    const input = document.querySelector('[data-testid="composer-input"]');
    const menuBox = menu?.getBoundingClientRect();
    const inputBox = input?.getBoundingClientRect();
    return {
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      menu: menuBox ? {
        left: Math.round(menuBox.left),
        right: Math.round(menuBox.right),
        width: Math.round(menuBox.width),
        height: Math.round(menuBox.height),
      } : null,
      input: inputBox ? {
        left: Math.round(inputBox.left),
        right: Math.round(inputBox.right),
        width: Math.round(inputBox.width),
      } : null,
      activeItems: document.querySelectorAll(".composer-menu-item.active").length,
    };
  });
}

async function runComposerScenario(page, options, outputDir) {
  const viewports = parseViewportList(options.viewports);
  const results = [];
  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
    await page.evaluate(() => {
      window.__EMBEDAGENT_VISUAL_DEBUG__.loadComposerFileTreeFixture();
    });
    await page.waitForSelector('[data-testid="composer-input"]', { timeout: 10000 });
    const input = page.locator('[data-testid="composer-input"]');

    await input.fill("/di");
    await page.waitForSelector('[data-testid="composer-command-menu"]', { timeout: 10000 });
    await page.keyboard.press("ArrowDown");
    const slashMenuText = await page.locator('[data-testid="composer-command-menu"]').innerText();
    if (!slashMenuText.includes("/diff")) {
      throw new Error(`Composer slash menu did not show /diff at ${viewport.name}: ${slashMenuText}`);
    }
    const slashMetrics = await composerMenuMetrics(page);
    if (slashMetrics.documentWidth > slashMetrics.viewportWidth + 1) {
      throw new Error(`Composer slash menu caused horizontal overflow at ${viewport.name}: ${slashMetrics.documentWidth}`);
    }
    if (!slashMetrics.menu || slashMetrics.menu.left < 0 || slashMetrics.menu.right > slashMetrics.viewportWidth + 1) {
      throw new Error(`Composer slash menu escaped viewport at ${viewport.name}: ${JSON.stringify(slashMetrics.menu)}`);
    }
    if (slashMetrics.activeItems !== 1) {
      throw new Error(`Composer slash menu should have one active item at ${viewport.name}`);
    }
    await page.keyboard.press("Enter");
    const slashValue = await input.inputValue();
    if (!slashValue.startsWith("/diff ")) {
      throw new Error(`Composer slash selection did not insert /diff: ${slashValue}`);
    }

    await input.fill("@par");
    await page.waitForSelector('[data-testid="composer-command-menu"]', { timeout: 10000 });
    const pathMenuText = await page.locator('[data-testid="composer-command-menu"]').innerText();
    if (!pathMenuText.includes("src/parser.c")) {
      throw new Error(`Composer path menu did not show src/parser.c at ${viewport.name}: ${pathMenuText}`);
    }
    const pathMetrics = await composerMenuMetrics(page);
    if (pathMetrics.documentWidth > pathMetrics.viewportWidth + 1) {
      throw new Error(`Composer path menu caused horizontal overflow at ${viewport.name}: ${pathMetrics.documentWidth}`);
    }
    await page.keyboard.press("Enter");
    const pathValue = await input.inputValue();
    if (pathValue !== "@src/parser.c ") {
      throw new Error(`Composer path selection did not insert @src/parser.c: ${pathValue}`);
    }

    const screenshot = path.join(outputDir, `composer-${viewport.name}.png`);
    await page.screenshot({ path: screenshot, fullPage: false });
    results.push({
      name: viewport.name,
      slashMenu: slashMetrics,
      pathMenu: pathMetrics,
      slashValue,
      pathValue,
      screenshot,
    });
  }
  return { viewports: results };
}
```

Add scenario dispatch in `runScenarios()` after `chat`:

```javascript
      } else if (scenario === "composer") {
        results.composer = await runComposerScenario(page, options, outputDir);
```

Update `printHelp()` scenario text:

```text
  --scenario load|chat|composer|diff|file|terminal|responsive|app|thread|timeline|interaction|all
```

- [ ] **Step 7: Run visual fixture, runner, and full webapp tests**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/visual-debug-fixtures.test.mjs').then((m) => { m.runVisualDebugFixturesTests(); console.log('visual debug fixture checks passed'); })"
node -e "import('./test/visual-debug-runner.test.mjs').then((m) => m.runVisualDebugRunnerTests().then(() => console.log('visual debug runner checks passed')))"
npm test
```

Expected:

- First command prints `visual debug fixture checks passed`.
- Second command prints `visual debug runner checks passed`.
- `npm test` prints `frontend helper checks passed`.

- [ ] **Step 8: Commit Task 7**

Run from repo root:

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs scripts/gui-visual-debug.mjs
git commit -m "test: add composer visual debug scenario"
```

---

## Task 8: Build, Visual Verification, And Documentation

**Files:**

- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Run the webapp tests**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
npm test
```

Expected: `frontend helper checks passed`.

- [ ] **Step 2: Build the GUI static bundle**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
npm run build
```

Expected: build completes without errors and updates `src/embedagent/frontend/gui/static/`.

- [ ] **Step 3: Run visual debug checks**

Run from repo root:

```bash
node scripts/gui-visual-debug.mjs --scenario composer,chat,responsive --no-build --output "$env:TEMP\embedagent-t3-composer-command-menu" --viewports 1280x720,700x640,520x720
```

Expected:

- The summary JSON reports successful `composer`, `chat`, and `responsive` scenarios.
- Composer screenshots exist for `1280x720`, `700x640`, and `520x720`.
- The `composer` scenario confirms `/diff ` and `@src/parser.c ` insertion.
- No horizontal overflow errors are reported.

- [ ] **Step 4: Update development tracker**

Add an entry to `docs/development-tracker.md` in the active GUI/T3 parity section:

```markdown
- 2026-06-18: Added T3-style composer command menu and context path selection in the GUI app-shell. The composer now owns ranked slash command search, `@` file context insertion from loaded file-tree state, compact primary send/stop controls, and a dedicated visual debug scenario. Prompt submission remains plain text and no Agent Core, backend protocol, permission policy, transcript, workflow, provider, or source-control mutation semantics changed.
```

- [ ] **Step 5: Update design change log**

Add an entry to `docs/design-change-log.md`:

```markdown
## 2026-06-18 - T3 Composer Command Menu And Context Tokens

- Replaced the GUI composer inline slash hint list with a composer-owned T3-style grouped command menu.
- Added frontend-only trigger, slash-command ranking, and loaded-file path context projection helpers.
- Added compact composer primary send/stop controls and visual debug coverage for slash selection, `@` path context selection, keyboard navigation, and narrow viewport overflow.
- Kept submitted prompts as plain text and kept all changes inside the GUI app-shell/read-model boundary.
```

- [ ] **Step 6: Check for accidental Core/backend/source-control boundary leaks**

Run from repo root:

```bash
rg -n "PermissionPolicy|transcript|workflow_state|source-control mutation|git commit|git push|fetch\\(" src/embedagent/frontend/gui/webapp/src/composer src/embedagent/frontend/gui/webapp/src/components/composer src/embedagent/frontend/gui/webapp/src/components/Composer.jsx
```

Expected:

- No output for `PermissionPolicy`, `transcript`, `workflow_state`, `source-control mutation`, `git commit`, or `git push`.
- `fetch(` has no output from the composer helper/component paths.

- [ ] **Step 7: Check diff cleanliness**

Run from repo root:

```bash
git diff --check
git status --short
```

Expected:

- `git diff --check` prints no whitespace errors.
- `git status --short` shows only files changed by this slice.

- [ ] **Step 8: Commit Task 8**

Run from repo root:

```bash
git add src/embedagent/frontend/gui/static src/embedagent/frontend/gui/webapp docs/development-tracker.md docs/design-change-log.md scripts/gui-visual-debug.mjs
git commit -m "feat: add t3 composer command menu"
```

---

## Final Verification Checklist

Run from repo root after Task 8:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd D:/Claude-project/ccode-win7
node scripts/gui-visual-debug.mjs --scenario composer,chat,responsive --no-build --output "$env:TEMP\embedagent-t3-composer-command-menu" --viewports 1280x720,700x640,520x720
git diff --check
git status --short
```

Expected:

- `npm test` prints `frontend helper checks passed`.
- `npm run build` completes without errors.
- Visual debug summary reports successful `composer`, `chat`, and `responsive` scenarios.
- `git diff --check` prints no errors.
- `git status --short` is clean after the final commit.

## Self-Review Notes

- Spec coverage:
  - Composer-owned command menu: Tasks 4, 5, 6, 7.
  - Slash trigger/parser and ranked command search: Tasks 1, 2, 5.
  - File context trigger/search and text insertion: Tasks 1, 3, 5, 7.
  - Primary send/stop action visuals: Tasks 4, 5, 6.
  - Interaction panel and branch toolbar preserved: Task 5 source assertions.
  - Visual checks for keyboard and narrow layouts: Task 7.
  - No backend/Core/protocol/source-control mutation: constraints plus Tasks 4, 5, 8 boundary checks.
- Red-flag scan:
  - No deferred-work markers, empty implementation prompts, or undefined function references remain in the tasks.
- Type/signature consistency:
  - `detectComposerTrigger`, `composerTriggerKey`, `replaceComposerTrigger`, `buildComposerCommandItems`, `searchComposerCommandItems`, `groupComposerCommandItems`, `flattenComposerPathCandidates`, `searchComposerPathCandidates`, `groupComposerPathCandidates`, and `buildPathContextInsertion` are defined before `Composer.jsx` uses them.
  - `ComposerCommandMenu` props match the values passed from `Composer.jsx`.
  - `ComposerPrimaryActions` props match the values passed from `Composer.jsx`.
