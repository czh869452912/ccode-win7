import React from "react";

export default function NoWorkspaceState({
  value,
  error,
  activating,
  workspaces,
  appHome,
  emptyState,
  onChange,
  onOpen,
  onActivate,
}) {
  const copy = emptyState || {};
  const scenarioLabel = copy.scenarioLabel || copy.scenario_label || "";
  const primary = copy.primary || "";
  const secondary = copy.secondary || "";
  const pathPlaceholder = copy.pathPlaceholder || copy.path_placeholder || "";
  const productName = appHome?.productName || "";
  const workspaceCopy = appHome?.workspace?.copy || {};
  const recentWorkspaces = Array.isArray(appHome?.workspace?.rows)
    ? appHome.workspace.rows
    : Array.isArray(workspaces)
      ? workspaces
      : [];

  function handleSubmit(event) {
    event.preventDefault();
    onOpen(value);
  }

  return (
    <main className="no-workspace" data-testid="no-workspace-state">
      <section className="no-workspace-inner" aria-label={workspaceCopy.openAriaLabel}>
        {productName ? <div className="no-workspace-kicker">{productName}</div> : null}
        {primary ? <h1 className="no-workspace-title">{primary}</h1> : null}
        {secondary ? <p className="no-workspace-subtitle">{secondary}</p> : null}
        {scenarioLabel ? <div className="no-workspace-scenario">{scenarioLabel}</div> : null}
        <form className="workspace-open-form" onSubmit={handleSubmit}>
          <input
            className="workspace-path-input"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder={pathPlaceholder || workspaceCopy.pathPlaceholder}
            disabled={activating}
            data-testid="workspace-path-input"
          />
          <button
            className="primary"
            type="submit"
            disabled={activating}
            data-testid="open-workspace-button"
          >
            {workspaceCopy.openLabel}
          </button>
        </form>
        {error ? <div className="workspace-error">{error}</div> : null}
        {recentWorkspaces.length ? (
          <div className="recent-workspaces app-home-recents" aria-label={workspaceCopy.recentsLabel}>
            <div className="recent-workspaces-heading">
              <span>{workspaceCopy.recentsLabel}</span>
              <small>{recentWorkspaces.length}</small>
            </div>
            {recentWorkspaces.map((workspace) => (
              <button
                key={workspace.id}
                type="button"
                className={`recent-workspace-row ${workspace.status || ""}`}
                disabled={workspace.disabled || activating || !workspace.exists}
                onClick={() => onActivate(workspace.id)}
              >
                <span>{workspace.label}</span>
                <small>{workspace.pathLabel}</small>
              </button>
            ))}
          </div>
        ) : null}
      </section>
    </main>
  );
}
