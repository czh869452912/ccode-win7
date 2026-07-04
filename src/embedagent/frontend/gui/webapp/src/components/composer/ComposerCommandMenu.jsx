import React from "react";

export default function ComposerCommandMenu({
  open,
  trigger,
  groups = [],
  activeItemId = "",
  onSelect,
  onHighlight,
  emptyText = "",
  chrome = {},
}) {
  if (!open) return null;

  const safeGroups = Array.isArray(groups) ? groups : [];
  const itemCount = safeGroups.reduce((count, group) => count + (Array.isArray(group.items) ? group.items.length : 0), 0);
  const menuEmptyText = emptyText || chrome.defaultEmptyText || "";
  const ariaLabel = trigger?.kind === "path" ? chrome.pathAriaLabel : chrome.commandAriaLabel;
  const itemKindLabels = {
    "path-context": chrome.pathItemKindLabel || "",
    "slash-command": chrome.commandItemKindLabel || "",
  };

  return (
    <div
      id="composer-command-menu"
      className="composer-command-menu"
      role="listbox"
      aria-label={ariaLabel || ""}
      data-trigger-kind={trigger?.kind || ""}
      data-testid="composer-command-menu"
    >
      {itemCount === 0 && (
        <div className="composer-menu-empty" data-testid="composer-menu-empty">
          {menuEmptyText}
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
                  {itemKindLabels[item.type] && (
                    <span className="composer-menu-item-kind">{itemKindLabels[item.type]}</span>
                  )}
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
