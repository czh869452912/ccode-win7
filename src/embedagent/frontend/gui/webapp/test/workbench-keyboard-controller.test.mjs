import assert from "node:assert/strict";

import { createWorkbenchKeyboardController } from "../src/app-runtime/workbench-keyboard-controller.js";

function createWindowHarness() {
  const listeners = {};
  return {
    listeners,
    addEventListener(name, callback) {
      listeners[name] = callback;
    },
    removeEventListener(name, callback) {
      if (listeners[name] === callback) delete listeners[name];
    },
  };
}

function keyEvent(key, options = {}) {
  return {
    key,
    ctrlKey: Boolean(options.ctrlKey),
    metaKey: Boolean(options.metaKey),
    altKey: Boolean(options.altKey),
    shiftKey: Boolean(options.shiftKey),
    prevented: false,
    preventDefault() {
      this.prevented = true;
    },
  };
}

export function runWorkbenchKeyboardControllerTests() {
  const windowObject = createWindowHarness();
  const executedCommands = [];
  const cancelled = [];
  const resolverCalls = [];
  const documentObject = {
    activeElement: { dataset: { testid: "composer-input" } },
  };
  const controller = createWorkbenchKeyboardController({
    windowObject,
    documentObject,
    getKeybindings: () => [{ key: "mod+k", commandId: "palette.open", when: "composer" }],
    getCommandContext: () => ({
      paletteOpen: false,
      isRunning: true,
      capabilities: { commands: [] },
      appCapabilities: {},
    }),
    getCurrentStatus: () => "running",
    isTurnInterruptibleStatus: (status) => status === "running",
    cancelSession: () => cancelled.push("cancel"),
    executeWorkbenchCommand: (command) => executedCommands.push(command),
    resolveKeybinding: (bindings, key, context) => {
      resolverCalls.push({ bindings, key, context });
      return key === "mod+k" && context.composerFocused ? { id: "palette.open" } : null;
    },
  });

  const cleanup = controller.install();
  assert.equal(typeof windowObject.listeners.keydown, "function");

  const shortcutEvent = keyEvent("k", { ctrlKey: true });
  windowObject.listeners.keydown(shortcutEvent);
  assert.equal(shortcutEvent.prevented, true);
  assert.deepEqual(executedCommands, [{ id: "palette.open" }]);
  assert.equal(resolverCalls[0].context.composerFocused, true);

  const escapeEvent = keyEvent("Escape");
  windowObject.listeners.keydown(escapeEvent);
  assert.deepEqual(cancelled, ["cancel"]);

  cleanup();
  assert.equal(windowObject.listeners.keydown, undefined);
}
