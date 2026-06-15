import React from "react";

export default function NoWorkspaceState({
  value,
  error,
  activating,
  workspaces,
  onChange,
  onOpen,
  onActivate,
}) {
  const recentWorkspaces = Array.isArray(workspaces) ? workspaces : [];

  function handleSubmit(event) {
    event.preventDefault();
    onOpen(value);
  }

  return (
    <main className="no-workspace" data-testid="no-workspace-state">
      <section className="no-workspace-inner" aria-label="Open workspace">
        <div className="no-workspace-kicker">EmbedAgent</div>
        <h1 className="no-workspace-title">Open a workspace</h1>
        <p className="no-workspace-subtitle">
          Choose a local project folder to start managing threads, files, tasks, and agent runs.
        </p>
        <form className="workspace-open-form" onSubmit={handleSubmit}>
          <input
            className="workspace-path-input"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder="D:\\work\\my-c-project"
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
          <div className="recent-workspaces" aria-label="Recent workspaces">
            {recentWorkspaces.map((workspace) => (
              <button
                key={workspace.id}
                type="button"
                className="recent-workspace-row"
                disabled={activating || !workspace.exists}
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
