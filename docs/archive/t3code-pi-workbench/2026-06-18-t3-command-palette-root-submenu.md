# T3 Command Palette Root And Submenu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the GUI command palette's flat command list with a T3 Code-style grouped root palette, submenu view, rich result rows, and keyboard execution for commands, recent sessions, and workspaces.

**Architecture:** This is a frontend-only GUI app-shell slice. A pure command-palette model projects existing workbench commands, sessions, workspaces, and keybindings into grouped item descriptors; React components render the modal and forward selected descriptors back to `App.jsx`, which keeps owning command/session/workspace execution.

**Tech Stack:** React 18, Vite static build, plain JavaScript ES modules, CSS in `styles.css`, Node-based webapp tests, Playwright visual debug runner.

---

## Constraints

- Do not touch Agent Core, backend routes, transcript reducers, permission policy, provider configuration, telemetry, source-control mutation, or workflow state.
- Preserve Windows 7 and offline deployment constraints. Do not add runtime dependencies.
- Keep browser code compatible with WebView2 109-era APIs. Use React state, refs, and CSS only.
- Use existing workbench command IDs and existing App callbacks. Do not invent a second command execution path.
- Keep palette state GUI-local. It must not write transcript history, workflow state, runtime reducers, permission state, provider config, or source-control checkpoints.
- Use official product vocabulary: `build`, `tasks`, `current_phase`, `discipline_profile`.

## File Structure

Create:

- `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`
  - Pure projection/search model for T3-like palette groups and rows.
  - Builds root groups from visible commands, recent sessions, workspaces, and command category submenu entries.
  - Builds submenu groups from command categories.
  - Formats command shortcuts from `DEFAULT_KEYBINDINGS`.
- `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPaletteResults.jsx`
  - Stateless grouped result renderer.
  - Renders rich rows, disabled rows, shortcut hints, metadata, and submenu chevrons.
- `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`
  - Behavior tests for model projection, ranking, malformed input handling, and active metadata.
- `src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs`
  - Static source tests for component boundaries, keyboard handling, App wiring, and Core isolation.

Modify:

- `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx`
  - Replace flat `visibleCommands(context)` filtering with model-driven root/submenu views.
  - Own local view state, highlighted index, keyboard handling, and row activation.
- `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Pass visible commands, sessions, current session id, workspaces, active workspace, keybindings, and callbacks into `CommandPalette`.
  - Add explicit `onSelectSession` and `onSelectWorkspace` callbacks that call existing `loadSession(sessionId)` and `activateWorkspace(workspaceId)`.
- `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Replace flat palette styling with grouped modal/result row styling.
  - Add mobile guardrails for rich metadata rows.
- `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Register new command palette tests and update static assertions.
- `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`
  - Assert grouped palette, submenu, shortcut, metadata, and mobile classes.
- `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`
  - Assert visual runner supports `palette` scenario.
- `scripts/gui-visual-debug.mjs`
  - Add `palette` scenario for root groups, submenu navigation, keyboard highlight, enter execution, and narrow viewport overflow.
- `docs/development-tracker.md`
- `docs/design-change-log.md`

---

## Task 1: Command Palette Model

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`
- Create: `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write the failing model tests**

Create `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`:

```javascript
import assert from "node:assert/strict";

import {
  buildCommandPaletteRootGroups,
  buildCommandPaletteSubmenuGroups,
  flattenPaletteGroups,
  formatPaletteShortcut,
  normalizePaletteQuery,
} from "../src/workbench/command-palette-model.js";

const commands = [
  { id: "session.new", group: "session", label: "New Session", slash: "/new", visibleWhen: "always" },
  { id: "surface.diff", group: "surface", label: "Open Diff", slash: "/diff", visibleWhen: "always", keywords: ["changes"] },
  { id: "mode.build", group: "mode", label: "Mode: Build", slash: "/mode build", visibleWhen: "has_session" },
  { id: "view.toggle_right_panel", group: "view", label: "Toggle Right Panel", slash: "", visibleWhen: "always" },
  { id: "workspace.refresh", group: "workspace", label: "Refresh Workspaces", slash: "", visibleWhen: "always", keywords: ["reload"] },
];

const sessions = [
  {
    session_id: "sess-active",
    thread: { title: "Fix parser recovery" },
    current_mode: "debug",
    updated_at: "2026-06-18T09:30:00.000Z",
  },
  {
    session_id: "sess-next",
    user_goal: "Verify diff rendering",
    current_mode: "verify",
    updated_at: "",
  },
  { session_id: "", user_goal: "ignored" },
  null,
];

const workspaces = [
  { id: "ws-active", label: "ccode-win7", path: "D:/Claude-project/ccode-win7", exists: true },
  { id: "ws-missing", label: "", path: "D:/missing/workspace", exists: false },
  { id: "", path: "ignored" },
];

const keybindings = [
  { key: "mod+k", commandId: "palette.open", when: "not_palette" },
  { key: "mod+3", commandId: "surface.diff", when: "always" },
  { key: "mod+b", commandId: "view.toggle_right_panel", when: "always" },
];

export function runCommandPaletteModelTests() {
  assert.equal(normalizePaletteQuery("  Diff  "), "diff");
  assert.equal(normalizePaletteQuery(null), "");
  assert.equal(formatPaletteShortcut("mod+3"), "Ctrl+3");
  assert.equal(formatPaletteShortcut("mod+shift+p"), "Ctrl+Shift+P");

  const root = buildCommandPaletteRootGroups({
    commands,
    sessions,
    currentSessionId: "sess-active",
    workspaces,
    activeWorkspaceId: "ws-active",
    keybindings,
    query: "",
  });

  assert.deepEqual(root.map((group) => group.id), ["commands", "sessions", "workspaces"]);

  const commandItems = root.find((group) => group.id === "commands").items;
  assert.equal(commandItems.some((item) => item.type === "submenu" && item.id === "submenu:surface"), true);
  assert.equal(commandItems.some((item) => item.type === "command" && item.commandId === "surface.diff"), true);
  assert.equal(
    commandItems.find((item) => item.commandId === "surface.diff").shortcut,
    "Ctrl+3",
  );
  assert.equal(
    commandItems.find((item) => item.id === "submenu:surface").trailing,
    "1",
  );

  const sessionItems = root.find((group) => group.id === "sessions").items;
  assert.equal(sessionItems.length, 2);
  assert.equal(sessionItems[0].id, "session:sess-active");
  assert.equal(sessionItems[0].title, "Fix parser recovery");
  assert.equal(sessionItems[0].description, "debug");
  assert.equal(sessionItems[0].trailing, "Current");
  assert.equal(sessionItems[1].title, "Verify diff rendering");

  const workspaceItems = root.find((group) => group.id === "workspaces").items;
  assert.equal(workspaceItems.length, 2);
  assert.equal(workspaceItems[0].id, "workspace:ws-active");
  assert.equal(workspaceItems[0].trailing, "Current");
  assert.equal(workspaceItems[0].disabled, false);
  assert.equal(workspaceItems[1].title, "workspace");
  assert.equal(workspaceItems[1].description, "D:/missing/workspace");
  assert.equal(workspaceItems[1].trailing, "Missing");
  assert.equal(workspaceItems[1].disabled, true);

  const diffRoot = buildCommandPaletteRootGroups({
    commands,
    sessions,
    currentSessionId: "sess-active",
    workspaces,
    activeWorkspaceId: "ws-active",
    keybindings,
    query: "diff",
  });
  const diffItems = flattenPaletteGroups(diffRoot);
  assert.equal(diffItems.some((item) => item.commandId === "surface.diff"), true);
  assert.equal(diffItems.some((item) => item.id === "session:sess-next"), true);
  assert.equal(diffItems.some((item) => item.commandId === "session.new"), false);

  const submenu = buildCommandPaletteSubmenuGroups({
    commands,
    keybindings,
    groupId: "surface",
    query: "changes",
  });
  assert.deepEqual(submenu.map((group) => group.id), ["surface"]);
  assert.equal(submenu[0].title, "Surface");
  assert.equal(submenu[0].items.length, 1);
  assert.equal(submenu[0].items[0].commandId, "surface.diff");
  assert.equal(submenu[0].items[0].meta, "/diff");
  assert.equal(submenu[0].items[0].shortcut, "Ctrl+3");

  assert.deepEqual(buildCommandPaletteSubmenuGroups({ commands, groupId: "missing" }), []);
  assert.deepEqual(flattenPaletteGroups([{ id: "x", items: [{ id: "a" }, { id: "b" }] }]).map((item) => item.id), ["a", "b"]);
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` imports near the other webapp test imports:

```javascript
import { runCommandPaletteModelTests } from "./command-palette-model.test.mjs";
```

Call it near the workbench/app-shell tests:

```javascript
  runWorkbenchStateTests();
  runCommandPaletteModelTests();
```

- [ ] **Step 2: Run the model test and verify it fails**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
node -e "import('./test/command-palette-model.test.mjs').then((m) => { m.runCommandPaletteModelTests(); console.log('command palette model checks passed'); })"
```

Expected: fail with `ERR_MODULE_NOT_FOUND` for `src/workbench/command-palette-model.js`.

- [ ] **Step 3: Implement the model helper**

Create `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`:

```javascript
const ROOT_COMMAND_LIMIT = 8;
const RECENT_SESSION_LIMIT = 12;

const GROUP_TITLES = {
  app: "App",
  session: "Sessions",
  message: "Message",
  mode: "Mode",
  surface: "Surface",
  workspace: "Workspace",
  workflow: "Workflow",
  view: "View",
};

const GROUP_DESCRIPTIONS = {
  app: "App shell commands",
  session: "Create, refresh, and resume threads",
  message: "Send or stop the current turn",
  mode: "Switch the active agent mode",
  surface: "Open workbench surfaces",
  workspace: "Open or refresh local workspaces",
  workflow: "Run workflow views",
  view: "Toggle workbench layout",
};

function asText(value) {
  return String(value || "").trim();
}

function basename(path) {
  const text = asText(path).replace(/\\/g, "/");
  const parts = text.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : text;
}

function titleCase(value) {
  const text = asText(value);
  if (!text) return "";
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function normalizePaletteQuery(query) {
  return asText(query).toLowerCase();
}

export function formatPaletteShortcut(key) {
  const text = asText(key);
  if (!text) return "";
  return text
    .split("+")
    .filter(Boolean)
    .map((part) => {
      if (part === "mod") return "Ctrl";
      if (part === "ctrl") return "Ctrl";
      if (part === "alt") return "Alt";
      if (part === "shift") return "Shift";
      if (part === "escape") return "Esc";
      return part.length === 1 ? part.toUpperCase() : titleCase(part);
    })
    .join("+");
}

function shortcutByCommandId(keybindings = []) {
  const result = {};
  for (const binding of keybindings || []) {
    const commandId = asText(binding && binding.commandId);
    if (!commandId || result[commandId]) continue;
    const formatted = formatPaletteShortcut(binding.key);
    if (formatted) result[commandId] = formatted;
  }
  return result;
}

function commandDescription(command = {}) {
  if (command.slash) return command.slash;
  if (command.surface) return `Open ${command.surface}`;
  if (command.drawer) return `Open ${command.drawer}`;
  return GROUP_DESCRIPTIONS[command.group] || command.id;
}

function searchableText(item = {}) {
  return [
    item.title,
    item.description,
    item.meta,
    item.trailing,
    item.group,
    item.commandId,
    item.sessionId,
    item.workspaceId,
    ...(item.searchTerms || []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function rankItem(item, query) {
  const normalized = normalizePaletteQuery(query);
  if (!normalized) return 1;
  const title = asText(item.title).toLowerCase();
  const meta = asText(item.meta).toLowerCase();
  const text = searchableText(item);
  if (title === normalized || meta === normalized) return 100;
  if (title.startsWith(normalized) || meta.startsWith(normalized)) return 80;
  if (text.split(/\s+/).some((part) => part.startsWith(normalized))) return 60;
  if (text.includes(normalized)) return 40;
  return 0;
}

function filterAndRank(items, query) {
  return (items || [])
    .map((item, index) => ({ item, index, score: rankItem(item, query) }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score || left.index - right.index)
    .map((entry) => entry.item);
}

function commandItem(command, shortcutMap) {
  const group = asText(command.group);
  return {
    id: `command:${command.id}`,
    type: "command",
    commandId: asText(command.id),
    group,
    title: asText(command.label) || asText(command.id),
    description: commandDescription(command),
    meta: asText(command.slash || command.id),
    shortcut: shortcutMap[command.id] || "",
    leading: titleCase(group).slice(0, 1) || ">",
    disabled: false,
    searchTerms: [asText(command.slash), ...(command.keywords || [])],
  };
}

function groupCommandItems(commands = [], shortcutMap = {}) {
  const groups = {};
  for (const command of commands || []) {
    if (!command || !command.id) continue;
    const group = asText(command.group) || "commands";
    if (!groups[group]) groups[group] = [];
    groups[group].push(commandItem(command, shortcutMap));
  }
  return groups;
}

function submenuItem(groupId, items) {
  const title = GROUP_TITLES[groupId] || titleCase(groupId);
  return {
    id: `submenu:${groupId}`,
    type: "submenu",
    submenuId: groupId,
    group: groupId,
    title,
    description: GROUP_DESCRIPTIONS[groupId] || `${title} commands`,
    meta: "Commands",
    trailing: String(items.length),
    leading: title.slice(0, 1) || ">",
    disabled: items.length === 0,
    searchTerms: [groupId, title],
  };
}

function sessionTitle(session) {
  const sessionId = asText(session && (session.session_id || session.id));
  return (
    asText(session && session.thread && session.thread.title)
    || asText(session && session.title)
    || asText(session && session.user_goal)
    || asText(session && session.summary_text)
    || `Session ${sessionId.slice(0, 8)}`
  );
}

function sessionItems(sessions = [], currentSessionId = "") {
  return (Array.isArray(sessions) ? sessions : [])
    .filter((session) => session && asText(session.session_id || session.id))
    .slice(0, RECENT_SESSION_LIMIT)
    .map((session) => {
      const sessionId = asText(session.session_id || session.id);
      const mode = asText(session.current_mode || session.mode || "explore");
      const updated = asText(session.updated_at || session.created_at);
      return {
        id: `session:${sessionId}`,
        type: "session",
        sessionId,
        title: sessionTitle(session),
        description: mode,
        meta: updated,
        trailing: sessionId === currentSessionId ? "Current" : "",
        leading: "T",
        disabled: false,
        searchTerms: [sessionId, mode, updated],
      };
    });
}

function workspaceTitle(workspace) {
  return asText(workspace && workspace.label) || basename(workspace && workspace.path) || "Workspace";
}

function workspaceItems(workspaces = [], activeWorkspaceId = "") {
  return (Array.isArray(workspaces) ? workspaces : [])
    .filter((workspace) => workspace && asText(workspace.id))
    .map((workspace) => {
      const workspaceId = asText(workspace.id);
      const exists = workspace.exists !== false;
      return {
        id: `workspace:${workspaceId}`,
        type: "workspace",
        workspaceId,
        title: workspaceTitle(workspace),
        description: asText(workspace.path),
        meta: "Workspace",
        trailing: workspaceId === activeWorkspaceId ? "Current" : exists ? "" : "Missing",
        leading: "W",
        disabled: !exists,
        searchTerms: [workspaceId, workspace.path, workspace.label],
      };
    });
}

function nonEmptyGroup(id, title, items) {
  return items.length > 0 ? { id, title, items } : null;
}

export function buildCommandPaletteRootGroups({
  commands = [],
  sessions = [],
  currentSessionId = "",
  workspaces = [],
  activeWorkspaceId = "",
  keybindings = [],
  query = "",
} = {}) {
  const shortcutMap = shortcutByCommandId(keybindings);
  const commandGroups = groupCommandItems(commands, shortcutMap);
  const submenuItems = Object.keys(commandGroups)
    .sort()
    .map((groupId) => submenuItem(groupId, commandGroups[groupId]));
  const allCommandItems = Object.keys(commandGroups)
    .sort()
    .reduce((items, groupId) => items.concat(commandGroups[groupId]), []);
  const commandRootItems = filterAndRank(submenuItems.concat(allCommandItems), query).slice(0, ROOT_COMMAND_LIMIT);
  const groups = [
    nonEmptyGroup("commands", "Commands", commandRootItems),
    nonEmptyGroup("sessions", "Sessions", filterAndRank(sessionItems(sessions, currentSessionId), query)),
    nonEmptyGroup("workspaces", "Workspaces", filterAndRank(workspaceItems(workspaces, activeWorkspaceId), query)),
  ];
  return groups.filter(Boolean);
}

export function buildCommandPaletteSubmenuGroups({
  commands = [],
  keybindings = [],
  groupId = "",
  query = "",
} = {}) {
  const targetGroup = asText(groupId);
  if (!targetGroup) return [];
  const shortcutMap = shortcutByCommandId(keybindings);
  const items = (commands || [])
    .filter((command) => command && asText(command.group) === targetGroup)
    .map((command) => commandItem(command, shortcutMap));
  const ranked = filterAndRank(items, query);
  const title = GROUP_TITLES[targetGroup] || titleCase(targetGroup);
  return ranked.length > 0 ? [{ id: targetGroup, title, items: ranked }] : [];
}

export function flattenPaletteGroups(groups = []) {
  return (groups || []).reduce((items, group) => items.concat(group.items || []), []);
}
```

- [ ] **Step 4: Run the focused model test and verify it passes**

Run:

```bash
node -e "import('./test/command-palette-model.test.mjs').then((m) => { m.runCommandPaletteModelTests(); console.log('command palette model checks passed'); })"
```

Expected: prints `command palette model checks passed`.

- [ ] **Step 5: Run full webapp tests**

Run:

```bash
npm test
```

Expected: `frontend helper checks passed`.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat: add command palette model"
```

---

## Task 2: Results Renderer

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPaletteResults.jsx`
- Create: `src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write the failing component source tests**

Create `src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs`:

```javascript
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function sourcePath(...parts) {
  return path.join(WEBAPP_ROOT, "src", ...parts);
}

function readSource(...parts) {
  return fs.readFileSync(sourcePath(...parts), "utf8").replace(/\r\n?/g, "\n");
}

export function runCommandPaletteSourceTests() {
  const resultsSource = readSource("components", "workbench", "CommandPaletteResults.jsx");
  assert.equal(resultsSource.includes("export default function CommandPaletteResults"), true);
  assert.equal(resultsSource.includes("cmd-palette-group"), true);
  assert.equal(resultsSource.includes("cmd-palette-row"), true);
  assert.equal(resultsSource.includes("cmd-palette-row-shortcut"), true);
  assert.equal(resultsSource.includes("cmd-palette-row-chevron"), true);
  assert.equal(resultsSource.includes("aria-disabled"), true);
  assert.equal(resultsSource.includes("fetch("), false);
  assert.equal(resultsSource.includes("transcript"), false);
  assert.equal(resultsSource.includes("embedagent"), false);

  const paletteSource = readSource("components", "workbench", "CommandPalette.jsx");
  assert.equal(paletteSource.includes("CommandPaletteResults"), false);

  const modelSource = readSource("workbench", "command-palette-model.js");
  assert.equal(modelSource.includes("buildCommandPaletteRootGroups"), true);
  assert.equal(modelSource.includes("buildCommandPaletteSubmenuGroups"), true);
  assert.equal(modelSource.includes("fetch("), false);
  assert.equal(modelSource.includes("transcript"), false);
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` imports:

```javascript
import { runCommandPaletteSourceTests } from "./command-palette-source.test.mjs";
```

Call it after `runCommandPaletteModelTests()`:

```javascript
  runCommandPaletteModelTests();
  runCommandPaletteSourceTests();
```

- [ ] **Step 2: Run the component source test and verify it fails**

Run:

```bash
node -e "import('./test/command-palette-source.test.mjs').then((m) => { m.runCommandPaletteSourceTests(); console.log('command palette source checks passed'); })"
```

Expected: fail with `ENOENT` for `CommandPaletteResults.jsx`.

- [ ] **Step 3: Implement the grouped results renderer**

Create `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPaletteResults.jsx`:

```javascript
import React from "react";

function rowClassName(item, active) {
  const classes = ["cmd-palette-row"];
  if (active) classes.push("active");
  if (item.disabled) classes.push("disabled");
  if (item.type === "submenu") classes.push("has-submenu");
  return classes.join(" ");
}

function itemTestId(item) {
  if (item.type === "command") return `command-palette-command--${item.commandId}`;
  if (item.type === "session") return `command-palette-session--${item.sessionId}`;
  if (item.type === "workspace") return `command-palette-workspace--${item.workspaceId}`;
  if (item.type === "submenu") return `command-palette-submenu--${item.submenuId}`;
  return `command-palette-item--${item.id}`;
}

export default function CommandPaletteResults({
  groups = [],
  activeItemId = "",
  onHoverItem,
  onSelectItem,
  emptyLabel = "No matching commands, sessions, or workspaces",
}) {
  const hasItems = groups.some((group) => (group.items || []).length > 0);
  if (!hasItems) {
    return (
      <div className="cmd-palette-empty" data-testid="command-palette-empty">
        {emptyLabel}
      </div>
    );
  }
  return (
    <div className="cmd-palette-results" role="listbox" data-testid="command-palette-results">
      {groups.map((group) => (
        <section className="cmd-palette-group" key={group.id} data-testid={`command-palette-group--${group.id}`}>
          <div className="cmd-palette-group-title">{group.title}</div>
          <div className="cmd-palette-group-items">
            {(group.items || []).map((item) => {
              const active = item.id === activeItemId;
              return (
                <button
                  key={item.id}
                  type="button"
                  className={rowClassName(item, active)}
                  onMouseEnter={() => onHoverItem(item.id)}
                  onClick={() => {
                    if (!item.disabled) onSelectItem(item);
                  }}
                  disabled={Boolean(item.disabled)}
                  aria-disabled={Boolean(item.disabled)}
                  aria-selected={active}
                  role="option"
                  data-testid={itemTestId(item)}
                >
                  <span className="cmd-palette-row-leading" aria-hidden="true">
                    {item.leading || ">"}
                  </span>
                  <span className="cmd-palette-row-main">
                    <span className="cmd-palette-row-title">{item.title}</span>
                    <span className="cmd-palette-row-description">{item.description}</span>
                  </span>
                  <span className="cmd-palette-row-meta">
                    {item.shortcut ? <kbd className="cmd-palette-row-shortcut">{item.shortcut}</kbd> : null}
                    {item.trailing ? <span className="cmd-palette-row-trailing">{item.trailing}</span> : null}
                    {item.meta ? <span className="cmd-palette-row-id">{item.meta}</span> : null}
                    {item.type === "submenu" ? <span className="cmd-palette-row-chevron">›</span> : null}
                  </span>
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

- [ ] **Step 4: Run the focused source test and verify it passes**

Run:

```bash
node -e "import('./test/command-palette-source.test.mjs').then((m) => { m.runCommandPaletteSourceTests(); console.log('command palette source checks passed'); })"
```

Expected: prints `command palette source checks passed`.

- [ ] **Step 5: Run full webapp tests**

Run:

```bash
npm test
```

Expected: `frontend helper checks passed`.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPaletteResults.jsx src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat: render grouped command palette results"
```

---

## Task 3: Command Palette Root And Submenu Interaction

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Extend source tests for palette interaction**

Modify `src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs` inside `runCommandPaletteSourceTests()` after the existing `paletteSource` assertions:

```javascript
  assert.equal(paletteSource.includes("CommandPaletteResults"), true);
  assert.equal(paletteSource.includes("buildCommandPaletteRootGroups"), true);
  assert.equal(paletteSource.includes("buildCommandPaletteSubmenuGroups"), true);
  assert.equal(paletteSource.includes("flattenPaletteGroups"), true);
  assert.equal(paletteSource.includes("viewKind"), true);
  assert.equal(paletteSource.includes("submenuId"), true);
  assert.equal(paletteSource.includes("handleKeyDown"), true);
  assert.equal(paletteSource.includes('event.key === "ArrowDown"'), true);
  assert.equal(paletteSource.includes('event.key === "ArrowUp"'), true);
  assert.equal(paletteSource.includes('event.key === "Enter"'), true);
  assert.equal(paletteSource.includes('event.key === "Backspace"'), true);
  assert.equal(paletteSource.includes("activateItem"), true);
  assert.equal(paletteSource.includes("onSelectSession"), true);
  assert.equal(paletteSource.includes("onSelectWorkspace"), true);
  assert.equal(paletteSource.includes("visibleCommands"), false);
```

Keep the original assertion `assert.equal(paletteSource.includes("CommandPaletteResults"), false);` removed because it is replaced by the positive assertion above.

- [ ] **Step 2: Run the source test and verify it fails**

Run:

```bash
node -e "import('./test/command-palette-source.test.mjs').then((m) => { m.runCommandPaletteSourceTests(); console.log('command palette source checks passed'); })"
```

Expected: fail because `CommandPalette.jsx` has not imported `CommandPaletteResults` or model helpers yet.

- [ ] **Step 3: Implement model-driven palette interaction**

Replace `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx` with:

```javascript
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  buildCommandPaletteRootGroups,
  buildCommandPaletteSubmenuGroups,
  flattenPaletteGroups,
} from "../../workbench/command-palette-model.js";
import CommandPaletteResults from "./CommandPaletteResults.jsx";

function clampIndex(index, length) {
  if (length <= 0) return 0;
  return Math.max(0, Math.min(index, length - 1));
}

function firstEnabledIndex(items) {
  const index = (items || []).findIndex((item) => !item.disabled);
  return index < 0 ? 0 : index;
}

export default function CommandPalette({
  open,
  query,
  commands = [],
  sessions = [],
  currentSessionId = "",
  workspaces = [],
  activeWorkspaceId = "",
  keybindings = [],
  onQueryChange,
  onClose,
  onSelect,
  onSelectSession,
  onSelectWorkspace,
}) {
  const [viewKind, setViewKind] = useState("root");
  const [submenuId, setSubmenuId] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setViewKind("root");
    setSubmenuId("");
    setSelectedIndex(0);
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  const groups = useMemo(() => {
    if (viewKind === "submenu") {
      return buildCommandPaletteSubmenuGroups({
        commands,
        keybindings,
        groupId: submenuId,
        query,
      });
    }
    return buildCommandPaletteRootGroups({
      commands,
      sessions,
      currentSessionId,
      workspaces,
      activeWorkspaceId,
      keybindings,
      query,
    });
  }, [activeWorkspaceId, commands, currentSessionId, keybindings, query, sessions, submenuId, viewKind, workspaces]);

  const items = useMemo(() => flattenPaletteGroups(groups), [groups]);
  const activeIndex = clampIndex(selectedIndex, items.length);
  const activeItem = items[activeIndex] || null;
  const activeItemId = activeItem ? activeItem.id : "";

  useEffect(() => {
    setSelectedIndex(firstEnabledIndex(items));
  }, [items, viewKind]);

  if (!open) return null;

  function returnToRoot() {
    setViewKind("root");
    setSubmenuId("");
    onQueryChange("");
    setSelectedIndex(0);
  }

  function activateItem(item) {
    if (!item || item.disabled) return;
    if (item.type === "submenu") {
      setViewKind("submenu");
      setSubmenuId(item.submenuId);
      onQueryChange("");
      setSelectedIndex(0);
      return;
    }
    onClose();
    if (item.type === "command") {
      onSelect({ id: item.commandId });
    } else if (item.type === "session") {
      onSelectSession(item.sessionId);
    } else if (item.type === "workspace") {
      onSelectWorkspace(item.workspaceId);
    }
  }

  function moveSelection(delta) {
    if (items.length === 0) return;
    let next = activeIndex;
    for (let step = 0; step < items.length; step += 1) {
      next = (next + delta + items.length) % items.length;
      if (!items[next].disabled) {
        setSelectedIndex(next);
        return;
      }
    }
  }

  function handleKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveSelection(1);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveSelection(-1);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      activateItem(activeItem);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === "Backspace" && !query && viewKind === "submenu") {
      event.preventDefault();
      returnToRoot();
    }
  }

  const title = viewKind === "submenu" ? "Command group" : "Command palette";

  return (
    <div className="cmd-palette-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="cmd-palette"
        role="dialog"
        aria-label="Command palette"
        onMouseDown={(event) => event.stopPropagation()}
        data-testid="command-palette"
      >
        {viewKind === "submenu" ? (
          <div className="cmd-palette-submenu-header">
            <button type="button" className="cmd-palette-back" onClick={returnToRoot} data-testid="command-palette-back">
              ←
            </button>
            <span>{title}</span>
          </div>
        ) : null}
        <input
          ref={inputRef}
          className="cmd-palette-input"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
          aria-label="Command search"
          placeholder={viewKind === "submenu" ? "Search this group" : "Search commands, sessions, workspaces"}
          data-testid="command-palette-input"
        />
        <CommandPaletteResults
          groups={groups}
          activeItemId={activeItemId}
          onHoverItem={(id) => {
            const nextIndex = items.findIndex((item) => item.id === id);
            if (nextIndex >= 0) setSelectedIndex(nextIndex);
          }}
          onSelectItem={activateItem}
          emptyLabel={
            viewKind === "submenu"
              ? "No matching commands in this group"
              : "No matching commands, sessions, or workspaces"
          }
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run focused source tests and verify they pass**

Run:

```bash
node -e "import('./test/command-palette-source.test.mjs').then((m) => { m.runCommandPaletteSourceTests(); console.log('command palette source checks passed'); })"
```

Expected: prints `command palette source checks passed`.

- [ ] **Step 5: Run full webapp tests**

Run:

```bash
npm test
```

Expected: `frontend helper checks passed`.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs
git commit -m "feat: add command palette submenu interaction"
```

---

## Task 4: App Wiring For Commands, Sessions, And Workspaces

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing App wiring assertions**

Modify `src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs` inside `runCommandPaletteSourceTests()`:

```javascript
  const appSource = readSource("App.jsx");
  assert.equal(appSource.includes("paletteCommands"), true);
  assert.equal(appSource.includes("activeWorkspaceId"), true);
  assert.equal(appSource.includes("sessions={state.sessions}"), true);
  assert.equal(appSource.includes("currentSessionId={state.currentSessionId}"), true);
  assert.equal(appSource.includes("workspaces={state.app.workspaces}"), true);
  assert.equal(appSource.includes("keybindings={DEFAULT_KEYBINDINGS}"), true);
  assert.equal(appSource.includes("onSelectSession={(sessionId) =>"), true);
  assert.equal(appSource.includes("void loadSession(sessionId)"), true);
  assert.equal(appSource.includes("onSelectWorkspace={(workspaceId) =>"), true);
  assert.equal(appSource.includes("void activateWorkspace(workspaceId)"), true);
```

- [ ] **Step 2: Run the source test and verify it fails**

Run:

```bash
node -e "import('./test/command-palette-source.test.mjs').then((m) => { m.runCommandPaletteSourceTests(); console.log('command palette source checks passed'); })"
```

Expected: fail because `App.jsx` still passes only `context`, `selectedIndex`, and command-only callbacks.

- [ ] **Step 3: Wire App state and callbacks into the palette**

Modify `src/embedagent/frontend/gui/webapp/src/App.jsx` near `composerCommands`:

```javascript
  const paletteCommands = useMemo(() => visibleCommands(commandContext), [commandContext]);
  const composerCommands = paletteCommands;
  const activeWorkspaceId = state.app.activeWorkspace?.id || "";
```

Replace the `CommandPalette` props at the bottom with:

```javascript
    <CommandPalette
      open={state.workbench.commandPalette.open}
      query={state.workbench.commandPalette.query}
      commands={paletteCommands}
      sessions={state.sessions}
      currentSessionId={state.currentSessionId}
      workspaces={state.app.workspaces}
      activeWorkspaceId={activeWorkspaceId}
      keybindings={DEFAULT_KEYBINDINGS}
      onQueryChange={(query) => dispatch({ type: "workbench_command_palette_query_changed", query })}
      onClose={() => dispatch({ type: "workbench_command_palette_closed" })}
      onSelect={(command) => {
        dispatch({ type: "workbench_command_palette_closed" });
        void executeWorkbenchCommand(commandById(command.id));
      }}
      onSelectSession={(sessionId) => {
        dispatch({ type: "workbench_command_palette_closed" });
        void loadSession(sessionId);
      }}
      onSelectWorkspace={(workspaceId) => {
        dispatch({ type: "workbench_command_palette_closed" });
        void activateWorkspace(workspaceId);
      }}
    />
```

Remove the obsolete props `selectedIndex={...}` and `context={commandContext}` from the palette call.

- [ ] **Step 4: Run focused source tests and verify they pass**

Run:

```bash
node -e "import('./test/command-palette-source.test.mjs').then((m) => { m.runCommandPaletteSourceTests(); console.log('command palette source checks passed'); })"
```

Expected: prints `command palette source checks passed`.

- [ ] **Step 5: Run full webapp tests**

Run:

```bash
npm test
```

Expected: `frontend helper checks passed`.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs
git commit -m "feat: wire command palette app actions"
```

---

## Task 5: T3 Palette Visual Styling

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`

- [ ] **Step 1: Add failing CSS assertions**

Modify `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs` inside `runVisualLanguageCssTests()` near the existing palette/style assertions:

```javascript
  assertIncludes(styles, ".cmd-palette-results", "command palette should render grouped results");
  assertIncludes(styles, ".cmd-palette-group", "command palette should style groups");
  assertIncludes(styles, ".cmd-palette-group-title", "command palette should style group titles");
  assertIncludes(styles, ".cmd-palette-row", "command palette should style rich rows");
  assertIncludes(styles, ".cmd-palette-row-leading", "command palette should style leading markers");
  assertIncludes(styles, ".cmd-palette-row-description", "command palette should style row descriptions");
  assertIncludes(styles, ".cmd-palette-row-shortcut", "command palette should style shortcut hints");
  assertIncludes(styles, ".cmd-palette-row-chevron", "command palette should style submenu chevrons");
  assertIncludes(styles, ".cmd-palette-submenu-header", "command palette should style submenu header");
  assertIncludes(styles, ".cmd-palette-back", "command palette should style submenu back button");
  assertIncludes(styles, ".cmd-palette-row.disabled", "command palette should style disabled rows");
```

- [ ] **Step 2: Run CSS tests and verify they fail**

Run:

```bash
node -e "import('./test/visual-language-css.test.mjs').then((m) => { m.runVisualLanguageCssTests(); console.log('visual language css checks passed'); })"
```

Expected: fail because the grouped palette classes are not styled yet.

- [ ] **Step 3: Replace flat palette CSS with grouped T3-like rows**

In `src/embedagent/frontend/gui/webapp/src/styles.css`, replace the block from `.cmd-palette-backdrop` through `.cmd-palette-empty` with:

```css
.cmd-palette-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(1, 4, 9, 0.48);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 10vh var(--sp-3) var(--sp-3);
}

.cmd-palette {
  width: min(720px, calc(100vw - 32px));
  max-height: min(620px, calc(100vh - 72px));
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-default);
  border-radius: var(--r-md);
  background: var(--bg-default);
  box-shadow: 0 24px 72px rgba(0, 0, 0, 0.46);
  overflow: hidden;
}

.cmd-palette-submenu-header {
  min-height: 36px;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  border-bottom: 1px solid var(--border-default);
  padding: 0 var(--sp-2);
  color: var(--text-muted);
  font-size: 12px;
}

.cmd-palette-back {
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.cmd-palette-back:hover {
  border-color: var(--border-default);
  background: var(--bg-subtle);
  color: var(--text-primary);
}

.cmd-palette-input {
  height: 46px;
  flex: 0 0 auto;
  border: 0;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-default);
  color: var(--text-primary);
  padding: 0 var(--sp-3);
  font-size: 14px;
  outline: none;
}

.cmd-palette-results {
  overflow: auto;
  padding: var(--sp-2);
}

.cmd-palette-group + .cmd-palette-group {
  margin-top: var(--sp-2);
}

.cmd-palette-group-title {
  padding: var(--sp-1) var(--sp-2);
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.cmd-palette-group-items {
  display: grid;
  gap: 2px;
}

.cmd-palette-row {
  width: 100%;
  min-height: 48px;
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  gap: var(--sp-2);
  align-items: center;
  border: 1px solid transparent;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text-primary);
  padding: var(--sp-2);
  text-align: left;
  cursor: pointer;
}

.cmd-palette-row:hover,
.cmd-palette-row.active {
  border-color: var(--border-focus);
  background: var(--bg-subtle);
}

.cmd-palette-row.disabled {
  color: var(--text-muted);
  cursor: default;
  opacity: 0.58;
}

.cmd-palette-row-leading {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  background: var(--bg-panel);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 700;
}

.cmd-palette-row-main {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.cmd-palette-row-title,
.cmd-palette-row-description,
.cmd-palette-row-id,
.cmd-palette-row-trailing {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cmd-palette-row-title {
  font-size: 13px;
  color: var(--text-primary);
}

.cmd-palette-row-description {
  font-size: 11px;
  color: var(--text-muted);
}

.cmd-palette-row-meta {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--sp-2);
  color: var(--text-muted);
  font-size: 10px;
}

.cmd-palette-row-shortcut {
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  background: var(--bg-panel);
  color: var(--text-secondary);
  padding: 2px 5px;
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1.2;
}

.cmd-palette-row-id {
  max-width: 150px;
  font-family: var(--font-mono);
}

.cmd-palette-row-chevron {
  color: var(--text-secondary);
  font-size: 18px;
  line-height: 1;
}

.cmd-palette-empty {
  color: var(--text-muted);
  padding: var(--sp-4);
  font-family: var(--font-mono);
  font-size: 11px;
}
```

Add this inside the existing `@media (max-width: 720px)` block:

```css
  .cmd-palette {
    width: calc(100vw - 20px);
    max-height: calc(100vh - 48px);
  }

  .cmd-palette-row {
    grid-template-columns: 24px minmax(0, 1fr);
  }

  .cmd-palette-row-meta {
    grid-column: 2;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
```

- [ ] **Step 4: Run focused CSS tests and verify they pass**

Run:

```bash
node -e "import('./test/visual-language-css.test.mjs').then((m) => { m.runVisualLanguageCssTests(); console.log('visual language css checks passed'); })"
```

Expected: prints `visual language css checks passed`.

- [ ] **Step 5: Run full webapp tests**

Run:

```bash
npm test
```

Expected: `frontend helper checks passed`.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs
git commit -m "style: polish command palette groups"
```

---

## Task 6: Visual Debug Palette Scenario

**Files:**

- Modify: `scripts/gui-visual-debug.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`

- [ ] **Step 1: Add failing visual runner assertions**

Modify `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`:

Replace the `all` scenario assertion with:

```javascript
  assert.deepEqual(runner.parseScenarioList("all"), ["app", "load", "chat", "composer", "palette", "diff", "file", "terminal", "responsive", "thread", "timeline", "interaction"]);
```

Add near the other scenario parser assertions:

```javascript
  assert.deepEqual(runner.parseScenarioList("palette"), ["palette"]);
  assert.deepEqual(runner.parseScenarioList("load,palette"), ["load", "palette"]);
```

Add near the other `runnerSource.includes(...)` assertions:

```javascript
  assert.equal(runnerSource.includes('"palette"'), true);
  assert.equal(runnerSource.includes("runPaletteScenario"), true);
  assert.equal(runnerSource.includes("command-palette-group--commands"), true);
  assert.equal(runnerSource.includes("command-palette-submenu--surface"), true);
  assert.equal(runnerSource.includes("command-palette-command--surface.diff"), true);
  assert.equal(runnerSource.includes("command-palette-session--"), true);
  assert.equal(runnerSource.includes("command-palette-workspace--"), true);
```

- [ ] **Step 2: Run visual runner tests and verify they fail**

Run:

```bash
node -e "import('./test/visual-debug-runner.test.mjs').then((m) => m.runVisualDebugRunnerTests().then(() => console.log('visual debug runner checks passed')))"
```

Expected: fail because `palette` is not in `SCENARIOS` and `runPaletteScenario` does not exist.

- [ ] **Step 3: Implement palette visual scenario**

Modify the `SCENARIOS` constant near the top of `scripts/gui-visual-debug.mjs`:

```javascript
const SCENARIOS = ["app", "load", "chat", "composer", "palette", "diff", "file", "terminal", "responsive", "thread", "timeline", "interaction"];
```

Add this function after `runComposerScenario`:

```javascript
async function runPaletteScenario(page, options, outputDir) {
  const viewports = parseViewportList(options.viewports);
  const results = [];
  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.waitForSelector('[data-testid="workbench-layout"]', { timeout: 10000 });
    await page.waitForSelector('[data-testid="command-palette-input"]', { state: "detached", timeout: 1000 }).catch(() => {});

    await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
    await page.waitForSelector('[data-testid="command-palette"]', { timeout: 10000 });
    await page.waitForSelector('[data-testid="command-palette-group--commands"]', { timeout: 10000 });
    await page.waitForSelector('[data-testid^="command-palette-session--"]', { timeout: 10000 });
    await page.waitForSelector('[data-testid^="command-palette-workspace--"]', { timeout: 10000 });

    const rootText = await page.locator('[data-testid="command-palette"]').innerText();
    if (!rootText.includes("Commands") || !rootText.includes("Sessions") || !rootText.includes("Workspaces")) {
      throw new Error(`Palette root groups missing at ${viewport.name}: ${rootText}`);
    }

    const surfaceSubmenu = page.locator('[data-testid="command-palette-submenu--surface"]').first();
    await surfaceSubmenu.click();
    await page.waitForSelector('[data-testid="command-palette-back"]', { timeout: 10000 });
    await page.fill('[data-testid="command-palette-input"]', "diff");
    await page.waitForSelector('[data-testid="command-palette-command--surface.diff"]', { timeout: 10000 });

    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await page.waitForSelector('[data-testid="right-panel-surface-tab--diff"]', { timeout: 10000 });
    const noOverlap = await assertNoOverlap(page);
    if (!noOverlap) throw new Error(`Palette scenario overlapped layout at ${viewport.name}`);

    const screenshotPath = path.join(outputDir, `palette-${viewport.name}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    results.push({ viewport: viewport.name, noOverlap, screenshot: screenshotPath });
  }
  return { viewports: results };
}
```

Modify the scenario dispatch in `runScenarios`:

```javascript
      } else if (scenario === "palette") {
        results.palette = await runPaletteScenario(page, options, outputDir);
```

Place it after the `composer` branch and before `diff`.

- [ ] **Step 4: Run focused visual runner tests and verify they pass**

Run:

```bash
node -e "import('./test/visual-debug-runner.test.mjs').then((m) => m.runVisualDebugRunnerTests().then(() => console.log('visual debug runner checks passed')))"
```

Expected: prints `visual debug runner checks passed`.

- [ ] **Step 5: Run full webapp tests**

Run:

```bash
npm test
```

Expected: `frontend helper checks passed`.

- [ ] **Step 6: Commit Task 6**

Run:

```bash
git add scripts/gui-visual-debug.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs
git commit -m "test: add command palette visual scenario"
```

---

## Task 7: Docs And Full Verification

**Files:**

- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Add development tracker entry**

Add a dated entry to `docs/development-tracker.md`:

```markdown
### 2026-06-18 - T3 command palette root/submenu parity

- Added a GUI-local command palette model that projects visible commands, recent sessions, workspaces, and keybindings into grouped T3-like palette rows.
- Replaced the flat command palette with root/submenu views, rich rows, keyboard navigation, command/session/workspace execution callbacks, and visual debug coverage.
- Preserved Agent Core boundaries: the palette remains app-shell presentation state and does not write transcript, workflow, permission, provider, runtime reducer, telemetry, or source-control truth.
```

- [ ] **Step 2: Add design change log entry**

Add a dated entry to `docs/design-change-log.md`:

```markdown
### 2026-06-18 - T3 command palette root/submenu parity

- Copied T3 Code's command palette interaction shape into the GUI app-shell: grouped root results, command category submenu, rich metadata rows, shortcut hints, and keyboard-owned execution.
- Session and workspace rows route only through existing `App.jsx` callbacks (`loadSession` and `activateWorkspace`); command rows keep using existing workbench command IDs.
- No Agent Core, backend, transcript, workflow, permission, provider, telemetry, source-control, or runtime reducer contracts changed.
```

- [ ] **Step 3: Run full webapp tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: `frontend helper checks passed`.

- [ ] **Step 4: Run production build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: Vite build completes without errors.

- [ ] **Step 5: Run visual verification**

Run from the repository root:

```bash
node scripts/gui-visual-debug.mjs --scenario palette,chat,responsive --no-build --output "$env:TEMP\embedagent-t3-command-palette" --viewports 1280x720,700x640,520x720
```

Expected:

- Scenario summary includes `palette`, `chat`, and `responsive`.
- `console.count` is `0` or only contains known benign browser messages.
- Palette screenshots exist for all three viewports.
- No overlap error is thrown.

- [ ] **Step 6: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code `0`.

- [ ] **Step 7: Commit docs and final verification record**

Run:

```bash
git add docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: record command palette parity"
```

---

## Final Review Checklist

- [ ] `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js` contains no React, `fetch`, backend imports, Core imports, transcript references, or side effects.
- [ ] `CommandPalette.jsx` no longer imports `visibleCommands`; App passes already-visible commands.
- [ ] Command rows execute through existing `executeWorkbenchCommand(commandById(command.id))`.
- [ ] Session rows execute through existing `loadSession(sessionId)`.
- [ ] Workspace rows execute through existing `activateWorkspace(workspaceId)`.
- [ ] Empty root and submenu states render stable text.
- [ ] Disabled/missing workspaces do not call callbacks.
- [ ] `npm test`, `npm run build`, visual debug, and `git diff --check` passed after the final code changes.
