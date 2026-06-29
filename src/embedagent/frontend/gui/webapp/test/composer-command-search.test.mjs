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
  { id: "resources", group: "command", label: "/resources [reload]", slash: "/resources [reload]", insertion: "/resources ", visibleWhen: "always" },
  { id: "message.stop", group: "message", label: "Stop Running Turn", slash: "", visibleWhen: "running" },
];

export function runComposerCommandSearchTests() {
  const items = buildComposerCommandItems(COMMANDS);
  assert.deepEqual(
    items.map((item) => item.id),
    ["slash:session.resume", "slash:surface.diff", "slash:mode.build", "slash:mode.debug", "slash:resources"],
  );
  assert.equal(items[1].insertion, "/diff ");
  assert.equal(items[1].detail, "/diff");
  assert.equal(items[1].type, "slash-command");
  assert.equal(items[4].detail, "/resources [reload]");
  assert.equal(items[4].insertion, "/resources ");

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
