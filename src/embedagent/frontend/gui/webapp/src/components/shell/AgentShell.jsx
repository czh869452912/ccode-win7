import React, { useState } from "react";
import { PanelLeftOpen } from "lucide-react";

import ContributionOutlet from "../contributions/ContributionOutlet.jsx";
import SessionComposer from "./SessionComposer.jsx";
import SessionRail from "./SessionRail.jsx";
import SessionStatusFooter from "./SessionStatusFooter.jsx";
import SessionTimeline from "./SessionTimeline.jsx";
import ShellOverlayHost from "./ShellOverlayHost.jsx";

function WorkspaceGate({ actions, sessions }) {
  return (
    <main className="workspace-gate">
      <form onSubmit={(event) => { event.preventDefault(); actions.openWorkspace(sessions.workspacePathInput); }}>
        <label htmlFor="workspace-gate-path">Open a workspace</label>
        <div>
          <input id="workspace-gate-path" value={sessions.workspacePathInput} onChange={(event) => actions.setWorkspacePath(event.target.value)} placeholder="Workspace path" />
          <button type="submit" disabled={sessions.activatingWorkspace}>Open</button>
        </div>
        {sessions.workspaceError ? <p role="alert">{sessions.workspaceError}</p> : null}
      </form>
      {sessions.workspaces.length ? (
        <div className="workspace-recent-list">
          {sessions.workspaces.map((workspace) => <button type="button" key={workspace.id} disabled={workspace.exists === false} onClick={() => actions.activateWorkspace(workspace.id)}>{workspace.label || workspace.path}</button>)}
        </div>
      ) : null}
    </main>
  );
}

export default function AgentShell({ actions, timelineRef, view }) {
  const [railCollapsed, setRailCollapsed] = useState(() => (
    typeof window !== "undefined" && window.matchMedia("(max-width: 700px)").matches
  ));
  const sessions = { ...view.sessions, productName: view.sessions.productName || "EmbedAgent" };
  return (
    <div className={`agent-shell${railCollapsed ? " rail-collapsed" : ""}`} data-agent-shell>
      {railCollapsed ? (
        <button
          type="button"
          className="mobile-rail-toggle icon-button"
          onClick={() => setRailCollapsed(false)}
          aria-label="Expand sessions"
          title="Expand sessions"
        >
          <PanelLeftOpen size={17} />
        </button>
      ) : null}
      <SessionRail
        collapsed={railCollapsed}
        commands={view.shell.commands}
        sessions={sessions}
        onArchiveSession={actions.archiveSession}
        onCollapseChange={setRailCollapsed}
        onCreateSession={() => actions.createSession(view.modes.current)}
        onForkSession={actions.forkSession}
        onOpenCommandPalette={actions.openCommandPalette}
        onOpenWorkspace={actions.openWorkspace}
        onRenameSession={actions.renameSession}
        onSelectSession={actions.selectSession}
        onWorkspacePathChange={actions.setWorkspacePath}
      />
      <div className="agent-main">
        {view.sessions.hasActiveWorkspace ? (
          <>
            <SessionTimeline ref={timelineRef} actions={actions} status={view.status} timeline={view.timeline} />
            <SessionComposer actions={actions} composer={view.composer} interaction={view.interaction} modes={view.modes} />
          </>
        ) : <WorkspaceGate actions={actions} sessions={view.sessions} />}
        <SessionStatusFooter connection={view.connection} modes={view.modes} sessions={view.sessions} status={view.status} />
      </div>
      <ShellOverlayHost actions={actions} shell={view.shell} sessions={view.sessions} />
      <ContributionOutlet actions={actions} contribution={view.shell.contributions} />
    </div>
  );
}
