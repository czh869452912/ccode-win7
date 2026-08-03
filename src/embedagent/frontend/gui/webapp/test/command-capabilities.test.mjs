import assert from "node:assert/strict";

import {
  buildComposerCommandsFromCapabilities,
  normalizeCommandCapabilities,
} from "../src/session-runtime/command-capabilities.js";
import {
  capabilitySnapshot,
  commandDescriptor,
  modeDescriptor,
} from "./protocol-fixtures.mjs";

export function runCommandCapabilitiesTests() {
  const capabilities = normalizeCommandCapabilities(capabilitySnapshot({
    commands: [
      commandDescriptor("resources", "/resources [reload]", {
        summary: "Reload resources",
        source_type: "builtin",
        source_id: "slash_commands",
      }),
      commandDescriptor("skill:code-review", "/skill:code-review [args]", {
        summary: "Review local C changes",
        source_type: "builtin",
        source_id: "slash_commands",
      }),
    ],
  }));

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
  const appShellGroupedCommands = buildComposerCommandsFromCapabilities(capabilities, {
    defaultGroupId: "action",
  });
  assert.equal(appShellGroupedCommands[0].group, "command");

  const protocolCapabilities = normalizeCommandCapabilities(capabilitySnapshot({
    modes: [modeDescriptor("python-build", "Python Build")],
    commands: [
      commandDescriptor("help", "/help", {
        dispatch: { kind: "session.command", command: "/help" },
      }),
    ],
  }));
  assert.equal(protocolCapabilities.commands[0].usage, "/help");
  assert.equal(protocolCapabilities.commands[0].name, "help");
  assert.equal(buildComposerCommandsFromCapabilities(protocolCapabilities)[0].insertion, "/help ");
  assert.equal(protocolCapabilities.commands[0].group, "command");
  assert.equal(protocolCapabilities.modes[0].id, "python-build");
  assert.equal(protocolCapabilities.commands.some((item) => item.id === "mode.python-build"), true);
  assert.equal(
    protocolCapabilities.commands.find((item) => item.id === "mode.python-build").slash,
    "/mode python-build",
  );
}
