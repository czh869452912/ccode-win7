import React from "react";
import Inspector from "../Inspector.jsx";
import FilesSurface from "./FilesSurface.jsx";
import { TerminalSurface } from "./BottomDrawer.jsx";

function inspectorKindForSurface(surface) {
  if (!surface) return "";
  if (surface.kind === "diff") return "diff";
  if (surface.kind === "plan") return "plan";
  return surface.kind;
}

export default function RightPanelSurfaceBody({
  surface,
  inspectorProps,
  fileTree,
  treeHeight,
  onOpenFile,
  onLoadFileChildren,
  terminal,
  onTerminalNew,
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
  if (surface.kind === "terminal") {
    return (
      <TerminalSurface
        terminal={terminal}
        onNew={onTerminalNew}
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
