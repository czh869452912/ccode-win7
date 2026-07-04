import React from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";
import { formatDiagnosticsRows } from "../app-shell/diagnostics.js";
import DiffPanel from "./diff/DiffPanel.jsx";
import SourceControlPanel from "./source-control/SourceControlPanel.jsx";

export default function SurfacePanel({
  surfaceKind,
  plan,
  diffSurface,
  sourceControl,
  appShell,
  onFocusDiffFile,
  onRefreshSourceControl,
  onSelectSourceControlFile,
  onAppSettingsChange,
}) {
  const lang = useLang();

  return (
    <aside className="inspector" role="complementary" aria-label="Surface panel" data-testid="surface-panel">
      <div className="inspector-body">
        {surfaceKind === "plan" && <PlanPanel plan={plan} lang={lang} />}
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
            lang={lang}
            onAppSettingsChange={onAppSettingsChange}
          />
        )}
        {surfaceKind === "diagnostics" && (
          <DiagnosticsPanel appShell={appShell} lang={lang} />
        )}
      </div>
    </aside>
  );
}

function SettingsPanel({ appShell, lang, onAppSettingsChange }) {
  const settings = appShell?.settings || {};
  const update = (key, value) => {
    if (onAppSettingsChange) {
      onAppSettingsChange({ [key]: value });
    }
  };
  return (
    <div className="panel-preview">
      <h3>{t("inspector.settings", lang)}</h3>
      <div className="app-settings-grid">
        <label className="app-setting-row">
          <input
            className="app-setting-check"
            type="checkbox"
            checked={settings.confirm_workspace_switch !== false}
            onChange={(event) => update("confirm_workspace_switch", event.target.checked)}
          />
          <span>{t("inspector.confirmWorkspaceSwitch", lang)}</span>
        </label>
        <label className="app-setting-row">
          <input
            className="app-setting-check"
            type="checkbox"
            checked={settings.show_diagnostics_badge !== false}
            onChange={(event) => update("show_diagnostics_badge", event.target.checked)}
          />
          <span>{t("inspector.showDiagnosticsBadge", lang)}</span>
        </label>
      </div>
    </div>
  );
}

function DiagnosticsPanel({ appShell, lang }) {
  const diagnostics = appShell?.diagnostics || {};
  const capabilities = appShell?.capabilities || {};
  const rows = formatDiagnosticsRows(diagnostics);
  const appCommands = Array.isArray(capabilities.appCommands) ? capabilities.appCommands : [];
  const workspaceCommands = Array.isArray(capabilities.workspaceCommands)
    ? capabilities.workspaceCommands
    : [];
  const surfaces = capabilities.surfaces || {};
  const rightPanel = Array.isArray(surfaces.rightPanel) ? surfaces.rightPanel : [];
  return (
    <div className="panel-preview">
      <h3>{t("inspector.diagnostics", lang)}</h3>
      {rows.length > 0 ? (
        <div className="diagnostics-table">
          {rows.map((row) => (
            <div key={`${row.group}-${row.key}`} className="diagnostics-row">
              <span className="diagnostics-group">{t(`inspector.diagnostics.${row.group}`, lang)}</span>
              <span className="diagnostics-key">{row.label}</span>
              <code className="diagnostics-value">{row.value || "-"}</code>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-copy">{t("inspector.noDiagnostics", lang)}</div>
      )}
      <h3>{t("inspector.capabilities", lang)}</h3>
      <div className="rule-chip-list">
        {appCommands.concat(workspaceCommands).map((command) => (
          <span key={command} className="rule-chip monospace">{command}</span>
        ))}
        {rightPanel.map((surface) => (
          <span key={`surface-${surface}`} className="rule-chip muted monospace">right:{surface}</span>
        ))}
      </div>
    </div>
  );
}

function PlanPanel({ plan, lang }) {
  if (!plan) {
    return <div className="empty-copy">{t("inspector.noPlan", lang)}</div>;
  }
  return (
    <div className="panel-preview">
      <h3>{plan.title || t("inspector.plan", lang)}</h3>
      <pre>{plan.content}</pre>
    </div>
  );
}
