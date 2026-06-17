import React, { useMemo, useState } from "react";

function sessionFor(terminal, terminalId) {
  return (terminal && terminal.sessions && terminal.sessions[terminalId]) || null;
}

function terminalLabel(session, terminalId) {
  return (session && session.label) || terminalId || "Terminal";
}

function terminalStatus(session) {
  return (session && session.status) || "closed";
}

export default function RightPanelTerminalSurface({
  surface,
  terminal,
  onNew,
  onSplit,
  onSplitVertical,
  onSelect,
  onSend,
  onClear,
  onRestart,
  onClose,
}) {
  const [draftsById, setDraftsById] = useState({});
  const terminalIds = Array.isArray(surface && surface.terminalIds)
    ? surface.terminalIds
    : [];
  const activeTerminalId = String((surface && surface.activeTerminalId) || terminalIds[0] || "");
  const splitDirection = surface && surface.splitDirection === "vertical" ? "vertical" : "horizontal";
  const panes = useMemo(
    () =>
      terminalIds.map((terminalId) => ({
        terminalId,
        session: sessionFor(terminal, terminalId),
      })),
    [terminal, terminalIds],
  );

  return (
    <div
      className={`right-panel-terminal-surface split-${splitDirection}`}
      data-testid="right-panel-terminal-surface"
      data-split-direction={splitDirection}
    >
      <div className="right-panel-terminal-toolbar">
        <button type="button" onClick={onNew} title="New terminal">New</button>
        <button type="button" onClick={onSplit} disabled={!activeTerminalId} title="Split terminal horizontally">
          Split
        </button>
        <button type="button" onClick={onSplitVertical} disabled={!activeTerminalId} title="Split terminal vertically">
          Split vertical
        </button>
      </div>
      <div className="right-panel-terminal-panes" data-testid="right-panel-terminal-panes">
        {panes.length > 0 ? (
          panes.map(({ terminalId, session }) => {
            const active = terminalId === activeTerminalId;
            const draft = draftsById[terminalId] || "";
            return (
              <section
                key={terminalId}
                className={`right-panel-terminal-pane${active ? " active" : ""}`}
                data-testid={`right-panel-terminal-pane--${terminalId}`}
              >
                <div className="right-panel-terminal-pane-header">
                  <button
                    type="button"
                    className="right-panel-terminal-pane-title"
                    onClick={() => onSelect(terminalId)}
                    aria-pressed={active}
                    title={(session && session.cwd) || terminalId}
                  >
                    <span>{terminalLabel(session, terminalId)}</span>
                    <span className={`terminal-status-dot ${terminalStatus(session)}`} />
                  </button>
                  <span className="right-panel-terminal-pane-status">{terminalStatus(session)}</span>
                  <button type="button" onClick={() => onClear(terminalId)} disabled={!session}>
                    Clear
                  </button>
                  <button type="button" onClick={() => onRestart(terminalId)} disabled={!session}>
                    Restart
                  </button>
                  <button type="button" onClick={() => onClose(terminalId)}>
                    Close
                  </button>
                </div>
                <pre className="right-panel-terminal-buffer">
                  {session ? session.buffer || "" : "Terminal unavailable."}
                </pre>
                <form
                  className="right-panel-terminal-input-row"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const text = draft;
                    if (!text.trim()) return;
                    setDraftsById((current) => ({ ...current, [terminalId]: "" }));
                    onSend(terminalId, `${text}\n`);
                  }}
                >
                  <span>&gt;</span>
                  <input
                    value={draft}
                    onFocus={() => onSelect(terminalId)}
                    onChange={(event) =>
                      setDraftsById((current) => ({
                        ...current,
                        [terminalId]: event.target.value,
                      }))
                    }
                    placeholder="Type a command"
                    disabled={!session || terminalStatus(session) === "closed"}
                  />
                </form>
              </section>
            );
          })
        ) : (
          <div className="right-panel-terminal-empty">
            <button type="button" onClick={onNew}>New terminal</button>
          </div>
        )}
      </div>
    </div>
  );
}
