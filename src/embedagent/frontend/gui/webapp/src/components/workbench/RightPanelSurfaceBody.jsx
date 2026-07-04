import React from "react";
import SurfacePanel from "../SurfacePanel.jsx";
import FilePreviewSurface from "./FilePreviewSurface.jsx";
import FilesSurface from "./FilesSurface.jsx";
import PreviewSurface from "./PreviewSurface.jsx";
import TerminalShell from "./TerminalShell.jsx";

export default function RightPanelSurfaceBody({
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
  if (!surface) {
    return null;
  }
  if (surface.kind === "files") {
    return (
      <FilesSurface
        fileTree={fileTree}
        treeHeight={treeHeight}
        onOpenFile={onOpenFile}
        onLoadFileChildren={onLoadFileChildren}
      />
    );
  }
  if (surface.kind === "file") {
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
  if (surface.kind === "preview") {
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
  }
  if (surface.kind === "terminal") {
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
  }
  return (
    <SurfacePanel
      {...surfacePanelProps}
      surfaceKind={surface.kind}
    />
  );
}
