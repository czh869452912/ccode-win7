import React from "react";
import SurfacePanel from "../SurfacePanel.jsx";
import FilePreviewSurface from "./FilePreviewSurface.jsx";
import FilesSurface from "./FilesSurface.jsx";
import PreviewSurface from "./PreviewSurface.jsx";
import TerminalShell from "./TerminalShell.jsx";
import { surfaceDefinitionFor } from "../../workbench/surfaces.js";

const RIGHT_PANEL_BODY_RENDERERS = Object.freeze({
  files: ({ surface, fileTree, treeHeight, onOpenFile, onLoadFileChildren }) => (
    <FilesSurface
      surface={surface}
      fileTree={fileTree}
      treeHeight={treeHeight}
      onOpenFile={onOpenFile}
      onLoadFileChildren={onLoadFileChildren}
    />
  ),
  file_preview: ({
    surface,
    filePreviewsByPath,
    filePreviewChrome,
    projectName,
    onOpenFile,
    onOpenFilesSurface,
  }) => {
    const filePath = surface.filePath || surface.resourceId || "";
    return (
      <FilePreviewSurface
        surface={surface}
        filePreview={(filePreviewsByPath || {})[filePath]}
        filePreviewChrome={filePreviewChrome}
        projectName={projectName}
        onReload={onOpenFile}
        onOpenFilesSurface={onOpenFilesSurface}
      />
    );
  },
  preview: ({
    surface,
    previewChrome,
    previewServers,
    onPreviewOpenUrl,
    onPreviewRefresh,
    onPreviewOpenExternal,
  }) => (
    <PreviewSurface
      surface={surface}
      previewChrome={previewChrome}
      servers={previewServers}
      onOpenUrl={onPreviewOpenUrl}
      onRefresh={onPreviewRefresh}
      onOpenExternal={onPreviewOpenExternal}
    />
  ),
  terminal: ({
    surface,
    terminal,
    terminalChrome,
    onTerminalNew,
    onTerminalSplit,
    onTerminalSplitVertical,
    onTerminalSelect,
    onTerminalSend,
    onTerminalClear,
    onTerminalRestart,
    onTerminalClose,
  }) => (
    <TerminalShell
      owner="right-panel"
      surface={surface}
      terminal={terminal}
      terminalChrome={terminalChrome}
      onNew={onTerminalNew}
      onSplit={onTerminalSplit}
      onSplitVertical={onTerminalSplitVertical}
      onSelect={onTerminalSelect}
      onSend={onTerminalSend}
      onClear={onTerminalClear}
      onRestart={onTerminalRestart}
      onClose={onTerminalClose}
    />
  ),
  surface_panel: ({ activeDefinition, surfacePanelProps }) => (
    <SurfacePanel
      {...surfacePanelProps}
      panelKind={activeDefinition ? activeDefinition.panelKind || "" : ""}
      surfaceDefinition={activeDefinition}
    />
  ),
});

function rightPanelBody(activeDefinition, props) {
  const activeBodyKind = activeDefinition ? activeDefinition.bodyKind : "surface_panel";
  const renderBody =
    RIGHT_PANEL_BODY_RENDERERS[activeBodyKind] || RIGHT_PANEL_BODY_RENDERERS.surface_panel;
  return renderBody({ ...props, activeDefinition });
}

export default function RightPanelSurfaceBody(props) {
  const { appCapabilities, surface } = props;
  if (!surface) {
    return null;
  }
  const activeDefinition = surfaceDefinitionFor(surface.kind, appCapabilities) || null;
  return rightPanelBody(activeDefinition, props);
}
