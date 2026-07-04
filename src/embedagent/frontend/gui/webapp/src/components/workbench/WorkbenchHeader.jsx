import React from "react";
import { modeBadgeLabel, modeBadgeStyle } from "../../session-runtime/mode-style.js";

export default function WorkbenchHeader({
  productName,
  chrome = {},
  currentMode,
  currentStatus,
  currentSessionId,
  activeWorkspace,
  turnsUsed,
  maxTurns,
  rightPanelOpen,
  bottomDrawerOpen,
  modeCatalog = {},
  onRefresh,
  onToggleRightPanel,
  onToggleBottomDrawer,
  onOpenPalette,
}) {
  const turnCounter = chrome.turnsLabel
    ? `${chrome.turnsLabel} ${turnsUsed}/${maxTurns}`
    : `${turnsUsed}/${maxTurns}`;
  return (
    <header className="app-header workbench-header" data-testid="workbench-header">
      <span className="app-logo">{productName}</span>
      <span className="mode-badge" style={modeBadgeStyle(currentMode, modeCatalog)}>
        {modeBadgeLabel(currentMode, modeCatalog)}
      </span>
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
            <span className="meta-text">{turnCounter}</span>
          ) : null}
        </div>
        <div className="header-action-group">
          <button
            className="ghost"
            onClick={onOpenPalette}
            aria-label={chrome.commandPaletteLabel}
            data-testid="open-command-palette"
          >
            {chrome.commandPaletteShortLabel}
          </button>
          <button
            className="ghost"
            onClick={onRefresh}
            aria-label={chrome.refreshLabel}
            data-testid="refresh-sessions"
          >
            {chrome.refreshLabel}
          </button>
          <button
            className={`ghost drawer-toggle${bottomDrawerOpen ? " active" : ""}`}
            onClick={onToggleBottomDrawer}
            aria-pressed={bottomDrawerOpen}
            title={chrome.bottomDrawerTitle}
            data-testid="drawer-toggle"
          >
            {chrome.bottomDrawerLabel}
          </button>
          <button
            className={`ghost right-panel-toggle${rightPanelOpen ? " active" : ""}`}
            onClick={onToggleRightPanel}
            title={chrome.rightPanelTitle}
            aria-pressed={rightPanelOpen}
            data-testid="right-panel-toggle"
          >
            {chrome.rightPanelLabel}
          </button>
        </div>
      </div>
    </header>
  );
}
