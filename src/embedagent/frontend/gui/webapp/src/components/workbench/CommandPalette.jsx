import React from "react";
import { visibleCommands } from "../../workbench/commands.js";

function matchesQuery(command, query) {
  const normalized = String(query || "").trim().toLowerCase();
  if (!normalized) return true;
  return (
    command.id.toLowerCase().includes(normalized) ||
    command.label.toLowerCase().includes(normalized) ||
    command.group.toLowerCase().includes(normalized) ||
    String(command.slash || "").toLowerCase().includes(normalized)
  );
}

export default function CommandPalette({
  open,
  query,
  selectedIndex,
  context,
  onQueryChange,
  onClose,
  onSelect,
}) {
  if (!open) return null;
  const commands = visibleCommands(context || {}).filter((command) => matchesQuery(command, query));
  const selected = Math.max(0, Math.min(selectedIndex || 0, Math.max(commands.length - 1, 0)));
  return (
    <div className="cmd-palette-backdrop" role="presentation" onMouseDown={onClose}>
      <div className="cmd-palette" role="dialog" aria-label="Command palette" onMouseDown={(event) => event.stopPropagation()}>
        <input
          className="cmd-palette-input"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          autoFocus
          aria-label="Command search"
          data-testid="command-palette-input"
        />
        <div className="cmd-palette-list" role="listbox">
          {commands.map((command, index) => (
            <button
              key={command.id}
              type="button"
              className={`cmd-palette-item${index === selected ? " active" : ""}`}
              onClick={() => onSelect(command)}
              role="option"
              aria-selected={index === selected}
              data-testid={`command-palette-item--${command.id}`}
            >
              <span className="cmd-palette-title">{command.label}</span>
              <span className="cmd-palette-meta">{command.slash || command.id}</span>
            </button>
          ))}
          {commands.length === 0 ? (
            <div className="cmd-palette-empty">No matching command</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
