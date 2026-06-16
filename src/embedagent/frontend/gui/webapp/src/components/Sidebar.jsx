import React from "react";
import { Tree } from "react-arborist";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";

export default function Sidebar({
  app,
  appHome,
  sidebarTab,
  currentSessionId,
  fileTree,
  treeHeight,
  currentMode,
  workspacePathInput,
  onWorkspacePathChange,
  onTabChange,
  onLoadSession,
  onCreateSession,
  onOpenWorkspace,
  onActivateWorkspace,
  onRemoveWorkspace,
  onOpenFile,
  onLoadFileChildren,
}) {
  const lang = useLang();
  const workspaceModel = appHome?.workspace || {};
  const threadModel = appHome?.threads || {};
  const workspaces = Array.isArray(workspaceModel.rows) ? workspaceModel.rows : [];
  const threads = Array.isArray(threadModel.rows) ? threadModel.rows : [];
  const activatingWorkspace = Boolean(app?.activatingWorkspace);

  function handleOpenWorkspace(event) {
    event.preventDefault();
    onOpenWorkspace(workspacePathInput);
  }

  return (
    <aside className="sidebar" role="navigation" aria-label="Sidebar" data-testid="sidebar">
      <div className="brand app-nav-brand">
        <div className="brand-mark">EmbedAgent</div>
        <div className="brand-sub">{t("brand.sub", lang)}</div>
      </div>
      <div className="workspace-switcher app-workspace-manager" data-testid="workspace-switcher">
        <div className="workspace-section-header">
          <span className="workspace-section-title">Project</span>
          <span className="workspace-count">{workspaces.length}</span>
        </div>
        <div className="workspace-current" data-testid="workspace-current-card">
          <span className="workspace-current-label">
            {workspaceModel.activeLabel || "No workspace"}
          </span>
          <span className="workspace-current-path">
            {workspaceModel.activePath || "Open a local project"}
          </span>
        </div>
        <form className="workspace-mini-form" onSubmit={handleOpenWorkspace}>
          <input
            value={workspacePathInput}
            onChange={(event) => onWorkspacePathChange(event.target.value)}
            placeholder="Workspace path"
            disabled={activatingWorkspace}
            data-testid="sidebar-workspace-path-input"
          />
          <button className="ghost" type="submit" disabled={activatingWorkspace}>
            Open
          </button>
        </form>
        {app?.workspaceError ? (
          <div className="workspace-error compact">{app.workspaceError}</div>
        ) : null}
        {workspaces.length ? (
          <div className="workspace-list" aria-label="Recent workspaces">
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
                  <small>{workspace.exists ? workspace.path : "Missing path"}</small>
                </button>
                <button
                  type="button"
                  className="workspace-remove"
                  aria-label={`Remove ${workspace.label}`}
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
          aria-selected={sidebarTab === "chats"}
          className={`sidebar-tab${sidebarTab === "chats" ? " active" : ""}`}
          onClick={() => onTabChange("chats")}
          data-testid="sidebar-tab--chats"
        >
          <span data-testid="sidebar-tab--threads">Threads</span>
        </button>
        <button
          role="tab"
          aria-selected={sidebarTab === "files"}
          className={`sidebar-tab${sidebarTab === "files" ? " active" : ""}`}
          onClick={() => onTabChange("files")}
          data-testid="sidebar-tab--files"
        >
          {t("sidebar.files", lang)}
        </button>
      </div>
      {sidebarTab === "chats" ? (
        <div className="thread-panel" role="tabpanel" aria-label={t("sidebar.chats", lang)}>
          <div className="thread-panel-header">
            <div>
              <span className="thread-panel-kicker">Threads</span>
              <span className="thread-panel-count">{threadModel.count || 0}</span>
            </div>
            <button
              className="primary compact"
              onClick={() => onCreateSession(currentMode)}
              disabled={!threadModel.canCreateThread}
              data-testid="new-session-btn"
            >
              <span data-testid="new-thread-btn">New</span>
            </button>
          </div>
          <div className="thread-list" role="list" data-testid="thread-list">
            {threadModel.empty ? (
              <div className="thread-empty" data-testid="thread-empty-state">
                <span>No threads yet</span>
                <small>Start one for this project.</small>
              </div>
            ) : null}
            {threads.map((session) => (
              <button
                key={session.id}
                role="listitem"
                className={`thread-card ${currentSessionId === session.id ? "selected" : ""}`}
                aria-pressed={currentSessionId === session.id}
                onClick={() => onLoadSession(session.id)}
                data-testid={`session-card--${session.id}`}
              >
                <span className="thread-title">{session.title}</span>
                <span className="thread-meta">
                  <span className={`thread-mode mode-${session.mode}`}>{session.mode}</span>
                  {session.updated ? (
                    <span className="thread-detail">{session.updated}</span>
                  ) : null}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="files-panel" role="tabpanel" aria-label={t("sidebar.files", lang)}>
          <Tree
            data={fileTree}
            width={300}
            height={treeHeight}
            rowHeight={30}
            indent={18}
            onActivate={(node) => {
              if (node.data.kind === "file") {
                onOpenFile(node.data.path);
              } else if (!node.data.childrenLoaded && node.data.hasChildren) {
                onLoadFileChildren(node.data.path);
              }
            }}
          >
            {({ node, style }) => (
              <div
                style={style}
                className={`tree-row ${node.data.kind}`}
                role="treeitem"
                aria-expanded={node.data.kind === "dir" ? node.isOpen : undefined}
                onClick={() => {
                  if (node.data.kind === "dir") {
                    if (!node.data.childrenLoaded && node.data.hasChildren) {
                      onLoadFileChildren(node.data.path);
                    }
                    node.toggle();
                  } else {
                    onOpenFile(node.data.path);
                  }
                }}
                data-testid={`file-tree-node--${node.data.path}`}
              >
                <span className="tree-icon" aria-hidden="true">
                  {node.data.kind === "dir" ? (node.isOpen ? "▾" : "▸") : "·"}
                </span>
                <span className="tree-label">{node.data.name}</span>
              </div>
            )}
          </Tree>
        </div>
      )}
    </aside>
  );
}
