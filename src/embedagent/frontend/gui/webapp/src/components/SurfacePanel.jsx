import React from "react";
import { formatDiagnosticsRows } from "../app-shell/diagnostics.js";
import DiffPanel from "./diff/DiffPanel.jsx";
import SourceControlPanel from "./source-control/SourceControlPanel.jsx";

export default function SurfacePanel({
  surfaceKind,
  plan,
  diffSurface,
  sourceControl,
  appShell,
  chrome = {},
  onFocusDiffFile,
  onRefreshSourceControl,
  onSelectSourceControlFile,
  onAppSettingsChange,
}) {
  return (
    <aside className="surface-panel" role="complementary" aria-label={chrome.ariaLabel} data-testid="surface-panel">
      <div className="surface-panel-body">
        {surfaceKind === "plan" && <PlanPanel plan={plan} chrome={chrome} />}
        {surfaceKind === "diff" && (
          <DiffPanel surface={diffSurface} onFocusFile={onFocusDiffFile} />
        )}
        {surfaceKind === "source_control" && (
          <SourceControlPanel
            sourceControl={sourceControl}
            onRefresh={onRefreshSourceControl}
            onSelectFile={onSelectSourceControlFile}
          />
        )}
        {surfaceKind === "settings" && (
          <SettingsPanel
            appShell={appShell}
            chrome={chrome}
            onAppSettingsChange={onAppSettingsChange}
          />
        )}
        {surfaceKind === "diagnostics" && (
          <DiagnosticsPanel appShell={appShell} chrome={chrome} />
        )}
      </div>
    </aside>
  );
}

function SettingsPanel({ appShell, chrome, onAppSettingsChange }) {
  const settings = appShell?.settings || {};
  const update = (key, value) => {
    if (onAppSettingsChange) {
      onAppSettingsChange({ [key]: value });
    }
  };
  return (
    <div className="panel-preview">
      <h3>{chrome.settingsTitle}</h3>
      <div className="app-settings-grid">
        <label className="app-setting-row">
          <input
            className="app-setting-check"
            type="checkbox"
            checked={settings.confirm_workspace_switch !== false}
            onChange={(event) => update("confirm_workspace_switch", event.target.checked)}
          />
          <span>{chrome.confirmWorkspaceSwitchLabel}</span>
        </label>
        <label className="app-setting-row">
          <input
            className="app-setting-check"
            type="checkbox"
            checked={settings.show_diagnostics_badge !== false}
            onChange={(event) => update("show_diagnostics_badge", event.target.checked)}
          />
          <span>{chrome.showDiagnosticsBadgeLabel}</span>
        </label>
      </div>
    </div>
  );
}

function DiagnosticsPanel({ appShell, chrome }) {
  const diagnostics = appShell?.diagnostics || {};
  const capabilities = appShell?.capabilities || {};
  const rows = formatDiagnosticsRows(diagnostics);
  const appCommands = Array.isArray(capabilities.appCommands) ? capabilities.appCommands : [];
  const workspaceCommands = Array.isArray(capabilities.workspaceCommands)
    ? capabilities.workspaceCommands
    : [];
  const surfaces = capabilities.surfaces || {};
  const rightPanel = Array.isArray(surfaces.rightPanel) ? surfaces.rightPanel : [];
  const surfaceLabel = (surface) => String(surface?.kind || surface?.id || "");
  const diagnosticGroups = chrome.diagnosticGroups || {};
  return (
    <div className="panel-preview">
      <h3>{chrome.diagnosticsTitle}</h3>
      {rows.length > 0 ? (
        <div className="diagnostics-table">
          {rows.map((row) => (
            <div key={`${row.group}-${row.key}`} className="diagnostics-row">
              <span className="diagnostics-group">{diagnosticGroups[row.group] || row.group}</span>
              <span className="diagnostics-key">{row.label}</span>
              <code className="diagnostics-value">{row.value || "-"}</code>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-copy">{chrome.noDiagnostics}</div>
      )}
      <h3>{chrome.capabilitiesTitle}</h3>
      <div className="rule-chip-list">
        {appCommands.concat(workspaceCommands).map((command) => (
          <span key={command.id} className="rule-chip monospace">{command.id}</span>
        ))}
        {rightPanel.map((surface) => (
          <span key={`surface-${surfaceLabel(surface)}`} className="rule-chip muted monospace">right:{surfaceLabel(surface)}</span>
        ))}
      </div>
    </div>
  );
}

function PlanPanel({ plan, chrome }) {
  if (!plan) {
    return <div className="empty-copy">{chrome.noPlan}</div>;
  }
  return (
    <div className="panel-preview">
      <h3>{plan.title || chrome.planTitle}</h3>
      <pre>{plan.content}</pre>
    </div>
  );
}
