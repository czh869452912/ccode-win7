import React from "react";
import { modeBadgeLabel, modeBadgeStyle } from "../session-runtime/mode-style.js";

export default function Sidebar({
  app,
  appHome,
  chrome = {},
  currentSessionId,
  currentMode,
  modeCatalog = {},
  workspacePathInput,
  onWorkspacePathChange,
  onLoadSession,
  onCreateSession,
  onThreadLifecycleAction,
  onOpenWorkspace,
  onActivateWorkspace,
  onRemoveWorkspace,
}) {
  const workspaceModel = appHome?.workspace || {};
  const threadModel = appHome?.threads || {};
  const workspaceCopy = workspaceModel.copy || {};
  const threadCopy = threadModel.copy || {};
  const workspaces = Array.isArray(workspaceModel.rows) ? workspaceModel.rows : [];
  const threads = Array.isArray(threadModel.rows) ? threadModel.rows : [];
  const activatingWorkspace = Boolean(app?.activatingWorkspace);

  function handleOpenWorkspace(event) {
    event.preventDefault();
    onOpenWorkspace(workspacePathInput);
  }

  return (
    <aside className="sidebar" role="navigation" aria-label={chrome.sidebarAriaLabel} data-testid="sidebar">
      <div className="brand app-nav-brand">
        <div className="brand-mark">{app?.app?.productName}</div>
        <div className="brand-sub">{chrome.brandSubtitle}</div>
      </div>
      <div className="workspace-switcher app-workspace-manager" data-testid="workspace-switcher">
        <div className="workspace-section-header">
          <span className="workspace-section-title">{workspaceCopy.sectionTitle}</span>
          <span className="workspace-count">{workspaces.length}</span>
        </div>
        <div className="workspace-current" data-testid="workspace-current-card">
          <span className="workspace-current-label">
            {workspaceModel.activeLabel}
          </span>
          <span className="workspace-current-path">
            {workspaceModel.activePath}
          </span>
        </div>
        <form className="workspace-mini-form" onSubmit={handleOpenWorkspace}>
          <input
            value={workspacePathInput}
            onChange={(event) => onWorkspacePathChange(event.target.value)}
            placeholder={workspaceCopy.pathPlaceholder}
            disabled={activatingWorkspace}
            data-testid="sidebar-workspace-path-input"
          />
          <button className="ghost" type="submit" disabled={activatingWorkspace}>
            {workspaceCopy.openLabel}
          </button>
        </form>
        {app?.workspaceError ? (
          <div className="workspace-error compact">{app.workspaceError}</div>
        ) : null}
        {workspaces.length ? (
          <div className="workspace-list" aria-label={workspaceCopy.recentsLabel}>
            {workspaces.map((workspace) => (
              <div
                key={workspace.id}
                className={`workspace-row ${workspace.status || "available"}${
                  workspace.isActive ? " active" : ""
                }`}
                data-testid={`workspace-row--${workspace.id}`}
              >
                <button
                  type="button"
                  disabled={workspace.disabled}
                  onClick={() => onActivateWorkspace(workspace.id)}
                >
                  <span>{workspace.label}</span>
                  <small>{workspace.pathLabel}</small>
                </button>
                <button
                  type="button"
                  className="workspace-remove"
                  aria-label={`${workspaceCopy.removeLabel} ${workspace.label}`.trim()}
                  disabled={activatingWorkspace}
                  onClick={() => onRemoveWorkspace(workspace.id)}
                >
                  x
                </button>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <div className="sidebar-tabs" role="tablist">
        <button
          role="tab"
          aria-selected="true"
          className="sidebar-tab active"
          data-testid="sidebar-tab--threads"
        >
          <span>{threadCopy.sectionTitle}</span>
        </button>
      </div>
      <div
        className="thread-panel"
        role="tabpanel"
        aria-label={chrome.threadPanelAriaLabel}
        data-testid="thread-lifecycle-panel"
      >
        <div className="thread-panel-header" data-testid="thread-panel-header">
          <div>
            <span className="thread-panel-kicker">{threadCopy.sectionTitle}</span>
            <span className="thread-panel-count">{threadModel.count || 0}</span>
          </div>
          <button
            className="primary compact"
            onClick={() => onCreateSession(currentMode)}
            disabled={!threadModel.canCreateThread}
            data-testid="new-session-btn"
          >
            <span data-testid="new-thread-btn">{threadCopy.newLabel}</span>
          </button>
        </div>
        <div className="thread-list" role="list" data-testid="thread-list">
          {threadModel.empty ? (
            <div className="thread-empty" data-testid="thread-empty-state">
              <span>{threadCopy.emptyTitle}</span>
              <small>{threadCopy.emptyBody}</small>
            </div>
          ) : null}
          {threads.map((session) => (
            <div
              key={session.id}
              role="listitem"
              className={`thread-card ${currentSessionId === session.id ? "selected" : ""}`}
              data-testid={`session-card--${session.id}`}
            >
              <button
                type="button"
                className="thread-open"
                aria-pressed={currentSessionId === session.id}
                onClick={() => onLoadSession(session.id)}
                data-testid={`session-open--${session.id}`}
              >
                <span className="thread-title">{session.title}</span>
                <span className="thread-meta">
                  <span className="thread-mode" style={modeBadgeStyle(session.mode, modeCatalog)}>
                    {modeBadgeLabel(session.mode, modeCatalog)}
                  </span>
                  {session.isActive ? (
                    <span className="thread-state">{threadCopy.activeLabel}</span>
                  ) : null}
                  {session.updated ? (
                    <span className="thread-detail">{session.updated}</span>
                  ) : null}
                </span>
              </button>
              <div
                className="thread-actions"
                aria-label={`${threadCopy.actionsLabelPrefix} ${session.title}`.trim()}
                data-testid={`thread-actions--${session.id}`}
              >
                {(session.actions || []).map((action) => (
                  <button
                    key={action.id}
                    type="button"
                    className="thread-action"
                    disabled={!action.enabled}
                    title={action.reasonLabel || action.label}
                    aria-label={`${action.label} ${session.title}`}
                    onClick={() => onThreadLifecycleAction?.(action.id, session.id)}
                    data-testid={`thread-action--${action.id}--${session.id}`}
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
