import React from "react";

export default function ComposerCommandMenu({
  open,
  trigger,
  groups = [],
  activeItemId = "",
  onSelect,
  onHighlight,
  emptyText = "No matches",
}) {
  if (!open) return null;

  const safeGroups = Array.isArray(groups) ? groups : [];
  const itemCount = safeGroups.reduce((count, group) => count + (Array.isArray(group.items) ? group.items.length : 0), 0);

  return (
    <div
      id="composer-command-menu"
      className="composer-command-menu"
      role="listbox"
      aria-label={trigger?.kind === "path" ? "File context suggestions" : "Slash command suggestions"}
      data-trigger-kind={trigger?.kind || ""}
      data-testid="composer-command-menu"
    >
      {itemCount === 0 && (
        <div className="composer-menu-empty" data-testid="composer-menu-empty">
          {emptyText}
        </div>
      )}
      {safeGroups.map((group) => (
        <section className="composer-menu-group" key={group.id || group.label}>
          <div className="composer-menu-group-label">{group.label}</div>
          <div className="composer-menu-group-items">
            {(Array.isArray(group.items) ? group.items : []).map((item) => {
              const active = item.id === activeItemId;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="option"
                  aria-selected={active}
                  className={`composer-menu-item${active ? " active" : ""}`}
                  data-testid={`composer-menu-item--${item.id}`}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseMove={() => {
                    if (typeof onHighlight === "function") onHighlight(item);
                  }}
                  onClick={() => {
                    if (typeof onSelect === "function") onSelect(item);
                  }}
                >
                  <span className="composer-menu-item-main">
                    <span className="composer-menu-item-label">{item.label}</span>
                    {item.detail && <span className="composer-menu-item-detail">{item.detail}</span>}
                  </span>
                  {item.type === "path-context" && <span className="composer-menu-item-kind">file</span>}
                  {item.type === "slash-command" && <span className="composer-menu-item-kind">command</span>}
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
