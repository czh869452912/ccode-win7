import React from "react";
import SurfacePanel from "../SurfacePanel.jsx";
import FilePreviewSurface from "./FilePreviewSurface.jsx";
import FilesSurface from "./FilesSurface.jsx";
import PreviewSurface from "./PreviewSurface.jsx";
import TerminalShell from "./TerminalShell.jsx";
import { surfaceDefinitionFor } from "../../workbench/surfaces.js";

function rightPanelBody(activeDefinition, {
  surface,
  surfacePanelProps,
  filePreviewsByPath,
  filePreviewChrome,
  projectName,
  fileTree,
  treeHeight,
  onOpenFile,
  onOpenFilesSurface,
  onLoadFileChildren,
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
  previewChrome,
  previewServers,
  onPreviewOpenUrl,
  onPreviewRefresh,
  onPreviewOpenExternal,
}) {
  const activeBodyKind = activeDefinition ? activeDefinition.bodyKind : "surface_panel";
  switch (activeBodyKind) {
    case "files":
      return (
        <FilesSurface
          surface={surface}
          fileTree={fileTree}
          treeHeight={treeHeight}
          onOpenFile={onOpenFile}
          onLoadFileChildren={onLoadFileChildren}
        />
      );
    case "file_preview": {
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
    }
    case "preview":
      return (
        <PreviewSurface
          surface={surface}
          previewChrome={previewChrome}
          servers={previewServers}
          onOpenUrl={onPreviewOpenUrl}
          onRefresh={onPreviewRefresh}
          onOpenExternal={onPreviewOpenExternal}
        />
      );
    case "terminal":
      return (
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
      );
    default:
      return (
        <SurfacePanel
          {...surfacePanelProps}
          surfaceKind={surface.kind}
        />
      );
  }
}

export default function RightPanelSurfaceBody(props) {
  const { surface } = props;
  if (!surface) {
    return null;
  }
  const activeDefinition = surfaceDefinitionFor(surface.kind) || null;
  return rightPanelBody(activeDefinition, props);
}
