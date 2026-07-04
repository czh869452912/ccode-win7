import React from "react";
import { surfaceDefinitionFor } from "../../workbench/surfaces.js";
import Inspector from "../Inspector.jsx";
import FilePreviewSurface from "./FilePreviewSurface.jsx";
import FilesSurface from "./FilesSurface.jsx";
import PreviewSurface from "./PreviewSurface.jsx";
import TerminalShell from "./TerminalShell.jsx";

function inspectorKindForSurface(surface) {
  if (!surface) return "";
  const definition = surfaceDefinitionFor(surface.kind);
  return definition?.inspectorKind || surface.kind;
}

export default function RightPanelSurfaceBody({
  surface,
  inspectorProps,
  filePreviewsByPath,
  projectName,
  fileTree,
  treeHeight,
  onOpenFile,
  onOpenFilesSurface,
  onLoadFileChildren,
  terminal,
  onTerminalNew,
  onTerminalSplit,
  onTerminalSplitVertical,
  onTerminalSelect,
  onTerminalSend,
  onTerminalClear,
  onTerminalRestart,
  onTerminalClose,
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
    <Inspector
      {...inspectorProps}
      inspectorTab={inspectorKindForSurface(surface)}
    />
  );
}
