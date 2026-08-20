import { FRONTEND_PROTOCOL_SCHEMA_VERSION } from "../session-runtime/protocol-version.js";

const SECRET_KEY_PARTS = ["api_key", "authorization", "password", "secret", "token"];
const BLOCKED_KEYS = ["prompt", "transcript", "tool_output"];

export function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isBlockedKey(key) {
  const lowered = String(key || "").toLowerCase();
  if (BLOCKED_KEYS.includes(lowered)) return true;
  return SECRET_KEY_PARTS.some((part) => lowered.includes(part));
}

export function safeValue(value) {
  if (Array.isArray(value)) return value.map(safeValue);
  if (isRecord(value)) {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !isBlockedKey(key))
        .map(([key, item]) => [key, safeValue(item)]),
    );
  }
  return value;
}

export function validateShellDescriptor(shell) {
  if (!isRecord(shell) || shell.schemaVersion !== FRONTEND_PROTOCOL_SCHEMA_VERSION) {
    throw new TypeError("invalid_app_bootstrap:shell");
  }
  for (const key of [
    "commands",
    "surfaces",
    "keybindings",
    "toolPresentations",
    "timelineItems",
    "interactions",
  ]) {
    if (!Array.isArray(shell[key])) throw new TypeError(`invalid_app_bootstrap:shell.${key}`);
  }
  return shell;
}
