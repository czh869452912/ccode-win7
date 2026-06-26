import React from "react";
import { t } from "../../strings.js";

export default function WorkbenchHeader({
  lang,
  currentMode,
  currentStatus,
  currentSessionId,
  activeWorkspace,
  turnsUsed,
  maxTurns,
  rightPanelOpen,
  bottomDrawerOpen,
  onRefresh,
  onToggleLang,
  onToggleRightPanel,
  onToggleBottomDrawer,
  onOpenPalette,
}) {
  return (
    <header className="app-header workbench-header" data-testid="workbench-header">
      <span className="app-logo">EmbedAgent</span>
      <span className={`mode-badge mode-${currentMode}`}>{currentMode}</span>
      {activeWorkspace ? (
        <span className="workspace-header-label" title={activeWorkspace.path}>
          {activeWorkspace.label}
        </span>
      ) : null}
      <div className="header-right">
        <div className="header-status-group">
          <span className={`status-dot ${currentStatus}`} title={currentStatus} />
          <span
            className={`status-label ${
              currentStatus === "idle" ? "idle" : currentStatus === "error" ? "error" : ""
            }`}
          >
            {currentStatus}
          </span>
          {currentSessionId ? (
            <span className="meta-text">{currentSessionId.slice(0, 8)}</span>
          ) : null}
          {turnsUsed > 0 && maxTurns != null ? (
            <span className="meta-text">turns {turnsUsed}/{maxTurns}</span>
          ) : null}
        </div>
        <div className="header-action-group">
          <button className="ghost" onClick={onOpenPalette} data-testid="open-command-palette">
            Cmd
          </button>
          <button className="ghost" onClick={onRefresh} aria-label={t("header.refresh", lang)} data-testid="refresh-sessions">
            {t("header.refresh", lang)}
          </button>
          <button
            className="ghost lang-toggle"
            onClick={onToggleLang}
            aria-label="Toggle language"
            data-testid="lang-toggle"
          >
            {t("lang.toggle", lang)}
          </button>
          <button
            className={`ghost drawer-toggle${bottomDrawerOpen ? " active" : ""}`}
            onClick={onToggleBottomDrawer}
            aria-pressed={bottomDrawerOpen}
            title="Toggle run output"
            data-testid="drawer-toggle"
          >
            Run
          </button>
          <button
            className={`ghost inspector-toggle${rightPanelOpen ? " active" : ""}`}
            onClick={onToggleRightPanel}
            title={t("header.toggleInspector", lang)}
            aria-pressed={rightPanelOpen}
            data-testid="inspector-toggle"
          >
            Panel
          </button>
        </div>
      </div>
    </header>
  );
}
