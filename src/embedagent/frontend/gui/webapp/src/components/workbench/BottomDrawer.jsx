import React from "react";
import {
  bottomDrawerSurfaceDefinitions,
  surfaceChromeLabels,
} from "../../workbench/surfaces.js";
import TerminalShell from "./TerminalShell.jsx";

function RunOutputDrawer({ runOutput, terminationReason, terminationMessage, chrome }) {
  const entries = Array.isArray(runOutput) ? runOutput.slice(-80) : [];
  const reasonPrefix = chrome.terminationReasonPrefix
    ? `${chrome.terminationReasonPrefix}=`
    : "";
  return (
    <>
      {terminationReason ? (
        <div className="drawer-line">
          {reasonPrefix}{terminationReason} {terminationMessage || ""}
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
        <div className="drawer-line muted">{chrome.runOutputEmptyMessage}</div>
      )}
    </>
  );
}

const BOTTOM_DRAWER_BODY_RENDERERS = Object.freeze({
  terminal: ({
    terminal,
    terminalChrome,
    onTerminalNew,
    onTerminalSelect,
    onTerminalSend,
    onTerminalClear,
    onTerminalRestart,
    onTerminalClose,
  }) => (
    <TerminalShell
      owner="drawer"
      terminal={terminal}
      terminalChrome={terminalChrome}
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
  ),
  run_output: ({ runOutput, terminationReason, terminationMessage, chrome }) => (
    <RunOutputDrawer
      runOutput={runOutput}
      terminationReason={terminationReason}
      terminationMessage={terminationMessage}
      chrome={chrome}
    />
  ),
});

function drawerBody(activeDefinition, props) {
  const activeBodyKind = activeDefinition ? activeDefinition.bodyKind : "";
  const renderBody = BOTTOM_DRAWER_BODY_RENDERERS[activeBodyKind] || null;
  return renderBody ? renderBody(props) : null;
}

export default function BottomDrawer({
  appCapabilities,
  activeKind,
  runOutput,
  terminationReason,
  terminationMessage,
  terminal,
  terminalChrome,
  onKindSelect,
  onTerminalNew,
  onTerminalSelect,
  onTerminalSend,
  onTerminalClear,
  onTerminalRestart,
  onTerminalClose,
}) {
  const drawerSurfaces = bottomDrawerSurfaceDefinitions(appCapabilities);
  const chrome = surfaceChromeLabels(appCapabilities);
  const activeDefinition =
    drawerSurfaces.find((definition) => definition.kind === activeKind) ||
    drawerSurfaces[0] ||
    null;
  const selectedKind = activeDefinition?.kind || "";
  return (
    <section
      className="bottom-drawer"
      aria-label={chrome.bottomDrawerAriaLabel}
      data-testid="bottom-drawer"
    >
      <div className="bottom-drawer-tabs" role="tablist">
        {drawerSurfaces.map((definition) => (
          <button
            key={definition.kind}
            className={`bottom-drawer-tab${selectedKind === definition.kind ? " active" : ""}`}
            type="button"
            onClick={() => onKindSelect(definition.kind)}
          >
            {definition.title}
          </button>
        ))}
      </div>
      <div className="bottom-drawer-body">
        {drawerBody(activeDefinition, {
          runOutput,
          terminationReason,
          terminationMessage,
          chrome,
          terminal,
          terminalChrome,
          onTerminalNew,
          onTerminalSelect,
          onTerminalSend,
          onTerminalClear,
          onTerminalRestart,
          onTerminalClose,
        })}
      </div>
    </section>
  );
}
