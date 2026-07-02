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
  const scenarioLabel = copy.scenarioLabel || copy.scenario_label || "local workspace";
  const primary = copy.primary || "Open a project";
  const secondary =
    copy.secondary || "Choose a local workspace to manage threads, files, tasks, and agent runs.";
  const pathPlaceholder = copy.pathPlaceholder || copy.path_placeholder || "D:\\work\\project";
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
      <section className="no-workspace-inner" aria-label="Open workspace">
        <div className="no-workspace-kicker">EmbedAgent</div>
        <h1 className="no-workspace-title">{primary}</h1>
        <p className="no-workspace-subtitle">
          {secondary}
        </p>
        <div className="no-workspace-scenario">{scenarioLabel}</div>
        <form className="workspace-open-form" onSubmit={handleSubmit}>
          <input
            className="workspace-path-input"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder={pathPlaceholder}
            disabled={activating}
            data-testid="workspace-path-input"
          />
          <button
            className="primary"
            type="submit"
            disabled={activating}
            data-testid="open-workspace-button"
          >
            Open
          </button>
        </form>
        {error ? <div className="workspace-error">{error}</div> : null}
        {recentWorkspaces.length ? (
          <div className="recent-workspaces app-home-recents" aria-label="Recent workspaces">
            <div className="recent-workspaces-heading">
              <span>Recent projects</span>
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
                <small>{workspace.exists ? workspace.path : "Missing path"}</small>
              </button>
            ))}
          </div>
        ) : null}
      </section>
    </main>
  );
}
