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
  { id: "surface.preview", group: "surface", label: "Open Preview", slash: "/preview", visibleWhen: "always", keywords: ["browser", "localhost"] },
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
  { key: "mod+4", commandId: "surface.preview", when: "always" },
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
  assert.equal(commandItems.some((item) => item.type === "command" && item.commandId === "surface.preview"), true);
  assert.equal(
    commandItems.find((item) => item.commandId === "surface.preview").shortcut,
    "Ctrl+4",
  );
  assert.equal(
    commandItems.find((item) => item.id === "submenu:surface").trailing,
    "2",
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
    query: "browser",
  });
  assert.deepEqual(submenu.map((group) => group.id), ["surface"]);
  assert.equal(submenu[0].title, "Surface");
  assert.equal(submenu[0].items.length, 1);
  assert.equal(submenu[0].items[0].commandId, "surface.preview");
  assert.equal(submenu[0].items[0].meta, "/preview");
  assert.equal(submenu[0].items[0].shortcut, "Ctrl+4");

  assert.deepEqual(buildCommandPaletteSubmenuGroups({ commands, groupId: "missing" }), []);
  assert.deepEqual(flattenPaletteGroups([{ id: "x", items: [{ id: "a" }, { id: "b" }] }]).map((item) => item.id), ["a", "b"]);
}
