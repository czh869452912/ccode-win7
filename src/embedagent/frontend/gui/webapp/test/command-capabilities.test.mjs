import assert from "node:assert/strict";

import {
  buildComposerCommandsFromCapabilities,
  normalizeCommandCapabilities,
} from "../src/session-runtime/command-capabilities.js";

export function runCommandCapabilitiesTests() {
  const capabilities = normalizeCommandCapabilities({
    commands: [
      {
        name: "resources",
        usage: "/resources [reload]",
        summary: "Reload resources",
        source_type: "builtin",
        source_id: "slash_commands",
        active: true,
      },
      {
        name: "skill:code-review",
        usage: "/skill:code-review [args]",
        summary: "Review local C changes",
        source_type: "builtin",
        source_id: "slash_commands",
        active: true,
      },
      {
        name: "hidden",
        usage: "/hidden",
        summary: "Inactive",
        active: false,
      },
      {
        name: "",
        usage: "/bad",
        active: true,
      },
    ],
  });

  assert.deepEqual(
    capabilities.commands.map((item) => item.usage),
    ["/resources [reload]", "/skill:code-review [args]"],
  );

  const commands = buildComposerCommandsFromCapabilities(capabilities);
  assert.deepEqual(
    commands.map((item) => item.slash),
    ["/resources [reload]", "/skill:code-review [args]"],
  );
  assert.equal(commands[0].id, "backend-command:resources");
  assert.equal(commands[0].group, "command");
  assert.equal(commands[0].label, "/resources [reload]");
  assert.equal(commands[0].insertion, "/resources ");
  assert.equal(commands[1].insertion, "/skill:code-review ");
  assert.deepEqual(commands[1].keywords, ["skill:code-review", "Review local C changes"]);

  const protocolCapabilities = normalizeCommandCapabilities({
    commands: [
      {
        id: "help",
        label: "/help",
        group: "command",
        dispatch: { kind: "slash", command: "help" },
        active: true,
      },
    ],
  });
  assert.equal(protocolCapabilities.commands[0].usage, "/help");
  assert.equal(protocolCapabilities.commands[0].name, "help");
  assert.equal(buildComposerCommandsFromCapabilities(protocolCapabilities)[0].insertion, "/help ");
}
