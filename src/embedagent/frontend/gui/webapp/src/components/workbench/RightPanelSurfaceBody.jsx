import React from "react";
import Inspector from "../Inspector.jsx";
import FilePreviewSurface from "./FilePreviewSurface.jsx";
import FilesSurface from "./FilesSurface.jsx";
import RightPanelTerminalSurface from "./RightPanelTerminalSurface.jsx";

function inspectorKindForSurface(surface) {
  if (!surface) return "";
  if (surface.kind === "diff") return "diff";
  if (surface.kind === "plan") return "plan";
  return surface.kind;
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
  if (surface.kind === "terminal") {
    return (
      <RightPanelTerminalSurface
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
      showTabs={false}
    />
  );
}
