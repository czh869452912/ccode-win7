import React from "react";

import SurfacePanel from "../SurfacePanel.jsx";
import FilePreviewSurface from "../workbench/FilePreviewSurface.jsx";
import FilesSurface from "../workbench/FilesSurface.jsx";
import PreviewSurface from "../workbench/PreviewSurface.jsx";
import TerminalShell from "../workbench/TerminalShell.jsx";

function FilesRenderer({ actions, contribution }) {
  return React.createElement(FilesSurface, {
    surface: contribution.active,
    fileTree: contribution.data.files,
    treeHeight: 560,
    onOpenFile: actions.openFile,
    onLoadFileChildren: (path) => actions.loadContribution("files.load", path),
  });
}

function FileRenderer({ actions, contribution }) {
  const surface = contribution.active;
  const path = surface?.filePath || surface?.resourceId || "";
  return React.createElement(FilePreviewSurface, {
    surface,
    filePreview: contribution.data.filePreviews?.[path],
    projectName: contribution.data.app?.activeWorkspace?.label || "",
    onReload: actions.openFile,
    onOpenFilesSurface: () => actions.loadContribution("files.open_surface"),
  });
}

function TerminalRenderer({ actions, contribution }) {
  return React.createElement(TerminalShell, {
    surface: contribution.active,
    terminal: contribution.data.terminal,
    terminalChrome: { newLabel: "New", newTitle: "New terminal", splitLabel: "Split", splitTitle: "Split terminal", splitVerticalLabel: "Split vertical", splitVerticalTitle: "Split terminal vertically", clearLabel: "Clear", restartLabel: "Restart", closeLabel: "Close", commandPlaceholder: "Command", emptyMessage: "No terminal", emptyActionLabel: "New terminal", unavailableMessage: "Terminal unavailable" },
    onNew: () => actions.loadContribution("terminal.open"),
    onSplit: () => actions.loadContribution("terminal.split"),
    onSplitVertical: () => actions.loadContribution("terminal.split_vertical"),
    onSelect: (id) => actions.loadContribution("terminal.activate", id),
    onSend: (id, data) => actions.loadContribution("terminal.send_to", id, data),
    onClear: (id) => actions.loadContribution("terminal.clear_by_id", id),
    onRestart: (id) => actions.loadContribution("terminal.restart_by_id", id),
    onClose: (id) => actions.loadContribution("terminal.close", id),
  });
}

function PreviewRenderer({ actions, contribution }) {
  return React.createElement(PreviewSurface, {
    surface: contribution.active,
    servers: contribution.data.previewServers,
    previewChrome: { urlPlaceholder: "http://localhost", urlAriaLabel: "Preview URL", refreshLabel: "Refresh", refreshAriaLabel: "Refresh preview", loadingLabel: "Loading", loadingAriaLabel: "Preview loading", openExternalLabel: "Open externally", annotateLabel: "Annotate", moreActionsLabel: "More actions", unavailableTitle: "Preview unavailable", unavailableBody: "The embedded preview is unavailable.", unreachableBody: "The preview server could not be reached.", reloadLabel: "Reload", failedNotice: "Preview failed" },
    onOpenUrl: (url) => actions.loadContribution("preview.open_url", url),
    onRefresh: (snapshot) => actions.loadContribution("preview.refresh", snapshot),
    onOpenExternal: (url) => actions.loadContribution("preview.open_external", url),
  });
}

function SourceControlRenderer({ actions, contribution }) {
  return React.createElement(SurfacePanel, {
    panelKind: "source_control",
    sourceControl: contribution.data.sourceControl,
    sourceControlChrome: { ariaLabel: "Source control" },
    onRefreshSourceControl: () => actions.loadContribution("source_control.refresh"),
    onSelectSourceControlFile: (path) => actions.loadContribution("source_control.open_file", path),
  });
}

function DiffRenderer({ actions, contribution }) {
  return React.createElement(SurfacePanel, {
    panelKind: "diff",
    diffSurface: contribution.data.diff,
    diffPanelChrome: {},
    onFocusDiffFile: (path) => actions.loadContribution("source_control.focus_diff", path),
  });
}

function DescriptorRenderer({ contribution }) {
  const active = contribution.active || {};
  return React.createElement(
    "div",
    { className: "contribution-placeholder" },
    React.createElement("h2", null, active.label),
    React.createElement("p", null, active.rendererKey),
  );
}

const RENDERERS = Object.freeze({
  descriptor: DescriptorRenderer,
  file_preview: FileRenderer,
  file_reference: FilesRenderer,
  inline_diff: DiffRenderer,
  preview: PreviewRenderer,
  source_control: SourceControlRenderer,
  terminal: TerminalRenderer,
});

export function contributionRenderer(rendererKey) {
  return RENDERERS[String(rendererKey || "")] || RENDERERS.descriptor;
}
