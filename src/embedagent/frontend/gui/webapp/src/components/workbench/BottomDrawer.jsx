import React from "react";
import TerminalShell from "./TerminalShell.jsx";

function RunOutputDrawer({ runOutput, terminationReason, terminationMessage }) {
  const entries = Array.isArray(runOutput) ? runOutput.slice(-80) : [];
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

export default function BottomDrawer({
  activeKind,
  runOutput,
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
          <TerminalShell
            owner="drawer"
            terminal={terminal}
            onNew={onTerminalNew}
            onSelect={onTerminalSelect}
            onSend={(terminalId, text) => {
              onTerminalSelect(terminalId);
              onTerminalSend(text);
            }}
            onClear={(terminalId) => {
              onTerminalSelect(terminalId);
              onTerminalClear();
            }}
            onRestart={(terminalId) => {
              onTerminalSelect(terminalId);
              onTerminalRestart();
            }}
            onClose={(terminalId) => {
              onTerminalSelect(terminalId);
              onTerminalClose();
            }}
          />
        ) : (
          <RunOutputDrawer
            runOutput={runOutput}
            terminationReason={terminationReason}
            terminationMessage={terminationMessage}
          />
        )}
      </div>
    </section>
  );
}
