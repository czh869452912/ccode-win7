import { eventToKey as defaultEventToKey, resolveKeybinding as defaultResolveKeybinding } from "../workbench/keybindings.js";

function defaultWindowObject() {
  return typeof window !== "undefined" ? window : null;
}

function composerFocused(documentObject) {
  return documentObject?.activeElement?.dataset?.testid === "composer-input";
}

export function createWorkbenchKeyboardController({
  windowObject,
  documentObject,
  getKeybindings,
  getCommandContext,
  getCurrentStatus,
  isTurnInterruptibleStatus,
  cancelSession,
  executeWorkbenchCommand,
  eventToKey = defaultEventToKey,
  resolveKeybinding = defaultResolveKeybinding,
} = {}) {
  const targetWindow = windowObject || defaultWindowObject();
  const readKeybindings = typeof getKeybindings === "function" ? getKeybindings : () => [];
  const readCommandContext =
    typeof getCommandContext === "function" ? getCommandContext : () => ({});
  const readCurrentStatus = typeof getCurrentStatus === "function" ? getCurrentStatus : () => "";
  const isInterruptible =
    typeof isTurnInterruptibleStatus === "function"
      ? isTurnInterruptibleStatus
      : () => false;

  function onKeyDown(event) {
    if (event.key === "Escape" && isInterruptible(readCurrentStatus())) {
      if (typeof cancelSession === "function") {
        void cancelSession();
      }
    }
    const context = {
      ...readCommandContext(),
      composerFocused: composerFocused(documentObject),
    };
    const command = resolveKeybinding(readKeybindings(), eventToKey(event), context);
    if (!command) return;
    event.preventDefault();
    if (typeof executeWorkbenchCommand === "function") {
      void executeWorkbenchCommand(command);
    }
  }

  function install() {
    if (!targetWindow || typeof targetWindow.addEventListener !== "function") {
      return () => {};
    }
    targetWindow.addEventListener("keydown", onKeyDown);
    return () => {
      targetWindow.removeEventListener("keydown", onKeyDown);
    };
  }

  return { install };
}
