import { commandById } from "./commands.js";

function normalizeKeyName(key) {
  const value = String(key || "").toLowerCase();
  if (value === " ") return "space";
  if (value === "esc") return "escape";
  if (value === "control") return "ctrl";
  return value;
}

export function eventToKey(event) {
  const parts = [];
  if (event.ctrlKey || event.metaKey) parts.push("mod");
  if (event.altKey) parts.push("alt");
  if (event.shiftKey) parts.push("shift");
  parts.push(normalizeKeyName(event.key));
  return parts.join("+");
}

function matchesWhen(rule, context) {
  const view = context || {};
  switch (rule || "always") {
    case "always":
      return true;
    case "palette":
      return Boolean(view.paletteOpen);
    case "not_palette":
      return !view.paletteOpen;
    case "running":
      return Boolean(view.isRunning);
    case "composer":
      return Boolean(view.composerFocused);
    default:
      return false;
  }
}

export function resolveKeybinding(bindings, key, context) {
  const view = context || {};
  const normalizedKey = String(key || "").toLowerCase();
  const match = (bindings || []).find(
    (binding) => binding.key === normalizedKey && matchesWhen(binding.when, view),
  );
  if (!match) return null;
  return commandById(
    match.commandId,
    view.capabilities || view.sessionCapabilities || {},
    view.appCapabilities || null,
  );
}
