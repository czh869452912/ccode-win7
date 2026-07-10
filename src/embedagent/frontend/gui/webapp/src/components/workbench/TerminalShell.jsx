import React, { useMemo, useState } from "react";
import { getTerminalLabel } from "../../terminal/terminal-labels.js";

function sessionFor(terminal, terminalId) {
  return (terminal && terminal.sessions && terminal.sessions[terminalId]) || null;
}

function terminalLabel(session, terminalId, chrome) {
  const explicitLabel = String((session && session.label) || "").trim();
  return explicitLabel || getTerminalLabel(terminalId, chrome);
}

function terminalStatus(session) {
  return (session && session.status) || "closed";
}

function terminalIdsFor(owner, surface, terminal) {
  if (owner === "right-panel") {
    return Array.isArray(surface && surface.terminalIds)
      ? surface.terminalIds
      : [surface && (surface.activeTerminalId || surface.terminalId)].filter(Boolean);
  }
  return (terminal && terminal.terminalIds) || [];
}

function activeTerminalFor(owner, surface, terminal, ids) {
  if (owner === "right-panel") return String((surface && surface.activeTerminalId) || ids[0] || "");
  return String((terminal && terminal.activeTerminalId) || ids[0] || "");
}

function TerminalPane({
  terminalId,
  session,
  active,
  draft,
  setDraft,
  onSelect,
  onSend,
  onClear,
  onRestart,
  onClose,
  chrome,
}) {
  const status = terminalStatus(session);
  return (
    <section
      className={`terminal-shell-pane${active ? " active" : ""}`}
      data-testid={`terminal-shell-pane--${terminalId}`}
      onMouseDown={() => onSelect && onSelect(terminalId)}
    >
      <header className="terminal-shell-pane-header">
        <button
          type="button"
          className="terminal-shell-pane-title"
          onClick={() => onSelect && onSelect(terminalId)}
          title={(session && session.cwd) || terminalId}
        >
          <span>{terminalLabel(session, terminalId, chrome)}</span>
          <span className={`terminal-status-dot ${status}`} />
        </button>
        <span className="terminal-shell-pane-status">{status}</span>
        <button type="button" onClick={() => onClear(terminalId)} disabled={!session}>{chrome.clearLabel}</button>
        <button type="button" onClick={() => onRestart(terminalId)} disabled={!session}>{chrome.restartLabel}</button>
        <button type="button" onClick={() => onClose(terminalId)}>{chrome.closeLabel}</button>
      </header>
      <pre className="terminal-shell-buffer">{session ? session.buffer || "" : chrome.unavailableMessage}</pre>
      <form
        className="terminal-shell-input-row"
        onSubmit={(event) => {
          event.preventDefault();
          const text = draft || "";
          if (!text.trim()) return;
          setDraft("");
          onSelect && onSelect(terminalId);
          onSend(terminalId, `${text}\n`);
        }}
      >
        <span>&gt;</span>
        <input
          value={draft}
          onFocus={() => onSelect && onSelect(terminalId)}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={chrome.commandPlaceholder}
          disabled={!session || status === "closed"}
        />
      </form>
    </section>
  );
}

export default function TerminalShell({
  owner,
  surface = null,
  terminal,
  onNew,
  onSplit,
  onSplitVertical,
  onSelect,
  onSend,
  onClear,
  onRestart,
  onClose,
  terminalChrome = {},
}) {
  const [draftsById, setDraftsById] = useState({});
  const terminalIds = terminalIdsFor(owner, surface, terminal);
  const activeTerminalId = activeTerminalFor(owner, surface, terminal, terminalIds);
  const splitDirection = surface && surface.splitDirection === "vertical" ? "vertical" : "horizontal";
  const panes = useMemo(
    () => terminalIds.map((terminalId) => ({ terminalId, session: sessionFor(terminal, terminalId) })),
    [terminal, terminalIds],
  );
  const isRightPanel = owner === "right-panel";
  const isDrawer = owner === "drawer";

  return (
    <section
      className={`terminal-shell owner-${owner}`}
      data-terminal-owner={owner}
      data-testid={isRightPanel ? "right-panel-terminal-surface" : "terminal-drawer"}
    >
      <header className="terminal-shell-toolbar">
        <button type="button" onClick={onNew} title={terminalChrome.newTitle}>{terminalChrome.newLabel}</button>
        {isRightPanel ? (
          <>
            <button type="button" onClick={onSplit} disabled={!activeTerminalId} title={terminalChrome.splitTitle}>
              {terminalChrome.splitLabel}
            </button>
            <button type="button" onClick={onSplitVertical} disabled={!activeTerminalId} title={terminalChrome.splitVerticalTitle}>
              {terminalChrome.splitVerticalLabel}
            </button>
          </>
        ) : null}
        {isDrawer ? <span className="terminal-shell-owner-label">{terminalChrome.drawerLabel}</span> : null}
      </header>
      {panes.length > 0 ? (
        <div
          className={`terminal-shell-panes split-${splitDirection}`}
          data-testid="terminal-shell-panes"
        >
          {panes.map(({ terminalId, session }) => (
            <TerminalPane
              key={terminalId}
              terminalId={terminalId}
              session={session}
              active={terminalId === activeTerminalId}
              draft={draftsById[terminalId] || ""}
              setDraft={(value) => setDraftsById((current) => ({ ...current, [terminalId]: value }))}
              onSelect={onSelect}
              onSend={onSend}
              onClear={onClear}
              onRestart={onRestart}
              onClose={onClose}
              chrome={terminalChrome}
            />
          ))}
        </div>
      ) : (
        <div className="terminal-shell-empty">
          <p>{terminalChrome.emptyMessage}</p>
          <button type="button" onClick={onNew}>{terminalChrome.emptyActionLabel}</button>
        </div>
      )}
    </section>
  );
}
