import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  buildCommandPaletteRootGroups,
  buildCommandPaletteSubmenuGroups,
  flattenPaletteGroups,
} from "../../workbench/command-palette-model.js";
import CommandPaletteResults from "./CommandPaletteResults.jsx";

function clampIndex(index, length) {
  if (length <= 0) return 0;
  return Math.max(0, Math.min(index, length - 1));
}

function firstEnabledIndex(items) {
  const index = (items || []).findIndex((item) => !item.disabled);
  return index < 0 ? 0 : index;
}

export default function CommandPalette({
  open,
  query,
  commands = [],
  sessions = [],
  currentSessionId = "",
  workspaces = [],
  activeWorkspaceId = "",
  keybindings = [],
  commandPalette = null,
  onQueryChange,
  onClose,
  onSelect,
  onSelectSession,
  onSelectWorkspace,
}) {
  const [viewKind, setViewKind] = useState("root");
  const [submenuId, setSubmenuId] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setViewKind("root");
    setSubmenuId("");
    setSelectedIndex(0);
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  const groups = useMemo(() => {
    if (viewKind === "submenu") {
      return buildCommandPaletteSubmenuGroups({
        commands,
        keybindings,
        commandPalette,
        groupId: submenuId,
        query,
      });
    }
    return buildCommandPaletteRootGroups({
      commands,
      sessions,
      currentSessionId,
      workspaces,
      activeWorkspaceId,
      keybindings,
      commandPalette,
      query,
    });
  }, [activeWorkspaceId, commandPalette, commands, currentSessionId, keybindings, query, sessions, submenuId, viewKind, workspaces]);

  const items = useMemo(() => flattenPaletteGroups(groups), [groups]);
  const activeIndex = clampIndex(selectedIndex, items.length);
  const activeItem = items[activeIndex] || null;
  const activeItemId = activeItem ? activeItem.id : "";

  useEffect(() => {
    setSelectedIndex(firstEnabledIndex(items));
  }, [items, viewKind]);

  if (!open) return null;

  function returnToRoot() {
    setViewKind("root");
    setSubmenuId("");
    onQueryChange("");
    setSelectedIndex(0);
  }

  function activateItem(item) {
    if (!item || item.disabled) return;
    if (item.type === "submenu") {
      setViewKind("submenu");
      setSubmenuId(item.submenuId);
      onQueryChange("");
      setSelectedIndex(0);
      return;
    }
    onClose();
    if (item.type === "command") {
      onSelect({ id: item.commandId });
    } else if (item.type === "session") {
      onSelectSession(item.sessionId);
    } else if (item.type === "workspace") {
      onSelectWorkspace(item.workspaceId);
    }
  }

  function moveSelection(delta) {
    if (items.length === 0) return;
    let next = activeIndex;
    for (let step = 0; step < items.length; step += 1) {
      next = (next + delta + items.length) % items.length;
      if (!items[next].disabled) {
        setSelectedIndex(next);
        return;
      }
    }
  }

  function handleKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveSelection(1);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveSelection(-1);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      activateItem(activeItem);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === "Backspace" && !query && viewKind === "submenu") {
      event.preventDefault();
      returnToRoot();
    }
  }

  const title = viewKind === "submenu" ? "Command group" : "Command palette";

  return (
    <div className="cmd-palette-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="cmd-palette"
        role="dialog"
        aria-label="Command palette"
        onMouseDown={(event) => event.stopPropagation()}
        data-testid="command-palette"
      >
        {viewKind === "submenu" ? (
          <div className="cmd-palette-submenu-header">
            <button type="button" className="cmd-palette-back" onClick={returnToRoot} data-testid="command-palette-back">
              ←
            </button>
            <span>{title}</span>
          </div>
        ) : null}
        <input
          ref={inputRef}
          className="cmd-palette-input"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
          aria-label="Command search"
          placeholder={viewKind === "submenu" ? "Search this group" : "Search commands, sessions, workspaces"}
          data-testid="command-palette-input"
        />
        <CommandPaletteResults
          groups={groups}
          activeItemId={activeItemId}
          onHoverItem={(id) => {
            const nextIndex = items.findIndex((item) => item.id === id);
            if (nextIndex >= 0) setSelectedIndex(nextIndex);
          }}
          onSelectItem={activateItem}
          emptyLabel={
            viewKind === "submenu"
              ? "No matching commands in this group"
              : "No matching commands, sessions, or workspaces"
          }
        />
      </div>
    </div>
  );
}
