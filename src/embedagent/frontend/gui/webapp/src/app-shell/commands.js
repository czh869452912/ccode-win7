export const APP_COMMANDS = [
  { id: "app.settings", group: "app", label: "Open Settings", slash: "", surface: "settings", visibleWhen: "always" },
  { id: "app.diagnostics", group: "app", label: "Open Diagnostics", slash: "", surface: "diagnostics", visibleWhen: "always" },
  { id: "app.source_control", group: "app", label: "Open Source Control", slash: "", surface: "source_control", visibleWhen: "always", keywords: ["git", "changes", "source", "source_control"] },
  { id: "app.reload", group: "app", label: "Reload App Shell", slash: "", visibleWhen: "always" },
];

export function isAppCommand(id) {
  return APP_COMMANDS.some((command) => command.id === id);
}
