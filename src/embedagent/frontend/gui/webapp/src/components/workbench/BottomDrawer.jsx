import React, { useState } from "react";

function RunOutputDrawer({ eventLog, terminationReason, terminationMessage }) {
  const entries = Array.isArray(eventLog) ? eventLog.slice(-80) : [];
  return (
    <>
      {terminationReason ? (
        <div className="drawer-line">
          reason={terminationReason} {terminationMessage || ""}
        </div>
      ) : null}
      {entries.length > 0 ? (
        entries.map((entry) => (
          <div className="drawer-line" key={`${entry.ts}-${entry.label}`}>
            <span className="drawer-label">{entry.label}</span>
            <span>{entry.detail || ""}</span>
          </div>
        ))
      ) : (
        <div className="drawer-line muted">No run output yet.</div>
      )}
    </>
  );
}

function TerminalSurface({ terminal, onNew, onSelect, onSend, onClear, onRestart, onClose }) {
  const [draft, setDraft] = useState("");
  const state = terminal || { sessions: {}, terminalIds: [], activeTerminalId: "" };
  const active = state.sessions[state.activeTerminalId] || null;
  const terminalIds = state.terminalIds || [];
  return (
    <div className="terminal-drawer-surface" data-testid="terminal-drawer">
      <div className="terminal-tabbar">
        {terminalIds.map((terminalId) => {
          const item = state.sessions[terminalId] || { label: terminalId, status: "closed" };
          return (
            <button
              key={terminalId}
              className={`terminal-tab${terminalId === state.activeTerminalId ? " active" : ""}`}
              type="button"
              onClick={() => onSelect(terminalId)}
              title={item.cwd || terminalId}
            >
              <span>{item.label || terminalId}</span>
              <span className={`terminal-status-dot ${item.status || "closed"}`} />
            </button>
          );
        })}
        <button className="terminal-icon-button" type="button" title="New terminal" onClick={onNew}>
          +
        </button>
      </div>
      <div className="terminal-toolbar">
        <span>{active ? active.cwd : "No terminal"}</span>
        <span>{active ? active.status : "closed"}</span>
        <button type="button" title="Clear terminal" onClick={onClear} disabled={!active}>
          Clear
        </button>
        <button type="button" title="Restart terminal" onClick={onRestart} disabled={!active}>
          Restart
        </button>
        <button type="button" title="Close terminal" onClick={onClose} disabled={!active}>
          Close
        </button>
      </div>
      <pre className="terminal-buffer">{active ? active.buffer || "" : "Open a terminal to start."}</pre>
      <form
        className="terminal-input-row"
        onSubmit={(event) => {
          event.preventDefault();
          const text = draft;
          if (!text.trim()) return;
          setDraft("");
          onSend(`${text}\n`);
        }}
      >
        <span>&gt;</span>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type a command"
          disabled={!active || active.status === "closed"}
        />
      </form>
    </div>
  );
}

export default function BottomDrawer({
  activeKind,
  eventLog,
  terminationReason,
  terminationMessage,
  terminal,
  onKindSelect,
  onTerminalNew,
  onTerminalSelect,
  onTerminalSend,
  onTerminalClear,
  onTerminalRestart,
  onTerminalClose,
}) {
  return (
    <section className="bottom-drawer" aria-label="Bottom drawer" data-testid="bottom-drawer">
      <div className="bottom-drawer-tabs" role="tablist">
        <button
          className={`bottom-drawer-tab${activeKind === "terminal" ? " active" : ""}`}
          type="button"
          onClick={() => onKindSelect("terminal")}
        >
          Terminal
        </button>
        <button
          className={`bottom-drawer-tab${activeKind === "run_output" ? " active" : ""}`}
          type="button"
          onClick={() => onKindSelect("run_output")}
        >
          Run Output
        </button>
        <button
          className={`bottom-drawer-tab${activeKind === "logs" ? " active" : ""}`}
          type="button"
          onClick={() => onKindSelect("logs")}
        >
          Logs
        </button>
      </div>
      <div className="bottom-drawer-body">
        {activeKind === "terminal" ? (
          <TerminalSurface
            terminal={terminal}
            onNew={onTerminalNew}
            onSelect={onTerminalSelect}
            onSend={onTerminalSend}
            onClear={onTerminalClear}
            onRestart={onTerminalRestart}
            onClose={onTerminalClose}
          />
        ) : (
          <RunOutputDrawer
            eventLog={eventLog}
            terminationReason={terminationReason}
            terminationMessage={terminationMessage}
          />
        )}
      </div>
    </section>
  );
}
