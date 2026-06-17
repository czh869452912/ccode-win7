import React from "react";
import { RIGHT_PANEL_SURFACES } from "../../workbench/surfaces.js";

const LABELS = {
  interaction: "Ask",
  tasks: "Tasks",
  plan: "Plan",
  artifacts: "Artifacts",
  run: "Run",
  problems: "Problems",
  review: "Review",
  diff: "Diff",
  source_control: "Source",
  permissions: "Permissions",
  runtime: "Runtime",
  settings: "Settings",
  diagnostics: "Diagnostics",
  preview: "Preview",
  log: "Log",
};

export default function RightPanelTabs({
  activeKind,
  counts,
  onSelect,
  children,
}) {
  const badges = counts || {};
  return (
    <aside className="right-panel" role="complementary" aria-label="Right panel" data-testid="right-panel">
      <div className="right-panel-tabs" role="tablist">
        {RIGHT_PANEL_SURFACES.map((kind) => (
          <button
            key={kind}
            type="button"
            role="tab"
            aria-selected={activeKind === kind}
            className={`right-panel-tab${activeKind === kind ? " active" : ""}`}
            onClick={() => onSelect(kind)}
            data-testid={`right-panel-tab--${kind}`}
          >
            <span>{LABELS[kind] || kind}</span>
            {badges[kind] > 0 ? <span className="tab-badge">{badges[kind]}</span> : null}
          </button>
        ))}
      </div>
      <div className="right-panel-body">{children}</div>
    </aside>
  );
}
