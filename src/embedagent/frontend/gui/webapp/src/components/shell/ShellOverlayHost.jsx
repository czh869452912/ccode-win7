import React, { useMemo } from "react";

import CommandPalette from "../workbench/CommandPalette.jsx";

function titleFromId(value) {
  return String(value || "").split(/[._-]+/).filter(Boolean).map((part) => `${part[0].toUpperCase()}${part.slice(1)}`).join(" ");
}

export default function ShellOverlayHost({ actions, shell, sessions }) {
  const config = useMemo(() => {
    const configured = shell.palette.config || {};
    const groupIds = Array.from(new Set(shell.palette.commands.map((command) => command.group).filter(Boolean)));
    return {
      ...configured,
      groups: configured.groups?.length ? configured.groups : groupIds.map((id, order) => ({ id, title: titleFromId(id), order })),
      labels: {
        commandsSection: "Commands",
        currentLabel: "Current",
        missingLabel: "Missing",
        rootEmpty: "No matches",
        rootPlaceholder: "Search commands, sessions, and workspaces",
        rootTitle: "Commands",
        searchLabel: "Search commands",
        sessionFallbackPrefix: "Session",
        sessionsSection: "Sessions",
        submenuEmpty: "No commands",
        submenuPlaceholder: "Search commands",
        submenuTitle: "Commands",
        workspaceFallback: "Workspace",
        workspaceMeta: "Workspace",
        workspacesSection: "Workspaces",
        ...(configured.labels || {}),
      },
    };
  }, [shell.palette.commands, shell.palette.config]);
  return (
    <CommandPalette
      open={shell.palette.open}
      query={shell.palette.query}
      commands={shell.palette.commands}
      sessions={sessions.items}
      currentSessionId={sessions.currentId}
      workspaces={sessions.workspaces}
      activeWorkspaceId={sessions.activeWorkspace?.id || ""}
      keybindings={shell.keybindings}
      commandPalette={config}
      onQueryChange={actions.setPaletteQuery}
      onClose={actions.closeCommandPalette}
      onSelect={actions.selectPaletteCommand}
      onSelectSession={actions.selectPaletteSession}
      onSelectWorkspace={actions.selectPaletteWorkspace}
    />
  );
}
