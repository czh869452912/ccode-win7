import React from "react";

function contextLabel(context) {
  const used = Number(context?.used_tokens || context?.used || 0);
  const limit = Number(context?.max_tokens || context?.limit || 0);
  if (!used && !limit) return "";
  return limit ? `${used}/${limit}` : String(used);
}

export default function SessionStatusFooter({ connection, modes, sessions, status }) {
  const workspace = sessions.activeWorkspace?.label || "No workspace";
  const context = contextLabel(status.context);
  return (
    <footer className="agent-status-footer" data-session-status>
      <span className={`connection-state status-${connection.status}`}>{connection.recovering ? "Recovering" : connection.status}</span>
      <span>{workspace}</span>
      <span>{modes.catalog?.[modes.current]?.label || modes.current}</span>
      <span>{status.session}</span>
      {context ? <span className="agent-status-context">Context {context}</span> : null}
    </footer>
  );
}
