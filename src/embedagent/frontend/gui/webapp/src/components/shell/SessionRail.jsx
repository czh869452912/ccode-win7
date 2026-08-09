import React, { useEffect, useMemo, useRef } from "react";
import {
  Command,
  FolderOpen,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
} from "lucide-react";

function sessionId(session) {
  return String(session?.session_id || session?.id || "");
}

function sessionTitle(session) {
  const id = sessionId(session);
  return String(session?.title || session?.thread?.title || session?.user_goal || id.slice(0, 8));
}

function commandFor(commands, kind) {
  return (commands || []).find((command) => command?.dispatch?.kind === kind) || null;
}

export default function SessionRail({
  collapsed,
  commands = [],
  sessions,
  onArchiveSession,
  onCollapseChange,
  onCreateSession,
  onForkSession,
  onOpenCommandPalette,
  onOpenWorkspace,
  onRenameSession,
  onSelectSession,
  onWorkspacePathChange,
}) {
  const selectedRef = useRef(null);
  const workspaceInputRef = useRef(null);
  const previousSignatureRef = useRef("");
  const items = sessions?.items || [];
  const currentId = sessions?.currentId || "";
  const signature = items.map(sessionId).join("|");
  const lifecycle = useMemo(() => ({
    archive: commandFor(commands, "session.archive"),
    fork: commandFor(commands, "session.fork"),
    rename: commandFor(commands, "session.rename"),
  }), [commands]);
  const createCommand = commandFor(commands, "session.create");

  useEffect(() => {
    if (previousSignatureRef.current && previousSignatureRef.current !== signature) {
      selectedRef.current?.focus();
    }
    previousSignatureRef.current = signature;
  }, [signature]);

  function revealWorkspaceInput() {
    if (collapsed) onCollapseChange(false);
    window.requestAnimationFrame(() => workspaceInputRef.current?.focus());
  }

  return (
    <nav
      className={`session-rail${collapsed ? " is-collapsed" : ""}`}
      aria-label="Sessions"
      data-testid="session-rail"
    >
      <div className="session-rail-header">
        {collapsed ? null : <strong className="session-rail-product">{sessions?.productName || "EmbedAgent"}</strong>}
        <button
          type="button"
          className="icon-button"
          onClick={() => onCollapseChange(!collapsed)}
          aria-label={collapsed ? "Expand sessions" : "Collapse sessions"}
          aria-expanded={!collapsed}
          title={collapsed ? "Expand sessions" : "Collapse sessions"}
        >
          {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
        </button>
      </div>
      <button
        type="button"
        className="session-rail-command"
        onClick={() => onCreateSession()}
        aria-label={createCommand?.label || "New Session"}
        title={createCommand?.label || "New Session"}
      >
        <Plus size={17} />
        {collapsed ? null : <span>{createCommand?.label || "New Session"}</span>}
      </button>
      <div className="session-rail-list" role="list">
        {items.map((session) => {
          const id = sessionId(session);
          const selected = id === currentId;
          const status = String(session?.status || "idle");
          const pending = Boolean(session?.pending_interaction || status.startsWith("waiting_"));
          return (
            <div className={`session-rail-row${selected ? " is-selected" : ""}`} role="listitem" key={id}>
              <button
                ref={selected ? selectedRef : null}
                type="button"
                className="session-rail-session"
                onClick={() => onSelectSession(id)}
                aria-current={selected ? "page" : undefined}
                title={collapsed ? sessionTitle(session) : undefined}
              >
                <span className={`session-state-dot status-${status}${pending ? " has-interaction" : ""}`} />
                {collapsed ? null : (
                  <span className="session-rail-session-copy">
                    <strong>{sessionTitle(session)}</strong>
                    <small>{session?.current_mode || session?.mode || status}</small>
                  </span>
                )}
              </button>
              {collapsed ? null : (
                <details className="session-rail-menu">
                  <summary aria-label={`Actions for ${sessionTitle(session)}`} title="Session actions">
                    <MoreHorizontal size={16} />
                  </summary>
                  <div className="session-rail-menu-items">
                    {lifecycle.rename ? <button type="button" onClick={() => onRenameSession(id)}>{lifecycle.rename.label}</button> : null}
                    {lifecycle.fork ? <button type="button" onClick={() => onForkSession(id)}>{lifecycle.fork.label}</button> : null}
                    {lifecycle.archive ? <button type="button" onClick={() => onArchiveSession(id)}>{lifecycle.archive.label}</button> : null}
                  </div>
                </details>
              )}
            </div>
          );
        })}
      </div>
      <div className="session-rail-footer">
        <button type="button" className="session-rail-command" onClick={onOpenCommandPalette} aria-label="Commands" title="Commands">
          <Command size={17} />
          {collapsed ? null : <span>Commands</span>}
        </button>
        <button type="button" className="session-rail-command" onClick={revealWorkspaceInput} aria-label="Open Workspace" title="Open Workspace">
          <FolderOpen size={17} />
          {collapsed ? null : <span>{sessions?.activeWorkspace?.label || "Open Workspace"}</span>}
        </button>
        {collapsed ? null : (
          <form
            className="session-rail-workspace-form"
            onSubmit={(event) => {
              event.preventDefault();
              onOpenWorkspace(sessions?.workspacePathInput || "");
            }}
          >
            <input
              ref={workspaceInputRef}
              value={sessions?.workspacePathInput || ""}
              onChange={(event) => onWorkspacePathChange(event.target.value)}
              placeholder="Workspace path"
              aria-label="Workspace path"
              data-testid="sidebar-workspace-path-input"
            />
          </form>
        )}
      </div>
    </nav>
  );
}
