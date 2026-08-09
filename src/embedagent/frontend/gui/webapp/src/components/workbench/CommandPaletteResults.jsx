import React from "react";
import { ChevronRight } from "lucide-react";

function rowClassName(item, active) {
  const classes = ["cmd-palette-row"];
  if (active) classes.push("active");
  if (item.disabled) classes.push("disabled");
  if (item.type === "submenu") classes.push("has-submenu");
  return classes.join(" ");
}

function itemTestId(item) {
  if (item.type === "command") return `command-palette-command--${item.commandId}`;
  if (item.type === "session") return `command-palette-session--${item.sessionId}`;
  if (item.type === "workspace") return `command-palette-workspace--${item.workspaceId}`;
  if (item.type === "submenu") return `command-palette-submenu--${item.submenuId}`;
  return `command-palette-item--${item.id}`;
}

export default function CommandPaletteResults({
  groups = [],
  activeItemId = "",
  onHoverItem,
  onSelectItem,
  emptyLabel = "",
}) {
  const hasItems = groups.some((group) => (group.items || []).length > 0);
  if (!hasItems) {
    return (
      <div className="cmd-palette-empty" data-testid="command-palette-empty">
        {emptyLabel}
      </div>
    );
  }
  return (
    <div className="cmd-palette-results" role="listbox" data-testid="command-palette-results">
      {groups.map((group) => (
        <section className="cmd-palette-group" key={group.id} data-testid={`command-palette-group--${group.id}`}>
          <div className="cmd-palette-group-title">{group.title}</div>
          <div className="cmd-palette-group-items">
            {(group.items || []).map((item) => {
              const active = item.id === activeItemId;
              return (
                <button
                  key={item.id}
                  type="button"
                  className={rowClassName(item, active)}
                  onMouseEnter={() => onHoverItem(item.id)}
                  onClick={() => {
                    if (!item.disabled) onSelectItem(item);
                  }}
                  disabled={Boolean(item.disabled)}
                  aria-disabled={Boolean(item.disabled)}
                  aria-selected={active}
                  role="option"
                  data-testid={itemTestId(item)}
                >
                  {item.leading ? (
                    <span className="cmd-palette-row-leading" aria-hidden="true">
                      {item.leading}
                    </span>
                  ) : null}
                  <span className="cmd-palette-row-main">
                    <span className="cmd-palette-row-title">{item.title}</span>
                    <span className="cmd-palette-row-description">{item.description}</span>
                  </span>
                  <span className="cmd-palette-row-meta">
                    {item.shortcut ? <kbd className="cmd-palette-row-shortcut">{item.shortcut}</kbd> : null}
                    {item.trailing ? <span className="cmd-palette-row-trailing">{item.trailing}</span> : null}
                    {item.meta ? <span className="cmd-palette-row-id">{item.meta}</span> : null}
                    {item.type === "submenu" ? <ChevronRight className="cmd-palette-row-chevron" size={14} /> : null}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
