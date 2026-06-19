import { commandById } from "./commands.js";

export const DEFAULT_KEYBINDINGS = [
  { key: "mod+k", commandId: "palette.open", when: "not_palette" },
  { key: "escape", commandId: "palette.close", when: "palette" },
  { key: "escape", commandId: "message.stop", when: "running" },
  { key: "mod+b", commandId: "view.toggle_right_panel", when: "always" },
  { key: "mod+,", commandId: "app.settings", when: "always" },
  { key: "mod+j", commandId: "view.toggle_bottom_drawer", when: "always" },
  { key: "mod+1", commandId: "surface.files", when: "always" },
  { key: "mod+2", commandId: "surface.terminal", when: "always" },
  { key: "mod+3", commandId: "surface.diff", when: "always" },
  { key: "mod+4", commandId: "surface.preview", when: "always" },
  { key: "mod+enter", commandId: "message.send", when: "composer" },
];

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
  const normalizedKey = String(key || "").toLowerCase();
  const match = (bindings || []).find(
    (binding) => binding.key === normalizedKey && matchesWhen(binding.when, context || {}),
  );
  if (!match) return null;
  return commandById(match.commandId);
}
