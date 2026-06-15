import React from "react";

export default function BottomDrawer({
  activeKind,
  eventLog,
  terminationReason,
  terminationMessage,
}) {
  const entries = Array.isArray(eventLog) ? eventLog.slice(-80) : [];
  return (
    <section className="bottom-drawer" aria-label="Bottom drawer" data-testid="bottom-drawer">
      <div className="bottom-drawer-tabs" role="tablist">
        <button className={`bottom-drawer-tab${activeKind === "run_output" ? " active" : ""}`} type="button">
          Run Output
        </button>
        <button className={`bottom-drawer-tab${activeKind === "logs" ? " active" : ""}`} type="button">
          Logs
        </button>
      </div>
      <div className="bottom-drawer-body">
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
      </div>
    </section>
  );
}
